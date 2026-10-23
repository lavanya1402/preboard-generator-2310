"""Starts mcp_server/server.py over stdio (the way Claude Code does) and calls every tool.

Uses a temporary COPY of data/, so your real question bank is not changed.
Run:
    .venv\\Scripts\\python.exe scripts\\test_mcp_server.py
"""
import asyncio
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from mcp.client.client import Client, StdioServerParameters

ROOT = Path(__file__).resolve().parent.parent
EXPECTED_TOOLS = {"get_syllabus", "get_blueprint", "search_questions", "add_question",
                  "update_question_status", "generate_paper", "get_stats"}
passed = 0


def check(name, condition):
    global passed
    if not condition:
        raise SystemExit(f"FAIL: {name}")
    passed += 1
    print(f"PASS  {name}")


def data_of(result):
    if getattr(result, "is_error", False) or getattr(result, "isError", False):
        raise SystemExit(f"Tool error: {result.content}")
    structured = getattr(result, "structured_content", None) or getattr(result, "structuredContent", None)
    if structured is not None:
        return structured.get("result", structured) if set(structured) == {"result"} else structured
    return json.loads(result.content[0].text)


async def main(tmp):
    params = StdioServerParameters(
        command=sys.executable, args=[str(ROOT / "mcp_server" / "server.py")],
        env={**os.environ, "STORAGE": "json", "DATA_DIR": str(tmp / "data")},
    )
    async with Client(params) as client:
        call = lambda name, **kw: client.call_tool(name, kw)  # noqa: E731

        tools = {t.name for t in (await client.list_tools()).tools}
        check(f"server lists all 7 tools", EXPECTED_TOOLS <= tools)

        syl = data_of(await call("get_syllabus", chapter_id="heredity"))
        check("get_syllabus(chapter_id) returns one chapter", syl["name"] == "Heredity")
        check("get_blueprint returns 30 marks", data_of(await call("get_blueprint"))["total_marks"] == 30)

        found = data_of(await call("search_questions", chapter="Life Processes", qtype="case_based", difficulty="hard", limit=5))
        check("search_questions filters correctly",
              found["returned"] >= 1 and all(q["difficulty"] == "hard" and q["qtype"] == "case_based" for q in found["questions"]))

        new_q = {
            "chapter_id": "our_environment", "topic": "Ecosystem and its components", "qtype": "vsa",
            "difficulty": "medium", "competency_based": True, "status": "approved",
            "question": "A school aquarium has fish, water plants, snails and gravel. Name two biotic and two abiotic components in it.",
            "answer": "Biotic: fish, water plants, snails. Abiotic: water, gravel, light, temperature.",
            "marking_scheme": ["1 mark: two biotic components.", "1 mark: two abiotic components."],
        }
        added = data_of(await call("add_question", question_json=json.dumps(new_q)))
        check("add_question saves as pending even if told 'approved'", added["ok"] and added["status"] == "pending")
        bad = data_of(await call("add_question", question_json=json.dumps({**new_q, "marks": 5, "question": "Different text here?"})))
        check("add_question returns clear errors", not bad["ok"] and any("must carry 2 mark" in e for e in bad["errors"]))

        pending = data_of(await call("search_questions", status="pending"))
        check("new question is in pending list", any(q["id"] == added["id"] for q in pending["questions"]))
        ok = data_of(await call("update_question_status", id=added["id"], status="approved"))
        check("update_question_status approves", ok["ok"])
        check("unknown id gives an error", not data_of(await call("update_question_status", id="XX-1", status="approved"))["ok"])

        paper = data_of(await call("generate_paper", seed=42))
        s = paper["summary"]
        check(f"generate_paper: {s['total_questions']} questions, {s['total_marks']} marks",
              s["total_questions"] == 16 and s["total_marks"] == 30)
        check("paper matches chapter targets", s["chapter_marks"] == s["chapter_targets"])
        check("answer key has 16 entries", len(paper["answer_key"]) == 16)
        again = data_of(await call("generate_paper", seed=42))
        check("same seed gives same paper", [q["id"] for q in again["questions"]] == [q["id"] for q in paper["questions"]])

        stats = data_of(await call("get_stats"))
        check("get_stats counts the new question", stats["total"] == 68)

    bank = json.loads((tmp / "data" / "question_bank.json").read_text(encoding="utf-8"))
    used = [q for q in bank if q["last_used_in_paper"]]
    check("last_used_in_paper recorded for the 16 questions", len(used) == 16)


if __name__ == "__main__":
    tmp = Path(tempfile.mkdtemp(prefix="preboard_mcp_test_"))
    shutil.copytree(ROOT / "data", tmp / "data", ignore=shutil.ignore_patterns("sources"))
    try:
        asyncio.run(main(tmp))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"\nAll {passed} checks passed. Your real data/ folder was not changed.")
