"""Paper engine shared by the CLI (generate_preboard.py), the MCP server and the Streamlit app.

generate_paper() picks APPROVED questions that match a blueprint (paper type): question types
per section, subject per section (Biology / Chemistry / Physics), internal choices (OR) and
marks per chapter. It numbers them, builds the answer key and records last_used_in_paper.
"""
import random
from datetime import datetime

import storage

MAX_ATTEMPTS = 4000
LETTERS = "abcd"
AR_INSTRUCTION = ("The following question(s) consist of two statements – Assertion (A) and Reason (R). "
                  "Answer by selecting the appropriate option.")


def _slots(blueprint):
    """Blueprint sections in paper order, each with its index."""
    return [dict(s, index=i) for i, s in enumerate(blueprint["sections"])]


def assemble_paper(questions, blueprint, seed=None, subjects=None):
    """Choose questions for the blueprint. Pure function: no reading or writing.

    Each section slot takes `count` questions of its type (and subject, if the slot names one);
    `choice` of them get an OR alternative of the same type and subject, preferably from the same
    chapter. Chapter marks count the main questions only. Tries many random selections and keeps
    the one closest to the chapter-mark targets (then the difficulty mix). Same seed + bank = same paper.
    """
    rng = random.Random(seed)
    subjects = subjects or {}
    subject_of = lambda q: subjects.get(q["chapter_id"], "biology")  # noqa: E731
    pool = [q for q in questions if q.get("status") == "approved"]
    slots = _slots(blueprint)
    targets = blueprint["chapter_marks"]
    mix = blueprint.get("difficulty_mix", {})

    def candidates_for(slot):
        return [q for q in pool if q["qtype"] == slot["qtype"]
                and (not slot.get("subject") or subject_of(q) == slot["subject"])]

    for slot in slots:
        need = slot["count"] + slot.get("choice", 0)
        have = len(candidates_for(slot))
        if have < need:
            what = f"{slot.get('subject', '')} {slot['qtype']}".strip()
            raise ValueError(f"Not enough approved '{what}' questions: the blueprint needs {need} "
                             f"(including OR alternatives), the bank has {have}. Approve or add more of this type.")

    # fill the biggest questions first: they are the hardest to fit into chapter targets
    fill_order = sorted(slots, key=lambda s: -s["marks_each"])
    best, best_score = None, None
    for _ in range(MAX_ATTEMPTS):
        remaining = dict(targets)
        chosen = {}  # slot index -> (main questions, alternatives)
        for slot in fill_order:
            candidates = candidates_for(slot)
            rng.shuffle(candidates)
            candidates.sort(key=lambda q: remaining.get(q["chapter_id"], 0) < q["marks"])
            mains = candidates[: slot["count"]]
            for q in mains:
                remaining[q["chapter_id"]] = remaining.get(q["chapter_id"], 0) - q["marks"]
            rest = candidates[slot["count"]:]
            alts = []
            for q in mains[: slot.get("choice", 0)]:
                same = [r for r in rest if r["chapter_id"] == q["chapter_id"]] or rest
                alt = same[0]
                rest.remove(alt)
                alts.append(alt)
            chosen[slot["index"]] = (mains, alts)
        all_mains = [q for mains, _ in chosen.values() for q in mains]
        chapter_gap = sum(abs(v) for v in remaining.values())
        diff_gap = sum(abs(sum(q["difficulty"] == d for q in all_mains) - share * len(all_mains)) for d, share in mix.items())
        score = (chapter_gap, diff_gap)
        if best_score is None or score < best_score:
            best, best_score = chosen, score
        if chapter_gap == 0 and diff_gap <= 2:
            break

    paper, number = [], 0
    for slot in slots:
        mains, alts = best[slot["index"]]
        # questions with an OR alternative come last in their group, as in the CBSE paper
        ordered = [q for q in mains if q not in mains[: len(alts)]] + mains[: len(alts)]
        alt_of = {mains[i]["id"]: alts[i] for i in range(len(alts))}
        for q in ordered:
            number += 1
            item = {**q, "number": number, "section": slot["section"], "subject": slot.get("subject") or subject_of(q)}
            if q["id"] in alt_of:
                item["alternative"] = dict(alt_of[q["id"]])
            paper.append(item)
    return paper


def summarise(questions, blueprint, subjects=None):
    subjects = subjects or {}
    chapter_marks = {c: 0 for c in blueprint["chapter_marks"]}
    subject_marks = {}
    for q in questions:
        chapter_marks[q["chapter_id"]] = chapter_marks.get(q["chapter_id"], 0) + q["marks"]
        subj = q.get("subject") or subjects.get(q["chapter_id"], "biology")
        subject_marks[subj] = subject_marks.get(subj, 0) + q["marks"]
    return {
        "total_questions": len(questions),
        "total_marks": sum(q["marks"] for q in questions),
        "internal_choices": sum(1 for q in questions if q.get("alternative")),
        "chapter_marks": chapter_marks,
        "chapter_targets": blueprint["chapter_marks"],
        "subject_marks": subject_marks,
        "difficulty": {d: sum(q["difficulty"] == d for q in questions) for d in storage.DIFFICULTIES},
        "competency_based_share": round(sum(bool(q.get("competency_based")) for q in questions) / len(questions), 2),
    }


def correct_letter(q):
    return LETTERS[q["options"].index(q["answer"])] if q.get("options") else None


def _key_entry(q):
    entry = {"id": q["id"], "marks": q["marks"], "answer": q["answer"], "marking_scheme": q.get("marking_scheme", [])}
    if q.get("options"):
        entry["option"] = correct_letter(q)
        entry["explanation"] = q.get("explanation", "")
    return entry


def answer_key(questions):
    key = []
    for q in questions:
        entry = {"number": q["number"], **_key_entry(q)}
        if q.get("alternative"):
            entry["alternative"] = _key_entry(q["alternative"])
        key.append(entry)
    return key


def section_labels(blueprint):
    titles = blueprint.get("section_titles") or {}
    labels = {s["section"]: s["label"] for s in reversed(blueprint["sections"])}
    return {sec: titles.get(sec, label) for sec, label in labels.items()}


def generate_paper(seed=None, record=True, paper_type=None):
    """Build a paper + answer key from approved questions. Returns a JSON-friendly dict.

    paper_type: a blueprint name from storage.list_blueprints() (default: Biology 30 marks).
    If seed is None a random one is chosen (and returned) so the paper can be rebuilt later.
    If record is True, each chosen question's last_used_in_paper is set to this paper's id.
    """
    if seed is None:
        seed = random.randrange(1, 1_000_000)
    blueprint = storage.get_blueprint(paper_type)
    if blueprint is None:
        raise ValueError(f"Unknown paper type '{paper_type}'. Choose one of: {', '.join(storage.list_blueprints())}.")
    subjects = storage.chapter_subjects()
    questions = assemble_paper(storage.list_questions(status="approved"), blueprint, seed, subjects)
    paper_id = f"paper-{datetime.now():%Y%m%d-%H%M%S}-seed{seed}"
    if record:
        used = [q["id"] for q in questions] + [q["alternative"]["id"] for q in questions if q.get("alternative")]
        storage.mark_used(used, paper_id)
    return {
        "paper_id": paper_id,
        "paper_type": paper_type or storage.DEFAULT_PAPER,
        "seed": seed,
        "title": blueprint["title"],
        "duration": blueprint["duration"],
        "general_instructions": blueprint.get("general_instructions", []),
        "section_labels": section_labels(blueprint),
        "summary": summarise(questions, blueprint, subjects),
        "questions": questions,
        "answer_key": answer_key(questions),
    }


def _text_lines(q, indent="     "):
    lines = [q["question"]]
    lines += [f"{indent}({l}) {o}" for l, o in zip(LETTERS, q.get("options") or [])]
    return lines


def _key_lines(number, a):
    out = []
    if a.get("option"):
        out.append(f"Q{number}. ({a['option']}) {a['answer']}")
        if a.get("explanation"):
            out.append(f"     {a['explanation']}")
    else:
        out.append(f"Q{number}. {a['answer']}")
    out += [f"     • {step}" for step in a["marking_scheme"]]
    return out


def render_text(paper):
    """Plain-text (question paper, answer key) for the terminal."""
    lines = [paper["title"], f"Time: {paper['duration']}    Maximum Marks: {paper['summary']['total_marks']}", "",
             "General Instructions:"]
    lines += [f"  {i}. {t}" for i, t in enumerate(paper["general_instructions"], 1)]
    key = [f"ANSWER KEY – {paper['title']}"]
    current, prev_type = None, None
    for q, a in zip(paper["questions"], paper["answer_key"]):
        if q["section"] != current:
            current, prev_type = q["section"], None
            lines += ["", f"SECTION {current} – {paper['section_labels'][current]}"]
            key += ["", f"SECTION {current}"]
        if q["qtype"] == "assertion_reason" and prev_type != "assertion_reason":
            lines.append(AR_INSTRUCTION)
        prev_type = q["qtype"]
        body = _text_lines(q)
        lines.append(f"Q{q['number']}. {body[0]}  [{q['marks']}]")
        lines += body[1:]
        key += _key_lines(q["number"], a)
        if q.get("alternative"):
            lines.append("     OR")
            lines += ["     " + line for line in _text_lines(q["alternative"])]
            key.append("     OR")
            key += _key_lines(q["number"], a["alternative"])
    return "\n".join(lines), "\n".join(key)
