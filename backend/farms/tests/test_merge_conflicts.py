import os
from pathlib import Path
from django.test import TestCase
from django.conf import settings


class MergeConflictMarkerTest(TestCase):
    def test_no_merge_conflict_markers_in_codebase(self):
        """
        Scans the codebase for unresolved Git merge conflict markers.
        Fails the test and prints the surrounding lines if any are found.
        """
        project_root = settings.BASE_DIR

        # Directories we definitely do not want to scan
        ignore_dirs = {
            ".git",
            "farm_venv",
            "venv",
            "__pycache__",
            "node_modules",
            "staticfiles",
            "media",
        }

        # Only scan readable text/code files
        allowed_extensions = {".py", ".html", ".js", ".css", ".txt", ".md"}

        conflicts_found = []

        for root, dirs, files in os.walk(project_root):
            # Modify dirs in-place to skip ignored directories
            dirs[:] = [d for d in dirs if d not in ignore_dirs]

            for file in files:
                file_path = Path(root) / file

                if file_path.suffix not in allowed_extensions:
                    continue

                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        lines = f.readlines()

                        for i, line in enumerate(lines):
                            # Git markers are always placed at the very beginning of a line.
                            # We use startswith() and an exact match for "=======" to avoid
                            # triggering false positives on comment dividers or this script itself!
                            is_conflict = (
                                line.startswith("<<<<<<< ")
                                or line.strip() == "======="
                                or line.startswith(">>>>>>> ")
                            )

                            if is_conflict:
                                # Grab context (2 lines before and 2 lines after)
                                start = max(0, i - 2)
                                end = min(len(lines), i + 3)
                                context_lines = "".join(lines[start:end])

                                error_msg = (
                                    f"\n🚨 Merge conflict marker found in {file_path.relative_to(project_root)} "
                                    f"at line {i + 1}:\n\n{context_lines}\n"
                                    f"{'-' * 50}"
                                )
                                conflicts_found.append(error_msg)

                                # Break out of checking this specific file to avoid
                                # printing the same conflict block 3 times (for each marker)
                                break

                except UnicodeDecodeError:
                    # Silently skip any weird binary files that slip through
                    pass

        # If the list is not empty, fail the test and print all conflicts
        if conflicts_found:
            self.fail("\n" + "\n".join(conflicts_found))
