import datetime
import html

import altair as alt
import pandas as pd
import streamlit as st

import papers
import pdfs
import ui

ui.page_header("Generate paper", "Builds a 30-mark Biology preboard from approved questions only, following the blueprint.")

with st.form("paper_details"):
    col1, col2 = st.columns(2)
    school = col1.text_input("School name", placeholder="e.g. Kendriya Vidyalaya No. 1, Lucknow")
    exam = col2.text_input("Exam name", value="Preboard Examination 2026-27")
    col3, col4, col5 = st.columns(3)
    date = col3.date_input("Date", value=datetime.date.today(), format="DD/MM/YYYY")
    duration = col4.text_input("Duration", value="3 Hours")
    seed = col5.number_input("Seed (optional)", min_value=1, value=None, step=1,
                             help="The same seed always gives the same paper. Leave empty for a new random paper.")
    submitted = st.form_submit_button("Generate", type="primary", icon=":material/auto_awesome:")

if submitted:
    if not school.strip():
        st.warning("Please enter the school name – it is printed at the top of the paper.")
    else:
        try:
            with st.spinner("Choosing questions…"):
                paper = papers.generate_paper(int(seed) if seed else None)
                meta = {"school": school.strip(), "exam": exam.strip() or "Preboard Examination",
                        "date": date.strftime("%d-%m-%Y"), "duration": duration.strip() or "3 Hours"}
                # Keep everything in session state so downloads and reruns never change the paper.
                st.session_state.paper = paper
                st.session_state.paper_meta = meta
                st.session_state.paper_pdf = pdfs.question_paper_pdf(paper, meta)
                st.session_state.key_pdf = pdfs.answer_key_pdf(paper, meta)
            ui.data_changed()  # last_used_in_paper was updated
        except ValueError as e:
            st.error(str(e), title="Could not make a paper")

paper = st.session_state.get("paper")
if not paper:
    st.info("Fill in the details and press **Generate**.", icon=":material/arrow_upward:")
    st.stop()

meta = st.session_state.paper_meta
summary = paper["summary"]
names = ui.chapter_names()
safe = "".join(c if c.isalnum() else "_" for c in meta["school"])[:40]

with st.container(horizontal=True, vertical_alignment="bottom"):
    st.markdown(f"**{meta['school']}** · {meta['exam']} · {meta['date']}  \n"
                f":gray[Paper id `{paper['paper_id']}` · seed **{paper['seed']}** · "
                f"{summary['total_questions']} questions · {summary['total_marks']} marks]")
    st.space("stretch")
    st.download_button("Question paper PDF", st.session_state.paper_pdf, file_name=f"{safe}_question_paper.pdf",
                       mime="application/pdf", icon=":material/download:", type="primary", on_click="ignore")
    st.download_button("Answer key PDF", st.session_state.key_pdf, file_name=f"{safe}_answer_key.pdf",
                       mime="application/pdf", icon=":material/download:", on_click="ignore")

tab_paper, tab_key, tab_analysis = st.tabs(["Question paper", "Answer key", "Analysis"])

with tab_paper:
    with st.container(border=True):
        st.markdown(f"<div style='text-align:center'><b>{html.escape(meta['school'])}</b><br>{html.escape(meta['exam'])}<br>"
                    f"Class X · Science (Biology)</div>", unsafe_allow_html=True)
        st.markdown(f"Date: {meta['date']}  \nTime: {meta['duration']} · Maximum marks: {summary['total_marks']}")
        with st.expander("General instructions"):
            for i, line in enumerate(paper["general_instructions"], 1):
                st.markdown(f"{i}. {line}")
        current = None
        for q in paper["questions"]:
            if q["section"] != current:
                current = q["section"]
                st.subheader(f"Section {current}", anchor=False)
                st.caption(paper["section_labels"][current])
            st.markdown(f"**Q{q['number']}.** {ui.md(q['question'])} &nbsp; :gray[[{q['marks']}]]")
            for letter, option in zip("abcd", q.get("options") or []):
                st.markdown(f"&emsp;({letter}) {ui.md(option)}")

with tab_key:
    for a, q in zip(paper["answer_key"], paper["questions"]):
        with st.container(border=True):
            head = f"**Q{a['number']}** · {a['marks']} mark{'s' if a['marks'] > 1 else ''} · :gray[{q['id']}]"
            st.markdown(head)
            if a.get("option"):
                st.markdown(f"**({a['option']})** {ui.md(a['answer'])}")
                if a.get("explanation"):
                    st.caption(a["explanation"])
            else:
                st.markdown(ui.md(a["answer"]))
            st.markdown("\n".join(f"- {ui.md(step)}" for step in a["marking_scheme"]))

with tab_analysis:
    c1, c2, c3 = st.columns(3)
    c1.metric("Total marks", summary["total_marks"], border=True)
    c2.metric("Questions", summary["total_questions"], border=True)
    c3.metric("Competency-based questions", f"{summary['competency_based_share']:.0%}", border=True)

    rows = []
    for cid, target in summary["chapter_targets"].items():
        label = names.get(cid, cid)
        rows += [{"Chapter": label, "Kind": "This paper", "Marks": summary["chapter_marks"].get(cid, 0)},
                 {"Chapter": label, "Kind": "Blueprint target", "Marks": target}]
    chart = alt.Chart(pd.DataFrame(rows)).mark_bar(cornerRadiusEnd=3).encode(
        x=alt.X("Marks:Q"),
        y=alt.Y("Chapter:N", sort=None, title=None),
        yOffset="Kind:N",
        color=alt.Color("Kind:N", scale=alt.Scale(range=["#1f4fd1", "#c9d2dc"]), legend=alt.Legend(orient="bottom", title=None)),
        tooltip=["Chapter", "Kind", "Marks"],
    )
    st.subheader("Marks per chapter vs target", anchor=False)
    st.altair_chart(chart, alt="Bar chart of marks per chapter in this paper compared with the blueprint target")

    st.subheader("Difficulty", anchor=False)
    diff = pd.DataFrame({"Difficulty": list(summary["difficulty"]), "Questions": list(summary["difficulty"].values())})
    st.altair_chart(
        alt.Chart(diff).mark_bar(cornerRadiusEnd=3).encode(
            x=alt.X("Difficulty:N", sort=["easy", "medium", "hard"], title=None),
            y="Questions:Q",
            color=alt.Color("Difficulty:N", scale=alt.Scale(domain=["easy", "medium", "hard"],
                                                             range=["#2e8b57", "#e0a100", "#c8372d"]), legend=None),
            tooltip=["Difficulty", "Questions"]),
        alt="Bar chart of the number of easy, medium and hard questions")
