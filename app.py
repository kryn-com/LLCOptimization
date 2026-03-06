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
    tso_line_8r,
    nc_tax_rate=0.0425
):
    # --- 1. REVERSE ENGINEER THE CLEAN SLATE ---
    clean_agi = tso_current_agi - tso_line_8r
    clean_state_taxable = max(0, tso_state_taxable - tso_line_8r)

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
    st.success("💡 **Workflow:** You can enter the clean baseline before touching the 1098-T, OR enter the current numbers after TaxSlayer has processed the 1098-T. The app handles both!")

st.markdown("<div class='fake-header'>1. Education Documents</div>", unsafe_allow_html=True)

# Using Fixed-Height Divs to Guarantee Vertical Alignment
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown("<div style='height: 3.5rem;'><b>1098-T Box 1</b><br><span
