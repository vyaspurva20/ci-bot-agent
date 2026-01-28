import os
import subprocess
from pathlib import Path

from github import Github

# ---------------- CONFIG ----------------
TARGET_REPO_NAME = "vyaspurva20/event-management-api"
TARGET_DIR = "target-repo"

# ---------------- UTILS ----------------
def run(cmd, cwd=None, check=True):
    print(f"👉 Running: {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=cwd, check=check)


# ---------------- STEP 1: READ CI LOGS ----------------
logs = os.environ.get("CI_LOGS", "")
if not logs:
    print("⚠️ No CI_LOGS found. Exiting.")
    exit(0)

print("📥 CI logs received")

# ---------------- STEP 2: DETECT ERROR ----------------
fixes_applied = []
explanation = []

if "No module named 'oas'" in logs:
    fixes_applied.append("REMOVE_INVALID_OAS_IMPORT")
    explanation.append(
        "Removed invalid import `oas` from `manage.py` because the module does not exist."
    )

if not fixes_applied:
    print("🤷 No known fix patterns matched. Exiting safely.")
    exit(0)

# ---------------- STEP 3: APPLY FIXES ----------------
manage_py_path = Path(TARGET_DIR) / "manage.py"

if "REMOVE_INVALID_OAS_IMPORT" in fixes_applied:
    if manage_py_path.exists():
        code = manage_py_path.read_text()

        if "import oas" in code:
            code = code.replace("import oas\n", "")
            manage_py_path.write_text(code)
            print("✅ Fixed manage.py (removed `import oas`)")
        else:
            print("ℹ️ manage.py did not contain `import oas`")
    else:
        print("❌ manage.py not found")

# ---------------- STEP 4: COMMIT & PUSH ----------------
try:
    run(["git", "config", "user.name", "ci-bot-agent"], cwd=TARGET_DIR)
    run(["git", "config", "user.email", "ci-bot-agent@github.com"], cwd=TARGET_DIR)

    run(["git", "add", "."], cwd=TARGET_DIR)
    run(
        ["git", "commit", "-m", "🤖 CI Bot: auto-fix missing module error"],
        cwd=TARGET_DIR,
    )
    run(["git", "push"], cwd=TARGET_DIR)

    print("🚀 Changes committed and pushed")
except subprocess.CalledProcessError as e:
    print("⚠️ Git commit/push skipped:", e)

# ---------------- STEP 5: COMMENT ON PR ----------------
pr_number = os.environ.get("PR_NUMBER")

if pr_number:
    print(f"💬 Commenting on PR #{pr_number}")
    gh = Github(os.environ["AGENT_GITHUB_TOKEN"])
    repo = gh.get_repo(TARGET_REPO_NAME)
    pr = repo.get_pull(int(pr_number))

    pr.create_issue_comment(
        "🤖 **CI Bot Auto-Fix Applied**\n\n"
        + "\n".join(f"- {line}" for line in explanation)
    )
else:
    print("ℹ️ No PR_NUMBER found, skipping PR comment")

print("✅ CI Smart Agent finished successfully")
