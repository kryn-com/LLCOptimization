import math
import streamlit as st
import streamlit.components.v1 as components

from llc_engine import (STATES, DEFAULT_STATE, optimize_scholarship, prepare_baseline, rate_summary)
from llc_report import (process_rows, rows_to_html, gain_breakdown, gain_html, entry_steps, tie_out,
                        client_explanation, plain_text_report, html_report, money, NY_NOTICE)

st.set_page_config(page_title="Lifetime Learning Credit Optimizer", layout="wide")

st.markdown("""
<style>
.stNumberInput label p { font-size: 1.15rem !important; font-weight: 600 !important; }
.stNumberInput input { font-size: 1.15rem !important; padding-left: 28px !important; }
div[data-testid="stNumberInputContainer"]::before {
    content: "$"; position: absolute; left: 10px; top: 50%; transform: translateY(-50%);
    color: #888; font-size: 1.15rem; z-index: 1;
}
button[aria-label="Step up"], button[aria-label="Step down"], button[aria-label="Clear input"] { display: none !important; }
div[data-testid="stNumberInputContainer"] { padding-right: 0px !important; }
input[type="number"]::-webkit-inner-spin-button, input[type="number"]::-webkit-outer-spin-button { -webkit-appearance: none; margin: 0; }
input[type="number"] { -moz-appearance: textfield; }
.ui-math-table { width: 100%; border-collapse: collapse; margin-bottom: 1rem; }
.ui-math-table th, .ui-math-table td { border: 1px solid #555; padding: 8px 12px; text-align: right; }
.ui-math-table td:first-child, .ui-math-table th:first-child { text-align: left; width: 62%; }
.fake-header { font-size: 1.5rem; font-weight: 600; margin-top: 1.5rem; margin-bottom: 1rem; }
.col-title { font-size: 1.25rem; font-weight: 700; margin-bottom: 0.5rem; }
.gain-banner { font-size: 1.4rem; font-weight: 700; padding: 12px 16px; border-radius: 8px;
               background-color: rgba(40,167,69,0.15); margin: 8px 0 16px 0; }
</style>
""", unsafe_allow_html=True)


def rnd(x):
    return int(math.floor(x + 0.5)) if x else 0


def field(col, title, subtitle, key, height="3.5rem"):
    with col:
        st.markdown(f"<div style='height:{height};'><b>{title}</b><br>"
                    f"<span style='font-size:0.9em;font-weight:normal;'><i>{subtitle}</i></span></div>",
                    unsafe_allow_html=True)
        return st.number_input(key, min_value=0.0, value=0.0, step=1.0, format="%.0f", key=key,
                               label_visibility="collapsed")


st.title("🎓 Lifetime Learning Credit Optimizer")

with st.sidebar:
    st.header("Settings")
    year = st.selectbox("Tax Year", [2026, 2025], index=0)
    state = st.selectbox("State", list(STATES.keys()), index=list(STATES.keys()).index(DEFAULT_STATE),
                         format_func=lambda k: f"{k} - {STATES[k]['name']}")
    st.caption("Filing status: Single")
    st.caption(rate_summary(state, year))

if state == "NY":
    st.warning(f"**{NY_NOTICE}**")

st.markdown("<div class='fake-header'>1. Education Documents</div>", unsafe_allow_html=True)
c1, c2, c3, c4 = st.columns(4)
box_1_in = field(c1, "1098-T Box 1", "(Tuition Paid)", "box_1")
box_5_in = field(c2, "1098-T Box 5", "(Total Scholarship)", "box_5")
addl_qee_in = field(c3, "Other Qualified Expenses", "(Books, Supplies, etc.)", "addl_qee")
ext_funding_in = field(c4, "External Funding", "(Taxable, NOT on 1098-T)", "ext_funding")

st.markdown("<div class='fake-header'>2. TaxSlayer Current Status</div>", unsafe_allow_html=True)
entry_method = st.radio("Data Entry Status",
                        ["Pre-Entry: Education data NOT yet in TaxSlayer",
                         "Post-Entry: Education data ALREADY in TaxSlayer"], horizontal=False)
post = "Post-Entry" in entry_method

c5, c6, c7, c8 = st.columns(4)
agi_in = field(c5, "Federal AGI", "(Form 1040, Line 11a)", "agi", "4.5rem")
state_taxable_in = field(c6, "State Taxable Income", f"({STATES[state]['taxable_label']})", "state_taxable", "4.5rem")
if post:
    line_8r_in = field(c7, "Taxable Scholarship (Sch 1 Line 8r)", "*Includes 1098-T + Funding*", "line_8r", "4.5rem")
else:
    with c7:
        st.markdown("<div style='height:4.5rem;color:#888;'><b>Taxable Scholarship</b><br>"
                    "<span style='font-size:0.85em;'><i>(Hidden in Pre-Entry Mode)</i></span></div>",
                    unsafe_allow_html=True)
    line_8r_in = 0.0
sched_1a_in = field(c8, "Schedule 1-A Deductions", "(Tips, overtime, etc. - optional)", "sched_1a", "4.5rem")

if st.button("Calculate Optimization", type="primary"):
    box_1, box_5, addl_qee = rnd(box_1_in), rnd(box_5_in), rnd(addl_qee_in)
    ext_funding, agi, state_taxable, line_8r = rnd(ext_funding_in), rnd(agi_in), rnd(state_taxable_in), rnd(line_8r_in)
    sched_1a = rnd(sched_1a_in)

    if box_1 == 0 and box_5 == 0:
        st.warning("Please enter the 1098-T information to begin.")
        st.stop()

    base_agi, base_state, actual_8r = prepare_baseline("post" if post else "pre", agi, state_taxable,
                                                      ext_funding, line_8r, year, state)
    baseline, optimized = optimize_scholarship(box_1, addl_qee, box_5, base_agi, base_state, actual_8r,
                                               year, state, sched_1a)
    g = gain_breakdown(baseline, optimized)
    savings = g["net_gain"]

    st.divider()
    left_rows = process_rows(baseline, box_1, addl_qee, box_5, ext_funding, state, year)
    right_rows = process_rows(optimized, box_1, addl_qee, box_5, ext_funding, state, year)

    if savings > 5:
        st.markdown(f"<div class='gain-banner'>💰 Net gain to the taxpayer: {money(savings)}</div>", unsafe_allow_html=True)
    else:
        st.info("✅ **No optimization available.** Standard TaxSlayer processing is already the best outcome for this taxpayer.")

    st.markdown("<h3 style='margin-top:0;'>📊 Side-by-Side Processing</h3>", unsafe_allow_html=True)
    L, R = st.columns(2)
    with L:
        st.markdown("<div class='col-title'>Standard TaxSlayer processing</div>", unsafe_allow_html=True)
        st.markdown(rows_to_html(left_rows), unsafe_allow_html=True)
        st.caption(baseline["limit_reason"])
    with R:
        st.markdown("<div class='col-title'>Optimized processing</div>", unsafe_allow_html=True)
        st.markdown(rows_to_html(right_rows), unsafe_allow_html=True)
        st.caption(optimized["limit_reason"])

    if savings > 5:
        st.markdown("<h3>💰 How the Net Gain Adds Up</h3>", unsafe_allow_html=True)
        st.markdown(gain_html(g), unsafe_allow_html=True)

        a, b = st.columns(2)
        with a:
            st.markdown("<h3 style='margin-top:0;'>🛠️ TaxSlayer Entries</h3>", unsafe_allow_html=True)
            st.code("\n".join(entry_steps(optimized, box_1, addl_qee, ext_funding, state, year)), language=None)
            st.markdown("**Tie-out: after entering, TaxSlayer should show**")
            tie_html = "".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in tie_out(optimized, state))
            st.markdown(f"<table class='ui-math-table'>{tie_html}</table>", unsafe_allow_html=True)
        with b:
            st.markdown(f"<h3 style='margin-top:0;'>🗣️ Explanation for the Client - {STATES[state]['name']}</h3>",
                        unsafe_allow_html=True)
            st.markdown(f"<div style='font-size:1.05em;line-height:1.5;'>"
                        f"{client_explanation(baseline, optimized, g, box_5, state, year)}</div>", unsafe_allow_html=True)

        st.divider()
        d1, d2 = st.columns(2)
        with d1:
            st.download_button("📥 Download Printable Client Report",
                               data=html_report(baseline, optimized, g, box_1, addl_qee, box_5, ext_funding, state, year),
                               file_name=f"LLC_Optimization_{state}_{year}.html", mime="text/html")
        with d2:
            st.download_button("📋 Download TaxSlayer Entry Sheet (text)",
                               data=plain_text_report(baseline, optimized, g, box_1, addl_qee, box_5, ext_funding, state, year),
                               file_name=f"LLC_TaxSlayer_Entries_{state}_{year}.txt", mime="text/plain")

if "first_load" not in st.session_state:
    st.session_state.first_load = True
    components.html("""
        <script>
            let attempts = 0;
            let t = setInterval(function() {
                const inputs = window.parent.document.querySelectorAll('input[type="number"]');
                if (inputs.length > 0) { inputs[0].focus(); inputs[0].select(); clearInterval(t); }
                if (++attempts > 20) clearInterval(t);
            }, 100);
        </script>""", height=0)
