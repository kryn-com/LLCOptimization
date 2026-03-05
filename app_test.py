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
        nc_taxable = round(max(0, nc_taxable_calc))
        nc_tax = round(nc_taxable * nc_tax_rate)
        
        tax_free_scholarship = max(0, box_5_scholarship - inclusion_amount)
        qualified_expenses = max(0, total_qee - tax_free_scholarship)
        
        potential_credit = qualified_expenses * 0.20
        potential_credit = min(2000, potential_credit)
        usable_credit = round(min(potential_credit, fed_tax))
        
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
            "ts_box_5_entry": tax_free_scholarship,
            "expenses_to_claim": qualified_expenses
        }

    # --- 5. CALCULATE THE SCENARIOS ---
    min_inclusion = max(0, box_5_scholarship - total_qee)
    baseline = calculate_scenario(min_inclusion)

    coarse_step = 100
    coarse_steps = list(range(int(min_inclusion), int(box_5_scholarship), coarse_step))
    coarse_steps.append(box_5_scholarship)
    
    best_coarse = baseline
    for inc in coarse_steps:
        res = calculate_scenario(inc)
        if res['net_position'] > best_coarse['net_position']:
            best_coarse = res
            
    best_coarse_val = best_coarse['inclusion']
    start_fine = max(int(min_inclusion), int(best_coarse_val) - coarse_step)
    end_fine = min(int(box_5_scholarship), int(best_coarse_val) + coarse_step)
    
    optimized = best_coarse
    for inc in range(start_fine, end_fine + 1):
        res = calculate_scenario(inc)
        if res['net_position'] >= optimized['net_position']:
            optimized = res

    return baseline, optimized


# --- STREAMLIT UI ---
st.set_page_config(page_title="Lifetime Learning Credit Optimizer", layout="wide")
st.title("🎓 Lifetime Learning Credit Optimizer")

with st.sidebar:
    st.header("Settings")
    nc_rate = st.slider("State Tax Rate (%)", min_value=0.0, max_value=7.0, value=4.25, step=0.01) / 100
    st.success("💡 **Workflow:** You can enter the clean baseline before touching the 1098-T, OR enter the current numbers after TaxSlayer has processed the 1098-T. The app handles both!")

# Replaced Subheaders with "Fake" Headers (Divs) to permanently kill the anchor links
st.markdown("<div class='fake-header'>1. Education Documents</div>", unsafe_allow_html=True)

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown("**1098-T Box 1**<br><span style='font-size:0.9em; font-weight:normal;'>*(Tuition Paid)*</span>", unsafe_allow_html=True)
    box_1 = st.number_input("box_1", min_value=0, value=0, step=100, label_visibility="collapsed")
with col2:
    st.markdown("**1098-T Box 5**<br><span style='font-size:0.9em; font-weight:normal;'>*(Total Scholarship)*</span>", unsafe_allow_html=True)
    box_5 = st.number_input("box_5", min_value=0, value=0, step=100, label_visibility="collapsed")
with col3:
    st.markdown("**Other Qualified Expenses**<br><span style='font-size:0.9em; font-weight:normal;'>*(Books, Supplies, etc.)*</span>", unsafe_allow_html=True)
    addl_qee = st.number_input("addl_qee", min_value=0, value=0, step=100, label_visibility="collapsed")
with col4:
    st.empty()

st.markdown("<div class='fake-header'>2. TaxSlayer Current Status</div>", unsafe_allow_html=True)

col5, col6, col7, col8 = st.columns(4)
with col5:
    st.markdown("**Federal AGI**<br><span style='font-size:0.9em; font-weight:normal;'>*(Form 1040, Line 11)*</span><br>&nbsp;", unsafe_allow_html=True)
    agi = st.number_input("agi", min_value=0, value=0, step=100, label_visibility="collapsed")
with col6:
    st.markdown("**State Taxable Income**<br><span style='font-size:0.9em; font-weight:normal;'>*(NC D-400, Line 14)*</span><br>&nbsp;", unsafe_allow_html=True)
    nc_taxable = st.number_input("nc_taxable", min_value=0, value=0, step=100, label_visibility="collapsed")
with col7:
    st.markdown("**Taxable Scholarship** *(Line 8r)*<br><span style='font-size:0.85em; font-weight:normal;'>*Optional: Only if 1098-T entered to TaxSlayer*</span><br>&nbsp;", unsafe_allow_html=True)
    line_8r = st.number_input("line_8r", min_value=0, value=0, step=100, label_visibility="collapsed")
with col8:
    st.empty()

if st.button("Calculate Optimization", type="primary"):
    
    if box_1 == 0 and box_5 == 0:
        st.warning("Please enter the 1098-T information to begin.")
    else:
        baseline, optimized = optimize
