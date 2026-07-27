from tests.backend.test_classifier import load_mock_emails
from backend.classification.classifier import classify_email
from backend.prompts.prompt_builder import build_prompt


# ---------------------------------------------------------------------------
# What this script does:
#   1. Loads mock emails (reusing load_mock_emails from test_classifier.py)
#   2. Classifies each one
#   3. For those where reply_required=True, builds the actual prompt string
#   4. Prints it so you can visually inspect what will be sent to Ollama
# ---------------------------------------------------------------------------

def run():
    emails = load_mock_emails()

    for email in emails:
        classified = classify_email(email)

        print("=" * 90)
        print(f"Email ID: {classified.email.id}  |  Category: {classified.category.value}  |  Confidence: {classified.confidence}")

        if not classified.reply_required:
            print(">> No reply required — prompt builder skipped.")
            continue

        prompt = build_prompt(classified)
        print(">> PROMPT SENT TO MODEL:\n")
        print(prompt)

    print("=" * 90)


if __name__ == "__main__":
    run()