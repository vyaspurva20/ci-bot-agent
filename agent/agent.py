import os
import sys
import traceback
from groq import Groq

# =====================================================
# CONFIG
# =====================================================

SUPPORTED_MODELS = [
    "llama-3.1-8b-instant",
    "llama-3.1-70b-versatile",
]

SYSTEM_PROMPT = """
You are a senior CI/CD Fix Agent.

Your job:
- Analyze CI/CD failure logs
- Explain the root cause clearly
- Suggest exact fixes
- Mention filenames and corrected snippets when possible

Do NOT hallucinate.
If logs are insufficient, say so clearly.
"""

# =====================================================
# HELPERS
# =====================================================

def log(msg):
    print(msg, flush=True)

def get_api_key():
    api_key = os.getenv("LLM_API_KEY")
    if not api_key:
        raise RuntimeError("LLM_API_KEY is not set in environment")
    return api_key

# =====================================================
# LLM CALL WITH FALLBACK
# =====================================================

def call_llm(prompt: str) -> str:
    client = Groq(api_key=get_api_key())
    last_error = None

    for model in SUPPORTED_MODELS:
        try:
            log(f"🔁 Trying model: {model}")
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
            )
            return response.choices[0].message.content

        except Exception as e:
            log(f"❌ Model failed ({model}): {e}")
            last_error = e

    raise RuntimeError(f"All LLM models failed. Last error: {last_error}")

# =====================================================
# FAILURE ANALYSIS
# =====================================================

def read_ci_logs():
    """
    For now, we rely on logs passed via environment.
    Later you can extend this to read job logs automatically.
    """
    return os.getenv("CI_LOGS", "No CI logs provided.")

def analyze_failure(logs: str) -> str:
    prompt = f"""
The following CI/CD job failed.

Logs:
----------------
{logs}
----------------

Tasks:
1. Identify the root cause
2. Explain why it failed
3. Provide the exact fix
4. Mention file names and corrected snippets
"""
    return call_llm(prompt)

# =====================================================
# MAIN
# =====================================================

def main():
    try:
        log("🔍 Detecting CI/CD system...")
        log("✅ Detected: github_actions")

        log("📥 Reading CI logs...")
        logs = read_ci_logs()

        log("🧠 Analyzing failure...")
        result = analyze_failure(logs)

        log("\n================ FIX SUGGESTION ================\n")
        print(result)
        log("\n================================================\n")

    except Exception as e:
        log("🚨 LLM failure (not retryable)")
        log(str(e))
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()