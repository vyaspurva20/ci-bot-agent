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

KNOWN_COMMAND_TOOLS = {
    "npm": "node",
    "yarn": "node",
    "pip": "python",
    "pip3": "python",
    "python": "python",
    "docker": "docker",
    "docker-compose": "docker",
    "make": "build",
    "aws": "aws",
    "kubectl": "kubernetes",
    "terraform": "terraform",
}

COMMON_COMMAND_TYPOS = {
    "pyhton": "python",
    "dockre": "docker",
    "npn": "npm",
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
    match = re.search(
        r"NameError: name '([^']+)' is not defined\. Did you mean: '([^']+)'",
        logs,
    )
    if match:
        return match.group(1), match.group(2)
    return None


def extract_command_not_found(logs: str) -> Optional[str]:
    match = re.search(r"(\S+): command not found", logs)
    return match.group(1) if match else None

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

        with open(file_path, "w") as f:
            f.write(content.replace(old_name, new_name))

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
        print("⚠️ requirements.txt not found, skipping dependency install")
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
# COMMAND NOT FOUND HANDLING (OPTION-1 LOGIC)
# -------------------------------------------------

def handle_command_not_found(logs: str) -> Optional[str]:
    cmd = extract_command_not_found(logs)
    if not cmd:
        return None

    print(f"❌ Command not found: {cmd}")

    if cmd in COMMON_COMMAND_TYPOS:
        return f"Fix typo: replace '{cmd}' with '{COMMON_COMMAND_TYPOS[cmd]}'"

    if cmd.startswith("./"):
        return "Make script executable using chmod +x"

    if cmd.endswith(".sh"):
        return "Use ./script.sh instead of script.sh"

    tool = KNOWN_COMMAND_TOOLS.get(cmd)
    if tool:
        return f"Install missing tool: {tool}"

    return "Unknown shell command — manual intervention required"

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

    # 1️⃣ Fix NameError
    name_error = extract_name_error_fix(logs)
    if name_error:
        old_name, new_name = name_error
        fix_name_error(old_name, new_name)
        git_commit_and_push(
            f"🤖 CI Bot: fix NameError {old_name} → {new_name}"
        )
        return

    # 2️⃣ Fix missing dependency / import
    missing_module = extract_missing_module(logs)
    if missing_module:
        print(f"🔍 Missing module detected: {missing_module}")

        if missing_module in SAFE_PYPI_PACKAGES:
            add_dependency(missing_module)
            fix_type = "dependency"
        else:
            remove_import(missing_module)
            fix_type = "import"

        git_commit_and_push(
            f"🤖 CI Bot: auto-fix missing {fix_type} ({missing_module})"
        )
        return

    # 3️⃣ Handle command not found
    cmd_fix = handle_command_not_found(logs)
    if cmd_fix:
        print(f"💡 Suggested fix: {cmd_fix}")
        return

    print("ℹ️ No supported fix found in CI logs")

if __name__ == "__main__":
    main()
