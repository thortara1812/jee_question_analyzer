"""Student interface with explicit requests and optional local history."""
import sqlite3
import streamlit as st
from agentic_jee_system.history import clear, recent, save
from agentic_jee_system.reliability import ServiceError
from agentic_jee_system.workflow import run

st.set_page_config(page_title="Agentic JEE Assistant", page_icon="🎓", layout="wide")
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


with st.sidebar:
    mode = st.radio("Workflow", ["solve", "fact_check"], format_func=lambda x: "Question solving" if x == "solve" else "Fact checking")
    subject = st.selectbox("Subject", ["Auto", *SAMPLES])
    store = st.checkbox("Save requests on this computer", value=False,
                        help="Keeps up to 100 requests in .local/history.sqlite3. Off by default.")
    st.caption("External search requires TAVILY_API_KEY. Credentials are read from local environment configuration.")
    if st.button("Clear local history"):
        try:
            clear()
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
            result = run(question, mode, subject)
        st.session_state.result = result.model_dump(mode="json")
        if store:
            try:
                save(question, result)
            except (OSError, sqlite3.Error):
                st.warning("Result is available, but history could not be saved.")
    except (ValueError, ServiceError) as exc:
        st.error(str(exc))
    except Exception:
        st.error("The workflow could not complete. Check your installation and provider configuration, then retry.")

if st.session_state.get("result"):
    result = st.session_state.result
    st.caption(f"Workflow: {result['mode']} · Status: {result['status']}")
    st.markdown(result["markdown"])
    with st.expander("Computational tool use"):
        st.json(result["tool_calls"] or {"note": "No computational tool invocation recorded."})
    if result["evidence"]:
        with st.expander("Retrieved evidence"):
            for item in result["evidence"]:
                st.write(item["title"])
                st.link_button("Open source", item["url"])
                st.write(item["excerpt"])

with st.expander("Previous locally saved requests"):
    try:
        for item in recent():
            st.caption(item["created"] + " UTC")
            st.write(item["question"])
            st.markdown(item["result"]["markdown"])
    except (OSError, sqlite3.Error):
        st.info("Local history is unavailable.")
st.caption("Verification is an additional check, not a guarantee. Review answers against your textbook.")
