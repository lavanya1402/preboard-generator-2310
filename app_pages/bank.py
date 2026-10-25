import altair as alt
import pandas as pd
import streamlit as st

import ui

ui.page_header("Question bank", "Search every question – approved, pending and rejected.")

questions = ui.all_questions()
names = ui.chapter_names()
subjects = ui.chapter_subjects()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total questions", len(questions), border=True)
c2.metric("Approved", sum(q.get("status") == "approved" for q in questions), border=True)
c3.metric("Pending review", sum(q.get("status") == "pending" for q in questions), border=True)
c4.metric("AI-written", sum(q.get("source") == "ai" for q in questions), border=True)

with st.container(border=True):
    text = st.text_input("Search", placeholder="Search words in the question or topic, e.g. nephron",
                         icon=":material/search:")
    f1, f2 = st.columns(2)
    chapters = f1.multiselect("Chapter", list(names.values()), placeholder="All chapters")
    qtypes = f2.multiselect("Type", list(ui.QTYPE_LABELS.values()), placeholder="All types")
    f3, f4 = st.columns(2)
    difficulty = f3.pills("Difficulty", ["easy", "medium", "hard"], selection_mode="multi")
    status = f4.pills("Status", ["approved", "pending", "rejected"], selection_mode="multi")

rows = [q for q in questions
        if (not text or text.lower() in (q["question"] + " " + q["topic"]).lower())
        and (not chapters or q["chapter"] in chapters)
        and (not qtypes or ui.QTYPE_LABELS[q["qtype"]] in qtypes)
        and (not difficulty or q["difficulty"] in difficulty)
        and (not status or q.get("status") in status)]

st.caption(f"{len(rows)} question(s) found. Click a row to see the full question.")
table = pd.DataFrame([{
    "ID": q["id"], "Subject": subjects.get(q["chapter_id"], "biology").title(), "Chapter": q["chapter"], "Type": ui.QTYPE_LABELS[q["qtype"]], "Marks": q["marks"],
    "Difficulty": q["difficulty"], "Status": q.get("status"), "Source": q.get("source"),
    "Last used": q.get("last_used_in_paper") or "", "Question": q["question"].replace("\n", " "),
} for q in rows])
event = st.dataframe(
    table, hide_index=True, on_select="rerun", selection_mode="single-row", height=380,
    column_config={"Question": st.column_config.TextColumn(width="large"),
                   "Marks": st.column_config.NumberColumn(width="small")},
    alt="Table of questions matching the filters",
)

selected = event.selection.rows if rows else []
if selected:
    q = rows[selected[0]]
    with st.container(border=True):
        with st.container(horizontal=True):
            st.markdown(f"**{q['id']}**")
            st.badge(q.get("status", "?"), color=ui.STATUS_COLORS.get(q.get("status"), "gray"))
            st.badge(q["difficulty"], color=ui.DIFF_COLORS[q["difficulty"]])
        st.caption(f"{q['chapter']} · {q['topic']}")
        st.markdown(ui.md(q["question"]))
        for letter, option in zip("abcd", q.get("options") or []):
            st.markdown(f"&emsp;({letter}) {ui.md(option)}" + (" :green[:material/check:]" if option == q["answer"] else ""))
        if not q.get("options"):
            st.markdown("**Answer:**  \n" + ui.md(q["answer"]))
        st.markdown("\n".join(f"- {ui.md(step)}" for step in q["marking_scheme"]))

st.subheader("Approved questions per chapter and type", anchor=False)
approved = [q for q in questions if q.get("status") == "approved"]
if approved:
    df = pd.DataFrame([{"Chapter": q["chapter"], "Type": ui.QTYPE_LABELS[q["qtype"]]} for q in approved])
    counts = df.value_counts().reset_index(name="Questions")
    st.altair_chart(
        alt.Chart(counts).mark_bar().encode(
            x=alt.X("sum(Questions):Q", title="Approved questions"),
            y=alt.Y("Chapter:N", title=None),
            color=alt.Color("Type:N", legend=alt.Legend(orient="bottom", title=None)),
            tooltip=["Chapter", "Type", "Questions"]),
        alt="Stacked bar chart of approved questions per chapter, split by question type")
