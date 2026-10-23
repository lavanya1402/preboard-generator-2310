import streamlit as st

import storage
import ui

PAGE_SIZE = 10

ui.page_header("Teacher review", "AI-written questions wait here. Nothing reaches a paper until you approve it.")

if "review_msg" in st.session_state:
    st.toast(st.session_state.pop("review_msg"), icon=":material/check_circle:")


def decide(qid, status):
    storage.set_status(qid, status)
    ui.data_changed()
    st.session_state.review_msg = f"{qid} {status}"


@st.dialog("Edit question", width="large")
def edit_dialog(q):
    topics = ui.syllabus_topics().get(q["chapter_id"], [])
    st.caption(f"{q['id']} · {q['chapter']} · {ui.QTYPE_LABELS[q['qtype']]}")
    with st.form(f"edit_{q['id']}", border=False):
        question = st.text_area("Question", q["question"], height=160)
        options = None
        if q.get("options") and q["qtype"] == "mcq":
            cols = st.columns(2)
            options = [cols[i % 2].text_input(f"Option ({l})", o) for i, (l, o) in enumerate(zip("abcd", q["options"]))]
        elif q.get("options"):
            options = q["options"]  # assertion-reason options are standard wording
        if options:
            current = q["options"].index(q["answer"]) if q["answer"] in q["options"] else 0
            correct = st.segmented_control("Correct option", list("abcd"), default="abcd"[current])
            explanation = st.text_area("Explanation", q.get("explanation", ""), height=80)
        else:
            answer = st.text_area("Answer", q["answer"], height=140)
        scheme = st.text_area("Marking scheme (one step per line)", "\n".join(q["marking_scheme"]), height=110)
        c1, c2, c3 = st.columns(3)
        difficulty = c1.segmented_control("Difficulty", list(storage.DIFFICULTIES), default=q["difficulty"])
        topic = c2.selectbox("Topic", topics or [q["topic"]],
                             index=(topics.index(q["topic"]) if q["topic"] in topics else 0))
        competency = c3.toggle("Competency-based", value=bool(q.get("competency_based")))
        b1, b2 = st.columns(2)
        save = b1.form_submit_button("Save", icon=":material/save:", width="stretch")
        save_approve = b2.form_submit_button("Save and approve", type="primary", icon=":material/done_all:", width="stretch")

    if save or save_approve:
        changes = {"question": question.strip(), "difficulty": difficulty or q["difficulty"], "topic": topic,
                   "competency_based": competency,
                   "marking_scheme": [line.strip() for line in scheme.splitlines() if line.strip()]}
        if options:
            options = [o.strip() for o in options]
            changes.update(options=options, answer=options["abcd".index(correct or "a")], explanation=explanation.strip())
        else:
            changes["answer"] = answer.strip()
        if save_approve:
            changes["status"] = "approved"
        try:
            storage.update_question(q["id"], changes)
        except storage.ValidationError as e:
            st.error("\n".join(f"- {err}" for err in e.errors), title="Not saved")
        else:
            ui.data_changed()
            st.session_state.review_msg = f"{q['id']} saved" + (" and approved" if save_approve else "")
            st.rerun()


questions = ui.all_questions()
names = ui.chapter_names()
pending = [q for q in questions if q.get("status") == "pending"]

with st.container(horizontal=True, vertical_alignment="bottom"):
    chapter = st.selectbox("Chapter", ["All chapters"] + list(names.values()))
    qtype = st.selectbox("Type", ["All types"] + list(ui.QTYPE_LABELS.values()))
    st.metric("Waiting for review", len(pending))
    if st.button("Refresh", icon=":material/refresh:", help="Show questions the agents just added"):
        ui.data_changed()
        st.rerun()

shown = [q for q in pending
         if (chapter == "All chapters" or q["chapter"] == chapter)
         and (qtype == "All types" or ui.QTYPE_LABELS[q["qtype"]] == qtype)]

if not pending:
    st.success("Nothing to review. When the Question Agent writes new questions, they will appear here.",
               icon=":material/task_alt:")
    st.stop()
if not shown:
    st.info("No pending questions match these filters.")
    st.stop()

pages = (len(shown) - 1) // PAGE_SIZE + 1
page_no = st.number_input(f"Page (of {pages})", 1, pages, 1) if pages > 1 else 1
batch = shown[(page_no - 1) * PAGE_SIZE: page_no * PAGE_SIZE]

with st.popover(f"Approve all {len(batch)} shown", icon=":material/done_all:"):
    st.markdown("Approve every question on this page? Only do this after reading them.")
    if st.button("Yes, approve them", type="primary"):
        for q in batch:
            storage.set_status(q["id"], "approved")
        ui.data_changed()
        st.session_state.review_msg = f"{len(batch)} questions approved"
        st.rerun()

for q in batch:
    with st.container(border=True):
        with st.container(horizontal=True, vertical_alignment="center"):
            st.markdown(f"**{q['id']}**")
            st.badge(q["chapter"], color="blue")
            st.badge(f"{ui.QTYPE_LABELS[q['qtype']]} · {q['marks']} mark{'s' if q['marks'] > 1 else ''}", color="gray")
            st.badge(q["difficulty"], color=ui.DIFF_COLORS[q["difficulty"]])
            if q.get("competency_based"):
                st.badge("competency", color="violet")
            st.badge(f"by {q.get('source', '?')}", color="gray", icon=":material/smart_toy:" if q.get("source") == "ai" else None)
        st.caption(q["topic"])
        st.markdown(ui.md(q["question"]))
        for letter, option in zip("abcd", q.get("options") or []):
            mark = " :green[:material/check:]" if option == q["answer"] else ""
            st.markdown(f"&emsp;({letter}) {ui.md(option)}{mark}")
        with st.expander("Answer and marking scheme", expanded=not q.get("options")):
            if not q.get("options"):
                st.markdown(ui.md(q["answer"]))
            elif q.get("explanation"):
                st.caption(q["explanation"])
            st.markdown("\n".join(f"- {ui.md(step)}" for step in q["marking_scheme"]))
        with st.container(horizontal=True):
            st.button("Approve", key=f"ok_{q['id']}", type="primary", icon=":material/check:",
                      on_click=decide, args=(q["id"], "approved"))
            if st.button("Edit", key=f"ed_{q['id']}", icon=":material/edit:"):
                edit_dialog(q)
            st.button("Reject", key=f"no_{q['id']}", icon=":material/close:",
                      on_click=decide, args=(q["id"], "rejected"))
