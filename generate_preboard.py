"""Preboard Generator – command-line version.

Builds one Biology preboard paper from APPROVED questions in the question bank,
following data/paper_blueprint.json (question types per section and marks per
chapter), and prints the paper and its answer key.

Usage:
    .venv\\Scripts\\python.exe generate_preboard.py            # random paper
    .venv\\Scripts\\python.exe generate_preboard.py --seed 7   # same seed = same paper
    .venv\\Scripts\\python.exe generate_preboard.py --save out.txt
    .venv\\Scripts\\python.exe generate_preboard.py --no-record  # don't update last_used_in_paper
"""
import argparse
import sys
from pathlib import Path

import papers


def main():
    parser = argparse.ArgumentParser(description="Generate a CBSE Class 10 Biology preboard paper.")
    parser.add_argument("--seed", type=int, default=None, help="same seed gives the same paper")
    parser.add_argument("--save", help="also save paper + answer key to this text file")
    parser.add_argument("--no-record", action="store_true", help="do not record last_used_in_paper")
    args = parser.parse_args()

    try:
        paper = papers.generate_paper(args.seed, record=not args.no_record)
    except ValueError as e:
        sys.exit(f"Could not make a paper: {e}")
    paper_text, key_text = papers.render_text(paper)
    s = paper["summary"]
    summary = (f"\n--- {paper['paper_id']}: {s['total_questions']} questions, {s['total_marks']} marks | "
               f"chapter marks {s['chapter_marks']} | difficulty {s['difficulty']} ---")
    output = paper_text + "\n\n" + key_text + summary
    print(output)
    if args.save:
        Path(args.save).write_text(output, encoding="utf-8")
        print(f"Saved to {args.save}")


if __name__ == "__main__":
    main()
