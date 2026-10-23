"""Preboard Generator – command-line version.

Builds one Biology preboard paper from APPROVED questions in the question bank,
following data/paper_blueprint.json (question types per section and marks per
chapter), and prints the paper and its answer key.

Usage:
    .venv\\Scripts\\python.exe generate_preboard.py            # random paper
    .venv\\Scripts\\python.exe generate_preboard.py --seed 7   # same seed = same paper
    .venv\\Scripts\\python.exe generate_preboard.py --save out.txt
"""
import argparse
import json
import random
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"
MAX_ATTEMPTS = 4000


def load_json(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def assemble_paper(questions, blueprint, seed=None):
    """Pick questions that match the blueprint's sections and chapter marks.

    Tries many random selections and keeps the one closest to the chapter-mark
    targets (and then to the difficulty mix). Returns a dict with the chosen
    questions in section order plus a summary.
    """
    rng = random.Random(seed)
    pool = [q for q in questions if q.get("status", "approved") == "approved"]
    slots = sorted(blueprint["sections"], key=lambda s: -s["marks_each"])
    targets = blueprint["chapter_marks"]
    mix = blueprint.get("difficulty_mix", {})

    for s in slots:
        have = sum(1 for q in pool if q["qtype"] == s["qtype"])
        if have < s["count"]:
            raise ValueError(f"Not enough approved '{s['qtype']}' questions: need {s['count']}, have {have}.")

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
        n = len(chosen)
        diff_gap = sum(abs(sum(q["difficulty"] == d for q in chosen) - share * n) for d, share in mix.items())
        score = (chapter_gap, diff_gap)
        if best_score is None or score < best_score:
            best, best_score = chosen, score
        if chapter_gap == 0 and diff_gap <= 2:
            break

    order = {(s["section"], s["qtype"]): i for i, s in enumerate(blueprint["sections"])}
    section_of = {s["qtype"]: s["section"] for s in blueprint["sections"]}
    best.sort(key=lambda q: order[(section_of[q["qtype"]], q["qtype"])])

    chapter_marks = {}
    for q in best:
        chapter_marks[q["chapter_id"]] = chapter_marks.get(q["chapter_id"], 0) + q["marks"]
    return {
        "seed": seed,
        "questions": best,
        "total_marks": sum(q["marks"] for q in best),
        "chapter_marks": chapter_marks,
        "chapter_targets": targets,
        "difficulty": {d: sum(q["difficulty"] == d for q in best) for d in ("easy", "medium", "hard")},
    }


def render_text(paper, blueprint):
    """Return (question_paper_text, answer_key_text)."""
    labels = {s["section"]: s["label"] for s in reversed(blueprint["sections"])}
    paper_lines = [blueprint["title"], f"Time: {blueprint['duration']}    Maximum Marks: {paper['total_marks']}", "",
                   "General Instructions:"]
    paper_lines += [f"  {i}. {t}" for i, t in enumerate(blueprint.get("general_instructions", []), 1)]
    key_lines = [f"ANSWER KEY – {blueprint['title']}", ""]
    section_of = {s["qtype"]: s["section"] for s in blueprint["sections"]}
    current = None
    for n, q in enumerate(paper["questions"], 1):
        sec = section_of[q["qtype"]]
        if sec != current:
            current = sec
            paper_lines += ["", f"SECTION {sec}"]
            key_lines += ["", f"SECTION {sec}"]
        paper_lines.append(f"Q{n}. {q['question']}  [{q['marks']}]")
        for letter, opt in zip("abcd", q.get("options", [])):
            paper_lines.append(f"     ({letter}) {opt}")
        if q.get("options"):
            letter = "abcd"[q["options"].index(q["answer"])]
            key_lines.append(f"Q{n}. ({letter}) {q['answer']}")
            if q.get("explanation"):
                key_lines.append(f"     {q['explanation']}")
        else:
            key_lines.append(f"Q{n}. {q['answer']}")
        key_lines += [f"     • {step}" for step in q.get("marking_scheme", [])]
    return "\n".join(paper_lines), "\n".join(key_lines)


def main():
    parser = argparse.ArgumentParser(description="Generate a CBSE Class 10 Biology preboard paper.")
    parser.add_argument("--seed", type=int, default=None, help="same seed gives the same paper")
    parser.add_argument("--save", help="also save paper + answer key to this text file")
    args = parser.parse_args()

    blueprint = load_json("paper_blueprint.json")
    paper = assemble_paper(load_json("question_bank.json"), blueprint, args.seed)
    paper_text, key_text = render_text(paper, blueprint)
    summary = (f"\n--- {len(paper['questions'])} questions, {paper['total_marks']} marks | "
               f"chapter marks {paper['chapter_marks']} | difficulty {paper['difficulty']} ---")
    output = paper_text + "\n\n" + key_text + summary
    print(output)
    if args.save:
        Path(args.save).write_text(output, encoding="utf-8")
        print(f"Saved to {args.save}")


if __name__ == "__main__":
    main()
