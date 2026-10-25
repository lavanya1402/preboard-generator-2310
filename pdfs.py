"""PDF builder for the question paper and answer key (fpdf2 + DejaVu fonts so →, °, ₂ print)."""
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import MethodReturnValue, XPos, YPos

FONTS = Path(__file__).resolve().parent / "fonts"
BRAND_FOOTER = "Prepared with Preboard Generator – Lavanya AI Consultancy"
INK = (31, 79, 209)
TEXT = (27, 42, 74)
MUTED = (95, 107, 133)
LETTERS = "abcd"
AR_INSTRUCTION = ("The following question(s) consist of two statements – Assertion (A) and Reason (R). "
                  "Answer by selecting the appropriate option.")


def subject_line(paper):
    subjects = set(paper["summary"].get("subject_marks", {})) or {"biology"}
    return "Science (Biology)" if subjects == {"biology"} else "Science"


class PaperPDF(FPDF):
    def __init__(self, footer_note=None):
        super().__init__(format="A4")
        self.footer_note = footer_note
        self.add_font("DejaVu", "", str(FONTS / "DejaVuSans.ttf"))
        self.add_font("DejaVu", "B", str(FONTS / "DejaVuSans-Bold.ttf"))
        self.set_margins(16, 14, 16)
        self.set_auto_page_break(True, margin=18)
        self.set_text_color(*TEXT)

    def footer(self):
        self.set_y(-13)
        self.set_font("DejaVu", "", 8)
        self.set_text_color(*MUTED)
        if self.footer_note:
            self.cell(0, 5, self.footer_note, align="L")
            self.set_x(self.l_margin)
        self.cell(0, 5, f"Page {self.page_no()} of {{nb}}", align="R")
        self.set_text_color(*TEXT)

    def rule(self):
        self.set_draw_color(*INK)
        self.set_line_width(0.4)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(3)


def text_height(pdf, width, line_h, text, size, bold=False):
    pdf.set_font("DejaVu", "B" if bold else "", size)
    lines = pdf.multi_cell(width, line_h, text, dry_run=True, output=MethodReturnValue.LINES)
    return len(lines) * line_h


def keep_together(pdf, height):
    """Start a new page if `height` mm will not fit on the current one."""
    if pdf.get_y() + height > pdf.page_break_trigger:
        pdf.add_page()


def header_block(pdf, meta, paper, subtitle=None):
    pdf.add_page()
    pdf.set_font("DejaVu", "B", 15)
    pdf.multi_cell(0, 7, meta["school"].strip() or "School Name", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("DejaVu", "B", 12)
    pdf.multi_cell(0, 6, meta["exam"], align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("DejaVu", "", 10.5)
    pdf.cell(0, 6, f"Class X  ·  {subject_line(paper)}", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    if subtitle:
        pdf.set_font("DejaVu", "B", 11)
        pdf.set_text_color(*INK)
        pdf.cell(0, 7, subtitle, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_text_color(*TEXT)
    pdf.ln(2)
    pdf.set_font("DejaVu", "", 10)
    y = pdf.get_y()
    pdf.cell(0, 6, f"Date: {meta['date']}", align="L")
    pdf.set_xy(pdf.l_margin, y)
    pdf.cell(0, 6, f"Time: {meta['duration']}      Maximum Marks: {paper['summary']['total_marks']}", align="R",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(1)
    pdf.rule()


def section_heading(pdf, section, label):
    pdf.ln(2)
    keep_together(pdf, 30)  # heading + start of the first question
    pdf.set_font("DejaVu", "B", 11)
    pdf.cell(0, 6, f"SECTION {section}", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("DejaVu", "", 9)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 5, label, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(*TEXT)
    pdf.ln(1)


def numbered_block(pdf, number, text, marks=None):
    """'Q1.' + wrapped text, with [marks] at the right of the first line. Returns nothing."""
    num_w, marks_w = 11, 12
    y = pdf.get_y()
    if marks is not None:
        pdf.set_xy(pdf.w - pdf.r_margin - marks_w, y)
        pdf.cell(marks_w, 5.5, f"[{marks}]", align="R")
    pdf.set_xy(pdf.l_margin, y)
    pdf.set_font("DejaVu", "B", 10)
    pdf.cell(num_w, 5.5, f"{number}.")
    pdf.set_font("DejaVu", "", 10)
    pdf.multi_cell(pdf.epw - num_w - marks_w, 5.5, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def indented(pdf, text, indent=11, size=10, color=TEXT, height=5.2):
    pdf.set_font("DejaVu", "", size)
    pdf.set_text_color(*color)
    pdf.set_x(pdf.l_margin + indent)
    pdf.multi_cell(pdf.epw - indent - 12, height, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(*TEXT)


def question_paper_pdf(paper, meta):
    pdf = PaperPDF()
    header_block(pdf, meta, paper)
    pdf.set_font("DejaVu", "B", 10)
    pdf.cell(0, 6, "General Instructions:", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("DejaVu", "", 9.5)
    for i, line in enumerate(paper["general_instructions"], 1):
        pdf.set_x(pdf.l_margin + 4)
        pdf.multi_cell(pdf.epw - 4, 5, f"{i}. {line}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    current, prev_type = None, None
    for q in paper["questions"]:
        if q["section"] != current:
            current, prev_type = q["section"], None
            section_heading(pdf, current, paper["section_labels"][current])
        if q["qtype"] == "assertion_reason" and prev_type != "assertion_reason":
            keep_together(pdf, 30)
            indented(pdf, AR_INSTRUCTION, indent=0, size=9.5, color=MUTED)
            for letter, option in zip(LETTERS, q["options"]):
                indented(pdf, f"({letter}) {option}", indent=6, size=9.5, color=MUTED)
            pdf.ln(1.5)
        prev_type = q["qtype"]
        ar = q["qtype"] == "assertion_reason"  # options already listed once above
        options = [] if ar else [f"({l}) {o}" for l, o in zip(LETTERS, q.get("options") or [])]
        alt = q.get("alternative")
        alt_options = [f"({l}) {o}" for l, o in zip(LETTERS, (alt or {}).get("options") or [])]
        keep_together(pdf, text_height(pdf, pdf.epw - 23, 5.5, q["question"], 10)
                      + sum(text_height(pdf, pdf.epw - 29, 5.2, o, 10) for o in options) + 2.5
                      + (text_height(pdf, pdf.epw - 23, 5.5, alt["question"], 10) + 8 if alt else 0))
        numbered_block(pdf, f"Q{q['number']}", q["question"], q["marks"])
        for option in options:
            indented(pdf, option, indent=17)
        if alt:
            pdf.set_font("DejaVu", "B", 10)
            pdf.cell(0, 6, "OR", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            indented(pdf, alt["question"])
            for option in alt_options:
                indented(pdf, option, indent=17)
        pdf.ln(2.5)
    pdf.ln(4)
    pdf.set_font("DejaVu", "B", 10)
    pdf.cell(0, 6, "*** End of Question Paper ***", align="C")
    return bytes(pdf.output())


def answer_key_pdf(paper, meta):
    pdf = PaperPDF(footer_note=BRAND_FOOTER)
    header_block(pdf, meta, paper, subtitle="ANSWER KEY & MARKING SCHEME")
    by_number = {q["number"]: q for q in paper["questions"]}
    current = None
    for a in paper["answer_key"]:
        q = by_number[a["number"]]
        if q["section"] != current:
            current = q["section"]
            section_heading(pdf, current, paper["section_labels"][current])
        parts = [a] + ([a["alternative"]] if a.get("alternative") else [])
        height = 2.5
        for part in parts:
            answer = f"({part['option']}) {part['answer']}" if part.get("option") else part["answer"]
            height += (text_height(pdf, pdf.epw - 23, 5.5, answer, 10)
                       + text_height(pdf, pdf.epw - 23, 5.2, part.get("explanation") or "", 9)
                       + sum(text_height(pdf, pdf.epw - 26, 5.2, f"• {st}", 9) for st in part["marking_scheme"]) + 6)
        keep_together(pdf, height)
        for i, part in enumerate(parts):
            answer = f"({part['option']}) {part['answer']}" if part.get("option") else part["answer"]
            if i == 0:
                numbered_block(pdf, f"Q{a['number']}", answer, a["marks"])
            else:
                pdf.set_font("DejaVu", "B", 10)
                pdf.cell(0, 6, "OR", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                indented(pdf, answer)
            if part.get("explanation"):
                indented(pdf, part["explanation"], size=9, color=MUTED)
            for step in part["marking_scheme"]:
                indented(pdf, f"• {step}", indent=14, size=9)
        pdf.ln(2.5)
    return bytes(pdf.output())
