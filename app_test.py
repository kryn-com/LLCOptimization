import streamlit as st
import pandas as pd

# --- CUSTOM CSS FOR UI STYLING ---
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
    color: #666;
    font-size: 1.15rem;
    z-index: 1;
}

/* Keep slider clean */
div[data-testid="stSlider"] div[data-testid="stNumberInputContainer"]::before {
    content: "";
}

/* Make blockquotes look unified */
blockquote {
    border-left: 4px solid #cccccc;
    padding-left: 1rem;
    color: #555555;
    background-color: #f9f9f9;
    padding: 10px;
    border-radius: 5px;
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

# Using raw HTML to prevent Streamlit from creating tab-stealing anchor links
st.markdown("<h3 style='margin-top:1rem;'>1. Education Documents</h3>", unsafe_allow_html=True)

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown("**1098-T Box 1**<br><span style='font-size:0.9em; font-weight:normal;'>*(Tuition Paid)*</span>", unsafe_allow_html=True)
    box_1_in = st.number_input("box_1", value=None, step=100, label_visibility="collapsed")
with col2:
    st.markdown("**1098-T Box 5**<br><span style='font-size:0.9em; font-weight:normal;'>*(Total Scholarship)*</span>", unsafe_allow_html=True)
    box_5_in = st.number_input("box_5", value=None, step=100, label_visibility="collapsed")
with col3:
    st.markdown("**Other Qualified Expenses**<br><span style='font-size:0.9em; font-weight:normal;'>*(Books, Supplies, etc.)*</span>", unsafe_allow_html=True)
    addl_qee_in = st.number_input("addl_qee", value=None, step=100, label_visibility="collapsed")
with col4:
    st.empty()

st.markdown("<h3 style='margin-top:1rem;'>2. TaxSlayer Current Status</h3>", unsafe_allow_html=True)

col5, col6, col7, col8 = st.columns(4)
with col5:
    st.markdown("**Federal AGI**<br><span style='font-size:0.9em; font-weight:normal;'>*(Form 1040, Line 11)*</span><br>&nbsp;", unsafe_allow_html=True)
    agi_in = st.number_input("agi", value=None, step=100, label_visibility="collapsed")
with col6:
    st.markdown("**State Taxable Income**<br><span style='font-size:0.9em; font-weight:normal;'>*(NC D-400, Line 14)*</span><br>&nbsp;", unsafe_allow_html=True)
    nc_taxable_in = st.number_input("nc_taxable", value=None, step=100, label_visibility="collapsed")
with col7:
    st.markdown("**Taxable Scholarship** *(Line 8r)*<br><span style='font-size:0.85em; font-weight:normal;'>*Optional: Only if 1098-T is already entered*</span>", unsafe_allow_html=True)
    line_8r_in = st.number_input("line_8r", value=None, step=100, label_visibility="collapsed")
with col8:
    st.empty()

if st.button("Calculate Optimization", type="primary"):
    
    # Coalesce None values to 0 to prevent math errors
    box_1 = box_1_in or 0
    box_5 = box_5_in or 0
    addl_qee = addl_qee_in or 0
    agi = agi_in or 0
    nc_taxable = nc_taxable_in or 0
    line_8r = line_8r_in or 0
    
    if box_1 == 0 and box_5 == 0:
        st.warning("Please enter the 1098-T information to begin.")
    else:
        baseline, optimized = optimize_scholarship(box_1, addl_qee, box_5, agi, nc_taxable, line_8r, nc_rate)
        
        savings = baseline['tax_burden'] - optimized['tax_burden']
        total_qee = box_1 + addl_qee
        
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
                    client_text = f"Because your total scholarship (\${box_5:,.0f}) was larger than your educational expenses (\${total_qee:,.0f}), standard tax software automatically reports the difference (\${baseline['inclusion']:,.0f}) as taxable income. If we stopped there, your total tax burden would be \${baseline['tax_burden']:,.0f}.\n\n> However, we used an IRS-approved strategy to lower your bill. We voluntarily reported an additional \${added_income:,.0f} of your scholarship as income. While this temporarily increased your taxes by \${added_tax:,.0f}, doing so unlocked a Lifetime Learning Credit of \${added_credit:,.0f}. That credit completely paid for the tax increase and put an extra \${savings:,.0f} in your pocket!"
                else:
                    client_text = f"Normally, because your educational expenses (\${total_qee:,.0f}) were higher than your scholarship (\${box_5:,.0f}), none of your scholarship would be taxed. Standard tax software would calculate your total tax burden as \${baseline['tax_burden']:,.0f}.\n\n> However, we used an IRS-approved strategy to lower your bill. We voluntarily reported \${added_income:,.0f} of your tax-free scholarship as taxable income. While this temporarily increased your taxes by \${added_tax:,.0f}, doing so unlocked a Lifetime Learning Credit of \${added_credit:,.0f}. That credit completely paid for the tax increase and put an extra \${savings:,.0f} in your pocket!"
                
                st.markdown(f"> {client_text}")

            st.divider()
            
            st.subheader("📊 The Math Breakdown")
            
            # Format the credit so it doesn't show as -$0
            base_credit_str = f"-${baseline['credit']:,.0f}" if baseline['credit'] > 0 else "$0"
            opt_credit_str = f"-${optimized['credit']:,.0f}" if optimized['credit'] > 0 else "$0"
            
            df = pd.DataFrame({
                "Metric": [
                    "Tax-Free Scholarship", 
                    "TOTAL SCHOLARSHIP",
                    "Taxable Scholarship",
                    "Federal AGI", 
                    "Federal Tax", 
                    "State Tax",
                    "Lifetime Learning Credit",
                    "TOTAL NET TAX BURDEN"
                ],
                "Standard TaxSlayer Entry": [
                    f"${baseline['ts_box_5_entry']:,.0f}", 
                    f"${box_5:,.0f}",
                    f"${baseline['inclusion']:,.0f}",
                    f"${baseline['agi']:,.0f}", 
                    f"${baseline['fed_tax']:,.0f}", 
                    f"${baseline['nc_tax']:,.0f}", 
                    base_credit_str,
                    f"${baseline['tax_burden']:,.0f}"
                ],
                "After Optimization": [
                    f"${optimized['ts_box_5_entry']:,.0f}", 
                    f"${box_5:,.0f}",
                    f"${optimized['inclusion']:,.0f}",
                    f"${optimized['agi']:,.0f}", 
                    f"${optimized['fed_tax']:,.0f}", 
                    f"${optimized['nc_tax']:,.0f}", 
                    opt_credit_str,
                    f"${optimized['tax_burden']:,.0f}"
                ]
            })
                
            st.table(df)
            st.markdown(f"**Optimization was successful and resulted in a \${savings:,.0f} net tax savings.**")
            
            # --- GENERATE PRINTABLE HTML REPORT ---
            html_report = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>Lifetime Learning Credit Optimization Report</title>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; max-width: 800px; margin: 20px auto; color: #333; }}
                    h2 {{ color: #2c3e50; border-bottom: 2px solid #eee; padding-bottom: 10px; }}
                    h3 {{ color: #34495e; margin-top: 30px; }}
                    .client-box {{ background-color: #f9f9f9; border-left: 4px solid #cccccc; padding: 15px; font-style: italic; color: #555555; }}
                    table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
                    th, td {{ border: 1px solid #ddd; padding: 10px 12px; text-align: right; }}
                    th:first-child, td:first-child {{ text-align: left; font-weight: bold; }}
                    th {{ background-color: #f4f6f8; }}
                    .summary {{ font-size: 1.1em; font-weight: bold; color: #155724; background-color: #d4edda; border: 1px solid #c3e6cb; padding: 15px; border-radius: 5px; text-
