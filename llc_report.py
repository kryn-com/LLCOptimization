"""llc_report.py - side-by-side comparison, TaxSlayer entry steps, and explanations (no Streamlit)."""
from llc_engine import STATES, FED


NY_NOTICE = ("Do not use this tool for New York City or Yonkers residents. "
             "City income taxes are not included, so the results would understate total tax.")


def money(v):
    return f"${v:,.0f}"


def neg_money(v):
    return f"-${v:,.0f}" if v > 0 else "$0"


def marginal_rate(taxable, brackets):
    """Rate of the bracket that the last dollar of taxable income falls in."""
    rate = brackets[0][1]
    for floor, r in brackets:
        if taxable > floor:
            rate = r
    return rate


def marginal_rates(optimized, state, year):
    fed = marginal_rate(optimized["fed_taxable"], FED[year]["brackets"])
    st = marginal_rate(optimized["state_taxable"], STATES[state]["years"][year]["brackets"])
    return fed, st


def process_rows(res, box_1, addl_qee, box_5, ext_funding, state, year):
    st = STATES[state]
    rows = [
        ("1098-T Box 5 scholarship (total)", money(box_5), False),
        ("  Reported tax-free (Grants & Scholarships)", money(res["ts_box_5_entry"]), False),
        ("  Reported taxable (added to income)", money(res["inclusion"]), False),
        ("External funding (taxable, not on 1098-T)", money(ext_funding), False),
        ("Federal AGI", money(res["agi"]), False),
    ]
    if res.get("sched_1a"):
        rows.append(("Schedule 1-A deductions (tips, overtime)", money(res["sched_1a"]), False))
    rows += [
        ("Federal taxable income", money(res["fed_taxable"]), False),
        ("Federal tax before credit", money(res["fed_tax"]), False),
        ("Qualified expenses for the credit", money(res["expenses_to_claim"]), False),
        ("Lifetime Learning Credit", neg_money(res["credit"]), False),
        ("Federal tax after credit", money(res["final_fed_tax"]), True),
        (f"{state} taxable income ({st['taxable_label']})", money(res["state_taxable"]), False),
        (f"{state} income tax", money(res["state_tax"]), True),
        ("Modeled income tax (federal + state)", money(res["tax_burden"]), True),
    ]
    return rows


def rows_to_html(rows, css_class="ui-math-table"):
    out = [f'<table class="{css_class}">']
    for label, value, strong in rows:
        indent = "padding-left:28px;" if label.startswith("  ") else ""
        style = ' style="font-weight:bold;background-color:rgba(128,128,128,0.08);"' if strong else ""
        out.append(f'<tr{style}><td style="{indent}">{label.strip()}</td><td>{value}</td></tr>')
    out.append("</table>")
    return "\n".join(out)


def gain_breakdown(baseline, optimized):
    credit_gain = optimized["credit"] - baseline["credit"]
    fed_inc = optimized["fed_tax"] - baseline["fed_tax"]
    state_inc = optimized["state_tax"] - baseline["state_tax"]
    return {"added_income": optimized["inclusion"] - baseline["inclusion"],
            "credit_gain": credit_gain, "fed_increase": fed_inc, "state_increase": state_inc,
            "net_gain": credit_gain - fed_inc - state_inc}


def gain_html(g, css_class="ui-math-table"):
    """Savings table in dollars."""
    rows = [
        ("Scholarship counted as taxable income", money(g.get("added_income", 0)), False),
        ("Larger Lifetime Learning Credit", f"+{money(g['credit_gain'])}", False),
        ("Extra federal income tax", f"-{money(g['fed_increase'])}", False),
        ("Extra state income tax", f"-{money(g['state_increase'])}", False),
        ("NET SAVINGS TO THE TAXPAYER", money(g["net_gain"]), True),
    ]
    return rows_to_html(rows, css_class)


def entry_steps(opt, box_1, addl_qee, ext_funding, state, year):
    taxable_total = opt["inclusion"] + ext_funding
    lines = [
        f"TAXSLAYER ENTRIES - Tax Year {year} - Single - {STATES[state]['name']}",
        "",
        "STEP 1  Federal > Income > Other Income > Other Compensation > Scholarships and Grants",
        f"        Enter: {money(taxable_total)}",
    ]
    if ext_funding > 0:
        lines.append(f"        (= {money(opt['inclusion'])} taxable 1098-T portion + {money(ext_funding)} external funding)")
    lines += [
        "        Overwrite any amount TaxSlayer already placed here.",
        "",
        "STEP 2  Federal > Deductions > Credits > Education Credits (1098-T screen)",
        f"        Tuition Paid (Box 1):          {money(box_1)}",
        f"        Grants and Scholarships:       {money(opt['ts_box_5_entry'])}   (tax-free portion that remains)",
        f"        Other Qualified Expenses:      {money(addl_qee)}",
        "        Choose the Lifetime Learning Credit (not AOTC).",
    ]
    return lines


def tie_out(opt, state):
    st = STATES[state]
    return [
        ("Federal AGI (Form 1040, Line 11a)", money(opt["agi"])),
        ("Federal taxable income", money(opt["fed_taxable"])),
        ("Federal tax before credits", money(opt["fed_tax"])),
        ("Lifetime Learning Credit (Form 8863 / Schedule 3)", money(opt["credit"])),
        (f"{state} taxable income ({st['taxable_label']})", money(opt["state_taxable"])),
        (f"{state} income tax ({st['tax_label']})", money(opt["state_tax"])),
    ]


def client_explanation(baseline, optimized, g, box_5, state, year):
    """Plain-language summary. Shows only the change from the strategy, not whole-return totals."""
    name = STATES[state]["name"]
    added = g["added_income"]
    extra_tax = g["fed_increase"] + g["state_increase"]
    fed_m, st_m = marginal_rates(optimized, state, year)
    combined = fed_m + st_m
    why = (
        f"<b>Why this works:</b> every dollar of scholarship we count as taxable lets another dollar of tuition count "
        f"toward the credit, and the credit pays back 20% of it. Your extra income is taxed at a lower rate "
        f"(federal {fed_m * 100:.0f}% + {name} {st_m * 100:.2f}% = about {combined * 100:.0f}%), "
        f"so you keep the difference."
    ) if combined < 0.20 else (
        "<b>Why this works:</b> each $1 of scholarship we count as taxable lets $1 more of tuition count toward the credit."
    )
    return (
        f"Your school reported {money(box_5)} in scholarships and grants. Scholarship money spent on tuition is normally "
        f"tax-free, but the tax law lets you choose to count part of it as taxable income.<br><br>"
        f"We chose to count <b>{money(added)}</b> of your scholarship as taxable income. "
        f"That raises your Lifetime Learning Credit by {money(g['credit_gain'])} and adds {money(extra_tax)} of federal "
        f"and {name} income tax on the extra income.<br><br>"
        f"{why}<br><br>"
        f"<b>Overall, this saves you about {money(g['net_gain'])} in income tax compared with the standard approach.</b>"
    )


def plain_text_report(baseline, optimized, g, box_1, addl_qee, box_5, ext_funding, state, year):
    lines = entry_steps(optimized, box_1, addl_qee, ext_funding, state, year)
    lines += ["", "TIE-OUT - TaxSlayer should now show:"]
    lines += [f"  {k}: {v}" for k, v in tie_out(optimized, state)]
    lines += ["", f"NET GAIN TO TAXPAYER: {money(g['net_gain'])}",
              f"  Credit gain {money(g['credit_gain'])}, extra federal tax {money(g['fed_increase'])}, "
              f"extra {state} tax {money(g['state_increase'])}"]
    if state == "NY":
        lines += ["", "NOTE: " + NY_NOTICE]
    return "\n".join(lines)


def html_report(baseline, optimized, g, box_1, addl_qee, box_5, ext_funding, state, year):
    """Client-facing report: simple explanation and the savings math only."""
    name = STATES[state]["name"]
    note = f"<p><b>Note:</b> {NY_NOTICE}</p>" if state == "NY" else ""
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Education Credit Savings</title>
<style>
body{{font-family:Arial,sans-serif;font-size:15px;line-height:1.5;max-width:700px;margin:20px auto;color:#333}}
h2{{color:#2c3e50;border-bottom:2px solid #eee;padding-bottom:5px}} h3{{color:#34495e;margin:18px 0 6px}}
table{{width:100%;border-collapse:collapse;margin:6px 0}} td{{border:1px solid #ddd;padding:6px 10px}}
td:last-child{{text-align:right}}
</style></head><body>
<h2>Education Credit Savings - {name} - Tax Year {year}</h2>
<h3>What we did ({name})</h3><div>{client_explanation(baseline, optimized, g, box_5, state, year)}</div>
<h3>How the savings add up</h3>{gain_html(g, "m")}
{note}
</body></html>"""
