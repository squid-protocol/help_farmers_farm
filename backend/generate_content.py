import os

# Configuration
# The 6 distinct SaaS subsystems we want to generate separate markdown files for.
SUBSYSTEMS = {"accounts", "analytics", "billing", "farms", "helpingfarmersfarm", "logs"}

# Folders we want to completely skip
IGNORE_DIRS = {
    "farm_venv",
    "__pycache__",
    ".git",
    "theme",
    "media",
    "migrations",
    ".github",
    "tests",
}

# File extensions we want to skip (binaries, logs, databases)
IGNORE_EXTS = {".pyc", ".sqlite3", ".log", ".json", ".png", ".jpg", ".ico"}

# Specific files to skip (so it doesn't try to read its own output)
IGNORE_FILES = {
    "generate_content.py",
    "generate_context.py",
    "django_errors.log",
    "final_schuler_data.json",
    ".env",
    "pytest.ini",
    ".gitignore",
}


def get_language(filename):
    """Maps file extensions to markdown code block languages."""
    ext = filename.split(".")[-1] if "." in filename else ""
    mapping = {
        "py": "python",
        "html": "html",
        "js": "javascript",
        "css": "css",
        "md": "markdown",
        "sh": "bash",
    }
    return mapping.get(ext, "text")


def get_subsystem_name(root_path):
    """Extracts the top-level folder name to determine the subsystem routing."""
    # Strip the leading './' from os.walk paths
    clean_path = root_path.removeprefix(".").removeprefix(os.sep)

    if not clean_path:
        return "core"  # Files sitting in the very root directory

    top_folder = clean_path.split(os.sep)[0]
    if top_folder in SUBSYSTEMS:
        return top_folder

    return "core"  # Catch-all for anything outside the 6 main apps


def build_tree_map(startpath):
    """Generates a text-based tree map of the directory, respecting ignore lists."""
    tree = []
    if not os.path.exists(startpath):
        return "Directory not found."

    for root, dirs, files in os.walk(startpath):
        # Modify dirs in-place to skip ignored directories in the tree map
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

        level = root.replace(startpath, "").count(os.sep)
        indent = " " * 4 * level
        tree.append(f"{indent}📁 {os.path.basename(root)}/")

        subindent = " " * 4 * (level + 1)
        for f in files:
            if (
                any(f.endswith(ext) for ext in IGNORE_EXTS)
                or f in IGNORE_FILES
                or f.endswith("_context.md")
            ):
                continue
            tree.append(f"{subindent}📄 {f}")

    return "\n".join(tree)


def generate_context():
    print("🔍 Scanning directory and splitting into subsystems...")

    # Dictionary to store file contents grouped by subsystem
    subsystem_contents = {subsystem: [] for subsystem in SUBSYSTEMS}
    subsystem_contents["core"] = []

    files_added = 0

    # Walk through the directory tree
    for root, dirs, files in os.walk("."):
        # Modify dirs in-place to tell os.walk to skip ignored directories entirely
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

        for file in files:
            # Skip ignored extensions, specific files, and any generated markdown files
            if (
                any(file.endswith(ext) for ext in IGNORE_EXTS)
                or file in IGNORE_FILES
                or file.endswith("_context.md")
            ):
                continue

            file_path = os.path.join(root, file)
            subsystem = get_subsystem_name(root)
            language = get_language(file)

            try:
                with open(file_path, "r", encoding="utf-8") as infile:
                    content = infile.read()

                # Format as clean Markdown
                # Format as clean Markdown
                formatted_content = (
                    f"## FILE: `{file_path.removeprefix('./')}`\n\n"
                    f"```{language}\n"
                    f"{content}\n"
                    f"```\n\n---\n\n"
                )
                subsystem_contents[subsystem].append(formatted_content)

                files_added += 1
            except Exception as e:
                print(f"⚠️ Skipping {file_path} due to read error: {e}")

    # Write out the separated markdown files
    for subsystem, contents in subsystem_contents.items():
        if not contents:
            continue  # Skip creating empty files

        output_filename = f"{subsystem}_context.md"

        # Build the tree map for the specific subsystem (or root for core)
        search_path = f"./{subsystem}" if subsystem != "core" else "."
        tree_map = build_tree_map(search_path)

        with open(output_filename, "w", encoding="utf-8") as outfile:
            outfile.write(f"# Subsystem: {subsystem.title()}\n\n")
            outfile.write("## Directory Structure\n```text\n")
            outfile.write(tree_map)
            outfile.write("\n```\n\n---\n\n")
            outfile.writelines(contents)

        print(f"📄 Created {output_filename} with {len(contents)} files.")

    print(f"\n✅ Success! Bundled {files_added} total files.")


if __name__ == "__main__":
    generate_context()
