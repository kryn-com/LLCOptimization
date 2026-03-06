import streamlit as st
import pandas as pd

def optimize_scholarship(
    box_1_tuition,
    box_5_scholarship,
    sch1_line_8r_current,
    form1040_line_11_agi,
    ncd400_line_14_taxable,
    nc_tax_rate=0.0425
):
    # --- 1. CONSTANTS ---
    FED_STD_DEDUCTION = 15750 
    NC_STD_DEDUCTION = 12750 
    FED_BRACKETS = [
        (11925, 0.10),
        (48475, 0.12),
        (103350, 0.22),
        (float('inf'), 0.24)
    ]

    # --- 2. CALIBRATION ---
    if ncd400_line_14_taxable > 0:
        state_adjustment_factor = ncd400_line_14_taxable - (form1040_line_11_agi - NC_STD_DEDUCTION)
    else:
        state_adjustment_factor = 0
        
    base_fed_income = form1040_line_11_agi - sch1_line_8r_current

    # --- 3. CALCULATION ENGINE ---
    def calculate_scenario(inclusion_amount):
        if inclusion_amount > box_5_scholarship:
            inclusion_amount = box_5_scholarship

        new_agi = base_fed_income + inclusion_amount
        
        fed_taxable = max(0, new_agi - FED_STD_DEDUCTION)
        fed_tax = 0
        remaining = fed_taxable
        prev_limit = 0
        for limit, rate in FED_BRACKETS:
            bracket_amt = min(remaining, limit - prev_limit)
            fed_tax += bracket_amt * rate
            remaining -= bracket_amt
            prev_limit = limit
            if remaining <= 0: break
                
        nc_taxable_calc = new_agi - NC_STD_DEDUCTION + state_adjustment_factor
        nc_taxable = max(0, nc_taxable_calc)
        nc_tax = nc_taxable * nc_tax_rate
        
        tax_free_scholarship = max(0, box_5_scholarship - inclusion_amount)
        qualified_expenses = max(0, box_1_tuition - tax_free_scholarship)
        potential_credit = min(2000, qualified_expenses * 0.20)
        usable_credit = min(potential_credit, fed_tax)
        
        net_position = usable_credit - (fed_tax + nc_tax)
        
        return {
            "inclusion": inclusion_amount,
            "net_position": net_position,
            "fed_tax": fed_tax,
            "nc_tax": nc_tax,
            "credit": usable_credit,
            "agi": new_agi,
            "expenses_to_claim": qualified_expenses
        }

   # --- 4. OPTIMIZATION LOOP ---
    
    # NEW FIX: The Hard Floor for Mandatory Excess
    # If scholarships exceed tuition, the excess MUST be taxable. 
    # The loop cannot test values below this minimum.
    min_inclusion = max(0, box_5_scholarship - box_1_tuition)
    
    # STAGE 1: Coarse Scan
    coarse_step = 100
    # START the range at min_inclusion instead of 0
    coarse_steps = list(range(int(min_inclusion), int(box_5_scholarship), coarse_step))
    coarse_steps.append(box_5_scholarship)
    
    # We must also ensure the current baseline doesn't crash if the preparer 
    # erroneously entered a number below the legal minimum.
    safe_baseline_inclusion = max(sch1_line_8r_current, min_inclusion)
    best_coarse = calculate_scenario(safe_baseline_inclusion)
    
    for inc in coarse_steps:
        res = calculate_scenario(inc)
        if res['net_position'] > best_coarse['net_position']:
            best_coarse = res
            
    # STAGE 2: Fine Tuning
    best_coarse_val = best_coarse['inclusion']
    # Ensure the fine-tuning window also respects the minimum floor
    start_fine = max(int(min_inclusion), int(best_coarse_val) - coarse_step)
    end_fine = min(int(box_5_scholarship), int(best_coarse_val) + coarse_step)
    
    best_final = best_coarse
    for inc in range(start_fine, end_fine + 1):
        res = calculate_scenario(inc)
        if res['net_position'] >= best_final['net_position']:
            best_final = res

    manual_result = calculate_scenario(sch1_line_8r_current)
    return manual_result, best_final

# --- STREAMLIT UI ---
st.set_page_config(page_title="Scholarship Optimizer", layout="centered")
st.title("🎓 Tax-Aide Scholarship Optimizer")

with st.sidebar:
    st.header("Settings")
    nc_rate = st.slider("State Tax Rate (%)", min_value=0.0, max_value=7.0, value=4.25, step=0.01) / 100

st.write("Enter the current sub-optimal draft return values below to find the mathematical peak.")

col1, col2 = st.columns(2)
with col1:
    box_1 = st.number_input("1098-T Box 1 (Tuition/QEE)", min_value=0, value=13552, step=100)
    box_5 = st.number_input("1098-T Box 5 (Scholarship)", min_value=0, value=14235, step=100)
    line_8r = st.number_input("Current Line 8r (Taxable Sch.)", min_value=0, value=7900, step=100)
with col2:
    agi = st.number_input("Current Federal AGI (Line 11)", min_value=0, value=29639, step=100)
    nc_taxable = st.number_input("Current State Taxable", min_value=0, value=16889, step=100)
    current_credit = st.number_input("Current LLC (Line 19)", min_value=0, value=1420, step=10)

if st.button("Calculate Optimization", type="primary"):
    current, best = optimize_scholarship(box_1, box_5, line_8r, agi, nc_taxable, nc_rate)
    diff = best['net_position'] - current['net_position']
    
    if diff > 5:
        st.success(f"### 💰 Opportunity Found: +${diff:,.0f} for the client!")
        
        st.subheader("🛠️ Step-by-Step TaxSlayer Instructions")
        st.markdown(f"""
        To achieve this exact refund, you must manually allocate the expenses and income. **Do not** simply enter the 1098-T as printed, or TaxSlayer will auto-calculate incorrectly.
        
        **Step 1: Enter the Taxable Scholarship**
        * Go to **Federal Section > Income > Less Common Income > Other Compensation > Scholarships and Grants**.
        * Enter exactly **${best['inclusion']:,.0f}**.
        
        **Step 2: Claim the Education Credit**
        * Go to **Federal Section > Deductions > Credits > Education Credits**.
        * Answer the qualifying questions and proceed to the 1098-T entry.
        * For **Tuition Paid**, enter **${best['expenses_to_claim']:,.0f}**.
        * For **Scholarships and Grants**, enter **$0** (leave blank).
        """)
        
        st.subheader("📊 The Math Breakdown")
        df = pd.DataFrame({
            "Metric": ["Scholarship as Income", "Federal AGI", "Fed Tax Liability", "State Tax Liability", "LLC Generated"],
            "Current Return": [f"${current['inclusion']:,.0f}", f"${current['agi']:,.0f}", f"${current['fed_tax']:,.0f}", f"${current['nc_tax']:,.0f}", f"${current['credit']:,.0f}"],
            "Optimized": [f"${best['inclusion']:,.0f}", f"${best['agi']:,.0f}", f"${best['fed_tax']:,.0f}", f"${best['nc_tax']:,.0f}", f"${best['credit']:,.0f}"]
        })
        st.table(df)
        
    else:
        st.info("✅ The current return is already perfectly optimized! No changes needed.")
