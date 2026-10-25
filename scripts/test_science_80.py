"""Checks the 80-mark Board 2027 paper (science_80) against the official 2026-27 SQP structure.

Works on a temporary COPY of data/: applies the proposed syllabus (from syllabus_report) and adds
dummy approved Chemistry/Physics questions, so your real question bank is not changed.
Run:
    .venv\\Scripts\\python.exe scripts\\test_science_80.py
"""
import io
import json
import os
import shutil
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
TMP = Path(tempfile.mkdtemp(prefix="preboard_80_test_"))
shutil.copytree(ROOT / "data", TMP / "data", ignore=shutil.ignore_patterns("sources"))
os.environ.update(STORAGE="json", DATA_DIR=str(TMP / "data"))

from pypdf import PdfReader  # noqa: E402

import papers  # noqa: E402
import pdfs  # noqa: E402
import storage  # noqa: E402

storage.reset_backend()
passed = 0

# official structure (SQP 2026-27): section -> (subject, {qtype: count}, marks, OR choices)
OFFICIAL = {
    "A": ("biology", {"mcq": 7, "assertion_reason": 2, "vsa": 3, "sa": 2, "case_based": 1, "la": 1}, 30, 2),
    "B": ("chemistry", {"mcq": 7, "assertion_reason": 1, "vsa": 1, "sa": 2, "case_based": 1, "la": 1}, 25, 2),
    "C": ("physics", {"mcq": 2, "assertion_reason": 1, "vsa": 2, "sa": 3, "case_based": 1, "la": 1}, 25, 2),
}


def check(name, condition):
    global passed
    if not condition:
        raise SystemExit(f"FAIL: {name}")
    passed += 1
    print(f"PASS  {name}")


# 1. without Chemistry/Physics questions the app explains what is missing
try:
    papers.generate_paper(1, record=False, paper_type="science_80")
    check("missing Chemistry/Physics questions give a clear message", False)
except ValueError as e:
    check("missing Chemistry/Physics questions give a clear message", "Not enough approved" in str(e))

# 2. apply the proposed syllabus and add dummy approved questions (test fixture only)
storage.save_syllabus(storage.get_report("syllabus_report")["proposed_syllabus"])
check("blueprint science_80 is valid with the new syllabus", storage.validate_blueprint(storage.get_blueprint("science_80")) == [])
words = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi omicron pi rho sigma".split()
per_chapter = {"mcq": 4, "assertion_reason": 2, "vsa": 2, "sa": 2, "case_based": 1, "la": 1}
chem_phys = [c["chapter_id"] for c in storage.get_syllabus()["chapters"] if c["subject"] != "biology"]
n = 0
for cid in chem_phys:
    for qtype, count in per_chapter.items():
        for i in range(count):
            n += 1
            q = {"id": f"T-{n:04d}", "chapter_id": cid, "chapter": cid, "topic": "test", "qtype": qtype,
                 "marks": storage.QTYPE_MARKS[qtype], "difficulty": ["easy", "medium", "hard"][n % 3],
                 "competency_based": n % 2 == 0, "status": "approved", "source": "ai", "created_at": "2026-10-25",
                 "last_used_in_paper": None, "answer": f"answer {n}", "marking_scheme": ["1 mark: test"],
                 "question": f"Dummy {cid} {qtype} question {n} {' '.join(words[(n + k) % len(words)] for k in range(6))}?"}
            if qtype in ("mcq", "assertion_reason"):
                q["options"] = [f"option {n}{x}" for x in "abcd"]
                q["answer"] = q["options"][n % 4]
            storage.backend().insert_question(q)
print(f"      (added {n} dummy Chemistry/Physics questions to the temporary copy)")

# 3. three papers checked against the official structure
meta = {"school": "Test School", "exam": "Preboard Examination 2026-27", "date": "01-12-2026", "duration": "3 Hours"}
for seed in (1, 2, 3):
    paper = papers.generate_paper(seed, record=False, paper_type="science_80")
    qs, s = paper["questions"], paper["summary"]
    check(f"paper {seed}: {s['total_questions']} questions, {s['total_marks']} marks",
          s["total_questions"] == 39 and s["total_marks"] == 80)
    for sec, (subject, types, marks, choices) in OFFICIAL.items():
        part = [q for q in qs if q["section"] == sec]
        ok = (Counter(q["qtype"] for q in part) == Counter(types) and all(q["subject"] == subject for q in part)
              and sum(q["marks"] for q in part) == marks and sum(1 for q in part if q.get("alternative")) == choices)
        check(f"paper {seed}: Section {sec} = {subject}, {len(part)} questions, {marks} marks, {choices} OR choices", ok)
    numbers = [q["number"] for q in qs]
    check(f"paper {seed}: numbered 1–39 in order (Biology 1–16, Chemistry 17–29, Physics 30–39)",
          numbers == list(range(1, 40)) and qs[15]["section"] == "A" and qs[16]["section"] == "B" and qs[29]["section"] == "C")
    alts = [(q, q["alternative"]) for q in qs if q.get("alternative")]
    ids = [q["id"] for q in qs] + [a["id"] for _, a in alts]
    check(f"paper {seed}: OR alternatives match type and marks, no question used twice",
          all(a["qtype"] == q["qtype"] and a["marks"] == q["marks"] for q, a in alts) and len(ids) == len(set(ids)))
    check(f"paper {seed}: marks per chapter match the SQP split", s["chapter_marks"] == s["chapter_targets"])
    check(f"paper {seed}: subject marks Biology 30 / Chemistry 25 / Physics 25",
          s["subject_marks"] == {"biology": 30, "chemistry": 25, "physics": 25})
    qp, ak = pdfs.question_paper_pdf(paper, meta), pdfs.answer_key_pdf(paper, meta)
    text = "".join(p.extract_text() for p in PdfReader(io.BytesIO(qp)).pages)
    key = "".join(p.extract_text() for p in PdfReader(io.BytesIO(ak)).pages)
    check(f"paper {seed}: PDFs show Biology/Chemistry/Physics sections and OR",
          all(w in text for w in ("SECTION A", "Biology", "SECTION B", "Chemistry", "SECTION C", "Physics"))
          and text.count("OR") >= 6 and "Assertion (A) and Reason (R)" in text and key.count("OR") >= 6)
    if seed == 1:
        (TMP / "science_80_paper.pdf").write_bytes(qp)
        (TMP / "science_80_key.pdf").write_bytes(ak)

# 4. the 30-mark Biology paper is unchanged
bio = papers.generate_paper(1, record=False)
check("Biology 30-mark paper still 16 questions / 30 marks, no OR",
      bio["summary"]["total_marks"] == 30 and bio["summary"]["total_questions"] == 16 and bio["summary"]["internal_choices"] == 0)
check("paper types listed", set(storage.list_blueprints()) == {"biology_30", "science_80"})

print(f"\nAll {passed} checks passed. Sample 80-mark PDFs: {TMP}")
