import os
import re
import subprocess
from typing import Optional

# -----------------------------
# CONFIG
# -----------------------------

SAFE_PYPI_PACKAGES = {
    "django",
    "requests",
    "flask",
    "fastapi",
    "numpy",
    "pandas",
    "torch",
    "groq",
    "PyGithub",
    "pytest",
}

PROJECT_ROOT = os.getenv("GITHUB_WORKSPACE", os.getcwd())


# -----------------------------
# UTILITIES
# -----------------------------

def read_ci_logs() -> str:
    logs = os.environ.get("CI_LOGS")
    if not logs:
        raise RuntimeError("CI_LOGS env var not found")
    return logs


def extract_missing_module(logs: str) -> Optional[str]:
    """
    Extract module name from:
    ModuleNotFoundError: No module named 'xyz'
    """
    match = re.search(r"No module named ['\"]([^'\"]+)['\"]", logs)
    return match.group(1) if match else None


def find_python_files():
    for root, _, files in os.walk(PROJECT_ROOT):
        if ".git" in root:
            continue
        for f in files:
            if f.endswith(".py"):
                yield os.path.join(root, f)


# -----------------------------
# FIX STRATEGIES
# -----------------------------

def remove_import(module_name: str):
    print(f"🛠 Removing invalid import: {module_name}")

    for file_path in find_python_files():
        with open(file_path, "r") as f:
            lines = f.readlines()

        new_lines = []
        changed = False

        for line in lines:
            if (
                line.strip() == f"import {module_name}"
                or line.strip() == f"from {module_name} import"
                or line.strip().startswith(f"from {module_name} import ")
            ):
                changed = True
                continue
            new_lines.append(line)

        if changed:
            with open(file_path, "w") as f:
                f.writelines(new_lines)
            print(f"✅ Fixed import in {file_path}")


def add_dependency(module_name: str):
    print(f"📦 Adding dependency to requirements.txt: {module_name}")

    req_path = os.path.join(PROJECT_ROOT, "requirements.txt")
    if not os.path.exists(req_path):
        print("⚠️ requirements.txt not found, skipping")
        return

    with open(req_path, "r") as f:
        content = f.read()

    if module_name in content:
        print("ℹ️ Dependency already exists")
        return

    with open(req_path, "a") as f:
        f.write(f"\n{module_name}\n")

    print("✅ Dependency added")


# -----------------------------
# GIT
# -----------------------------

def git_commit(message: str):
    subprocess.run(["git", "config", "user.name", "ci-bot-agent"], check=False)
    subprocess.run(["git", "config", "user.email", "ci-bot-agent@github.com"], check=False)
    subprocess.run(["git", "add", "."], check=False)
    subprocess.run(["git", "commit", "-m", message], check=False)
    subprocess.run(["git", "push"], check=False)


# -----------------------------
# MAIN LOGIC
# -----------------------------

def main():
    print("🤖 CI Smart Agent started")

    logs = read_ci_logs()
    missing_module = extract_missing_module(logs)

    if not missing_module:
        print("✅ No missing module error detected")
        return

    print(f"🔍 Missing module detected: {missing_module}")

    if missing_module in SAFE_PYPI_PACKAGES:
        add_dependency(missing_module)
        fix_type = "dependency"
    else:
        remove_import(missing_module)
        fix_type = "code"

    git_commit(f"🤖 CI Bot: auto-fix missing {fix_type} ({missing_module})")
    print("🚀 Fix committed successfully")


if __name__ == "__main__":
    main()
