import os
import re
import subprocess
from typing import Optional, Tuple

# -------------------------------------------------
# CONFIG (DYNAMIC – DO NOT HARDCODE)
# -------------------------------------------------

TARGET_REPO = os.environ.get("TARGET_REPO")
TARGET_BRANCH = "main"

if not TARGET_REPO:
    raise RuntimeError("TARGET_REPO env var not set")

WORKDIR = f"/tmp/{TARGET_REPO.split('/')[-1]}"

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

# -------------------------------------------------
# UTILITIES
# -------------------------------------------------

def run(cmd: str):
    print(f"$ {cmd}")
    subprocess.run(cmd, shell=True, check=False)


def clone_target_repo():
    token = os.environ.get("AGENT_GITHUB_TOKEN")
    if not token:
        raise RuntimeError("AGENT_GITHUB_TOKEN not set")

    run(f"rm -rf {WORKDIR}")
    run(
        f"git clone https://x-access-token:{token}@github.com/{TARGET_REPO}.git {WORKDIR}"
    )
    os.chdir(WORKDIR)


def read_ci_logs() -> str:
    logs = os.environ.get("CI_LOGS")
    if not logs:
        raise RuntimeError("CI_LOGS env var not found")
    return logs


def find_python_files():
    for root, _, files in os.walk(WORKDIR):
        if ".git" in root:
            continue
        for f in files:
            if f.endswith(".py"):
                yield os.path.join(root, f)

# -------------------------------------------------
# ERROR EXTRACTION
# -------------------------------------------------

def extract_missing_module(logs: str) -> Optional[str]:
    match = re.search(r"No module named ['\"]([^'\"]+)['\"]", logs)
    return match.group(1) if match else None


def extract_name_error_fix(logs: str) -> Optional[Tuple[str, str]]:
    """
    Example:
    NameError: name 'load_dta' is not defined. Did you mean: 'load_data'?
    """
    match = re.search(
        r"NameError: name '([^']+)' is not defined\. Did you mean: '([^']+)'",
        logs,
    )
    if match:
        return match.group(1), match.group(2)
    return None

# -------------------------------------------------
# FIX STRATEGIES
# -------------------------------------------------

def fix_name_error(old_name: str, new_name: str):
    print(f"🛠 Fixing NameError: {old_name} → {new_name}")

    for file_path in find_python_files():
        with open(file_path, "r") as f:
            content = f.read()

        if old_name not in content:
            continue

        content = content.replace(old_name, new_name)

        with open(file_path, "w") as f:
            f.write(content)

        print(f"✅ Fixed NameError in {file_path}")


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
                or line.strip().startswith(f"from {module_name} import")
            ):
                changed = True
                continue
            new_lines.append(line)

        if changed:
            with open(file_path, "w") as f:
                f.writelines(new_lines)
            print(f"✅ Fixed import in {file_path}")


def add_dependency(module_name: str):
    print(f"📦 Adding dependency: {module_name}")

    req_path = os.path.join(WORKDIR, "requirements.txt")
    if not os.path.exists(req_path):
        print("⚠️ requirements.txt not found")
        return

    with open(req_path, "r") as f:
        content = f.read()

    if module_name in content:
        print("ℹ️ Dependency already exists")
        return

    with open(req_path, "a") as f:
        f.write(f"\n{module_name}\n")

    print("✅ Dependency added")

# -------------------------------------------------
# GIT
# -------------------------------------------------

def git_commit_and_push(message: str):
    token = os.environ.get("AGENT_GITHUB_TOKEN")

    run('git config user.name "ci-bot-agent"')
    run('git config user.email "ci-bot-agent@users.noreply.github.com"')

    run(
        f"git remote set-url origin https://x-access-token:{token}@github.com/{TARGET_REPO}.git"
    )

    run("git status --porcelain > /tmp/git_status.txt")

    if os.path.getsize("/tmp/git_status.txt") == 0:
        print("ℹ️ No changes detected, skipping commit")
        return

    run("git add .")
    run(f'git commit -m "{message}"')
    run(f"git push origin {TARGET_BRANCH}")

# -------------------------------------------------
# MAIN
# -------------------------------------------------

def main():
    print("🤖 CI Smart Agent started")

    clone_target_repo()
    logs = read_ci_logs()

    # 1️⃣ Fix NameError typos
    name_error = extract_name_error_fix(logs)
    if name_error:
        old_name, new_name = name_error
        fix_name_error(old_name, new_name)
        git_commit_and_push(
            f"🤖 CI Bot: fix NameError {old_name} → {new_name}"
        )
        print("🚀 NameError fixed successfully")
        return

    # 2️⃣ Fix missing dependency/import
    missing_module = extract_missing_module(logs)
    if missing_module:
        print(f"🔍 Missing module detected: {missing_module}")

        if missing_module in SAFE_PYPI_PACKAGES:
            add_dependency(missing_module)
            fix_type = "dependency"
        
        if "command not found" in logs:
        print("Detected invalid shell command")
        print("Suggested fix: remove or replace the invalid command")

        else:
            remove_import(missing_module)
            fix_type = "code"

        git_commit_and_push(
            f"🤖 CI Bot: auto-fix missing {fix_type} ({missing_module})"
        )
        print("🚀 Dependency/import fixed successfully")
        return

    print("ℹ️ No supported fix found in CI logs")

if __name__ == "__main__":
    main()
