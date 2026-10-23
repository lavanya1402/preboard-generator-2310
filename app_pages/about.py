from pathlib import Path

import streamlit as st

import ui

DIAGRAM = Path(__file__).resolve().parent.parent / "docs" / "architecture.html"

ui.page_header("About", "What this project is and how it works.")

left, right = st.columns([3, 2])
with left:
    st.subheader("Preboard Generator", anchor=False)
    st.markdown(
        "Making a good preboard paper takes a teacher **4–6 hours**: reading the CBSE pattern, choosing "
        "questions chapter by chapter, balancing difficulty, and typing the answer key. "
        "Preboard Generator does the repetitive work so a paper takes **about 15 minutes**.\n\n"
        "- **AI agents** study the official CBSE sample paper and past board papers, and draft new "
        "CBSE-style questions with marking schemes.\n"
        "- **The teacher reviews every question** – approve, edit or reject.\n"
        "- **Only approved questions** are used. Each paper follows the blueprint: 16 questions, 30 marks, "
        "the right marks per chapter, and a mix of easy, medium and hard.\n"
        "- Download a **print-ready question paper** with your school's name, and a **step-wise answer key**."
    )
    st.markdown(":red[**AI drafts. The teacher decides.**]")
with right:
    with st.container(border=True):
        st.subheader(f":blue[{ui.BRAND}]", anchor=False)
        st.markdown(f"**{ui.BRAND_LINE}.**")
        st.markdown(
            "Practical AI tools built by a CBSE teacher, for teachers – saving time on routine work while "
            "keeping every academic decision in the teacher's hands."
        )

st.subheader("How it works", anchor=False)
st.iframe(DIAGRAM, height=1400, alt="Animated architecture diagram of Preboard Generator")
