"""Add the review fields to every question in data/question_bank.json.

Existing questions without these fields get:
    status = "approved", source = "teacher" (change with --source),
    created_at = now, last_used_in_paper = None.
Questions that already have a field keep their value.

Usage:
    .venv\\Scripts\\python.exe scripts\\add_question_fields.py [--source teacher|ai]
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

BANK = Path(__file__).resolve().parent.parent / "data" / "question_bank.json"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["teacher", "ai"], default="teacher")
    args = parser.parse_args()

    questions = json.loads(BANK.read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    changed = 0
    for q in questions:
        before = dict(q)
        q.setdefault("status", "approved")
        q.setdefault("source", args.source)
        q.setdefault("created_at", now)
        q.setdefault("last_used_in_paper", None)
        changed += q != before

    BANK.write_text(json.dumps(questions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Updated {changed} of {len(questions)} questions in {BANK.name}")


if __name__ == "__main__":
    main()
