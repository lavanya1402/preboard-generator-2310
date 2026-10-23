"""Copy the local JSON data (data/) into Supabase.

Before running:
  1. Create the tables: run scripts/supabase_schema.sql in Supabase → SQL Editor.
  2. Put SUPABASE_URL and SUPABASE_KEY in your .env file.

Run:
    .venv\\Scripts\\python.exe scripts\\migrate_to_supabase.py
Safe to run again: existing rows are updated, not duplicated.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import storage  # noqa: E402


def main():
    local = storage.JsonBackend(storage.ROOT / "data")
    cloud = storage.SupabaseBackend(storage.get_setting("SUPABASE_URL"), storage.get_setting("SUPABASE_KEY"))

    questions = local.list_questions()
    chapters = {c["chapter_id"]: c["name"] for c in local.get_doc("syllabus")["chapters"]}
    problems = {q["id"]: storage.validate_question(q, questions, chapters) for q in questions}
    problems = {k: v for k, v in problems.items() if v}
    if problems:
        print("Fix these questions first (nothing was copied):")
        for qid, errs in problems.items():
            print(f"  {qid}: " + "; ".join(errs))
        sys.exit(1)

    for i in range(0, len(questions), 200):
        cloud.upsert_questions(questions[i:i + 200])
    print(f"Questions copied: {len(questions)}")

    docs = ["syllabus", "blueprint"] + local.list_docs("report:")
    for doc in docs:
        data = local.get_doc(doc)
        if data is not None:
            cloud.save_doc(doc, data)
            print(f"Document copied: {doc}")

    print(f"Check: Supabase now has {len(cloud.list_questions())} questions.")


if __name__ == "__main__":
    main()
