import json
from datetime import datetime

from backend.models.email import CanonicalEmail, EmailSender
from backend.classification.classifier import classify_email
from backend.config import MOCK_DATA_PATH


# ---------------------------------------------------------------------------
# What this script does:
#   1. Loads data/mock_data/emails.json
#   2. Converts each raw dict into a CanonicalEmail object
#   3. Runs classify_email() on each one
#   4. Prints a clean summary so you can visually confirm the rules work
#
# This is intentionally a plain script (not pytest yet) so you can just
# run it directly and read the output. Proper pytest assertions come later
# once the rules are stable.
# ---------------------------------------------------------------------------

def load_mock_emails() -> list[CanonicalEmail]:
    with open(MOCK_DATA_PATH, "r", encoding="utf-8") as f:
        raw_emails = json.load(f)

    emails = []
    for raw in raw_emails:
        email = CanonicalEmail(
            id=raw["id"],
            thread_id=raw.get("thread_id"),
            sender=EmailSender(**raw["sender"]),
            recipients=raw.get("recipients", []),
            subject=raw["subject"],
            body=raw["body"],
            timestamp=datetime.fromisoformat(raw["timestamp"].replace("Z", "+00:00")),
            is_reply=raw.get("is_reply", False),
            raw_headers=raw.get("raw_headers"),
        )
        emails.append(email)
    return emails


def run():
    emails = load_mock_emails()
    print(f"\nLoaded {len(emails)} mock emails.\n")
    print("=" * 90)

    for email in emails:
        result = classify_email(email)

        print(f"ID:              {result.email.id}")
        print(f"Subject:         {result.email.subject}")
        print(f"Sender:          {result.email.sender.email}")
        print(f"Category:        {result.category.value}")
        print(f"Reply Required:  {result.reply_required}")
        print(f"Confidence:      {result.confidence}")
        print(f"Reason:          {result.reason}")
        print("=" * 90)


if __name__ == "__main__":
    run()