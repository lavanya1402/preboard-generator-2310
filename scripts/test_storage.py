"""Checks storage.py on a temporary COPY of data/ (your real files are not touched).

Run:
    .venv\\Scripts\\python.exe scripts\\test_storage.py
"""
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TMP = Path(tempfile.mkdtemp(prefix="preboard_test_"))
shutil.copytree(ROOT / "data", TMP / "data", ignore=shutil.ignore_patterns("sources"))
os.environ["STORAGE"] = "json"
os.environ["DATA_DIR"] = str(TMP / "data")

import storage  # noqa: E402

storage.reset_backend()
passed = 0


def check(name, condition):
    global passed
    if not condition:
        raise SystemExit(f"FAIL: {name}")
    passed += 1
    print(f"PASS  {name}")


def rejected_with(q, words):
    try:
        storage.add_question(q)
    except storage.ValidationError as e:
        return any(words in err for err in e.errors)
    return False


GOOD = {
    "chapter_id": "life_processes", "topic": "Excretion in human beings and in plants", "qtype": "mcq",
    "difficulty": "easy", "question": "Which organ in plants stores waste products such as resins and gums in old xylem?",
    "options": ["Old xylem tissue", "Root hairs", "Guard cells", "Phloem sieve tubes"],
    "answer": "Old xylem tissue", "marking_scheme": ["1 mark for the correct option (a)."],
}

# 1. existing data
questions = storage.list_questions()
check("question bank loads (67 questions)", len(questions) == 67)
check("syllabus and blueprint load", storage.get_syllabus()["chapters"] and storage.get_blueprint()["sections"])
bad = {q["id"]: storage.validate_question(q) for q in questions}
bad = {k: v for k, v in bad.items() if v}
check(f"all existing questions pass validation {bad or ''}", not bad)
check("filters work", all(q["qtype"] == "case_based" for q in storage.list_questions(chapter="Life Processes", qtype="case_based")))

# 2. adding a good question
saved = storage.add_question(GOOD)
check("new question saved as pending / ai", saved["status"] == "pending" and saved["source"] == "ai")
check("id and marks filled automatically", saved["id"] == "LP-MCQ-008" and saved["marks"] == 1)
check("question is stored", storage.get_question(saved["id"]) is not None)

# 3. bad questions are refused with clear messages
check("wrong marks refused", rejected_with({**GOOD, "question": "Q about marks?", "marks": 3}, "must carry 1 mark"))
check("MCQ answer not in options refused",
      rejected_with({**GOOD, "question": "Another different stomata question?", "answer": "Leaves"}, "exactly one of the 4 options"))
check("missing field refused", rejected_with({k: v for k, v in GOOD.items() if k != "answer"}, "'answer' is missing"))
check("unknown chapter refused", rejected_with({**GOOD, "chapter_id": "magnetism", "question": "Totally new?"}, "not in the syllabus"))
check("near-duplicate refused",
      rejected_with({**GOOD, "question": "The opening and closing of the stomata is controlled by"}, "too similar"))
check("options on a 2-mark question refused",
      rejected_with({**GOOD, "qtype": "vsa", "question": "Explain the role of xylem in plants."}, "should not have options"))

# 4. status, edits, usage
storage.set_status(saved["id"], "approved")
check("status update works", storage.get_question(saved["id"])["status"] == "approved")
try:
    storage.update_question(saved["id"], {"answer": "Something not in options"})
    check("bad teacher edit refused", False)
except storage.ValidationError:
    check("bad teacher edit refused", True)
storage.update_question(saved["id"], {"difficulty": "medium"})
check("good teacher edit saved", storage.get_question(saved["id"])["difficulty"] == "medium")
storage.mark_used(["LP-MCQ-001", "CC-SA-001"], "test-paper")
check("last_used_in_paper recorded", storage.get_question("CC-SA-001")["last_used_in_paper"] == "test-paper")

# 5. reports and stats
storage.save_report("test_report", {"ok": True})
check("reports save and list", "test_report" in storage.list_reports() and storage.get_report("test_report") == {"ok": True})
s = storage.stats()
check("stats count everything", s["total"] == 68 and s["by_status"]["approved"] == 68)

# 6. settings
os.environ["STORAGE"] = "supabase"
os.environ.pop("SUPABASE_URL", None)
os.environ["SUPABASE_URL"] = ""
storage.reset_backend()
try:
    storage.backend()
    check("supabase without settings gives a clear error", False)
except RuntimeError as e:
    check("supabase without settings gives a clear error", "SUPABASE_URL" in str(e))

shutil.rmtree(TMP, ignore_errors=True)
print(f"\nAll {passed} checks passed. Your real data/ folder was not changed.")
