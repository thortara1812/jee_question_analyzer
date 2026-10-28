"""Student interface with explicit requests and optional local history."""
import sqlite3
import os
import streamlit as st
from dotenv import load_dotenv
from agentic_jee_system.history import clear, recent, save
from agentic_jee_system.reliability import ServiceError
from agentic_jee_system.workflow import compose, run
from agentic_jee_system.schemas import Result
from agentic_jee_system.presentation import student_text
from agentic_jee_system.api_client import run_remote

st.set_page_config(page_title="Agentic JEE Assistant", page_icon="🎓", layout="wide")
# Reading the secrets store promotes root-level Cloud secrets to environment
# variables before Settings or optional search reads them. Values are never shown.
try:
    st.secrets.to_dict()
except FileNotFoundError:
    pass
load_dotenv()
history_mode = os.getenv("JEE_HISTORY_MODE", "session").lower()
if history_mode not in {"session", "local"}:
    st.error("JEE_HISTORY_MODE must be session or local.")
    st.stop()
st.session_state.setdefault("request_history", [])
st.title("Agentic JEE Assistant")
st.caption("Analysis → solver with tools → independent verification → deterministic response")
SAMPLES = {
    "Mathematics": "Solve 2x + 5 = 15.",
    "Physics": "A 2 kg block starts from rest under an 8 N horizontal force on a frictionless surface for 5 seconds. Find its final kinetic energy.",
    "Chemistry": "Calculate the moles in 18 g of water. Molar mass is 18 g/mol.",
}


def use_sample(subject):
    st.session_state.question = SAMPLES[subject]
    st.session_state.pop("result", None)


def display_markdown(data):
    """Apply the current presentation to saved results without another model call."""
    result = Result.model_validate(data)
    if result.mode == "solve":
        if result.analysis and result.solution and result.verification:
            return compose(result.analysis, result.solution, result.verification)
        return student_text(result.markdown)
    return result.markdown


with st.sidebar:
    mode = st.radio("Workflow", ["solve", "fact_check"], format_func=lambda x: "Question solving" if x == "solve" else "Fact checking")
    subject = st.selectbox("Subject", ["Auto", *SAMPLES])
    store = st.checkbox("Save requests on this computer" if history_mode == "local" else "Keep history in this session", value=False,
                        help="Local mode uses SQLite; session mode is private to this browser session and resets on disconnect.")
    st.caption("Fact checking uses external evidence when search is configured.")
    if st.button("Clear local history" if history_mode == "local" else "Clear session history"):
        try:
            if history_mode == "local":
                clear()
            else:
                st.session_state.request_history = []
            st.success("History cleared.")
        except (OSError, sqlite3.Error):
            st.warning("Local history is unavailable.")

for column, name in zip(st.columns(3), SAMPLES):
    column.button(f"{name} example", on_click=use_sample, args=(name,), use_container_width=True)

with st.form("request"):
    question = st.text_area("Question or factual claim", key="question", height=180, max_chars=4000)
    submitted = st.form_submit_button("Run / retry", type="primary")

if submitted:
    st.session_state.pop("result", None)
    try:
        with st.spinner("Working through the selected workflow. Provider pacing may take a few minutes…"):
            result = (run_remote(question, mode, subject)
                      if os.getenv("JEE_API_URL", "").strip() else run(question, mode, subject))
        st.session_state.result = result.model_dump(mode="json")
        if store:
            try:
                if history_mode == "local":
                    save(question, result)
                else:
                    st.session_state.request_history.insert(0, {"question": question, "result": result.model_dump(mode="json")})
                    st.session_state.request_history = st.session_state.request_history[:20]
            except (OSError, sqlite3.Error):
                st.warning("Result is available, but history could not be saved.")
    except (ValueError, ServiceError) as exc:
        st.error(str(exc))
    except Exception:
        st.error("The workflow could not complete. Check your installation and provider configuration, then retry.")

if st.session_state.get("result"):
    result = st.session_state.result
    st.caption(f"Workflow: {result['mode']} · Status: {result['status']}")
    st.markdown(display_markdown(result))
    with st.expander("Computational tool use"):
        st.json(result["tool_calls"] or {"note": "No computational tool invocation recorded."})
    if result["evidence"]:
        with st.expander("Retrieved evidence"):
            for item in result["evidence"]:
                st.write(item["title"])
                st.link_button("Open source", item["url"])
                st.write(item["excerpt"])

with st.expander("Previous locally saved requests" if history_mode == "local" else "Previous requests in this session"):
    try:
        for item in (recent() if history_mode == "local" else st.session_state.request_history):
            if "created" in item:
                st.caption(item["created"] + " UTC")
            st.write(item["question"])
            st.markdown(display_markdown(item["result"]))
    except (OSError, sqlite3.Error):
        st.info("Local history is unavailable.")
st.caption("Verification is an additional check, not a guarantee. Review answers against your textbook.")
