import streamlit as st
import math
import pandas as pd

def calc_irs_table_tax_2025(taxable_income):
    """Calculates Federal Tax using the exact IRS $50 Table method (Single 2025)."""
    if taxable_income <= 0:
        return 0
    
    # The IRS tables use $50 increments for incomes under $100,000.
    if taxable_income < 100000:
        bucket_floor = math.floor(taxable_income / 50) * 50
        midpoint = bucket_floor + 25
        ti_to_use = midpoint
    else:
        ti_to_use = taxable_income 
        
    # 2025 Single brackets applied to the midpoint
    if ti_to_use <= 11925:
        tax = ti_to_use * 0.10
    elif ti_to_use <= 48475:
        tax = 11925 * 0.10 + (ti_to_use - 11925) * 0.12
    else:
        tax = 11925 * 0.10 + (48475 - 11925) * 0.12 + (ti_to_use - 48475) * 0.22
        
    return round(tax)

def optimize_scholarship_inclusion(w2_1099_income, max_scholarship=10000):
    best_savings = -1
    best_scholarship = 0
    best_fed_tax = 0
    best_nc_tax = 0
    best_fed_ti = 0
    
    # Baseline: What is the tax with 0 scholarship included?
    base_fed_ti = max(0, w2_1099_income - 15750)
    base_fed_tax = calc_irs_table_tax_2025(base_fed_ti)
    base_nc_ti = max(0, w2_1099_income - 12750)
    base_nc_tax = base_nc_ti * 0.0425
    base_total_tax = base_fed_tax + base_nc_tax
    
    # Iterate through every single dollar of scholarship
    for s in range(0, max_scholarship + 1):
        new_fed_ti = max(0, (w2_1099_income + s) - 15750)
        new_fed_tax = calc_irs_table_tax_2025(new_fed_ti)
        
        new_nc_ti = max(0, (w2_1099_income + s) - 12750)
        new_nc_tax = new_nc_ti * 0.0425
        
        llc = min(s * 0.20, 2000) # Max credit is $2,000
        
        net_fed_tax = max(0, new_fed_tax - llc)
        new_total_tax = net_fed_tax + new_nc_tax
        
        savings = base_total_tax - new_total_tax
        
        # Capture the highest savings. Tie-breaker naturally prefers lower scholarship amount.
        if savings > best_savings:
            best_savings = savings
            best_scholarship = s
            best_fed_tax = net_fed_tax
            best_nc_tax = new_nc_tax
            best_fed_ti = new_fed_ti

    return {
        "base_total_tax": base_total_tax,
        "optimal_scholarship": best_scholarship,
        "max_savings": best_savings,
        "final_net_fed_tax": best_fed_tax,
        "final_nc_tax": best_nc_tax,
        "final_fed_ti": best_fed_ti,
        "llc_claimed": min(best_scholarship * 0.20, 2000)
    }

# --- Streamlit UI ---
st.set_page_config(page_title="Tax-Aide Scholarship Optimizer", layout="centered")

st.title("Tax-Aide LLC Optimizer (2025)")
st.markdown("Identifies the exact dollar amount of taxable scholarship to include to maximize the Lifetime Learning Credit, utilizing the strict IRS $50 Tax Table bucketing strategy.")

# Input Field
w2_1099_income = st.number_input("Enter Base Income (W-2 + 1099):", min_value=0, value=24404, step=100)

if st.button("Optimize for 2025", type="primary"):
    result = optimize_scholarship_inclusion(w2_1099_income)
    
    st.divider()
    st.subheader("Optimization Results")
    
    # Top Level Metrics
    col1, col2, col3 = st.columns(3)
    col1.metric("Optimal Taxable Scholarship", f"${result['optimal_scholarship']:,.0f}")
    col2.metric("Maximum Tax Savings", f"${result['max_savings']:,.2f}")
    col3.metric("Final Federal Taxable Income", f"${result['final_fed_ti']:,.0f}")
    
    # Detailed Breakdown Table
    st.markdown("### The Breakdown")
    breakdown_data = {
        "Metric": [
            "Initial Total Tax (No Scholarship)", 
            "LLC Claimed", 
            "Final Net Federal Tax", 
            "Final NC State Tax"
        ],
        "Amount": [
            f"${result['base_total_tax']:,.2f}", 
            f"${result['llc_claimed']:,.2f}", 
            f"${result['final_net_fed_tax']:,.2f}", 
            f"${result['final_nc_tax']:,.2f}"
        ]
    }
    st.table(pd.DataFrame(breakdown_data))
    
    # The Sawtooth Tracker
    remainder = result['final_fed_ti'] % 50
    if remainder in [49, 99]:
        st.success(f"🎯 **Sawtooth Target Hit!** The Federal Taxable Income ends in **${remainder}**, resting perfectly at the top edge of an IRS $50 bucket before the tax steps up.")
    else:
        st.info(f"The Federal Taxable Income ends in **${remainder}**. The LLC naturally capped out before hitting the next bucket threshold.")
