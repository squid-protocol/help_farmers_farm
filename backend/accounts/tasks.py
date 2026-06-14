import hashlib
import logging
import boto3
from botocore.exceptions import BotoCoreError, ClientError
from datetime import timedelta
from django.template.loader import render_to_string
from django.core.files.base import ContentFile
from django.utils import timezone
from django.conf import settings
from weasyprint import HTML
from django.contrib.auth import get_user_model
from accounts.models import FormSignature
from farms.models import Farm, ComplianceForm

User = get_user_model()
logger = logging.getLogger(__name__)


def generate_pdf_receipt(signature_id, user_id, form_id, farm_id, ip_address):
    """
    Background task to generate, hash, and store a WORM-compliant PDF.
    """
    # 1. Fetch the records from the database
    sig_record = FormSignature.objects.get(id=signature_id)
    user = User.objects.get(id=user_id)
    form = ComplianceForm.objects.get(id=form_id)
    farm = Farm.objects.get(id=farm_id)

    # 2. Render the sterile HTML template
    html_string = render_to_string(
        "accounts/pdf_receipt.html",
        {
            "farm": farm,
            "form": form,
            "user": user,
            "signature_text": sig_record.digital_signature,
            "is_guardian": sig_record.is_guardian_signature,
            "relationship": sig_record.guardian_relationship,
            "timestamp": sig_record.signed_at.strftime("%Y-%m-%d %H:%M:%S"),
            "ip_address": ip_address,
        },
    )

    # 3. Use WeasyPrint to generate raw PDF bytes
    pdf_bytes = HTML(string=html_string).write_pdf()

    # 4. Generate the SHA-256 Hash
    pdf_hash = hashlib.sha256(pdf_bytes).hexdigest()

    # 5. Update the signature record with the WORM data
    sig_record.document_hash = pdf_hash
    filename = f"Waiver_{farm.id}_{user.id}_{form.id}.pdf"

    # This physical save operation also triggers the database save()
    sig_record.pdf_receipt.save(filename, ContentFile(pdf_bytes), save=True)

    return f"Secured PDF for Signature {signature_id}"


def purge_unverified_accounts():
    """
    Nightly cron job: Deletes any unattached volunteer account that is
    older than 7 days and has not verified their email address.
    """
    # Set the grace period to 1 full week
    cutoff_time = timezone.now() - timedelta(days=7)

    # Target ONLY volunteers who are unverified, past the cutoff, AND have no farm memberships
    ghosts = User.objects.filter(
        is_email_verified=False,
        date_joined__lt=cutoff_time,
        role="volunteer",
        memberships__isnull=True,
    )

    count = ghosts.count()
    if count > 0:
        # Django's .delete() on a queryset is highly efficient
        ghosts.delete()
        logger.info(f"Nightly Purge: Successfully deleted {count} unverified ghost accounts.")
    else:
        logger.info("Nightly Purge: No unverified ghost accounts found.")


def vault_unsigned_pdfs_to_s3():
    """
    Nightly cron job: Scans for generated PDFs that haven't been pushed
    to the AWS S3 WORM-compliant vault, uploads them, and marks them as vaulted.
    """
    # --- SAFETY VALVE: Bypass if no AWS keys are configured ---
    if not getattr(settings, "AWS_ACCESS_KEY_ID", None):
        logger.warning("S3 Vault Sync bypassed: No AWS credentials found in .env.")
        return "Bypassed: Missing AWS credentials."

    MAX_SIZE_BYTES = 500 * 1024 * 1024  # 0.5 GB
    unvaulted_signatures = FormSignature.objects.filter(pdf_receipt__isnull=False, is_vaulted=False).exclude(
        pdf_receipt__exact=""
    )

    if not unvaulted_signatures.exists():
        logger.info("S3 Vault Sync: No new documents to vault.")
        return "No documents to vault."

    # Initialize the S3 client
    try:
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME,
        )
        bucket_name = settings.AWS_STORAGE_BUCKET_NAME
    except Exception as e:
        logger.error(f"S3 Vault Sync: Failed to initialize boto3 client: {e}")
        return "Boto3 initialization failed."

    success_count = 0
    fail_count = 0

    for sig in unvaulted_signatures:
        # 1. Enforce PDF extension check
        if not sig.pdf_receipt.name.lower().endswith(".pdf"):
            logger.error(f"Vault rejected Record {sig.id}: File is not a PDF.")
            fail_count += 1
            continue

        # 2. Enforce 0.5 GB maximum size limit
        try:
            if sig.pdf_receipt.size > MAX_SIZE_BYTES:
                logger.error(f"Vault rejected Record {sig.id}: File size exceeds 0.5 GB limit.")
                fail_count += 1
                continue
        except Exception as e:
            logger.error(f"Could not verify file size for Record {sig.id}: {e}")
            fail_count += 1
            continue

        try:
            # Ensure the file actually exists on local disk before trying to read
            if not sig.pdf_receipt.storage.exists(sig.pdf_receipt.name):
                logger.error(f"S3 Vault Sync: Local file missing for Signature ID {sig.id}")
                fail_count += 1
                continue

            # Open the local file and stream it to S3
            with sig.pdf_receipt.open("rb") as pdf_file:
                s3_path = f"compliance_vault/{sig.pdf_receipt.name.split('/')[-1]}"

                s3_client.upload_fileobj(
                    pdf_file,
                    bucket_name,
                    s3_path,
                    ExtraArgs={"ContentType": "application/pdf"},
                )

            # If upload_fileobj succeeds without throwing an exception, mark as vaulted
            sig.is_vaulted = True
            sig.save(update_fields=["is_vaulted"])
            success_count += 1

        except (BotoCoreError, ClientError) as e:
            logger.error(f"S3 Vault Sync: AWS upload failed for Signature ID {sig.id}: {e}")
            fail_count += 1
        except Exception as e:
            logger.error(f"S3 Vault Sync: Unexpected error for Signature ID {sig.id}: {e}")
            fail_count += 1

    summary = f"S3 Vault Sync Complete. Success: {success_count}, Failed: {fail_count}."
    logger.info(summary)
    return summary
