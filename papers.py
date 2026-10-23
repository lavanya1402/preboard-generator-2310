"""Paper engine shared by the CLI (generate_preboard.py), the MCP server and the Streamlit app.

generate_paper() picks APPROVED questions that match the blueprint's sections and
chapter marks, numbers them, builds the answer key and records last_used_in_paper.
"""
import random
from datetime import datetime

import storage

MAX_ATTEMPTS = 4000
LETTERS = "abcd"


def assemble_paper(questions, blueprint, seed=None):
    """Choose questions for the blueprint. Pure function: no reading or writing.

    Tries many random selections and keeps the one closest to the chapter-mark
    targets (then to the difficulty mix). Same seed + same bank = same paper.
    """
    rng = random.Random(seed)
    pool = [q for q in questions if q.get("status") == "approved"]
    slots = sorted(blueprint["sections"], key=lambda s: -s["marks_each"])
    targets = blueprint["chapter_marks"]
    mix = blueprint.get("difficulty_mix", {})

    for s in slots:
        have = sum(1 for q in pool if q["qtype"] == s["qtype"])
        if have < s["count"]:
            raise ValueError(f"Not enough approved '{s['qtype']}' questions: the blueprint needs {s['count']}, "
                             f"the bank has {have}. Approve or add more questions of this type.")

    best, best_score = None, None
    for _ in range(MAX_ATTEMPTS):
        remaining = dict(targets)
        chosen = []
        for s in slots:
            candidates = [q for q in pool if q["qtype"] == s["qtype"]]
            rng.shuffle(candidates)
            # Prefer questions whose chapter still has room for these marks.
            candidates.sort(key=lambda q: remaining.get(q["chapter_id"], 0) < q["marks"])
            for q in candidates[: s["count"]]:
                chosen.append(q)
                remaining[q["chapter_id"]] = remaining.get(q["chapter_id"], 0) - q["marks"]
        chapter_gap = sum(abs(v) for v in remaining.values())
        diff_gap = sum(abs(sum(q["difficulty"] == d for q in chosen) - share * len(chosen)) for d, share in mix.items())
        score = (chapter_gap, diff_gap)
        if best_score is None or score < best_score:
            best, best_score = chosen, score
        if chapter_gap == 0 and diff_gap <= 2:
            break

    order = {(s["section"], s["qtype"]): i for i, s in enumerate(blueprint["sections"])}
    section_of = {s["qtype"]: s["section"] for s in blueprint["sections"]}
    best = sorted(best, key=lambda q: order[(section_of[q["qtype"]], q["qtype"])])
    return [{**q, "number": n, "section": section_of[q["qtype"]]} for n, q in enumerate(best, 1)]


def summarise(questions, blueprint):
    chapter_marks = {c: 0 for c in blueprint["chapter_marks"]}
    for q in questions:
        chapter_marks[q["chapter_id"]] = chapter_marks.get(q["chapter_id"], 0) + q["marks"]
    return {
        "total_questions": len(questions),
        "total_marks": sum(q["marks"] for q in questions),
        "chapter_marks": chapter_marks,
        "chapter_targets": blueprint["chapter_marks"],
        "difficulty": {d: sum(q["difficulty"] == d for q in questions) for d in storage.DIFFICULTIES},
        "competency_based_share": round(sum(bool(q.get("competency_based")) for q in questions) / len(questions), 2),
    }


def correct_letter(q):
    return LETTERS[q["options"].index(q["answer"])] if q.get("options") else None


def answer_key(questions):
    key = []
    for q in questions:
        entry = {"number": q["number"], "id": q["id"], "marks": q["marks"], "answer": q["answer"],
                 "marking_scheme": q.get("marking_scheme", [])}
        if q.get("options"):
            entry["option"] = correct_letter(q)
            entry["explanation"] = q.get("explanation", "")
        key.append(entry)
    return key


def generate_paper(seed=None, record=True):
    """Build a paper + answer key from approved questions. Returns a JSON-friendly dict.

    If seed is None a random one is chosen (and returned) so the paper can be rebuilt later.
    If record is True, each chosen question's last_used_in_paper is set to this paper's id.
    """
    if seed is None:
        seed = random.randrange(1, 1_000_000)
    blueprint = storage.get_blueprint()
    questions = assemble_paper(storage.list_questions(status="approved"), blueprint, seed)
    paper_id = f"paper-{datetime.now():%Y%m%d-%H%M%S}-seed{seed}"
    if record:
        storage.mark_used([q["id"] for q in questions], paper_id)
    return {
        "paper_id": paper_id,
        "seed": seed,
        "title": blueprint["title"],
        "duration": blueprint["duration"],
        "general_instructions": blueprint.get("general_instructions", []),
        "section_labels": {s["section"]: s["label"] for s in reversed(blueprint["sections"])},
        "summary": summarise(questions, blueprint),
        "questions": questions,
        "answer_key": answer_key(questions),
    }


def render_text(paper):
    """Plain-text (question paper, answer key) for the terminal."""
    lines = [paper["title"], f"Time: {paper['duration']}    Maximum Marks: {paper['summary']['total_marks']}", "",
             "General Instructions:"]
    lines += [f"  {i}. {t}" for i, t in enumerate(paper["general_instructions"], 1)]
    key = [f"ANSWER KEY – {paper['title']}"]
    current = None
    for q, a in zip(paper["questions"], paper["answer_key"]):
        if q["section"] != current:
            current = q["section"]
            lines += ["", f"SECTION {current}"]
            key += ["", f"SECTION {current}"]
        lines.append(f"Q{q['number']}. {q['question']}  [{q['marks']}]")
        lines += [f"     ({l}) {o}" for l, o in zip(LETTERS, q.get("options", []))]
        if a.get("option"):
            key.append(f"Q{a['number']}. ({a['option']}) {a['answer']}")
            if a.get("explanation"):
                key.append(f"     {a['explanation']}")
        else:
            key.append(f"Q{a['number']}. {a['answer']}")
        key += [f"     • {step}" for step in a["marking_scheme"]]
    return "\n".join(lines), "\n".join(key)
