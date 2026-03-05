import streamlit as st
import pandas as pd

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

    # --- 4. CALCULATION ENGINE ---
    def calculate_scenario(inclusion_amount):
        if inclusion_amount > box_5_scholarship:
            inclusion_amount = box_5_scholarship

        new_agi = clean_agi + inclusion_amount
        
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
            "ts_box_5_entry": tax_free_scholarship,
            "expenses_to_claim": qualified_expenses
        }

    # --- 5. CALCULATE THE SCENARIOS ---
    # The Baseline is calculated exactly as TaxSlayer would do it by default
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
    st.success("💡 **Workflow:** You can enter the clean baseline before touching the 1098-T, OR enter the current numbers after TaxSlayer has processed the 1098-T. The app handles both!")

st.write("### 1. Education Documents")
col1, col2, col3 = st.columns(3)
with col1:
    st.markdown("**1098-T Box 1** *(Tuition Paid)*")
    box_1 = st.number_input("box_1", min_value=0, value=0, step=100, label_visibility="collapsed")
with col2:
    st.markdown("**1098-T Box 5** *(Total Scholarship)*")
    box_5 = st.number_input("box_5", min_value=0, value=0, step=100, label_visibility="collapsed")
with col3:
    st.markdown("**Other Qualified Expenses** *(Books, etc.)*")
    addl_qee = st.number_input("addl_qee", min_value=0, value=0, step=100, label_visibility="collapsed")

st.write("### 2. TaxSlayer Current Status")
col4, col5, col6 = st.columns(3)
with col4:
    st.markdown("**Federal AGI** *(Form 1040, Line 11)*")
    agi = st.number_input("agi", min_value=0, value=0, step=100, label_visibility="collapsed")
with col5:
    st.markdown("**State Taxable** *(NC D-400, Line 14)*")
    nc_taxable = st.number_input("nc_taxable", min_value=0, value=0, step=100, label_visibility="collapsed")
with col6:
    st.markdown("**Taxable Scholarship** *(Optional: Only if 1098-T is already entered)*")
    line_8r = st.number_input("line_8r", min_value=0, value=0, step=100, label_visibility="collapsed")


if st.button("Calculate Optimization", type="primary"):
    # Guard against 0 inputs throwing errors
    if box_1 == 0 and box_5 == 0:
        st.warning("Please enter the 1098-T information to begin.")
    else:
        baseline, optimized = optimize_scholarship(box_1, addl_qee, box_5, agi, nc_taxable, line_8r, nc_rate)
        
        savings = baseline['tax_burden'] - optimized['tax_burden']
        total_qee = box_1 + addl_qee
        
        st.divider()
        
        if savings > 5:
            st.success(f"### 💰 Optimization Successful! You saved the client **\${savings:,.0f}**")
            
            c1, c2 = st.columns(2)
            
            with c1:
                st.subheader("🛠️ TaxSlayer Instructions")
                st.markdown(f"""
                **Step 1: Enter the Taxable Income**
                * Go to `Federal Section > Income > Other Income > Other Compensation > Scholarships and Grants`
                * Enter exactly: **\${optimized['inclusion']:,.0f}**
                *(Overwrite any number TaxSlayer may have already put here)*
                
                **Step 2: Enter the Education Credit**
                * Go to `Federal Section > Deductions > Credits > Education Credits`
                * On the 1098-T entry screen, enter these exact values:
                * **Tuition Paid:** **\${box_1:,.0f}**
                * **Grants and Scholarships:** **\${optimized['ts_box_5_entry']:,.0f}** *(This is the Tax-Free portion that remains)*
                * **Other Qualified Expenses:** **\${addl_qee:,.0f}**
                """)
                
            with c2:
                st.subheader("🗣️ Explanation for the Client")
                
                added_income = optimized['inclusion'] - baseline['inclusion']
                added_tax = (optimized['fed_tax'] + optimized['nc_tax']) - (baseline['fed_tax'] + baseline['nc_tax'])
                added_credit = optimized['credit'] - baseline['credit']
                
                if baseline['inclusion'] > 0:
                    st.markdown(f"""
                    > "Because your total scholarship (**\${box_5:,.0f}**) was larger than your educational expenses (**\${total_qee:,.0f}**), standard tax software automatically reports the difference (**\${baseline['inclusion']:,.0f}**) as taxable income. If we stopped there, your total tax burden would be **\${baseline['tax_burden']:,.0f}**.
                    > 
                    > However, we used an IRS-approved strategy to lower your bill. We voluntarily reported an additional **\${added_income:,.0f}** of your scholarship as income. While this temporarily increased your taxes by **\${added_tax:,.0f}**, doing so unlocked a Federal Education Credit of **\${added_credit:,.0f}**. That credit completely paid for the tax increase and put an extra **\${savings:,.0f}** in your pocket!"
                    """)
                else:
                    st.markdown(f"""
                    > "Normally, because your educational expenses (**\${total_qee:,.0f}**) were higher than your scholarship (**\${box_5:,.0f}**), none of your scholarship would be taxed. Standard tax software would calculate your total tax burden as **\${baseline['tax_burden']:,.0f}**.
                    > 
                    > However, we used an IRS-approved strategy to lower your bill. We voluntarily reported **\${added_income:,.0f}** of your tax-free scholarship as taxable income. While this temporarily increased your taxes by **\${added_tax:,.0f}**, doing so unlocked a Federal Education Credit of **\${added_credit:,.0f}**. That credit completely paid for the tax increase and put an extra **\${savings:,.0f}** in your pocket!"
                    """)

            st.divider()
            
            st.subheader("📊 The Math Breakdown")
            
            df = pd.DataFrame({
                "Metric": [
                    "Taxable Scholarship", 
                    "Net Expenses Used for Credit",
                    "Federal Tax", 
                    "State Tax", 
                    "Federal Education Credit", 
                    "TOTAL NET TAX BURDEN"
                ],
                "Standard TaxSlayer Entry": [
                    f"${baseline['inclusion']:,.0f}", 
                    f"${baseline['expenses_to_claim']:,.0f}",
                    f"${baseline['fed_tax']:,.0f}", 
                    f"${baseline['nc_tax']:,.0f}", 
                    f"${baseline['credit']:,.0f}", 
                    f"${baseline['tax_burden']:,.0f}"
                ],
                "After Optimization": [
                    f"${optimized['inclusion']:,.0f}", 
                    f"${optimized['expenses_to_claim']:,.0f}",
                    f"${optimized['fed_tax']:,.0f}", 
                    f"${optimized['nc_tax']:,.0f}", 
                    f"${optimized['credit']:,.0f}", 
                    f"${optimized['tax_burden']:,.0f}"
                ]
            })
                
            st.table(df)
            st.caption("*(Total Net Tax Burden = Federal Tax + State Tax - Federal Education Credit. A lower number means more money in the client's pocket.)*")
            
        else:
            st.info("✅ **No Optimization Available.** Standard TaxSlayer reporting is already the best mathematical outcome for this client.")
