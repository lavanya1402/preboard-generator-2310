"""Preboard Generator – Streamlit app (a Lavanya AI Consultancy initiative).

Run locally:  .venv\\Scripts\\python.exe -m streamlit run app.py
"""
import hmac

import streamlit as st

import storage
import ui

st.set_page_config(page_title=f"{ui.APP_NAME} · {ui.BRAND}", page_icon=ui.FAVICON, layout="wide")

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False


def login_screen():
    password = storage.get_setting("APP_PASSWORD")
    _, middle, _ = st.columns([1, 1.4, 1])
    with middle:
        st.space("large")
        with st.container(border=True, horizontal_alignment="center"):
            st.image(ui.LOGO, width=180)
            st.markdown(f"**{ui.BRAND}**")
            st.caption(ui.BRAND_LINE)
            st.title(ui.APP_NAME, anchor=False)
            st.markdown("CBSE Class 10 Science · Biology")
            if not password:
                st.error("No password is set. Add `APP_PASSWORD=...` to the `.env` file "
                         "(or to Streamlit Secrets on the cloud) and restart the app.", title="App password missing")
                st.stop()
            with st.form("login", border=False):
                typed = st.text_input("Password", type="password")
                if st.form_submit_button("Enter", type="primary", icon=":material/login:", width="stretch"):
                    if hmac.compare_digest(typed.encode(), password.encode()):
                        st.session_state.authenticated = True
                        st.rerun()
                    st.error("Wrong password. Please try again.")
            st.caption("AI drafts. The teacher decides.")


if not st.session_state.authenticated:
    login_screen()
    st.stop()

ui.sidebar_brand()
pending = sum(q.get("status") == "pending" for q in ui.all_questions())
review_title = f"Teacher review :red-badge[{pending}]" if pending else "Teacher review"

page = st.navigation([
    st.Page("app_pages/generate.py", title="Generate paper", icon=":material/description:", default=True),
    st.Page("app_pages/review.py", title=review_title, icon=":material/rate_review:"),
    st.Page("app_pages/bank.py", title="Question bank", icon=":material/library_books:"),
    st.Page("app_pages/about.py", title="About", icon=":material/info:"),
])

with st.sidebar:
    st.space("medium")
    if st.button("Log out", icon=":material/logout:"):
        st.session_state.clear()
        st.rerun()

page.run()
ui.footer()
