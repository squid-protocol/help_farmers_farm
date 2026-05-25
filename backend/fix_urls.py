import re
import sys
from pathlib import Path

# Target the specific file
file_path = Path("farms/tests/test_views.py")

if not file_path.exists():
    print(f"❌ Could not find {file_path}. Are you in the backend directory?")
    sys.exit(1)

content = file_path.read_text()

# Regex pattern: Looks for "[url](url)" inside double quotes and captures just the first url
# e.g., "[https://example.com](https://example.com)" becomes "[https://example.com](https://example.com)"
pattern = r'"\[(https?://[^\]]+)\]\([^\)]+\)"'
fixed_content = re.sub(pattern, r'"\1"', content)

if content == fixed_content:
    print("✅ No corrupted Markdown URLs found. The file is already clean.")
else:
    file_path.write_text(fixed_content)
    print(f"🚀 Successfully scrubbed corrupted Markdown URLs from {file_path}!")
