import os
import re
import sys
from pathlib import Path

# Terms that suggest a privileged secret.
# We fail if we see these assigned to non-placeholder values.
FORBIDDEN_KEYS = [
    "SUPABASE_SERVICE_ROLE_KEY",
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GOOGLE_API_KEY",
    "SERVICE_ROLE",
    "CLIENT_SECRET",
    "PRIVATE_KEY",
]

# Patterns that match actual secret values (not just keys).
# If we see these anywhere in source, fail.
FORBIDDEN_PATTERNS = [
    re.compile(r"sk-ant-[a-zA-Z0-9_-]{20,}"),  # Anthropic keys
    re.compile(r"sk-proj-[a-zA-Z0-9_-]{20,}"), # OpenAI keys
    re.compile(r"xoxb-[a-zA-Z0-9_-]+"),        # Slack tokens
    re.compile(r"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+"), # JWTs (Supabase)
]

# Allowlist for placeholders.
SAFE_VALUES = [
    "",
    "FILL_IN_LOCALLY",
    "your_key_here",
    "<insert_key>",
    "placeholder",
    "${{ secrets.ANTHROPIC_API_KEY }}",
    "${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}",
    "${{ secrets.OPENAI_API_KEY }}",
    "${{ secrets.GOOGLE_API_KEY }}",
    "os.environ.get('SUPABASE_SERVICE_ROLE_KEY')",
]

GENERATED_EXTRACTION_FILES = {
    "install_script.iss",
}


def is_generated_extraction_noise(path: Path) -> bool:
    parts = {part.lower() for part in path.parts}
    if "extracted" not in parts:
        return False
    if path.name in GENERATED_EXTRACTION_FILES:
        return True
    if "$PLUGINSDIR".lower() in parts or "tmp" in parts:
        return True
    return False


def is_safe_line(line: str) -> bool:
    # Ignore GitHub Actions secret mappings
    if "${{ secrets." in line:
        return True
    # Ignore known safe paths in the export script
    if "os.getenv" in line or "os.environ" in line:
        return True
    # Ignore generic instructions in markdown
    if line.strip().startswith("-") or line.strip().startswith("*") or line.strip().startswith("export "):
        if ".md" in line or "export OPENAI_API_KEY=" in line:
            return True
    return False

def check_file(path: Path) -> list[str]:
    if is_generated_extraction_noise(path):
        return []

    if path.name == ".env":
        parts = {part.lower() for part in path.parts}
        if "dist" in parts or "installer" in parts:
            return [f"{path}:1 - Bundled .env file is not allowed in release payloads"]

    errors = []
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return [] # skip binary files or non-utf8

    lines = content.splitlines()
    for i, line in enumerate(lines, 1):
        if is_safe_line(line):
            continue

        # 1. Check for forbidden patterns directly
        for pattern in FORBIDDEN_PATTERNS:
            if pattern.search(line):
                # Check if it's the known safe dummy token from tests
                if "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.dummy.signature" in line:
                    continue
                errors.append(f"{path}:{i} - Found forbidden secret pattern")

        # 2. Check for assignment of forbidden keys
        for key in FORBIDDEN_KEYS:
            # Check KEY=value or KEY="value" or "KEY": "value"
            match = re.search(rf"{key}\s*[:=]\s*([^\s,\`]+)", line)
            if match:
                val = match.group(1).strip(" '\".,;")
                if val and val not in SAFE_VALUES and not val.startswith("${{"):
                    errors.append(f"{path}:{i} - Found forbidden key '{key}' with non-placeholder value: {val}")

    return errors

def main() -> int:
    root = Path(__file__).parent.parent
    dist_dir = root / "dist" / "ReplyRight"
    installer_out = root / "installer" / "output"

    if os.environ.get("REPLYRIGHT_PAYLOAD_AUDIT") == "1":
        directories_to_scan = []
        files_to_scan = []
        if dist_dir.exists():
            directories_to_scan.append(dist_dir)
        extracted = installer_out / "extracted"
        for candidate in (extracted / "app", extracted / "{app}", extracted):
            if candidate.exists():
                directories_to_scan.append(candidate)
                break
    else:
        directories_to_scan = [
            root / "outlook_dashboard",
            root / "installer",
            root / "docs",
            root / ".github",
            root / "scripts",
        ]
        files_to_scan = [
            root / "README.md",
            root / ".env.example",
            root / "build_exe.ps1",
        ]
        if dist_dir.exists():
            directories_to_scan.append(dist_dir)
        if installer_out.exists():
            directories_to_scan.append(installer_out)

    all_files = set(files_to_scan)
    for d in directories_to_scan:
        if d.exists():
            for f in d.rglob("*"):
                if f.is_file() and not f.name.endswith(('.exe', '.dll', '.pyd', '.pyc')):
                    if f.name == "check_no_bundled_secrets.py":
                        continue
                    all_files.add(f)

    all_errors = []
    for f in all_files:
        if f.exists():
            all_errors.extend(check_file(f))

    if all_errors:
        print(f"SECURITY AUDIT FAILED: Found {len(all_errors)} potential secrets bundled!")
        for e in all_errors:
            print(f"  {e}")
        return 1

    print("Security audit passed. No bundled privileged secrets detected.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
