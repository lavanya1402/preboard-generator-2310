"""Helper commands used by the agents in agents/*.md (no API key needed).

    download URL [URL ...] --to FOLDER   download official CBSE/NCERT PDFs (or ZIPs of PDFs) into data/sources/FOLDER
    extract [PDF ...]                    pypdf text extraction -> .txt next to each PDF (default: all in data/sources)
    save-report NAME FILE                save a JSON report through storage.py (data/reports/NAME.json)
    show-report NAME                     print a saved report
    diff-syllabus                        compare syllabus_report["proposed_syllabus"] with the current syllabus
    apply-syllabus --approved            save the proposed syllabus (ONLY after the teacher said yes)
    diff-blueprint                       compare blueprint_report["proposed_blueprint"] with the current blueprint
    apply-blueprint --approved           save the proposed blueprint (ONLY after the teacher said yes)
    check-original FILE                  check questions in a JSON file are not copied from past papers

Run:  .venv\\Scripts\\python.exe scripts\\agent_tools.py <command> ...
"""
import argparse
import difflib
import io
import json
import re
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import papers  # noqa: E402
import storage  # noqa: E402

SOURCES = ROOT / "data" / "sources"
OFFICIAL_HOSTS = ("cbseacademic.nic.in", "cbse.gov.in", "cbse.nic.in", "ncert.nic.in")
COPY_THRESHOLD = 0.75


def is_official(url):
    p = urlparse(url)
    host = (p.hostname or "").lower()
    return p.scheme == "https" and any(host == h or host.endswith("." + h) for h in OFFICIAL_HOSTS)


def safe_name(name):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", Path(name).name)[:120] or "file"


# ---------------------------------------------------------------- download / extract
def cmd_download(args):
    import httpx

    dest = SOURCES / safe_name(args.to)
    dest.mkdir(parents=True, exist_ok=True)
    manifest_path = SOURCES / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else []
    saved, failed = [], []
    with httpx.Client(follow_redirects=True, timeout=60, headers={"User-Agent": "Mozilla/5.0 preboard-generator"}) as client:
        for url in args.urls:
            if not is_official(url):
                failed.append((url, "not an official https CBSE/NCERT address - skipped"))
                continue
            try:
                r = client.get(url)
                r.raise_for_status()
                if not is_official(str(r.url)):
                    raise ValueError(f"redirected to a non-official site ({r.url})")
                body = r.content
                files = []
                if body[:4] == b"%PDF":
                    path = dest / safe_name(urlparse(url).path or "file.pdf")
                    path = path if path.suffix.lower() == ".pdf" else path.with_suffix(".pdf")
                    path.write_bytes(body)
                    files.append(path)
                elif body[:2] == b"PK":
                    with zipfile.ZipFile(io.BytesIO(body)) as z:
                        for member in z.infolist():
                            if member.filename.lower().endswith(".pdf") and not member.is_dir():
                                data = z.read(member)
                                if data[:4] == b"%PDF":
                                    path = dest / safe_name(member.filename)
                                    path.write_bytes(data)
                                    files.append(path)
                    if not files:
                        raise ValueError("ZIP contained no PDF files")
                else:
                    raise ValueError("the address did not return a PDF (maybe a web page or login screen)")
                for f in files:
                    saved.append(f)
                    manifest.append({"url": url, "file": str(f.relative_to(SOURCES)), "downloaded_at": datetime.now().isoformat(timespec="seconds")})
            except Exception as e:  # report every failure so the teacher can download it by hand
                failed.append((url, str(e)[:200]))
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    for f in saved:
        print(f"SAVED   {f.relative_to(ROOT)}")
    for url, why in failed:
        print(f"FAILED  {url}\n        reason: {why}")
    print(f"\n{len(saved)} file(s) saved, {len(failed)} failed.")


def cmd_extract(args):
    from pypdf import PdfReader

    pdfs = [Path(p) for p in args.pdfs] or sorted(SOURCES.rglob("*.pdf"))
    for pdf in pdfs:
        txt = pdf.with_suffix(".txt")
        if txt.exists() and not args.pdfs:
            continue
        try:
            reader = PdfReader(str(pdf))
            pages = [page.extract_text() or "" for page in reader.pages]
        except Exception as e:
            print(f"FAILED  {pdf.name}: {e}")
            continue
        text = "\n\n".join(f"--- page {i} ---\n{t}" for i, t in enumerate(pages, 1))
        txt.write_text(text, encoding="utf-8")
        chars = sum(len(t.strip()) for t in pages)
        warn = "  (very little text - probably a scanned PDF; tell the teacher)" if chars < 40 * len(pages) else ""
        print(f"OK      {pdf.relative_to(ROOT) if pdf.is_relative_to(ROOT) else pdf}: {len(pages)} pages, {chars} characters{warn}")


# ---------------------------------------------------------------- reports
def cmd_save_report(args):
    data = json.loads(Path(args.file).read_text(encoding="utf-8"))
    data.setdefault("generated_at", datetime.now().isoformat(timespec="seconds"))
    storage.save_report(args.name, data)
    print(f"Saved report '{args.name}'.")


def cmd_show_report(args):
    report = storage.get_report(args.name)
    if report is None:
        sys.exit(f"No report '{args.name}'. Saved reports: {', '.join(storage.list_reports()) or 'none'}")
    print(json.dumps(report, ensure_ascii=False, indent=2))


def proposal(report_name, key):
    report = storage.get_report(report_name)
    if not report or key not in report:
        sys.exit(f"Report '{report_name}' has no '{key}'. Run the agent first.")
    return report[key]


# ---------------------------------------------------------------- syllabus
def validate_syllabus(s):
    errors = []
    chapters = s.get("chapters") or []
    if not chapters:
        errors.append("No chapters.")
    for c in chapters:
        for f in ("chapter_id", "name", "topics"):
            if not c.get(f):
                errors.append(f"Chapter {c.get('chapter_id', '?')}: '{f}' missing.")
    ids = [c.get("chapter_id") for c in chapters]
    if len(ids) != len(set(ids)):
        errors.append("Duplicate chapter_id.")
    return errors


def cmd_diff_syllabus(args):
    new, old = proposal("syllabus_report", "proposed_syllabus"), storage.get_syllabus()
    old_ch = {c["chapter_id"]: c for c in old["chapters"]}
    new_ch = {c["chapter_id"]: c for c in new["chapters"]}
    print("SYLLABUS CHANGES (proposed vs current)\n")
    changed = False
    for cid in sorted(set(old_ch) | set(new_ch)):
        a, b = old_ch.get(cid), new_ch.get(cid)
        if a is None:
            print(f"+ NEW CHAPTER {b['name']} ({cid})"); changed = True; continue
        if b is None:
            print(f"- REMOVED CHAPTER {a['name']} ({cid})"); changed = True; continue
        lines = []
        for t in b["topics"]:
            if t not in a["topics"]:
                lines.append(f"    + topic: {t}")
        for t in a["topics"]:
            if t not in b["topics"]:
                lines.append(f"    - topic: {t}")
        for t in b.get("deleted_or_formative_only", []):
            if t not in a.get("deleted_or_formative_only", []):
                lines.append(f"    ! now deleted / formative only: {t}")
        if a["name"] != b["name"]:
            lines.append(f"    ~ name: '{a['name']}' -> '{b['name']}'")
        if lines:
            changed = True
            print(f"* {b['name']} ({cid})")
            print("\n".join(lines))
    print("" if changed else "No differences.")
    errors = validate_syllabus(new)
    print("Problems: " + "; ".join(errors) if errors else "Proposed syllabus is well-formed.")


def cmd_apply_syllabus(args):
    if not args.approved:
        sys.exit("Refused: add --approved only after the teacher has said yes to the differences.")
    new = proposal("syllabus_report", "proposed_syllabus")
    errors = validate_syllabus(new)
    if errors:
        sys.exit("Not saved: " + "; ".join(errors))
    new = {**new, "verified": True, "approved_at": datetime.now().isoformat(timespec="seconds")}
    removed = set(storage.chapter_names()) - {c["chapter_id"] for c in new["chapters"]}
    storage.save_syllabus(new)
    print("Syllabus updated.")
    for cid in removed:
        n = len(storage.list_questions(chapter=cid))
        print(f"Note: chapter '{cid}' was removed; {n} question(s) still use it - ask the teacher what to do with them.")


# ---------------------------------------------------------------- blueprint
def blueprint_feasibility(bp):
    try:
        qs = papers.assemble_paper(storage.list_questions(status="approved"), bp, seed=1)
    except ValueError as e:
        return str(e)
    s = papers.summarise(qs, bp)
    if s["chapter_marks"] != bp["chapter_marks"]:
        return f"With today's approved questions the best paper has chapter marks {s['chapter_marks']} (target {bp['chapter_marks']})."
    return None


def cmd_diff_blueprint(args):
    new, old = proposal("blueprint_report", "proposed_blueprint"), storage.get_blueprint()
    print("BLUEPRINT CHANGES (proposed vs current)\n")
    print(f"{'Section / type':34} {'current':>10} {'proposed':>10}")
    key = lambda s: f"{s['section']} {s['qtype']}"  # noqa: E731
    old_s = {key(s): s for s in old["sections"]}
    new_s = {key(s): s for s in new["sections"]}
    for k in list(dict.fromkeys(list(old_s) + list(new_s))):
        a = f"{old_s[k]['count']} x {old_s[k]['marks_each']}" if k in old_s else "-"
        b = f"{new_s[k]['count']} x {new_s[k]['marks_each']}" if k in new_s else "-"
        print(f"{k:34} {a:>10} {b:>10}{'   <- changed' if a != b else ''}")
    print(f"\n{'Chapter marks':34} {'current':>10} {'proposed':>10}")
    for c in list(dict.fromkeys(list(old["chapter_marks"]) + list(new["chapter_marks"]))):
        a, b = old["chapter_marks"].get(c, "-"), new["chapter_marks"].get(c, "-")
        print(f"{c:34} {a:>10} {b:>10}{'   <- changed' if a != b else ''}")
    for field in ("total_marks", "total_questions", "difficulty_mix", "competency_based_target"):
        if old.get(field) != new.get(field):
            print(f"{field}: {old.get(field)} -> {new.get(field)}")
    for line in difflib.unified_diff(old.get("general_instructions", []), new.get("general_instructions", []), "current", "proposed", lineterm="", n=0):
        print("instructions " + line)
    errors = storage.validate_blueprint(new)
    print("\nProblems: " + "; ".join(errors) if errors else "\nProposed blueprint adds up correctly.")
    warn = None if errors else blueprint_feasibility(new)
    if warn:
        print("Warning: " + warn + " More approved questions are needed for some chapters/types.")


def cmd_apply_blueprint(args):
    if not args.approved:
        sys.exit("Refused: add --approved only after the teacher has said yes to the differences.")
    new = {**proposal("blueprint_report", "proposed_blueprint"), "verified": True,
           "approved_at": datetime.now().isoformat(timespec="seconds")}
    try:
        storage.save_blueprint(new)
    except storage.ValidationError as e:
        sys.exit(str(e))
    print("Blueprint updated.")
    warn = blueprint_feasibility(new)
    if warn:
        print("Warning: " + warn)


# ---------------------------------------------------------------- originality
def source_chunks():
    chunks = []
    for txt in SOURCES.rglob("*.txt"):
        text = re.sub(r"\s+", " ", txt.read_text(encoding="utf-8", errors="ignore"))
        for piece in re.split(r"(?<=[.?!])\s+", text):
            words = storage._normalise(piece)
            if len(words) >= 8:
                chunks.append((txt.name, words, piece[:160]))
    return chunks


def cmd_check_original(args):
    items = json.loads(Path(args.file).read_text(encoding="utf-8"))
    items = items if isinstance(items, list) else [items]
    chunks = source_chunks()
    if not chunks:
        print("No extracted past-paper text in data/sources yet - nothing to compare against.")
    problems = 0
    for i, q in enumerate(items, 1):
        for sentence in re.split(r"(?<=[.?!])\s+|\n", q.get("question", "")):
            words = storage._normalise(sentence)
            if len(words) < 8:
                continue
            for name, cw, raw in chunks:
                if abs(len(cw) - len(words)) > len(words):
                    continue
                ratio = difflib.SequenceMatcher(None, words, cw).ratio()
                if ratio >= COPY_THRESHOLD:
                    problems += 1
                    print(f"Question {i}: {ratio:.0%} similar to {name}:\n   ours:  {sentence[:160]}\n   paper: {raw}")
                    break
        dup = storage.find_near_duplicate(q.get("question", ""), storage.list_questions())
        if dup:
            problems += 1
            print(f"Question {i}: {dup[1]:.0%} similar to bank question {dup[0]}")
    print(f"\n{len(items)} question(s) checked, {problems} problem(s).")
    sys.exit(1 if problems else 0)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("download"); d.add_argument("urls", nargs="+"); d.add_argument("--to", required=True)
    e = sub.add_parser("extract"); e.add_argument("pdfs", nargs="*")
    s = sub.add_parser("save-report"); s.add_argument("name"); s.add_argument("file")
    r = sub.add_parser("show-report"); r.add_argument("name")
    sub.add_parser("diff-syllabus")
    a = sub.add_parser("apply-syllabus"); a.add_argument("--approved", action="store_true")
    sub.add_parser("diff-blueprint")
    b = sub.add_parser("apply-blueprint"); b.add_argument("--approved", action="store_true")
    c = sub.add_parser("check-original"); c.add_argument("file")
    args = p.parse_args()
    {"download": cmd_download, "extract": cmd_extract, "save-report": cmd_save_report, "show-report": cmd_show_report,
     "diff-syllabus": cmd_diff_syllabus, "apply-syllabus": cmd_apply_syllabus, "diff-blueprint": cmd_diff_blueprint,
     "apply-blueprint": cmd_apply_blueprint, "check-original": cmd_check_original}[args.cmd](args)


if __name__ == "__main__":
    main()
