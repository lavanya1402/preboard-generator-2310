"""Draw docs/architecture.svg – a standalone animated diagram that GitHub can show in the README.

Matches docs/architecture.html: 5 columns + review loop + "Deploy later" band.
Animation: CSS stroke-dashoffset on dashed arrows + SMIL <animateMotion> dots. Dark mode via
prefers-color-scheme inside the SVG. System fonts only.

Run:  .venv\\Scripts\\python.exe scripts\\make_architecture_svg.py
"""
from pathlib import Path
from xml.sax.saxutils import escape

OUT = Path(__file__).resolve().parent.parent / "docs" / "architecture.svg"

W, H = 1300, 780
COL_W, GAP, LEFT = 210, 46, 30
TOP, COL_H = 120, 400
ITEM_H, ITEM_GAP = 62, 12

COLUMNS = [
    ("1 · SOURCES", "Official CBSE material", "box", [
        ("Sample Paper 2026-27", "+ marking scheme (format)"),
        ("Past board papers", "~10 years (topic frequency)"),
        ("Syllabus 2026-27", "+ NCERT Biology chapters"),
    ]),
    ("2 · AGENTS", "Run by Claude Code", "box", [
        ("Pattern Agent", "marks per chapter, types"),
        ("Syllabus Agent", "topics, deleted portions"),
        ("Blueprint Agent", "~50% competency-based"),
        ("Question Agent", "new CBSE-style questions"),
    ]),
    ("3 · CBSE-PAPER-MCP", "MCP server + Storage", "mcp", [
        ("search · add_question", "new questions = pending"),
        ("update_status · stats", "the teacher's decision"),
        ("generate_paper", "approved only, follows blueprint"),
        ("storage.py", "JSON locally · Supabase cloud"),
    ]),
    ("4 · TEACHER REVIEW", "The red pen", "review", [
        ("Read each AI question", "answer + step-wise marking"),
        ("PILLS", ""),
        ("Only approved questions", "can ever reach a paper"),
    ]),
    ("5 · STREAMLIT APP", "Outputs", "box", [
        ("Generate Paper", "16 questions · 30 marks"),
        ("Question Paper PDF", "with school header"),
        ("Answer Key PDF", "step-wise marking scheme"),
        ("Analysis", "chapter marks vs target"),
    ]),
]

STYLE = """
  .bg { fill: #f5f7f6; }
  .t { fill: #1b2a4a; font-family: system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
  .muted { fill: #5b6b85; }
  .ink-text { fill: #1f4fd1; } .pen-text { fill: #c8372d; }
  .col { fill: #ffffff; stroke: #c9d2dc; stroke-width: 1.5; }
  .col.mcp { fill: #e8eefc; stroke: #1f4fd1; }
  .col.review { fill: #fbeceb; stroke: #c8372d; }
  .item { fill: #ffffff; stroke: #c9d2dc; stroke-width: 1; }
  .mcp-item { stroke: #9fb4ee; } .review-item { stroke: #e3a49e; }
  .band { fill: #eef1f4; stroke: #c9d2dc; stroke-width: 1.5; }
  .loop { fill: #fbeceb; stroke: #c8372d; stroke-width: 1.5; stroke-dasharray: 6 5; }
  .pill-ok { fill: #dfe7fb; } .pill-wait { fill: #f6d9d6; }
  .flow { fill: none; stroke-width: 3; stroke-dasharray: 8 6; animation: dash 0.9s linear infinite; }
  .ink { stroke: #1f4fd1; } .pen { stroke: #c8372d; }
  .head-ink { fill: #1f4fd1; } .head-pen { fill: #c8372d; }
  .dot-ink { fill: #1f4fd1; } .dot-pen { fill: #c8372d; } .dot-gold { fill: #e0a100; }
  .appear { opacity: 0; animation: rise 0.8s ease forwards; }
  @keyframes dash { to { stroke-dashoffset: -28; } }
  @keyframes rise { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: none; } }
  @media (prefers-color-scheme: dark) {
    .bg { fill: #10161f; }
    .t { fill: #e6ecf5; } .muted { fill: #9aa8bd; }
    .ink-text { fill: #7c9dff; } .pen-text { fill: #ff7b70; }
    .col { fill: #19212d; stroke: #34404f; }
    .col.mcp { fill: #1c2a4d; stroke: #7c9dff; }
    .col.review { fill: #3a1f1f; stroke: #ff7b70; }
    .item { fill: #19212d; stroke: #34404f; }
    .mcp-item { stroke: #4a64a8; } .review-item { stroke: #8a4540; }
    .band { fill: #161d27; stroke: #34404f; }
    .loop { fill: #2a1a1c; stroke: #ff7b70; }
    .pill-ok { fill: #24345e; } .pill-wait { fill: #4a2624; }
    .ink { stroke: #7c9dff; } .pen { stroke: #ff7b70; }
    .head-ink, .dot-ink { fill: #7c9dff; } .head-pen, .dot-pen { fill: #ff7b70; }
  }
  @media (prefers-reduced-motion: reduce) { .flow, .appear { animation: none; opacity: 1; } }
"""


def text(x, y, s, size=13, weight=400, cls="t", anchor="start", extra=""):
    return (f'<text x="{x}" y="{y}" class="{cls}" font-size="{size}" font-weight="{weight}" '
            f'text-anchor="{anchor}"{extra}>{escape(s)}</text>')


def column(i, num, title, kind, items):
    x = LEFT + i * (COL_W + GAP)
    out = [f'<g class="appear" style="animation-delay:{0.1 + i * 0.15:.2f}s">',
           f'<rect x="{x}" y="{TOP}" width="{COL_W}" height="{COL_H}" rx="14" class="col {kind if kind != "box" else ""}"/>',
           text(x + 14, TOP + 26, num, 11, 700, "t muted", extra=' letter-spacing="1"'),
           text(x + 14, TOP + 48, title, 16, 700)]
    y = TOP + 66
    item_cls = {"mcp": "item mcp-item", "review": "item review-item"}.get(kind, "item")
    for name, sub in items:
        out.append(f'<rect x="{x + 12}" y="{y}" width="{COL_W - 24}" height="{ITEM_H}" rx="9" class="{item_cls}"/>')
        if name == "PILLS":
            px = x + 20
            for label, cls, tcls in (("Approve", "pill-ok", "ink-text"), ("Edit", "pill-wait", "pen-text"),
                                     ("Reject", "pill-wait", "pen-text")):
                w = 12 + len(label) * 6.6
                out.append(f'<rect x="{px}" y="{y + 19}" width="{w:.0f}" height="24" rx="12" class="{cls}"/>')
                out.append(text(px + w / 2, y + 36, label, 12, 700, f"t {tcls}", "middle"))
                px += w + 6
        else:
            out.append(text(x + 24, y + 26, name, 13.5, 600))
            out.append(text(x + 24, y + 46, sub, 11.5, 400, "t muted"))
        y += ITEM_H + ITEM_GAP
    out.append("</g>")
    return "\n".join(out)


def main():
    mid = TOP + COL_H / 2
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
             f'role="img" aria-labelledby="title desc">',
             '<title id="title">Preboard Generator architecture</title>',
             '<desc id="desc">Official CBSE sources feed agents run by Claude Code, which save questions through the '
             'cbse-paper-mcp server into storage. The teacher approves, edits or rejects each question; only approved '
             'questions reach the Streamlit app, which produces the question paper, answer key and analysis.</desc>',
             f"<style>{STYLE}</style>",
             '<defs>',
             '<marker id="ah-ink" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
             '<path d="M0,0 L10,5 L0,10 z" class="head-ink"/></marker>',
             '<marker id="ah-pen" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
             '<path d="M0,0 L10,5 L0,10 z" class="head-pen"/></marker>',
             '</defs>',
             f'<rect width="{W}" height="{H}" class="bg"/>',
             text(LEFT, 52, "Preboard Generator", 30, 800),
             f'<text x="{LEFT}" y="84" class="t" font-size="16" font-family="system-ui, sans-serif">'
             f'<tspan class="ink-text" font-weight="700">AI drafts</tspan><tspan class="muted"> the repetitive work  ·  </tspan>'
             f'<tspan class="pen-text" font-weight="700">the teacher decides</tspan></text>',
             text(W - LEFT, 52, "A Lavanya AI Consultancy initiative", 14, 600, "t muted", "end"),
             text(W - LEFT, 74, "making Schools AI-enabled", 13, 400, "t muted", "end")]

    for i, col in enumerate(COLUMNS):
        parts.append(column(i, *col))

    # arrows between columns (3 -> 4 is red: pending questions go to the teacher)
    for i in range(4):
        x1 = LEFT + i * (COL_W + GAP) + COL_W + 4
        x2 = x1 + GAP - 10
        color = "pen" if i == 2 else "ink"
        pid = f"p{i}"
        parts.append(f'<path id="{pid}" d="M{x1},{mid} L{x2},{mid}" class="flow {color}" marker-end="url(#ah-{color})"/>')
        parts.append(f'<circle r="4.5" class="dot-{color}"><animateMotion dur="1.6s" begin="{i * 0.4:.1f}s" '
                     f'repeatCount="indefinite"><mpath href="#{pid}" xlink:href="#{pid}"/></animateMotion></circle>')

    # review loop: from Teacher Review back to storage (approved)
    rx = LEFT + 3 * (COL_W + GAP) + COL_W / 2
    mx = LEFT + 2 * (COL_W + GAP) + COL_W / 2
    by = TOP + COL_H
    loop = f"M{rx},{by + 4} C{rx},{by + 58} {mx},{by + 58} {mx},{by + 8}"
    parts.append(f'<path id="loop" d="{loop}" class="flow pen" marker-end="url(#ah-pen)"/>')
    parts.append('<circle r="5" class="dot-pen"><animateMotion dur="2.4s" repeatCount="indefinite">'
                 '<mpath href="#loop" xlink:href="#loop"/></animateMotion></circle>')
    parts.append(text((rx + mx) / 2, by + 62, "approved → saved in storage", 12, 600, "t pen-text", "middle"))

    # big journey dot: sources -> app
    journey = f"M{LEFT + COL_W / 2},{mid} L{LEFT + 4 * (COL_W + GAP) + COL_W / 2},{mid}"
    parts.append(f'<path id="journey" d="{journey}" fill="none" stroke="none"/>')
    parts.append('<circle r="6" class="dot-gold" opacity="0.9"><animateMotion dur="6s" repeatCount="indefinite">'
                 '<mpath href="#journey" xlink:href="#journey"/></animateMotion></circle>')

    # loop explanation band
    ly = by + 82
    parts.append(f'<rect x="{LEFT}" y="{ly}" width="{W - 2 * LEFT}" height="40" rx="12" class="loop"/>')
    parts.append(f'<circle cx="{LEFT + 22}" cy="{ly + 20}" r="5" class="dot-pen"><animate attributeName="r" '
                 f'values="4;7;4" dur="1.4s" repeatCount="indefinite"/></circle>')
    parts.append(text(LEFT + 38, ly + 25, "Approve / edit / reject updates each question's status in storage – "
                      "the paper engine only reads approved questions.", 13.5, 500, "t pen-text"))

    # deploy band
    dy = ly + 58
    parts.append(f'<rect x="{LEFT}" y="{dy}" width="{W - 2 * LEFT}" height="84" rx="14" class="band"/>')
    parts.append(text(LEFT + 20, dy + 47, "Deploy later", 16, 700))
    boxes = [("GitHub", "code + animated diagram"), ("Streamlit Community Cloud", "the live app"),
             ("Supabase", "data that survives restarts")]
    bx, bw = LEFT + 170, 300
    for j, (name, sub) in enumerate(boxes):
        x = bx + j * (bw + 60)
        parts.append(f'<rect x="{x}" y="{dy + 14}" width="{bw}" height="56" rx="9" class="item"/>')
        parts.append(text(x + 16, dy + 38, name, 13.5, 600))
        parts.append(text(x + 16, dy + 57, sub, 11.5, 400, "t muted"))
        if j < 2:
            pid = f"d{j}"
            parts.append(f'<path id="{pid}" d="M{x + bw + 6},{dy + 42} L{x + bw + 50},{dy + 42}" class="flow ink" '
                         f'marker-end="url(#ah-ink)"/>')
            parts.append(f'<circle r="4" class="dot-ink"><animateMotion dur="1.4s" begin="{j * 0.5}s" '
                         f'repeatCount="indefinite"><mpath href="#{pid}" xlink:href="#{pid}"/></animateMotion></circle>')

    parts.append(text(W / 2, H - 12, "Built by a CBSE teacher, for teachers. AI drafts, the teacher decides.",
                      12.5, 400, "t muted", "middle"))
    parts.append("</svg>")
    OUT.write_text("\n".join(parts) + "\n", encoding="utf-8")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
