"""llc_engine.py - pure calculation logic for the LLC optimizer (no Streamlit imports)."""
import math


DEFAULT_YEAR = 2026
DEFAULT_STATE = "NC"

# =====================================================================================================
# 2026 DATA YEAR - ITEMS STILL TO CONFIRM  (search this file for "CONFIRM-2026")
# Many 2026 state forms and instructions were not final when these numbers were entered.
# When an item is verified, change its status to VERIFIED with the date and the source document.
#
# CONFIRM-2026 | Federal      | VERIFIED: standard deduction and brackets (IRS Rev. Proc. 2025-32).
#                             | Tax Table bands: $25 under $3,000, $50 to $100,000 (midpoint method).
# CONFIRM-2026 | NC           | 2026 standard deduction $12,750 and rate 3.99% - confirm against the final
#                             | 2026 D-400 instructions. Form lines 14 (taxable income) and 15 (tax) are
#                             | carried over from 2025.
# CONFIRM-2026 | GA           | Rate 4.99% and standard deduction $15,000 - confirm with the Georgia DOR.
#                             | Form 500 line numbers are not used (labels are generic). Assumes
#                             | tax = taxable income x rate (no tax table).
# CONFIRM-2026 | NM           | 2026 rate table not yet available. Assumes $100 bands below $100,000 and the
#                             | 2025 base amounts ($4,356 and $9,746) above it. 2026 standard deduction set to
#                             | the federal $16,100. PIT-1 lines 17 and 18 carried over from 2025.
# CONFIRM-2026 | NY           | 2026 rates and the tax-table method are not verified. Assumes $50 bands below
#                             | $65,000 and the bracket formula above. The table also requires NY AGI of
#                             | $107,650 or less (2025 figure); that test is not modeled. IT-201 lines 37 and
#                             | 39 carried over from 2025. Not for NYC or Yonkers residents.
# CONFIRM-2026 | TaxSlayer    | Menu paths (Scholarships and Grants under Other Compensation; 1098-T
#                             | education credit screen) - confirm in the 2026 software.
# CONFIRM-2026 | Real returns | No real 2026 returns have been compared to TaxSlayer yet.
#
# Not modeled (any year): local/city income taxes, state credits and rebates, EITC and ACA premium
# credit interactions, dependent students, deductions other than the standard deduction and Schedule 1-A.
# =====================================================================================================


FED = {
    2025: {"std": 15750, "brackets": [(0, .10), (11925, .12), (48475, .22), (103350, .24),
                                      (197300, .32), (250525, .35), (626350, .37)]},
    2026: {"std": 16100, "brackets": [(0, .10), (12400, .12), (50400, .22), (105700, .24),
                                      (201775, .32), (256225, .35), (640600, .37)]},
}


NY_2025 = [(0, .04), (8500, .045), (11700, .0525), (13900, .055), (80650, .06),
           (215400, .0685), (1077550, .0965), (5000000, .103), (25000000, .109)]
NY_2026 = [(0, .039), (8500, .044), (11700, .0515), (13900, .054), (80650, .059),
           (215400, .0685), (1077550, .0965), (5000000, .103), (25000000, .109)]
NM_BRACKETS = [(0, .015), (5500, .032), (16500, .043), (33500, .047), (66500, .049), (210000, .059)]


# band / table_limit: state tax tables use the midpoint of a band while taxable income < table_limit.
# GA labels are generic until the 2026 Form 500 line numbers are published.
STATES = {
    "NC": {"name": "North Carolina", "taxable_label": "NC Form D-400, Line 14", "tax_label": "NC Form D-400, Line 15",
           "band": None, "table_limit": 0,
           "years": {2025: {"std": 12750, "brackets": [(0, .0425)]},
                     2026: {"std": 12750, "brackets": [(0, .0399)]}}},
    "GA": {"name": "Georgia", "taxable_label": "GA Form 500, Georgia taxable income",
           "tax_label": "GA Form 500, Georgia income tax",
           "band": None, "table_limit": 0,
           "years": {2025: {"std": 12000, "brackets": [(0, .0519)]},
                     2026: {"std": 15000, "brackets": [(0, .0499)]}}},
    "NM": {"name": "New Mexico", "taxable_label": "NM Form PIT-1, Line 17", "tax_label": "NM Form PIT-1, Line 18",
           "band": 100, "table_limit": 100000,
           "over_schedule": [(100000, 4356, .049), (210000, 9746, .059)],
           "years": {2025: {"std": 15750, "brackets": NM_BRACKETS},
                     2026: {"std": 16100, "brackets": NM_BRACKETS}}},
    "NY": {"name": "New York", "taxable_label": "NY Form IT-201, Line 37", "tax_label": "NY Form IT-201, Line 39",
           "band": 50, "table_limit": 65000,
           "years": {2025: {"std": 8000, "brackets": NY_2025},
                     2026: {"std": 8000, "brackets": NY_2026}}},
}


LLC_RATE, LLC_EXPENSE_CAP = 0.20, 10000
PHASEOUT_START, PHASEOUT_END = 80000, 90000


def irs_round(val):
    return int(math.floor(val + 0.5))


def year_cfg(state, year):
    """Standard deduction and brackets for a state/year."""
    return STATES[state]["years"][year]


def bracket_tax(amount, brackets):
    tax = 0.0
    for i, (floor, rate) in enumerate(brackets):
        ceiling = brackets[i + 1][0] if i + 1 < len(brackets) else float("inf")
        if amount > floor:
            tax += (min(amount, ceiling) - floor) * rate
    return tax


def marginal_rate(taxable, brackets):
    """Rate of the bracket that the last dollar of taxable income falls in."""
    rate = brackets[0][1]
    for floor, r in brackets:
        if taxable > floor:
            rate = r
    return rate

def fed_tax(taxable, year):
    """Federal tax the way the IRS Tax Table computes it (below $100,000 it uses the midpoint of a band).
    Bands are $25 wide under $3,000 and $50 wide from $3,000 to $100,000.
    The first rows under $25 are narrower still; ignored here (difference is $1 at most).
    """
    if taxable <= 0:
        return 0
    if taxable >= 100000:
        ti = taxable
    elif taxable < 3000:
        ti = math.floor(taxable / 25) * 25 + 12.5
    else:
        ti = math.floor(taxable / 50) * 50 + 25
    return irs_round(bracket_tax(ti, FED[year]["brackets"]))

def state_tax(taxable, state, year):
    cfg = STATES[state]
    if taxable <= 0:
        return 0
    ti = taxable
    if cfg["band"] and taxable < cfg["table_limit"]:
        ti = math.floor(taxable / cfg["band"]) * cfg["band"] + cfg["band"] / 2
    elif cfg.get("over_schedule") and taxable >= cfg["table_limit"]:
        for floor, base, rate in reversed(cfg["over_schedule"]):
            if taxable >= floor:
                return irs_round(base + (taxable - floor) * rate)
    return irs_round(bracket_tax(ti, year_cfg(state, year)["brackets"]))


def phaseout_ratio(agi):
    if agi <= PHASEOUT_START:
        return 1.0
    if agi >= PHASEOUT_END:
        return 0.0
    return round((PHASEOUT_END - agi) / (PHASEOUT_END - PHASEOUT_START), 3)


def rate_summary(state, year):
    rates = [r for _, r in year_cfg(state, year)["brackets"]]
    label = STATES[state]["name"]
    if len(rates) == 1:
        return f"{label} income tax rate: {rates[0]*100:.2f}% (flat)"
    return f"{label} income tax rates: {min(rates)*100:.2f}% to {max(rates)*100:.2f}% (progressive)"


def optimize_scholarship(box_1_tuition, additional_qee, box_5_scholarship, tso_current_agi,
                         tso_state_taxable, actual_1098t_8r, year=DEFAULT_YEAR, state=DEFAULT_STATE,
                         sched_1a=0):
    """sched_1a: federal Schedule 1-A deductions (tips, overtime, etc.) that reduce taxable income but not AGI."""
    fed_std = FED[year]["std"]
    ycfg = year_cfg(state, year)
    st_std = ycfg["std"]
    clean_agi = tso_current_agi - actual_1098t_8r
    clean_state_taxable = max(0, tso_state_taxable - actual_1098t_8r)
    total_qee = box_1_tuition + additional_qee
    state_adj = clean_state_taxable - (clean_agi - st_std) if clean_state_taxable > 0 else 0

    def scenario(inclusion):
        inclusion = min(inclusion, box_5_scholarship)
        agi = clean_agi + inclusion
        fed_taxable = irs_round(max(0, agi - fed_std - sched_1a))
        f_tax = fed_tax(fed_taxable, year)
        s_taxable = irs_round(max(0, agi - st_std + state_adj))
        s_tax = state_tax(s_taxable, state, year)
        tax_free_sch = max(0, box_5_scholarship - inclusion)
        qualified = max(0, total_qee - tax_free_sch)
        tentative = min(qualified, LLC_EXPENSE_CAP) * LLC_RATE
        ratio = phaseout_ratio(agi)
        after_phaseout = tentative * ratio
        credit = irs_round(min(after_phaseout, f_tax))
        if credit <= 0:
            limit = "No credit: no qualified expenses remain, no federal tax to offset, or income is above the phase-out range."
        elif ratio < 1:
            limit = "Reduced by the income phase-out (MAGI between $80,000 and $90,000)."
        elif credit < irs_round(after_phaseout):
            limit = "Limited by federal tax: the credit is nonrefundable, so it cannot exceed the tax it offsets."
        elif qualified >= LLC_EXPENSE_CAP:
            limit = "Maximum credit reached: 20% of the first $10,000 of expenses = $2,000."
        else:
            limit = "Credit is 20% of qualified expenses (not yet at the $2,000 maximum)."
        return {
            "inclusion": inclusion, "agi": agi, "sched_1a": sched_1a,
            "fed_taxable": fed_taxable, "fed_tax": f_tax,
            "state_taxable": s_taxable, "state_tax": s_tax, "credit": credit,
            "final_fed_tax": max(0, f_tax - credit),
            "net_position": credit - (f_tax + s_tax), "tax_burden": (f_tax + s_tax) - credit,
            "ts_box_5_entry": tax_free_sch, "expenses_to_claim": qualified,
            "tentative_credit": tentative, "phaseout_ratio": ratio, "limit_reason": limit,
            "fed_marginal": marginal_rate(fed_taxable, FED[year]["brackets"]),
            "state_marginal": marginal_rate(s_taxable, ycfg["brackets"]),
        }

    min_inclusion = max(0, box_5_scholarship - total_qee)
    baseline = scenario(min_inclusion)
    optimized = baseline
    max_inclusion = min(int(box_5_scholarship), int(min_inclusion) + 10000)
    for inc in range(int(min_inclusion), max_inclusion + 1):
        res = scenario(inc)
        if res["net_position"] > optimized["net_position"]:  # strict > keeps the lowest inclusion
            optimized = res
    return baseline, optimized


def prepare_baseline(mode, agi, state_taxable, ext_funding, line_8r, year, state):
    st_std = year_cfg(state, year)["std"]
    if mode == "pre":
        base_agi = agi + ext_funding
        adj = state_taxable - (agi - st_std) if state_taxable > 0 else 0
        return base_agi, max(0, base_agi - st_std + adj), 0
    return agi, state_taxable, max(0, line_8r - ext_funding)
