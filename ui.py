"""Shared Streamlit pieces: branding, cached data, small formatting helpers."""
import streamlit as st

import storage

BRAND = "Lavanya AI Consultancy"
BRAND_LINE = "An initiative to make Schools AI-enabled"
APP_NAME = "Preboard Generator"
QTYPE_LABELS = {"mcq": "MCQ", "assertion_reason": "Assertion–Reason", "vsa": "2-mark (VSA)",
                "sa": "3-mark (SA)", "la": "5-mark (LA)", "case_based": "Case-based (4)"}
DIFF_COLORS = {"easy": "green", "medium": "orange", "hard": "red"}
STATUS_COLORS = {"approved": "blue", "pending": "red", "rejected": "gray"}


def page_header(title, subtitle=None):
    with st.container(horizontal=True, vertical_alignment="center"):
        st.title(title, anchor=False)
        st.space("stretch")
        st.badge(f"A {BRAND} initiative · making Schools AI-enabled", icon=":material/school:", color="primary")
    if subtitle:
        st.caption(subtitle)


def sidebar_brand():
    with st.sidebar:
        st.markdown(f"### :blue[{BRAND}]")
        st.caption(BRAND_LINE)
        st.divider()


def footer():
    st.divider()
    st.caption(f"© 2026 {BRAND} · Built by a CBSE teacher, for teachers. AI drafts, the teacher decides.")


@st.cache_data(ttl=10, show_spinner=False)  # short: agents add questions from outside the app
def all_questions():
    return storage.list_questions()


@st.cache_data(ttl=300, show_spinner=False)
def chapter_names():
    return storage.chapter_names()


@st.cache_data(ttl=300, show_spinner=False)
def syllabus_topics():
    return {c["chapter_id"]: c["topics"] for c in storage.get_syllabus()["chapters"]}


def data_changed():
    """Call after any write so every page shows fresh data."""
    all_questions.clear()


def md(text):
    """Show question text safely in Markdown: keep line breaks, no accidental LaTeX."""
    return str(text).replace("$", "\\$").replace("\n", "  \n")
