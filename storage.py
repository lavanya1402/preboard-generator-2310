"""Single data layer for questions, syllabus, blueprint and agent reports.

Every other part of the project (app.py, mcp_server, generate_preboard.py,
scripts) reads and writes data ONLY through the functions in this file.

Backend is chosen by the STORAGE setting:
    json      (default) local files in data/
    supabase  Supabase Postgres tables (for Streamlit Cloud, whose disk is wiped on restart)

Settings are read from environment / .env locally and from st.secrets on Streamlit Cloud:
    STORAGE, SUPABASE_URL, SUPABASE_KEY, APP_PASSWORD, DATA_DIR (optional, json only)
"""
from __future__ import annotations

import difflib
import json
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:  # python-dotenv is optional at runtime
    pass

ROOT = Path(__file__).resolve().parent

QTYPE_MARKS = {"mcq": 1, "assertion_reason": 1, "vsa": 2, "sa": 3, "la": 5, "case_based": 4}
QTYPE_CODES = {"mcq": "MCQ", "assertion_reason": "AR", "vsa": "VSA", "sa": "SA", "la": "LA", "case_based": "CB"}
CHAPTER_CODES = {"life_processes": "LP", "control_coordination": "CC", "reproduction": "RP",
                 "heredity": "HD", "our_environment": "OE"}
DIFFICULTIES = ("easy", "medium", "hard")
STATUSES = ("approved", "pending", "rejected")
SOURCES = ("teacher", "ai")
OPTION_TYPES = ("mcq", "assertion_reason")
REQUIRED = ("id", "chapter_id", "chapter", "topic", "qtype", "marks", "difficulty",
            "question", "answer", "marking_scheme", "status", "source", "created_at")
DUPLICATE_THRESHOLD = 0.85
QUESTION_FIELDS = REQUIRED + ("competency_based", "options", "explanation", "last_used_in_paper")


class ValidationError(ValueError):
    """Raised when a question is not fit to be saved. .errors holds every problem found."""

    def __init__(self, errors):
        self.errors = list(errors)
        super().__init__("Question not saved:\n- " + "\n- ".join(self.errors))


# ---------------------------------------------------------------- settings
def get_setting(name, default=None):
    """Environment / .env first, then Streamlit secrets (only when running inside Streamlit)."""
    value = os.environ.get(name)
    if value not in (None, ""):
        return value
    try:
        from streamlit import runtime

        if runtime.exists():
            import streamlit as st

            if name in st.secrets:
                return str(st.secrets[name])
    except Exception:  # no streamlit, or no secrets file
        pass
    return default


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------- backends
class JsonBackend:
    """Local files: data/question_bank.json, data/syllabus.json, data/paper_blueprint.json, data/reports/*.json."""

    DOC_FILES = {"syllabus": "syllabus.json", "blueprint": "paper_blueprint.json"}

    def __init__(self, data_dir):
        self.dir = Path(data_dir)
        self.lock = threading.Lock()

    def _path(self, doc):
        if doc in self.DOC_FILES:
            return self.dir / self.DOC_FILES[doc]
        if doc.startswith("report:"):
            return self.dir / "reports" / f"{doc.split(':', 1)[1]}.json"
        raise KeyError(f"Unknown document '{doc}'")

    def _read(self, path, default):
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))

    def _write(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(path)  # atomic: a crash never leaves a half-written file

    @property
    def _bank(self):
        return self.dir / "question_bank.json"

    def list_questions(self):
        return self._read(self._bank, [])

    def insert_question(self, q):
        with self.lock:
            bank = self.list_questions()
            bank.append(q)
            self._write(self._bank, bank)

    def update_questions(self, ids, changes):
        with self.lock:
            bank = self.list_questions()
            for q in bank:
                if q["id"] in ids:
                    q.update(changes)
            self._write(self._bank, bank)

    def replace_question(self, q):
        with self.lock:
            bank = [q if x["id"] == q["id"] else x for x in self.list_questions()]
            self._write(self._bank, bank)

    def get_doc(self, doc):
        return self._read(self._path(doc), None)

    def save_doc(self, doc, data):
        with self.lock:
            self._write(self._path(doc), data)

    def list_docs(self, prefix):
        if prefix != "report:":
            return []
        return sorted(f"report:{p.stem}" for p in (self.dir / "reports").glob("*.json"))


class SupabaseBackend:
    """Supabase tables `questions` and `documents` (see scripts/supabase_schema.sql)."""

    PAGE = 1000

    def __init__(self, url, key):
        if not url or not key:
            raise RuntimeError("STORAGE=supabase needs SUPABASE_URL and SUPABASE_KEY in .env or Streamlit secrets.")
        from supabase import create_client

        self.db = create_client(url, key)

    def list_questions(self):
        rows, start = [], 0
        while True:
            page = (self.db.table("questions").select("*").order("id")
                    .range(start, start + self.PAGE - 1).execute().data)
            rows += page
            if len(page) < self.PAGE:
                break
            start += self.PAGE
        return [{k: v for k, v in r.items() if v is not None or k == "last_used_in_paper"} for r in rows]

    def insert_question(self, q):
        self.db.table("questions").insert(_question_row(q)).execute()

    def update_questions(self, ids, changes):
        self.db.table("questions").update(changes).in_("id", list(ids)).execute()

    def replace_question(self, q):
        self.db.table("questions").update(_question_row(q)).eq("id", q["id"]).execute()

    def upsert_questions(self, questions):
        self.db.table("questions").upsert([_question_row(q) for q in questions]).execute()

    def get_doc(self, doc):
        rows = self.db.table("documents").select("data").eq("name", doc).execute().data
        return rows[0]["data"] if rows else None

    def save_doc(self, doc, data):
        self.db.table("documents").upsert({"name": doc, "data": data, "updated_at": now_iso()}).execute()

    def list_docs(self, prefix):
        rows = self.db.table("documents").select("name").like("name", f"{prefix}%").execute().data
        return sorted(r["name"] for r in rows)


def _question_row(q):
    return {k: q.get(k) for k in QUESTION_FIELDS}


_backend = None


def backend():
    """The active backend (created once)."""
    global _backend
    if _backend is None:
        kind = (get_setting("STORAGE", "json") or "json").strip().lower()
        if kind == "json":
            _backend = JsonBackend(get_setting("DATA_DIR", str(ROOT / "data")))
        elif kind == "supabase":
            _backend = SupabaseBackend(get_setting("SUPABASE_URL"), get_setting("SUPABASE_KEY"))
        else:
            raise RuntimeError(f"STORAGE must be 'json' or 'supabase', not '{kind}'.")
    return _backend


def reset_backend():
    """Forget the cached backend (used by tests after changing settings)."""
    global _backend
    _backend = None


# ---------------------------------------------------------------- syllabus, blueprint, reports
def get_syllabus():
    return backend().get_doc("syllabus")


def save_syllabus(data):
    backend().save_doc("syllabus", data)


def get_blueprint():
    return backend().get_doc("blueprint")


def save_blueprint(data):
    backend().save_doc("blueprint", data)


def get_report(name):
    return backend().get_doc(f"report:{name}")


def save_report(name, data):
    if not re.fullmatch(r"[a-z0-9_]+", name):
        raise ValueError("Report names may only use lowercase letters, digits and underscores.")
    backend().save_doc(f"report:{name}", data)


def list_reports():
    return [d.split(":", 1)[1] for d in backend().list_docs("report:")]


def chapter_names():
    """{chapter_id: chapter name} from the syllabus."""
    return {c["chapter_id"]: c["name"] for c in (get_syllabus() or {}).get("chapters", [])}


# ---------------------------------------------------------------- questions: reading
def list_questions(chapter=None, qtype=None, difficulty=None, status=None, source=None, text=None):
    """All questions matching the filters. `chapter` accepts a chapter_id or the chapter name."""
    out = []
    for q in backend().list_questions():
        if chapter and chapter.lower() not in (q["chapter_id"].lower(), q["chapter"].lower()):
            continue
        if qtype and q["qtype"] != qtype:
            continue
        if difficulty and q["difficulty"] != difficulty:
            continue
        if status and q.get("status") != status:
            continue
        if source and q.get("source") != source:
            continue
        if text and text.lower() not in (q["question"] + " " + q.get("topic", "")).lower():
            continue
        out.append(q)
    return out


def get_question(qid):
    for q in backend().list_questions():
        if q["id"] == qid:
            return q
    return None


# ---------------------------------------------------------------- validation
def _normalise(text):
    return re.sub(r"[^a-z0-9 ]+", " ", text.lower()).split()


def find_near_duplicate(question_text, questions, ignore_id=None):
    """Return (id, similarity) of the most similar existing question if it is too similar, else None."""
    words = _normalise(question_text)
    best = None
    for other in questions:
        if other["id"] == ignore_id or other.get("status") == "rejected":
            continue
        ratio = difflib.SequenceMatcher(None, words, _normalise(other["question"])).ratio()
        if ratio >= DUPLICATE_THRESHOLD and (best is None or ratio > best[1]):
            best = (other["id"], ratio)
    return best


def validate_question(q, existing=None, chapters=None, is_new=False):
    """Return a list of clear, teacher-readable problems (empty list = OK)."""
    existing = backend().list_questions() if existing is None else existing
    chapters = chapter_names() if chapters is None else chapters
    errors = []

    if chapters and q.get("chapter_id") and q["chapter_id"] not in chapters:
        return [f"Chapter '{q['chapter_id']}' is not in the syllabus. Use one of: {', '.join(chapters)}."]
    for field in REQUIRED:
        value = q.get(field)
        if value is None or (isinstance(value, (str, list)) and not value):
            errors.append(f"'{field}' is missing or empty.")
    if errors:
        return errors

    qtype = q["qtype"]
    if qtype not in QTYPE_MARKS:
        errors.append(f"Question type '{qtype}' is not known. Use one of: {', '.join(QTYPE_MARKS)}.")
    elif q["marks"] != QTYPE_MARKS[qtype]:
        errors.append(f"A '{qtype}' question must carry {QTYPE_MARKS[qtype]} mark(s), not {q['marks']}.")
    if q["difficulty"] not in DIFFICULTIES:
        errors.append(f"Difficulty must be easy, medium or hard (got '{q['difficulty']}').")
    if q["status"] not in STATUSES:
        errors.append(f"Status must be approved, pending or rejected (got '{q['status']}').")
    if q["source"] not in SOURCES:
        errors.append(f"Source must be teacher or ai (got '{q['source']}').")
    if not isinstance(q["marking_scheme"], list) or not all(isinstance(s, str) and s.strip() for s in q["marking_scheme"]):
        errors.append("'marking_scheme' must be a list of steps (text).")

    if qtype in OPTION_TYPES:
        options = q.get("options")
        if not isinstance(options, list) or len(options) != 4:
            errors.append("MCQ and assertion-reason questions need exactly 4 options.")
        elif len({o.strip().lower() for o in options}) != 4:
            errors.append("The 4 options must all be different.")
        elif q["answer"] not in options:
            errors.append("The answer must be exactly one of the 4 options.")
    elif q.get("options"):
        errors.append(f"A '{qtype}' question should not have options.")

    if is_new and any(other["id"] == q["id"] for other in existing):
        errors.append(f"Another question already has the id '{q['id']}'.")
    dup = find_near_duplicate(q["question"], existing, ignore_id=q["id"])
    if dup:
        errors.append(f"This question is too similar ({dup[1]:.0%}) to existing question {dup[0]}.")
    return errors


# ---------------------------------------------------------------- questions: writing
def next_question_id(chapter_id, qtype, existing=None):
    existing = backend().list_questions() if existing is None else existing
    prefix = f"{CHAPTER_CODES.get(chapter_id, chapter_id[:2].upper())}-{QTYPE_CODES.get(qtype, qtype.upper())}-"
    numbers = [int(q["id"][len(prefix):]) for q in existing
               if q["id"].startswith(prefix) and q["id"][len(prefix):].isdigit()]
    return f"{prefix}{max(numbers, default=0) + 1:03d}"


def add_question(q, status="pending", source="ai"):
    """Validate and save a NEW question. Fills id, chapter name, marks, status, source, created_at.

    Returns the saved question. Raises ValidationError with all problems if it is not fit to save.
    """
    existing = backend().list_questions()
    chapters = chapter_names()
    q = {k: v for k, v in dict(q).items() if k in QUESTION_FIELDS}
    q.setdefault("status", status)
    q.setdefault("source", source)
    q.setdefault("created_at", now_iso())
    q.setdefault("last_used_in_paper", None)
    q.setdefault("competency_based", False)
    if q.get("qtype") in QTYPE_MARKS:
        q.setdefault("marks", QTYPE_MARKS[q["qtype"]])
    if q.get("chapter_id") in chapters:
        q.setdefault("chapter", chapters[q["chapter_id"]])
    if not q.get("id") and q.get("chapter_id") and q.get("qtype"):
        q["id"] = next_question_id(q["chapter_id"], q["qtype"], existing)

    errors = validate_question(q, existing, chapters, is_new=True)
    if errors:
        raise ValidationError(errors)
    backend().insert_question(q)
    return q


def update_question(qid, changes):
    """Edit an existing question (teacher edit). Re-validates the whole question before saving."""
    current = get_question(qid)
    if current is None:
        raise KeyError(f"No question with id '{qid}'.")
    changes = {k: v for k, v in changes.items() if k in QUESTION_FIELDS and k != "id"}
    updated = {**current, **changes}
    errors = validate_question(updated)
    if errors:
        raise ValidationError(errors)
    backend().replace_question(updated)
    return updated


def set_status(qid, status):
    if status not in STATUSES:
        raise ValueError(f"Status must be one of {', '.join(STATUSES)}.")
    if get_question(qid) is None:
        raise KeyError(f"No question with id '{qid}'.")
    backend().update_questions({qid}, {"status": status})


def mark_used(question_ids, paper_label):
    """Record which paper last used these questions."""
    if question_ids:
        backend().update_questions(set(question_ids), {"last_used_in_paper": paper_label})


def stats():
    questions = backend().list_questions()

    def count(key):
        out = {}
        for q in questions:
            out[q.get(key)] = out.get(q.get(key), 0) + 1
        return out

    approved = [q for q in questions if q.get("status") == "approved"]
    by_chapter = {}
    for q in approved:
        by_chapter[q["chapter_id"]] = by_chapter.get(q["chapter_id"], 0) + 1
    return {
        "total": len(questions),
        "by_status": count("status"),
        "by_source": count("source"),
        "by_qtype": count("qtype"),
        "by_difficulty": count("difficulty"),
        "approved_by_chapter": by_chapter,
        "competency_based_share": round(sum(bool(q.get("competency_based")) for q in approved) / len(approved), 2)
        if approved else 0,
    }
