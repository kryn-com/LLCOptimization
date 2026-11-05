# LLC Optimization - Project Notes

Streamlit tool that finds how much 1098-T scholarship to report as taxable income so a single filer gets the best
combined federal + state result from the Lifetime Learning Credit (LLC). Output is organized for entry into TaxSlayer.

Last updated: November 5, 2026

## 1. Repository layout

| File | Purpose |
|---|---|
| `app.py` | LIVE app (old version, until promoted) |
| `app_test.py` | TEST app (multi-year, multi-state version) |
| `app_old.py` | Backup of the earlier version |
| `llc_engine.py` | Tax tables, tax functions, optimizer (no Streamlit) |
| `llc_report.py` | Side-by-side rows, savings table, TaxSlayer entry steps, tie-out, client text, downloads |
| `test_llc_engine.py`, `test_llc_report.py` | pytest tests (28 at last run) |
| `requirements.txt` | Streamlit Cloud dependencies (keep pytest out of it) |

Deployment: Streamlit Community Cloud, Python 3.13 for both apps. Main file path for the live app is `app.py`;
for the test app it is `app_test.py`.

## 2. Run locally (Windows / PowerShell)

1. `.venv\Scripts\Activate.ps1`
2. `python -m pytest test_llc_engine.py test_llc_report.py -v` (naming the files avoids pytest collecting `app_test.py`)
3. `streamlit run app_test.py`

## 3. Scope

- Single filers only. LLC only (no AOTC).
- Federal + state income tax. No city taxes. New York shows a warning not to use the tool for NYC or Yonkers residents.
- Tax years 2026 (default) and 2025. States: NC (default), GA, NM, NY.
- Results compare standard TaxSlayer processing to the optimized amount. Totals are "modeled income tax" only
  (not the whole return), so the reliable number is the difference (net savings).

## 4. How the optimizer works

1. Baseline = TaxSlayer default: only scholarship above qualified expenses is taxable.
2. The optimizer tries every whole-dollar amount of extra taxable scholarship from the baseline up to $10,000 above it
   (and never above Box 5), computes federal tax, state tax and the LLC, and keeps the best net result.
   Ties keep the lowest taxable amount. A wider search changed nothing in 80 random tests.
3. LLC = 20% of qualified expenses (max $10,000 counted = $2,000), reduced by the MAGI phase-out
   ($80,000-$90,000, single, not indexed), and limited to federal tax (nonrefundable).
4. Federal tax uses the IRS $50 tax-table midpoint below $100,000 taxable income.
5. State tax is calibrated from the State Taxable Income entered from TaxSlayer, so state-specific additions and
   subtractions already in the software (for example Georgia's tips/overtime exclusions) carry through.
   If the entered state taxable income is $0, the tool assumes no state adjustments.
6. Schedule 1-A deductions (federal tips, overtime) are an optional input. They reduce federal taxable income, not AGI.

Why the strategy works: each $1 of scholarship counted as taxable frees $1 of tuition for the credit, which pays 20%.
It pays off when the combined marginal federal + state rate on the extra income is below 20%.

## 5. Tax data in use

| Item | 2025 | 2026 |
|---|---|---|
| Federal standard deduction (single) | $15,750 | $16,100 |
| Federal brackets (10/12/22/24 end at) | 11,925 / 48,475 / 103,350 / 197,300 | 12,400 / 50,400 / 105,700 / 201,775 |
| NC rate / standard deduction | 4.25% / $12,750 | 3.99% / $12,750 |
| GA rate / standard deduction | 5.19% / $12,000 | 4.99% / $15,000 |
| NM standard deduction | $15,750 | $16,100 |
| NM rates | 1.5, 3.2, 4.3, 4.7, 4.9, 5.9% | same |
| NM bracket tops | 5,500 / 16,500 / 33,500 / 66,500 / 210,000 | same |
| NY standard deduction (single) | $8,000 | $8,000 |
| NY lowest five rates | 4.0, 4.5, 5.25, 5.5, 6.0% | 3.9, 4.4, 5.15, 5.4, 5.9% |

Federal 2026 figures: IRS Rev. Proc. 2025-32. NM 2025 tax-table examples (12,050 -> 292; 25,350 -> 815; 49,950 -> 1,939)
and the over-$100,000 base amounts ($4,356 and $9,746) come from the official 2025 NM Tax Rate Table.

## 6. Open items - revisit when documents are finalized

| Item | Current assumption | Status |
|---|---|---|
| NY 2026 IT-201 instructions | $50 tax-table bands below $65,000 taxable income; bracket formula at $65,000+ | Not verified |
| NM 2026 tax rate table | $100 bands below $100,000; 2025 base amounts above it | 2026 table not yet available |
| NC 2026 D-400 and instructions | $12,750 standard deduction; Lines 14 and 15 carried over from 2025 | Not yet available |
| GA 2026 Form 500 | Generic labels; assumes tax = taxable income x rate; $15,000 standard deduction | Confirm with GA DOR |
| 2026 form line numbers | NM Lines 17-18, NY Lines 37 and 39 carried over from 2025; federal AGI is Line 11a (confirmed) | Re-check |
| TaxSlayer 2026 menu paths | Scholarships and Grants under Other Compensation; 1098-T education credit screen | Confirm in software |
| Real returns | No real 2026 returns tested yet | Compare tie-out table to TaxSlayer |

## 7. Known limits

- State credits and rebates are not modeled (for example NM rebates such as PIT-RC). Only state taxable income and tax.
- EITC and ACA premium tax credit interactions are not handled.
- Not for students who can be claimed as a dependent (they cannot claim the credit themselves; NY standard deduction also differs).
- Federal deductions other than the standard deduction and the optional Schedule 1-A amount are not modeled.
- Georgia's $1,750 tips/overtime exclusions (2026-2028) are picked up through the State Taxable Income entry,
  except when that entry is $0 (can overstate state tax by up to about $87 per $1,750 excluded).

## 8. Test cases (2026, Pre-Entry, NC unless noted)

Inputs: Box 1 $12,000; Box 5 $8,000; other expenses $0; external funding $0; AGI $28,000.

| Case | State taxable | Sched 1-A | Extra taxable scholarship | Credit (std -> opt) | Net savings |
|---|---|---|---|---|---|
| NC | 15,250 | 0 | $4,698 | $800 -> $1,740 | $204 |
| GA | 13,000 | 0 | $4,698 | $800 -> $1,740 | $158 |
| NC with tips deduction | 15,250 | 3,000 | $888 | $800 -> $978 | $57 |
| NC with large deduction | 15,250 | 12,000 | none | $0 -> $0 | $0 (no optimization) |

Hand check (NC, no deduction): AGI 28,000 - 16,100 = 11,900 taxable; table midpoint 11,925 x 10% = 1,193 federal tax;
15,250 x 3.99% = 608 NC tax; credit 20% x $4,000 = $800.

## 9. Git workflow

1. `git checkout -b <branch>` from `main`
2. Make changes, run tests, run the app locally
3. `git add .` then `git status` (confirm `.venv` and `app.py` are not listed)
4. `git commit -m "message"` then `git push -u origin <branch>`
5. Open a pull request on GitHub, check Files changed, merge
6. Streamlit Cloud redeploys the app tracking `main` (reboot from Manage app if it does not)

To promote the test version: copy `app_test.py` over `app.py` on a new branch and merge. Keep `app_old.py` as a fallback.

## 10. New tax year checklist

1. Add the year to `FED` (standard deduction and brackets) in `llc_engine.py`.
2. Add the year under each state in `STATES` (standard deduction, brackets, tax-table bands).
3. Confirm the LLC phase-out limits ($80,000-$90,000 single) and the $10,000 expense cap.
4. Update form line labels and TaxSlayer menu paths.
5. Update the tax-year choices in the sidebar of the app file.
6. Add tests for the new constants and run the full suite.
7. Test against real returns before promoting.
