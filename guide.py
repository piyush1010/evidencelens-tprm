"""A short, plain-language guide for first-time visitors."""

import streamlit as st

STEPS = [
    ("What is EvidenceLens?",
     "Companies have to check that their suppliers (vendors) keep data safe. That usually means "
     "reading long security policies by hand. EvidenceLens reads the policy for you and answers "
     "each security question with the exact sentence it found as proof."),
    ("Start in one click",
     "Pick a sample policy below and press **Run selected sample**. You don't need an account or an API key. "
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

# What the animated hand points at on each step (CSS selectors; None = no target).
TAB = '[data-baseweb="tab-list"] [data-baseweb="tab"]:nth-of-type({})'
TARGETS = [
    None,
    '.st-key-landing-run-sample button, [data-testid="stSidebar"] [data-testid="stFileUploader"]',
    TAB.format(1),
    TAB.format(2),
    TAB.format(3),
    TAB.format(4) + ", " + TAB.format(5),
]
TAB_STEPS = {2, 3, 4, 5}

HAND_CSS = """
<style>
@keyframes el-nudge {{ 0%, 100% {{ transform: translateX(0); }} 50% {{ transform: translateX(-8px); }} }}
@keyframes el-glow {{ 0%, 100% {{ box-shadow: 0 0 0 0 rgba(245, 158, 11, 0.55); }}
                      50% {{ box-shadow: 0 0 0 6px rgba(245, 158, 11, 0); }} }}
@keyframes el-wave {{ 0%, 60%, 100% {{ transform: rotate(0); }} 15%, 45% {{ transform: rotate(16deg); }}
                      30% {{ transform: rotate(-8deg); }} }}
{targets} {{ background-color: rgba(245, 158, 11, 0.16) !important; border-radius: 8px;
             animation: el-glow 1.6s ease-out infinite; }}
{targets_after} {{ content: "👈"; display: inline-block; margin-left: 8px; font-size: 1.3em;
                   animation: el-nudge 1s ease-in-out infinite; }}
.el-wave {{ display: inline-block; transform-origin: 70% 70%; animation: el-wave 2s ease-in-out infinite; }}
@media (prefers-reduced-motion: reduce) {{ .el-wave, {targets}, {targets_after} {{ animation: none !important; }} }}
</style>
"""

CARD_CSS = """
<style>
@keyframes el-slide {{ from {{ opacity: 0; transform: translateY(24px); }} to {{ opacity: 1; transform: none; }} }}
.st-key-guide-card {{
  position: fixed; right: 24px; bottom: 24px; z-index: 1000;
  width: min(400px, calc(100vw - 32px)); max-height: calc(100vh - 120px); overflow-y: auto;
  background: {bg}; color: {fg}; padding: 16px 18px; border-radius: 14px;
  border: 1px solid {border}; box-shadow: 0 12px 32px rgba(0, 0, 0, {shadow});
  animation: el-slide 0.35s ease-out;
}}
@media (max-width: 640px) {{ .st-key-guide-card {{ right: 16px; bottom: 16px; }} }}
@media (prefers-reduced-motion: reduce) {{ .st-key-guide-card {{ animation: none; }} }}
</style>
"""


def _theme_is_dark() -> bool:
    try:
        return st.context.theme.type == "dark"
    except Exception:
        return False


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


def _point_hand(step: int) -> None:
    """Highlight the element this step talks about and point an animated hand at it."""
    target = TARGETS[step]
    selectors = [part.strip() for part in target.split(",")] if target else [".el-none"]
    st.markdown(HAND_CSS.format(
        targets=", ".join(selectors),
        targets_after=", ".join(sel + "::after" for sel in selectors),
    ), unsafe_allow_html=True)


def render_guide(has_results: bool = False) -> None:
    """Show the step-by-step guide on a first visit, with a sidebar button to reopen it."""
    if "guide_step" not in st.session_state:
        st.session_state.guide_step = 0  # first visit: open the guide
    if st.sidebar.button("📘 How this app works", width="stretch"):
        st.session_state.guide_step = 0

    step = st.session_state.guide_step
    if step is None:
        return
    title, text = STEPS[step]
    _point_hand(step)
    dark = _theme_is_dark()
    st.markdown(CARD_CSS.format(
        bg="#1f2430" if dark else "#ffffff", fg="#f3f4f6" if dark else "#1f2937",
        border="#3a4150" if dark else "#e5e7eb", shadow="0.5" if dark else "0.18",
    ), unsafe_allow_html=True)
    with st.container(key="guide-card"):
        st.caption(f"Quick guide · step {step + 1} of {len(STEPS)}")
        hand = '<span class="el-wave">👋</span> ' if step == 0 else "👉 "
        st.markdown(f"{hand}**{title}**", unsafe_allow_html=True)
        st.markdown(text)
        if step in TAB_STEPS and not has_results:
            st.info("Run a sample first. The hand will then point to this tab.")
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
