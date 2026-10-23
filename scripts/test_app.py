"""Phase 5 test: 5 papers + PDFs, then every app page in a headless Streamlit test.

Uses a temporary COPY of data/, so your real question bank is not changed.
Run:
    .venv\\Scripts\\python.exe scripts\\test_app.py
"""
import io
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
TMP = Path(tempfile.mkdtemp(prefix="preboard_app_test_"))
shutil.copytree(ROOT / "data", TMP / "data", ignore=shutil.ignore_patterns("sources"))
os.environ.update(STORAGE="json", DATA_DIR=str(TMP / "data"), APP_PASSWORD="test-pass")

from pypdf import PdfReader  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402

import papers  # noqa: E402
import pdfs  # noqa: E402
import storage  # noqa: E402

storage.reset_backend()
passed = 0


def check(name, condition):
    global passed
    if not condition:
        raise SystemExit(f"FAIL: {name}")
    passed += 1
    print(f"PASS  {name}")


# ---------- 5 papers with PDFs
meta = {"school": "Test Public School", "exam": "Preboard Examination 2026-27", "date": "01-12-2026", "duration": "3 Hours"}
seen = set()
for seed in range(1, 6):
    paper = papers.generate_paper(seed)
    s = paper["summary"]
    qp, ak = pdfs.question_paper_pdf(paper, meta), pdfs.answer_key_pdf(paper, meta)
    (TMP / f"paper_{seed}.pdf").write_bytes(qp)
    (TMP / f"key_{seed}.pdf").write_bytes(ak)
    key_text = "".join(p.extract_text() for p in PdfReader(io.BytesIO(ak)).pages)
    paper_text = "".join(p.extract_text() for p in PdfReader(io.BytesIO(qp)).pages)
    check(f"paper {seed}: {s['total_questions']} questions, {s['total_marks']} marks, "
          f"PDFs {len(qp) // 1024} KB + {len(ak) // 1024} KB",
          s["total_questions"] == 16 and s["total_marks"] == 30 and qp[:4] == b"%PDF" and ak[:4] == b"%PDF"
          and "Test Public School" in paper_text and "Lavanya AI Consultancy" in key_text
          and "Lavanya" not in paper_text)
    seen.add(tuple(q["id"] for q in paper["questions"]))
check("the 5 papers are all different", len(seen) == 5)

# ---------- the app
at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
check("login screen shows first", not at.exception and at.text_input and "Password" in at.text_input[0].label)
at.text_input[0].set_value("wrong")
at.form_submit_button[0].click().run()
check("wrong password refused", at.error and not at.session_state["authenticated"])
at.text_input[0].set_value("test-pass")
at.form_submit_button[0].click().run()
check("right password opens the app", not at.exception and at.session_state["authenticated"])

at.text_input[0].set_value("Test Public School")
at.form_submit_button[0].click().run()
check("Generate paper works in the app", not at.exception and "paper" in at.session_state
      and at.session_state["paper"]["summary"]["total_marks"] == 30)
first_ids = [q["id"] for q in at.session_state["paper"]["questions"]]
at.run()
check("paper stays the same on rerun (session state)", [q["id"] for q in at.session_state["paper"]["questions"]] == first_ids)

# add a pending question so the review page has something to show
storage.add_question({"chapter_id": "heredity", "topic": "Sex determination", "qtype": "vsa", "difficulty": "easy",
                      "question": "Why is it said that the father decides whether the baby will be a boy or a girl?",
                      "answer": "Eggs carry X; sperms carry X or Y; the sperm decides.",
                      "marking_scheme": ["1 mark: egg X, sperm X or Y.", "1 mark: sperm decides."]})
import ui  # noqa: E402

ui.data_changed()  # same as pressing Refresh
for page in ("app_pages/review.py", "app_pages/bank.py", "app_pages/about.py"):
    at.switch_page(page).run()
    check(f"{page} opens without errors", not at.exception)
at.switch_page("app_pages/review.py").run()
approve = [b for b in at.button if b.label == "Approve"]
check("review page shows the pending question", len(approve) == 1)
approve[0].click().run()
check("Approve button saves the decision", not at.exception and storage.get_question("HD-VSA-003")["status"] == "approved")

print(f"\nAll {passed} checks passed. Sample PDFs are in {TMP}")
