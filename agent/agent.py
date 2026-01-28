import os
import re
import subprocess
from typing import Optional

# -----------------------------
# CONFIG
# -----------------------------

TARGET_REPO = "vyaspurva20/recommender-system"
TARGET_BRANCH = "main"

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

WORKDIR = "/tmp/recommender-system"


# -----------------------------
# UTILITIES
# -----------------------------

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


def extract_missing_module(logs: str) -> Optional[str]:
    match = re.search(r"No module named ['\"]([^'\"]+)['\"]", logs)
    return match.group(1) if match else None


def find_python_files():
    for root, _, files in os.walk(WORKDIR):
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


# -----------------------------
# GIT
# -----------------------------

def git_commit_and_push(message: str):
    token = os.environ.get("AGENT_GITHUB_TOKEN")

    run('git config user.name "ci-bot-agent"')
    run('git config user.email "ci-bot-agent@users.noreply.github.com"')

    run(
        f"git remote set-url origin https://x-access-token:{token}@github.com/{TARGET_REPO}.git"
    )

    run("git add .")
    run(f'git commit -m "{message}" || echo "No changes to commit"')
    run(f"git push origin {TARGET_BRANCH}")


# -----------------------------
# MAIN
# -----------------------------

def main():
    print("🤖 CI Smart Agent started")

    clone_target_repo()

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

    git_commit_and_push(
        f"🤖 CI Bot: auto-fix missing {fix_type} ({missing_module})"
    )

    print("🚀 Fix pushed to project repo successfully")


if __name__ == "__main__":
    main()
