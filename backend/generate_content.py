import os

# Configuration
OUTPUT_FILE = "llm_context.txt"

# Folders we want to completely skip
IGNORE_DIRS = {
    "farm_venv",
    "__pycache__",
    ".git",
    "theme",
    "media",
    "migrations",
    ".github",
}

# File extensions we want to skip (binaries, logs, databases)
IGNORE_EXTS = {".pyc", ".sqlite3", ".log", ".json", ".png", ".jpg", ".ico"}

# Specific files to skip (so it doesn't try to read its own output)
IGNORE_FILES = {
    OUTPUT_FILE,
    "generate_context.py",
    "django_errors.log",
    "final_schuler_data.json",
}


def generate_context():
    print("🔍 Scanning directory...")
    files_added = 0

    with open(OUTPUT_FILE, "w", encoding="utf-8") as outfile:
        # Walk through the directory tree
        for root, dirs, files in os.walk("."):
            # Modify dirs in-place to tell os.walk to skip ignored directories entirely
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

            for file in files:
                # Skip ignored extensions and specific files
                if (
                    any(file.endswith(ext) for ext in IGNORE_EXTS)
                    or file in IGNORE_FILES
                ):
                    continue

                file_path = os.path.join(root, file)

                try:
                    with open(file_path, "r", encoding="utf-8") as infile:
                        content = infile.read()

                    # Write the separator, file path header, and content
                    outfile.write(f"\n{'='*80}\n")
                    outfile.write(f"FILE: {file_path.removeprefix('./')}\n")
                    outfile.write(f"{'='*80}\n\n")
                    outfile.write(content)
                    outfile.write("\n\n")

                    files_added += 1
                except Exception as e:
                    print(f"⚠️ Skipping {file_path} due to read error: {e}")

    print(f"✅ Success! Bundled {files_added} files into '{OUTPUT_FILE}'")


if __name__ == "__main__":
    generate_context()
