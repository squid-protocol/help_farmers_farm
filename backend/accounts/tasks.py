import hashlib
from django.template.loader import render_to_string
from django.core.files.base import ContentFile
from weasyprint import HTML
from django.contrib.auth import get_user_model
from accounts.models import FormSignature
from farms.models import Farm, ComplianceForm

User = get_user_model()


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
