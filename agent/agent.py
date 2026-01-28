import os
import json
import subprocess
from pathlib import Path

from github import Github
from groq import Groq

# ---------------- CONFIG ----------------
REPO_NAME = os.environ.get("GITHUB_REPOSITORY")
GITHUB_TOKEN = os.environ.get("AGENT_GITHUB_TOKEN")
LLM_API_KEY = os.environ.get("LLM_API_KEY")
CI_LOGS = os.environ.get("CI_LOGS", "")

client = Groq(api_key=LLM_API_KEY)

# ---------------- HELPERS ----------------
def run(cmd):
    return subprocess.run(cmd, shell=True, text=True, capture_output=True)

def git_commit_push(message):
    run("git config user.name 'ci-bot-agent'")
    run("git config user.email 'ci-bot-agent@github.com'")
    run("git add .")
    run(f"git commit -m \"{message}\" || echo 'No changes to commit'")
    run("git push")

def comment_on_pr(comment):
    if not os.environ.get("GITHUB_EVENT_PATH"):
        return

    with open(os.environ["GITHUB_EVENT_PATH"]) as f:
        event = json.load(f)

    pr = event.get("pull_request")
    if not pr:
        return

    gh = Github(GITHUB_TOKEN)
    repo = gh.get_repo(REPO_NAME)
    repo.get_issue(pr["number"]).create_comment(comment)

# ---------------- LLM ----------------
def ask_llm_for_fix(logs):
    prompt = f"""
You are a senior CI/CD auto-fix agent.

Analyze the CI failure logs below and respond ONLY in valid JSON.

Rules:
- No explanations outside JSON
- JSON must contain an array called "fixes"
- Each fix must specify:
  - file (relative path)
  - action (remove_line | add_line | replace_line | add_dependency)
  - match (text to find, optional)
  - value (text to add/replace)
  - reason

CI LOGS:
{logs}

Example response:
{{
  "fixes": [
    {{
      "file": "manage.py",
      "action": "remove_line",
      "match": "import oas",
      "value": "",
      "reason": "Module does not exist"
    }}
  ]
}}
"""

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )

    return json.loads(response.choices[0].message.content)

# ---------------- APPLY FIXES ----------------
def apply_fix(fix):
    file_path = Path(fix["file"])

    if fix["action"] == "add_dependency":
        req = Path("requirements.txt")
        req.touch(exist_ok=True)
        req.write_text(req.read_text() + f"\n{fix['value']}\n")
        return

    if not file_path.exists():
        return

    lines = file_path.read_text().splitlines()

    if fix["action"] == "remove_line":
        lines = [l for l in lines if fix["match"] not in l]

    elif fix["action"] == "replace_line":
        lines = [fix["value"] if fix["match"] in l else l for l in lines]

    elif fix["action"] == "add_line":
        lines.append(fix["value"])

    file_path.write_text("\n".join(lines) + "\n")

# ---------------- MAIN ----------------
def main():
    if not CI_LOGS.strip():
        print("No CI logs provided — exiting")
        return

    print("🧠 Analyzing CI logs with LLM...")
    plan = ask_llm_for_fix(CI_LOGS)

    fixes = plan.get("fixes", [])
    if not fixes:
        print("No fixes suggested")
        return

    explanations = []

    for fix in fixes:
        apply_fix(fix)
        explanations.append(f"- `{fix['file']}` → {fix['reason']}")

    git_commit_push("🤖 CI Bot: auto-fix CI failure")

    comment_on_pr(
        "🤖 **CI Bot applied fixes automatically:**\n\n" +
        "\n".join(explanations)
    )

    print("✅ Fixes applied successfully")

if __name__ == "__main__":
    main()
