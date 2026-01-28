import os
import subprocess
from pathlib import Path
from github import Github

def run(cmd):
    print(f"$ {cmd}")
    subprocess.run(cmd, shell=True, check=False)

# ---------------- READ LOGS ----------------
logs = os.environ.get("CI_LOGS", "")
print("📥 CI LOGS RECEIVED")

# ---------------- SIMPLE FIX RULES ----------------
fix_applied = False
explanation = ""

# Example fix: remove invalid import "oas"
if "No module named 'oas'" in logs:
    manage_py = Path("manage.py")
    if manage_py.exists():
        content = manage_py.read_text()
        if "import oas" in content:
            manage_py.write_text(content.replace("import oas\n", ""))
            fix_applied = True
            explanation = "Removed invalid import `import oas` from manage.py"

# ---------------- STOP IF NOTHING TO FIX ----------------
if not fix_applied:
    print("ℹ️ No auto-fix applied")
    exit(0)

print("✅ Fix applied")

# ---------------- STEP 4: AUTO COMMIT ----------------
run("git config user.name 'ci-bot-agent'")
run("git config user.email 'ci-bot-agent@github.com'")
run("git add .")
run("git commit -m '🤖 CI Bot: auto-fix failing CI'")
run("git push")

# ---------------- STEP 5: COMMENT ON PR ----------------
repo_name = os.environ.get("GITHUB_REPOSITORY")
token = os.environ.get("AGENT_GITHUB_TOKEN")

if repo_name and token:
    g = Github(token)
    repo = g.get_repo(repo_name)

    prs = repo.get_pulls(state="open")
    for pr in prs:
        pr.create_issue_comment(
            f"🤖 **CI Bot Auto-Fix Applied**\n\n{explanation}"
        )

print("💬 PR comment added")
