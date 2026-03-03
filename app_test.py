import streamlit as st
import pandas as pd

def optimize_scholarship(
    box_1_tuition,
    additional_qee,
    box_5_scholarship,
    form1040_line_11_agi,
    ncd400_line_14_taxable,
    nc_tax_rate=0.0425
):
    # --- 1. CONSTANTS ---
    FED_STD_DEDUCTION = 15750 
    NC_STD_DEDUCTION = 12750 
    FED_BRACKETS = [(11925, 0.10), (48475, 0.12), (103350, 0.22), (float('inf'), 0.24)]

    # Combine QEE for internal math
    total_qee = box_1_tuition + additional_qee

    # --- 2. CALIBRATION ---
    if ncd400_line_14_taxable > 0:
        state_adjustment_factor = ncd400_line_14_taxable - (form1040_line_11_agi - NC_STD_DEDUCTION)
    else:
        state_adjustment_factor = 0
        
    base_fed_income = form1040_line_11_agi 

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
        
        # This is the number that gets entered into TaxSlayer's 1098-T screen
        tax_free_scholarship = max(0, box_5_scholarship - inclusion_amount)
        
        qualified_expenses = max(0, total_qee - tax_free_scholarship)
        potential_credit = min(2000, qualified_expenses * 0.20)
        usable_credit = min(potential_credit, fed_tax)
        
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
            "ts_box_5_entry": tax_free_scholarship 
        }

    # --- 4. CALCULATE THE SCENARIOS ---
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
st.set_page_config(page_title="Scholarship Optimizer", layout="wide")
st.title("🎓 Tax-Aide Scholarship Optimizer")

with st.sidebar:
    st.header("Settings")
    nc_rate = st.slider("State Tax Rate (%)", min_value=0.0, max_value=7.0, value=4.25, step=0.01) / 100
    st.info("💡 **Workflow Protocol:** You MUST enter the client's Federal AGI and State Taxable Income *before* opening the 1098-T screen in TaxSlayer.")

st.write("Enter the clean baseline numbers below to calculate the exact amount of scholarship to shift to taxable income to maximize the Federal Education Credit.")

col1, col2, col3 = st.columns(3)
with col1:
    box_1 = st.number_input("1098-T Box 1 (Tuition)", min_value=0, value=20000, step=100)
    addl_qee = st.number_input("Additional QEE (Books, etc.)", min_value=0, value=4865, step=100)
with col2:
    box_5 = st.number_input("1098-T Box 5 (Scholarship)", min_value=0, value=32289, step=100)
with col3:
    agi = st.number_input("Clean Base Federal AGI", min_value=0, value=16770, step=100)
    nc_taxable = st.number_input("Clean State Taxable", min_value=0, value=4020, step=100)

if st.button("Calculate Optimization", type="primary"):
    baseline, optimized = optimize_scholarship(box_1, addl_qee, box_5, agi, nc_taxable, nc_rate)
    
    savings = baseline['tax_burden'] - optimized['tax_burden']
    
    st.divider()
    
    if savings > 5:
        st.success(f"### 💰 Optimization Successful! You saved the client **${savings:,.0f}**")
        
        c1, c2 = st.columns(2)
        
        with c1:
            st.subheader("🛠️ TaxSlayer Instructions")
            st.markdown(f"""
            **Step 1: Enter the Taxable Income**
            * Go to `Federal Section > Income > Other Income > Other Compensation > Scholarships and Grants`
            * Enter exactly: **\${optimized['inclusion']:,.0f}**
            
            **Step 2: Enter the Education Credit**
            * Go to `Federal Section > Deductions > Credits > Education Credits`
            * Fill out the qualifying questions. On the 1098-T entry screen, enter these exact values:
            * **Tuition Paid:** **\${box_1:,.0f}** *(Unaltered)*
            * **Additional Expenses:** **\${addl_qee:,.0f}** *(Unaltered)*
            * **Grants and Scholarships:** **\${optimized['ts_box_5_entry']:,.0f}** *(This is the Tax-Free portion. TaxSlayer will automatically subtract this from the QEE to calculate the correct credit)*
            """)
            
        with c2:
            st.subheader("🗣️ Explanation for the Client")
            
            added_income = optimized['inclusion'] - baseline['inclusion']
            added_tax = (optimized['fed_tax'] + optimized['nc_tax']) - (baseline['fed_tax'] + baseline['nc_tax'])
            added_credit = optimized['credit'] - baseline['credit']
            
            if baseline['inclusion'] > 0:
                st.markdown(f"""
                > "Because your scholarship was larger than your tuition, the IRS **required** us to report **\${baseline['inclusion']:,.0f}** as taxable income. If we handled your return the ordinary way, your total tax burden would have been **\${baseline['tax_burden']:,.0f}**.
                > 
                > However, we used an IRS-approved strategy to lower your bill. We **voluntarily** reported an additional **\${added_income:,.0f}** of your scholarship as income. While this temporarily increased your taxes by **\${added_tax:,.0f}**, doing so unlocked a Federal Education Credit of **\${added_credit:,.0f}**. That credit completely paid for the tax increase and put an extra **\${savings:,.0f}** in your pocket!"
                """)
            else:
                st.markdown(f"""
                > "If we handled your 1098-T the ordinary way, your total tax burden would have been **\${baseline['tax_burden']:,.0f}**.
                > 
                > However, we used an IRS-approved strategy to lower your bill. We **voluntarily** reported **\${added_income:,.0f}** of your tax-free scholarship as taxable income. While this temporarily increased your taxes by **\${added_tax:,.0f}**, doing so unlocked a Federal Education Credit of **\${added_credit:,.0f}**. That credit completely paid for the tax increase and put an extra **\${savings:,.0f}** in your pocket!"
                """)

        st.divider()
        
        st.subheader("📊 The Math Breakdown")
        
        df = pd.DataFrame({
            "Metric": ["Taxable Scholarship", "Federal Tax", "State Tax", "Federal Education Credit", "TOTAL NET TAX BURDEN"],
            "Ordinary Reporting": [f"${baseline['inclusion']:,.0f}", f"${baseline['fed_tax']:,.0f}", f"${baseline['nc_tax']:,.0f}", f"${baseline['credit']:,.0f}", f"${baseline['tax_burden']:,.0f}"],
            "Optimized Strategy": [f"${optimized['inclusion']:,.0f}", f"${optimized['fed_tax']:,.0f}", f"${optimized['nc_tax']:,.0f}", f"${optimized['credit']:,.0f}", f"${optimized['tax_burden']:,.0f}"]
        })
            
        st.table(df)
        st.caption("*(Total Net Tax Burden = Federal Tax + State Tax - Federal Education Credit. A lower number means more money in the client's pocket.)*")
        
    else:
        st.info("✅ **No Optimization Available.** Ordinary reporting is already the best mathematical outcome for this client.")
