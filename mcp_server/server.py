"""cbse-paper-mcp – MCP server that lets Claude Code work with the question bank.

Built on the official MCP Python SDK (MCPServer, formerly called FastMCP) and on
storage.py / papers.py, so it shares all logic with the Streamlit app.

Run by Claude Code over stdio (registered with `claude mcp add`), or by hand:
    .venv\\Scripts\\python.exe mcp_server\\server.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp.server.mcpserver import MCPServer  # noqa: E402

import papers  # noqa: E402
import storage  # noqa: E402

mcp = MCPServer(
    "cbse-paper-mcp",
    instructions=(
        "Tools for a CBSE Class 10 Science (Biology) preboard question bank. "
        "New questions are always saved as 'pending' and only the teacher approves them. "
        "Papers are generated from approved questions only, following the blueprint."
    ),
)

QTYPES = ", ".join(storage.QTYPE_MARKS)


@mcp.tool()
def get_syllabus(chapter_id: str | None = None) -> dict:
    """Return the syllabus, or one chapter if chapter_id is given (e.g. 'life_processes')."""
    syllabus = storage.get_syllabus()
    if chapter_id is None:
        return syllabus
    for chapter in syllabus["chapters"]:
        if chapter_id.lower() in (chapter["chapter_id"], chapter["name"].lower()):
            return chapter
    return {"error": f"No chapter '{chapter_id}'. Chapters: {', '.join(c['chapter_id'] for c in syllabus['chapters'])}"}


@mcp.tool()
def get_blueprint() -> dict:
    """Return the paper blueprint: sections, question types, marks per chapter, difficulty mix."""
    return storage.get_blueprint()


@mcp.tool()
def search_questions(chapter: str | None = None, qtype: str | None = None, difficulty: str | None = None,
                     status: str | None = "approved", limit: int = 20) -> dict:
    """Search the question bank.

    chapter: chapter_id or name, e.g. 'life_processes' or 'Life Processes'.
    qtype: one of mcq, assertion_reason, vsa, sa, la, case_based.
    difficulty: easy, medium or hard.
    status: approved (default), pending, rejected, or 'any'.
    """
    if status in ("any", "all", ""):
        status = None
    found = storage.list_questions(chapter=chapter, qtype=qtype, difficulty=difficulty, status=status)
    return {"total_found": len(found), "returned": min(len(found), limit), "questions": found[:max(limit, 0)]}


@mcp.tool()
def add_question(question_json: str | dict) -> dict:
    """Add a NEW question. It is always saved with status 'pending' for the teacher to review.

    question_json fields: chapter_id, topic, qtype (mcq, assertion_reason, vsa, sa, la, case_based),
    difficulty, competency_based (true/false), question, answer, marking_scheme (list of steps),
    and for mcq / assertion_reason: options (list of 4) with answer exactly equal to one option,
    plus explanation. id, marks, chapter name and created_at are filled in automatically.
    source defaults to 'ai'.
    """
    try:
        q = json.loads(question_json) if isinstance(question_json, str) else dict(question_json)
    except json.JSONDecodeError as e:
        return {"ok": False, "errors": [f"question_json is not valid JSON: {e}"]}
    q["status"] = "pending"
    if q.get("source") not in storage.SOURCES:
        q["source"] = "ai"
    try:
        saved = storage.add_question(q)
    except storage.ValidationError as e:
        return {"ok": False, "errors": e.errors}
    return {"ok": True, "id": saved["id"], "status": saved["status"], "question": saved}


@mcp.tool()
def update_question_status(id: str, status: str) -> dict:
    """Set a question's status to approved, pending or rejected (the teacher's decision)."""
    try:
        storage.set_status(id, status)
    except (KeyError, ValueError) as e:
        return {"ok": False, "error": str(e).strip("'\"")}
    return {"ok": True, "id": id, "status": status}


@mcp.tool()
def generate_paper(seed: int | None = None) -> dict:
    """Generate a preboard paper from APPROVED questions following the blueprint.

    Returns the paper (numbered questions by section), the answer key with marking scheme,
    and a summary of marks per chapter vs target. Records last_used_in_paper on each question.
    The same seed gives the same paper.
    """
    try:
        paper = papers.generate_paper(seed)
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    return {"ok": True, **paper}


@mcp.tool()
def get_stats() -> dict:
    """Counts of questions by status, source, type, difficulty and approved questions per chapter."""
    return storage.stats()


if __name__ == "__main__":
    mcp.run()
