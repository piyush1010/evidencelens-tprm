"""A short, plain-language guide for first-time visitors."""

import streamlit as st

STEPS = [
    ("What is EvidenceLens?",
     "Companies have to check that their suppliers (vendors) keep data safe. That usually means "
     "reading long security policies by hand. EvidenceLens reads the policy for you and answers "
     "each security question with the exact sentence it found as proof."),
    ("Start in one click",
     "Pick a sample policy below and press **Run**. You don't need an account or an API key. "
     "To try your own document, upload it in the left panel and press **Run assessment**."),
    ("Vendor & risk",
     "Describe the vendor: what data they handle, how much you depend on them. EvidenceLens gives a "
     "starting risk level (Low, Medium, High or Critical) and shows which answers raised it. After the "
     "review, it suggests a final risk level, and a person approves or changes it."),
    ("Assessment",
     "Each security question gets an answer (**Yes**, **No** or **Insufficient evidence**), the quote "
     "it is based on, and how confident the tool is. If the document doesn't clearly say it, the "
     "answer is \"Insufficient evidence\" instead of a guess."),
    ("Review queue",
     "Anything unclear or low-confidence goes to a person. You can approve it, reject it or ask the "
     "vendor for more evidence. The AI never makes the final call."),
    ("Evaluation and Audit & export",
     "**Evaluation** shows how accurate the tool was on a labelled test set. **Audit & export** keeps "
     "a record of every decision and lets you download the results."),
]

TAB_HELP = {
    "vendor": "Who is the vendor, how risky are they to start with, and what is the final decision?",
    "assessment": "Every question with its answer, the quote used as proof, and the confidence.",
    "review": "Unclear answers waiting for a person to approve, reject or ask for more evidence.",
    "evaluation": "How accurate the tool was on a labelled test set, compared with simple keyword search.",
    "audit": "A record of every step and decision, ready to download.",
}

GLOSSARY = """
- **Vendor**: a supplier or service provider your company works with.
- **TPRM (third-party risk management)**: checking that vendors won't put your data or business at risk.
- **Evidence**: the exact sentence in the vendor's document that supports an answer.
- **Inherent risk**: how risky a vendor is *before* checking their security, based on what they do for you.
- **Residual risk**: the risk that *remains* after checking their evidence.
- **Human in the loop**: a person reviews and approves anything the AI isn't sure about.
"""


def render_guide() -> None:
    """Show the step-by-step guide on a first visit, with a sidebar button to reopen it."""
    if "guide_step" not in st.session_state:
        st.session_state.guide_step = 0  # first visit: open the guide
    if st.sidebar.button("📘 How this app works", width="stretch"):
        st.session_state.guide_step = 0

    step = st.session_state.guide_step
    if step is None:
        return
    title, text = STEPS[step]
    with st.container(border=True):
        st.caption(f"Quick guide · step {step + 1} of {len(STEPS)}")
        st.markdown(f"**{title}**")
        st.markdown(text)
        back, nxt, skip = st.columns([1, 1, 1])
        if back.button("← Back", disabled=step == 0, key="guide_back", width="stretch"):
            st.session_state.guide_step = step - 1
            st.rerun()
        last = step == len(STEPS) - 1
        if nxt.button("Finish" if last else "Next →", type="primary", key="guide_next", width="stretch"):
            st.session_state.guide_step = None if last else step + 1
            st.rerun()
        if skip.button("Skip guide", key="guide_skip", width="stretch"):
            st.session_state.guide_step = None
            st.rerun()
        with st.expander("Words used in this app"):
            st.markdown(GLOSSARY)
