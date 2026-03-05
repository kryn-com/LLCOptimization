import streamlit as st
import pandas as pd
import streamlit.components.v1 as components

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
    tso_line_8r,
    nc_tax_rate=0.0425
):
    # --- 1. REVERSE ENGINEER THE CLEAN SLATE ---
    clean_agi = tso_current_agi - tso_line_8r
    clean_state_taxable = max(0, tso_state_taxable - tso_line_8r)

    # --- 2. CONSTANTS ---
    FED_STD_DEDUCTION = 15750 
    NC_STD_DEDUCTION = 12750 
    FED_BRACKETS = [(11925, 0.10), (48475, 0.12), (103350, 0.22), (float('inf'), 0.24)]

    total_qee = box_1_tuition + additional_qee

    # --- 3. CALIBRATION ---
    if clean_state_taxable > 0:
        state_adjustment_factor = clean_state_taxable - (clean_agi - NC_STD_DEDUCTION)
    else:
        state_adjustment_factor = 0

    # --- 4. CALCULATION ENGINE (WITH ROUNDING) ---
    def calculate_scenario(inclusion_amount):
        if inclusion_amount > box_5_scholarship:
            inclusion_amount = box_5_scholarship

        new_agi = clean_agi + inclusion_amount
        
        fed_taxable = round(max(0, new_agi - FED_STD_DEDUCTION))
        fed_tax = 0
        remaining = fed_taxable
        prev_limit = 0
        for limit, rate in FED_BRACKETS:
            bracket_amt = min(remaining, limit - prev_limit)
            fed_tax += bracket_amt * rate
            remaining -= bracket_amt
            prev_limit = limit
            if remaining <= 0: break
                
        fed_tax = round(fed_tax)
        
        nc_taxable_calc = new_agi - NC_STD_DEDUCTION + state_adjustment_factor
