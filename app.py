import streamlit as st
import pandas as pd
import streamlit.components.v1 as components
import math

# --- CUSTOM CSS FOR UI STYLING & DARK MODE SUPPORT ---
st.markdown("""
<style>
/* Increase font sizes for labels and inputs */
.stNumberInput label p { 
    font-size: 1.15rem !important; 
    font-weight: 600 !important; 
}
.stNumberInput input { 
    font-size: 1.15rem !important; 
    padding-left: 28px !important; 
}

/* CSS Hack to inject a dollar sign inside the input boxes */
div[data-testid="stNumberInputContainer"]::before {
    content: "$";
    position: absolute;
    left: 10px;
    top: 50%;
    transform: translateY(-50%);
    color: #888;
    font-size: 1.15rem;
    z-index: 1;
}

/* Keep sidebar slider clean of the dollar sign */
div[data-testid="stSlider"] div[data-testid="stNumberInputContainer"]::before {
    content: "";
}

/* SLEDGEHAMMER: Hide Streamlit's default Step (+/-) and Clear (x) buttons */
button[aria-label="Step up"], 
button[aria-label="Step down"], 
button[aria-label="Clear input"] {
    display: none !important;
}

/* Remove the empty space the buttons leave behind */
div[data-testid="stNumberInputContainer"] {
    padding-right: 0px !important;
}

/* Custom UI Table Styling */
.ui-math-table {
    width: 100%;
    max-width: 700px;
    border-collapse: collapse;
    margin-bottom: 1rem;
}
.ui-math-table th, .ui-math-table td {
    border: 1px solid #555;
    padding: 8px 12px;
    text-align: right;
}
.ui-math-table th:first-child, .ui-math-table td:first-child {
    text-align: left;
    font-weight: bold;
    width: 50%;
}
.ui-math-table .total-row {
    background-color: rgba(128, 128, 128, 0.1);
}

/* Fake Header Styling (To prevent anchor link generation) */
.fake-header {
    font-size: 1.5rem;
    font-weight: 600;
    margin-top: 1.5rem;
    margin-bottom: 1rem;
}
</style>
""", unsafe_allow_html=True)

def optimize_scholarship(
    box_1_tuition,
    additional_qee,
    box_5_scholarship,
    tso_current_agi,
    tso_state_taxable,
    actual_1098t_8r,
    nc_tax_rate=0.0425
):
    # --- 1. REVERSE ENGINEER THE CLEAN SLATE ---
    clean_agi = tso_current_agi - actual_1098t_8r
    clean_state_taxable = max(0, tso_state_taxable - actual_1098t_8r)

    # --- 2. CONSTANTS ---
    FED_STD_DEDUCTION = 15750 
    NC_STD_DEDUCTION = 12750 
    
    total_qee = box_1_tuition + additional_qee

    # --- 3. CALIBRATION ---
    if clean_state_taxable > 0:
        state_adjustment_factor = clean_state_taxable - (clean_agi - NC_STD_DEDUCTION)
    else:
        state_adjustment_factor = 0

    # --- 4. CALCULATION ENGINE (WITH IRS $50 BUCKETING) ---
    def irs_round(val):
        """Forces traditional 'round half up' to match IRS rules and defeat Banker's Rounding."""
        return int(math.floor(val + 0.5))

    def calculate_scenario(inclusion_amount):
        if inclusion_amount > box_5_scholarship:
            inclusion_amount = box_5_scholarship

        new_agi = clean_agi + inclusion_amount
        fed_taxable = irs_round(max(0, new_agi - FED_STD_DEDUCTION))
        
        # IRS $50 Table Logic
        if fed_taxable <= 0:
            fed_tax = 0
        else:
            if fed_taxable < 100000:
                bucket_floor = math.floor(fed_taxable / 50) * 50
                midpoint = bucket_floor + 25
                ti_to_use = midpoint
            else:
                ti_to_use = fed_taxable
                
            # 2025 Single Bracket Rates applied to midpoint
            if ti_to_use <= 11925:
                tax_raw = ti_to_use * 0.10
            elif ti_to_use <= 48475:
                tax_raw = 11925 * 0.10 + (ti_to_use - 11925) * 0.12
            elif ti_to_use <= 103350:
                tax_raw = 11925 * 0.10 + (48475 - 11925) * 0.12 + (ti_to_use - 48475) * 0.22
            else:
                tax_raw = 11925 * 0.10 + (48475 - 11925) * 0.12 + (103350 - 48475) * 0.22 + (ti_to_use - 103350) * 0.24
                
            fed_tax = irs_round(tax_raw)
        
        nc_taxable_calc = new_agi - NC_STD_DEDUCTION + state_adjustment_factor
        nc_taxable = irs_round(max(0, nc_taxable_calc))
        nc_tax = irs_round(nc_taxable * nc_tax_rate)
        
        tax_free_scholarship = max(0, box_5_scholarship - inclusion_amount)
        qualified_expenses = max(0, total_qee - tax_free_scholarship)
        
        potential_credit = qualified_expenses * 0.20
        potential_credit = min(2000, potential_credit)
        usable_credit = irs_round(min(potential_credit, fed_tax))
        
        net_position = usable_credit - (fed_tax + nc_tax)
        tax_burden = (fed_tax + nc_tax) - usable_credit

        return {
            "inclusion": inclusion_amount,
            "net_position": net_position,
            "tax_burden": tax_burden,
            "fed_tax": fed_tax,
            "nc_tax": nc_tax,
            "credit": usable_credit,
            "agi": new_agi,
            "fed_taxable": fed_taxable, 
            "nc_taxable": nc_taxable,
            "ts_box_5_entry": tax_free_scholarship,
            "expenses_to_claim": qualified_expenses
        }

    # --- 5. CALCULATE THE SCENARIOS (DOLLAR-BY-DOLLAR TO HIT THE SAWTOOTH) ---
    min_inclusion = max(0, box_5_scholarship - total_qee)
    baseline = calculate_scenario(min_inclusion)

    optimized = baseline
    
    # SAFETY VALVE: Cap the max inclusion shift to $10,000 above the baseline
    max_inclusion = min(int(box_5_scholarship), int(min_inclusion) + 10000)
    
    # Iterate exactly dollar-by-dollar up to the hard cap
    for inc in range(int(min_inclusion), max_inclusion + 1):
        res = calculate_scenario(inc)
        # Using strict > ensures we capture the LOWEST scholarship amount that achieves the maximum savings
        if res['net_position'] > optimized['net_position']:
            optimized = res

    return baseline, optimized

# --- STREAMLIT UI ---
st.set_page_config(page_title="Lifetime Learning Credit Optimizer", layout="wide")
st.title("🎓 Lifetime Learning Credit Optimizer")

with st.sidebar:
    st.header("Settings")
    nc_rate = st.slider("State Tax Rate (%)", min_value=0.0, max_value=7.0, value=4.25, step=0.01) / 100

st.markdown("<div class='fake-header'>1. Education Documents</div>", unsafe_allow_html=True)

# Using Fixed-Height Divs to Guarantee Vertical Alignment
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown("<div style='height: 3.5rem;'><b>1098-T Box 1</b><br><span style='font-size:0.9em; font-weight:normal;'><i>(Tuition Paid)</i></span></div>", unsafe_allow_html=True)
    box_1_in = st.number_input("box_1", min_value=0.0, value=0.0, step=100.0, format="%.0f", label_visibility="collapsed")
with col2:
    st.markdown("<div style='height: 3.5rem;'><b>1098-T Box 5</b><br><span style='font-size:0.9em; font-weight:normal;'><i>(Total Scholarship)</i></span></div>", unsafe_allow_html=True)
    box_5_in = st.number_input("box_5", min_value=0.0, value=0.0, step=100.0, format="%.0f", label_visibility="collapsed")
with col3:
    st.markdown("<div style='height: 3.5rem;'><b>Other Qualified Expenses</b><br><span style='font-size:0.9em; font-weight:normal;'><i>(Books, Supplies, etc.)</i></span></div>", unsafe_allow_html=True)
    addl_qee_in = st.number_input("addl_qee", min_value=0.0, value=0.0, step=100.0, format="%.0f", label_visibility="collapsed")
with col4:
    st.markdown("<div style='height: 3.5rem;'><b>External Stipends</b><br><span style='font-size:0.9em; font-weight:normal;'><i>(Taxable, NOT on 1098-T)</i></span></div>", unsafe_allow_html=True)
    ext_stipend_in = st.number_input("ext_stipend", min_value=0.0, value=0.0, step=100.0, format="%.0f", label_visibility="collapsed")

st.markdown("<div class='fake-header'>2. TaxSlayer Current Status</div>", unsafe_allow_html=True)

# ADDED: The Workflow Toggle
entry_method = st.radio(
    "How are you entering the data?",
    ["Clean Slate (I have NOT entered the 1098-T or Stipend into TaxSlayer yet)", 
     "Reverse Engineer (TaxSlayer has already processed the 1098-T and Stipend)"],
    horizontal=False
)

col5, col6, col7, col8 = st.columns(4)
with col5:
    st.markdown("<div style='height: 4.5rem;'><b>Federal AGI</b><br><span style='font-size:0.9em; font-weight:normal;'><i>(Form 1040, Line 11)</i></span></div>", unsafe_allow_html=True)
    agi_in = st.number_input("agi", min_value=0.0, value=0.0, step=100.0, format="%.0f", label_visibility="collapsed")
with col6:
    st.markdown("<div style='height: 4.5rem;'><b>State Taxable Income</b><br><span style='font-size:0.9em; font-weight:normal;'><i>(NC D-400, Line 14)</i></span></div>", unsafe_allow_html=True)
    nc_taxable_in = st.number_input("nc_taxable", min_value=0.0, value=0.0, step=100.0, format="%.0f", label_visibility="collapsed")
with col7:
    if "Reverse Engineer" in entry_method:
        st.markdown("<div style='height: 4.5rem;'><b>Taxable Scholarship</b> <i>(Sch 1 Line 8r)</i><br><span style='font-size:0.85em; font-weight:normal;'><i>*Includes 1098-T + Stipends*</i></span></div>", unsafe_allow_html=True)
        line_8r_in = st.number_input("line_8r", min_value=0.0, value=0.0, step=100.0, format="%.0f", label_visibility="collapsed")
    else:
        st.markdown("<div style='height: 4.5rem; color:#888;'><b>Taxable Scholarship</b><br><span style='font-size:0.85em; font-weight:normal;'><i>(Hidden in Clean Slate Mode)</i></span></div>", unsafe_allow_html=True)
        line_8r_in = 0.0
with col8:
    st.empty()

if st.button("Calculate Optimization", type="primary"):
    
    # Properly round any decimals to the nearest whole dollar
    box_1 = int(math.floor(box_1_in + 0.5)) if box_1_in else 0
    box_5 = int(math.floor(box_5_in + 0.5)) if box_5_in else 0
    addl_qee = int(math.floor(addl_qee_in + 0.5)) if addl_qee_in else 0
    ext_stipend = int(math.floor(ext_stipend_in + 0.5)) if ext_stipend_in else 0
    agi = int(math.floor(agi_in + 0.5)) if agi_in else 0
    nc_taxable = int(math.floor(nc_taxable_in + 0.5)) if nc_taxable_in else 0
    line_8r = int(math.floor(line_8r_in + 0.5)) if line_8r_in else 0
    
    # --- WORKFLOW TOGGLE LOGIC ---
    if "Clean Slate" in entry_method:
        # Stipend is NOT in TaxSlayer yet. We must add it to construct the true baseline.
        base_agi_to_pass = agi + ext_stipend
        
        # We must recalculate State Taxable to account for any "unused" standard deduction
        # if their baseline W-2 AGI was below the $12,750 NC threshold.
        NC_STD_DED = 12750
        
        # Find any custom state adjustments (like additions/subtractions) the user already entered
        if nc_taxable > 0:
            implied_state_adj = nc_taxable - (agi - NC_STD_DED)
        else:
            implied_state_adj = 0 # Assume 0 if floored, which is standard for grad students
            
        # Mathematically rebuild the true state taxable floor
        base_nc_to_pass = max(0, base_agi_to_pass - NC_STD_DED + implied_state_adj)
        actual_1098t_8r = 0
        
    else:
        # Stipend IS already in TaxSlayer. We pass the AGI as-is and let the engine strip the 1098-T.
        base_agi_to_pass = agi
        base_nc_to_pass = nc_taxable
        actual_1098t_8r = max(0, line_8r - ext_stipend)
    
    if box_1 == 0 and box_5 == 0:
        st.warning("Please enter the 1098-T information to begin.")
    else:
        baseline, optimized = optimize_scholarship(
            box_1, addl_qee, box_5, base_agi_to_pass, base_nc_to_pass, actual_1098t_8r, nc_rate
        )
        
        savings = baseline['tax_burden'] - optimized['tax_burden']
        total_qee = box_1 + addl_qee
        
        st.divider()
        
        if savings > 5:
            st.success(f"### 💰 Optimization Successful! You saved the client **${savings:,.0f}**")
            
            c1, c2 = st.columns(2)
            
            with c1:
                st.markdown("<h3 style='margin-top:0;'>🛠️ TaxSlayer Instructions</h3>", unsafe_allow_html=True)
                
                # Recombine the optimized 1098-T amount with the external stipend for the final TaxSlayer entry
                final_ts_entry = optimized['inclusion'] + ext_stipend
                stipend_note = f"(This combines the ${ext_stipend:,.0f} stipend with the ${optimized['inclusion']:,.0f} 1098-T shift)" if ext_stipend > 0 else "(Overwrite any number TaxSlayer may have already put here)"
                
                instructions = (
                    "**Step 1: Enter the Taxable Income**\n"
                    "* Go to `Federal Section > Income > Other Income > Other Compensation > Scholarships and Grants`\n"
                    f"* Enter exactly: **${final_ts_entry:,.0f}**\n"
                    f"  <i>{stipend_note}</i>\n\n"
                    "**Step 2: Enter the Education Credit**\n"
                    "* Go to `Federal Section > Deductions > Credits > Education Credits`\n"
                    "* On the 1098-T entry screen, enter these exact values:\n"
                    f"* **Tuition Paid:** **${box_1:,.0f}**\n"
                    f"* **Grants and Scholarships:** **${optimized['ts_box_5_entry']:,.0f}** *(This is the Tax-Free portion that remains)*\n"
                    f"* **Other Qualified Expenses:** **${addl_qee:,.0f}**\n"
                )
                st.markdown(instructions, unsafe_allow_html=True)
                
            with c2:
                st.markdown("<h3 style='margin-top:0;'>🗣️ Explanation for the Client</h3>", unsafe_allow_html=True)
                
                added_income = optimized['inclusion'] - baseline['inclusion']
                added_tax = (optimized['fed_tax'] + optimized['nc_tax']) - (baseline['fed_tax'] + baseline['nc_tax'])
                
                client_text = (
                    f"<b>Standard Tax Software Outcome:</b><br>"
                    f"If we processed your education documents using standard default settings, your return would generate a Lifetime Learning Credit of ${baseline['credit']:,.0f} "
                    f"and a total net tax burden of ${baseline['tax_burden']:,.0f}.<br><br>"
                    f"<b>Tax-Aide Optimized Outcome:</b><br>"
                    f"We applied an advanced, IRS-approved optimization strategy to your return. By voluntarily electing to report an additional ${added_income:,.0f} "
                    f"of your scholarship as taxable income, we were able to unlock a larger Lifetime Learning Credit of ${optimized['credit']:,.0f}.<br><br>"
                    f"<b>The Result:</b><br>"
                    f"Even after accounting for the slightly higher base income tax, this strategy successfully lowered your overall tax bill to ${optimized['tax_burden']:,.0f}, "
                    f"putting a net profit of ${savings:,.0f} directly back in your pocket!"
                )
                
                st.markdown(f"<div style='font-size:1.05em; line-height:1.5;'>{client_text}</div>", unsafe_allow_html=True)

            st.divider()
            
            st.markdown("<h3 style='margin-top:0;'>📊 The Math Breakdown</h3>", unsafe_allow_html=True)
            
            base_credit_str = f"-${baseline['credit']:,.0f}" if baseline['credit'] > 0 else "$0"
            opt_credit_str = f"-${optimized['credit']:,.0f}" if optimized['credit'] > 0 else "$0"
            
            base_final_fed = max(0, baseline['fed_tax'] - baseline['credit'])
            opt_final_fed = max(0, optimized['fed_tax'] - optimized['credit'])
            
            ui_table = (
                '<table class="ui-math-table">'
                '<tr><th>Metric</th><th>Standard TaxSlayer Entry</th><th>After Optimization</th></tr>'
                f'<tr><td>Tax-Free 1098-T Scholarship</td><td>${baseline["ts_box_5_entry"]:,.0f}</td><td>${optimized["ts_box_5_entry"]:,.0f}</td></tr>'
                f'<tr><td>Taxable 1098-T Scholarship</td><td>${baseline["inclusion"]:,.0f}</td><td>${optimized["inclusion"]:,.0f}</td></tr>'
                f'<tr style="background-color: rgba(128, 128, 128, 0.05);"><td>TOTAL 1098-T SCHOLARSHIP</td><td>${box_5:,.0f}</td><td>${box_5:,.0f}</td></tr>'
                f'<tr><td>Federal AGI</td><td>${baseline["agi"]:,.0f}</td><td>${optimized["agi"]:,.0f}</td></tr>'
                f'<tr><td>Federal Tax</td><td>${baseline["fed_tax"]:,.0f}</td><td>${optimized["fed_tax"]:,.0f}</td></tr>'
                f'<tr><td>Lifetime Learning Credit</td><td>{base_credit_str}</td><td>{opt_credit_str}</td></tr>'
                f'<tr style="font-weight: bold; background-color: rgba(128, 128, 128, 0.05);"><td>Final Federal Tax</td><td>${base_final_fed:,.0f}</td><td>${opt_final_fed:,.0f}</td></tr>'
                f'<tr><td>State Taxable Income</td><td>${baseline["nc_taxable"]:,.0f}</td><td>${optimized["nc_taxable"]:,.0f}</td></tr>'
                f'<tr><td>State Tax</td><td>${baseline["nc_tax"]:,.0f}</td><td>${optimized["nc_tax"]:,.0f}</td></tr>'
                f'<tr class="total-row"><td>TOTAL NET TAX BURDEN</td><td>${baseline["tax_burden"]:,.0f}</td><td>${optimized["tax_burden"]:,.0f}</td></tr>'
                '</table>'
            )
            
            st.markdown(ui_table, unsafe_allow_html=True)
            st.markdown(f"<p style='font-size:1.1em; font-weight:bold; margin-top:10px;'>Optimization was successful and resulted in a ${savings:,.0f} net tax savings.</p>", unsafe_allow_html=True)
            
            # --- GENERATE PRINTABLE HTML REPORT ---
            html_report = (
                '<!DOCTYPE html>\n<html>\n<head>\n'
                '<meta charset="utf-8">\n<title>Lifetime Learning Credit Optimization Report</title>\n'
                '<style>\n'
                'body { font-family: Arial, sans-serif; line-height: 1.6; max-width: 800px; margin: 20px auto; color: #333; }\n'
                'h2 { color: #2c3e50; border-bottom: 2px solid #eee; padding-bottom: 10px; }\n'
                'h3 { color: #34495e; margin-top: 30px; }\n'
                '.client-box { padding: 5px 0; font-size: 1.05em; }\n'
                'table { width: 100%; max-width: 700px; border-collapse: collapse; margin: 20px 0; }\n'
                'th, td { border: 1px solid #ddd; padding: 10px 12px; text-align: right; }\n'
                'th:first-child, td:first-child { text-align: left; font-weight: bold; width: 50%; }\n'
                'th { background-color: #f4f6f8; }\n'
                '.summary { font-size: 1.1em; font-weight: bold; color: #155724; border-top: 2px solid #333; padding-top: 15px; margin-top: 20px; }\n'
                '@media print { body { margin: 0; } .no-print { display: none; } }\n'
                '</style>\n</head>\n<body>\n'
                '<h2>Tax-Aide Optimization Report</h2>\n'
                '<h3>Explanation</h3>\n'
                f'<div class="client-box">{client_text}</div>\n'
                '<h3>The Math Breakdown</h3>\n'
                '<table>\n'
                '<tr><th>Metric</th><th>Standard TaxSlayer Entry</th><th>After Optimization</th></tr>\n'
                f'<tr><td>Tax-Free 1098-T Scholarship</td><td>${baseline["ts_box_5_entry"]:,.0f}</td><td>${optimized["ts_box_5_entry"]:,.0f}</td></tr>\n'
                f'<tr><td>Taxable 1098-T Scholarship</td><td>${baseline["inclusion"]:,.0f}</td><td>${optimized["inclusion"]:,.0f}</td></tr>\n'
                f'<tr style="background-color:#fefefe"><td>TOTAL 1098-T SCHOLARSHIP</td><td>${box_5:,.0f}</td><td>${box_5:,.0f}</td></tr>\n'
                f'<tr><td>Federal AGI</td><td>${baseline["agi"]:,.0f}</td><td>${optimized["agi"]:,.0f}</td></tr>\n'
                f'<tr><td>Federal Tax</td><td>${baseline["fed_tax"]:,.0f}</td><td>${optimized["fed_tax"]:,.0f}</td></tr>\n'
                f'<tr><td>Lifetime Learning Credit</td><td>{base_credit_str}</td><td>{opt_credit_str}</td></tr>\n'
                f'<tr style="font-weight: bold; background-color:#fefefe"><td>Final Federal Tax</td><td>${base_final_fed:,.0f}</td><td>${opt_final_fed:,.0f}</td></tr>\n'
                f'<tr><td>State Taxable Income</td><td>${baseline["nc_taxable"]:,.0f}</td><td>${optimized["nc_taxable"]:,.0f}</td></tr>\n'
                f'<tr><td>State Tax</td><td>${baseline["nc_tax"]:,.0f}</td><td>${optimized["nc_tax"]:,.0f}</td></tr>\n'
                f'<tr style="background-color:#f4f6f8"><td>TOTAL NET TAX BURDEN</td><td>${baseline["tax_burden"]:,.0f}</td><td>${optimized["tax_burden"]:,.0f}</td></tr>\n'
                '</table>\n'
                f'<div class="summary">Optimization was successful and resulted in a ${savings:,.0f} net tax savings.</div>\n'
                '<p class="no-print" style="text-align:center; margin-top:30px; color:#666;">'
                '<em>Tip: Press <strong>Ctrl+P</strong> (or Cmd+P on Mac) to print this page or save it as a PDF.</em></p>\n'
                '</body>\n</html>'
            )
            
            st.divider()
            st.markdown("<h3 style='margin-top:0;'>📄 Export Documentation</h3>", unsafe_allow_html=True)
            st.download_button(
                label="📥 Download Printable Client Report",
                data=html_report,
                file_name="LLC_Optimization_Report.html",
                mime="text/html"
            )
            
        else:
            st.info("✅ **No Optimization Available.** Standard TaxSlayer reporting is already the best mathematical outcome for this client.")

# --- INVISIBLE JS TO AUTO-FOCUS FIRST INPUT BOX ON INITIAL LOAD ---
if 'first_load' not in st.session_state:
    st.session_state.first_load = True
    components.html("""
        <script>
            let attempts = 0;
            let focusInterval = setInterval(function() {
                const doc = window.parent.document;
                const inputs = doc.querySelectorAll('input[type="number"]');
                if (inputs.length > 0 && inputs[0]) {
                    inputs[0].focus();
                    inputs[0].select();
                    clearInterval(focusInterval);
                }
                attempts++;
                if (attempts > 20) clearInterval(focusInterval); // Stop trying after 2 seconds
            }, 100);
        </script>
    """, height=0)
