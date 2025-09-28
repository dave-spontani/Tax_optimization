import streamlit as st
import pandas as pd
from datetime import date
import numpy as np

st.set_page_config(page_title="Zürich Tax Deductions & Optimizer", layout="wide")

st.title("Zürich — Tax Deduction Questionnaire & Optimizer")

# --- Zurich tax calculation helpers ---
ZURICH_BASIC_BRACKETS = [
    (0, 6900, 0.0, 0.0),
    (6900, 11800, 0.0, 0.02),
    (11800, 16600, 98.0, 0.03),
    (16600, 24500, 242.0, 0.04),
    (24500, 34100, 558.0, 0.05),
    (34100, 45100, 1038.0, 0.06),
    (45100, 58000, 1698.0, 0.07),
    (58000, 75400, 2601.0, 0.08),
    (75400, 109000, 3993.0, 0.09),
    (109000, 142200, 7017.0, 0.10),
    (142200, 194900, 10337.0, 0.11),
    (194900, 263300, 16134.0, 0.12),
    (263300, 10**12, 24342.0, 0.13),
]

FEDERAL_BRACKETS = [
    (0, 14700, 0.0, 0.0),
    (14700, 31500, 0.0, 0.01),
    (31500, 41400, 168.0, 0.02),
    (41400, 52400, 384.0, 0.03),
    (52400, 75500, 714.0, 0.04),
    (75500, 103600, 1582.0, 0.055),
    (103600, 134600, 3100.0, 0.065),
    (134600, 176000, 5140.0, 0.075),
    (176000, 755000, 8360.0, 0.085),
    (755000, 10**12, 54860.0, 0.095),
]

def zurich_basic_tax(taxable_income_chf: float) -> float:
    x = max(0.0, taxable_income_chf)
    for low, high, base, pct in ZURICH_BASIC_BRACKETS:
        if x > low:
            if x <= high:
                return base + (x - low) * pct
    return 0.0

def federal_tax(taxable_income_chf: float) -> float:
    x = max(0.0, taxable_income_chf)
    for low, high, base, pct in FEDERAL_BRACKETS:
        if x > low:
            if x <= high:
                return base + (x - low) * pct
    return 0.0

MUNICIPALITIES = {
    "Zurich City": {"commune_multiplier": 1.19, "church_tax_percent": 0.5},
    "Kloten": {"commune_multiplier": 1.10, "church_tax_percent": 0.5},
    "Opfikon": {"commune_multiplier": 1.12, "church_tax_percent": 0.5},
    "Winterthur": {"commune_multiplier": 1.18, "church_tax_percent": 0.5},
}

# --- Tabs ---
tab1, tab2 = st.tabs(["Questionnaire & Estimate", "Optimizer"])

with tab1:
    st.header("Part 1 — Questionnaire")

    with st.form("qform"):
        full_name = st.text_input("Full name")
        age = st.number_input("Age", min_value=18, max_value=100, value=30)
        marital_status = st.selectbox("Marital status", ["Single", "Married"])
        has_children = st.checkbox("Do you have children?")
        employment_type = st.selectbox("Employment type", ["Employee with pension fund", "Self-employed or employee w/o pension fund"])
        municipality = st.selectbox("Municipality", list(MUNICIPALITIES.keys()), index=0)

        # Bruttoeinkommen input
        gross_income = st.number_input("Gross income (Bruttoeinkommen, CHF)", min_value=0.0, value=80000.0)

        # Auto-suggest Pillar 2 contribution based on age & gross income
        if employment_type == "Employee with pension fund":
            if age < 25:
                default_pillar2 = gross_income * 0.07
            elif age < 35:
                default_pillar2 = gross_income * 0.10
            elif age < 45:
                default_pillar2 = gross_income * 0.15
            elif age < 55:
                default_pillar2 = gross_income * 0.18
            elif age < 65:
                default_pillar2 = gross_income * 0.20
            else:
                default_pillar2 = gross_income * 0.0
        else:
            default_pillar2 = 0.0
        pillar2_contrib = st.number_input("2nd pillar contributions (CHF)", min_value=0.0, value=default_pillar2)

        # Net income field override
        net_income_override = st.number_input("Net income (after any additional deductions, optional override)", min_value=0.0, value=gross_income - pillar2_contrib)

        # Other inputs
        other_income = st.number_input("Other taxable income (CHF)", min_value=0.0, value=0.0)
        securities_value = st.number_input("Value of securities portfolio (CHF)", min_value=0.0, value=0.0)

        # --- Pauschalen defaults ---
        default_berufskosten = max(2000, min(gross_income * 0.03, 4000))
        berufskosten = st.number_input("Professional expenses (Berufskosten)", min_value=0.0, value=default_berufskosten)

        default_vm = securities_value * 0.003
        vermoegensverwaltung = st.number_input("Asset management costs (Vermögensverwaltungskosten)", min_value=0.0, value=default_vm)

        # Health insurance deduction with caps
        max_health_adult = 2900
        max_health_child = 1300
        default_health = max_health_adult if marital_status == "Single" else 2 * max_health_adult
        if has_children:
            default_health += max_health_child
        health_insurance = st.number_input(f"Health insurance premiums (max CHF {default_health})", min_value=0.0, value=default_health, max_value=default_health)
        st.caption("Note: Only mandatory basic insurance premiums are deductible. Supplementary/private insurance is not deductible.")

        default_child_deduction = 9400 if has_children else 0
        child_deduction = st.number_input("Child deduction", min_value=0.0, value=default_child_deduction)

        pillar3a = st.number_input("Voluntary Pillar 3a contributions (CHF)", min_value=0.0, value=0.0)
        charitable = st.number_input("Charitable donations (CHF)", min_value=0.0, value=0.0)

        submitted = st.form_submit_button("Estimate")

    if submitted:
        muni_info = MUNICIPALITIES[municipality]
        commune_multiplier = muni_info["commune_multiplier"]
        church_percent = muni_info["church_tax_percent"]

        # Taxable income calculation starting from Bruttoeinkommen
        total_income = gross_income + other_income
        deductions = berufskosten + vermoegensverwaltung + health_insurance + child_deduction + pillar2_contrib + pillar3a + charitable

        # If user manually overrides net income, use it instead of calculated gross - deductions
        taxable_income = net_income_override if net_income_override > 0 else max(0.0, total_income - deductions)

        canton_factor = 0.98
        basic_tax = zurich_basic_tax(taxable_income)
        cantonal_tax = basic_tax * canton_factor * commune_multiplier
        church_tax = cantonal_tax * (church_percent / 100.0)
        federal = federal_tax(taxable_income)
        total_tax = cantonal_tax + church_tax + federal

        st.subheader("Estimate")
        st.write(f"Taxable income: CHF {taxable_income:,.2f}")
        st.write(f"Federal tax: CHF {federal:,.2f}")
        st.write(f"Cantonal + communal tax: CHF {cantonal_tax:,.2f}")
        st.write(f"Church tax: CHF {church_tax:,.2f}")
        st.success(f"**Estimated total tax: CHF {total_tax:,.2f}**")

        st.session_state["estimate"] = {
            "taxable_income": taxable_income,
            "total_tax": total_tax,
            "commune_multiplier": commune_multiplier,
            "church_percent": church_percent,
            "canton_factor": canton_factor
        }
# ----------------------
# Tab 2: Optimizer
# ----------------------
with tab2:
    st.header("Part 2 — Budget Optimizer (100 CHF increments)")

    if "estimate" not in st.session_state:
        st.info("Please complete Tab 1 (Questionnaire & Estimate) first and press Save & Estimate.")
    else:
        est = st.session_state["estimate"]
        st.markdown(f"Current taxable income: CHF {est['taxable_income']:,.2f} — Estimated total tax: CHF {est['total_tax']:,.2f}")

        max_budget = st.number_input("Maximum extra deduction budget (CHF)", min_value=0.0, value=5000.0, step=100.0)
        st.markdown("Choose which deduction channels to include in the optimizer (100 CHF steps):")
        inc_pillar3a = st.checkbox("Pillar 3a (additional)", value=True)
        inc_pillar2 = st.checkbox("Pillar 2 buy‑in (voluntary)", value=True)
        inc_donations = st.checkbox("Charitable donations", value=True)
        inc_moving = st.checkbox("Moving costs (job‑related)", value=False)

        selected = [k for k, v in [("Pillar 3a", inc_pillar3a), ("Pillar 2", inc_pillar2), ("Donations", inc_donations), ("Moving", inc_moving)] if v]

        if len(selected) == 0:
            st.warning("Select at least one deduction channel for the optimizer.")
        else:
            if st.button("Run Optimizer"):
                step = 100

                # Build allocation ranges per selected category
                alloc_ranges = {}
                remaining_pillar3a = max(0.0, est.get("pillar3a_cap", 0.0) - est.get("pillar3a_current", 0.0))

                for cat in selected:
                    if cat == "Pillar 3a":
                        max_alloc = min(remaining_pillar3a, max_budget)
                    else:
                        max_alloc = max_budget
                    # Build values from 0 to max_alloc inclusive in 'step' increments
                    alloc_ranges[cat] = list(np.arange(0, max_alloc + 1e-9, step).astype(int))

                # Quick check on complexity
                counts = [len(v) for v in alloc_ranges.values()]
                total_combinations = int(np.prod(counts)) if counts else 0
                if total_combinations > 200000:
                    st.error("Too many combinations to evaluate with the current budget/step/selection. Please increase step size, reduce budget or reduce number of categories.")
                else:
                    results = []

                    def calc_total_tax_from_ti(ti):
                        basic = zurich_basic_tax(ti)
                        cant = basic * est["canton_factor"] * est["commune_multiplier"]
                        ch = cant * (est["church_percent"] / 100.0)
                        fed = federal_tax(ti)
                        return cant + ch + fed

                    base_tax = est["total_tax"]

                    # iterate product of ranges
                    keys = list(alloc_ranges.keys())
                    for combo in itertools.product(*[alloc_ranges[k] for k in keys]):
                        alloc = dict(zip(keys, combo))
                        extra = sum(alloc.values())
                        if extra == 0:
                            continue
                        if extra > max_budget + 1e-9:
                            continue

                        # taxable income reduced by the sum of extra deductible allocations
                        # NOTE: pillar 3a allocation is only allowed up to remaining_pillar3a (ranges already respect that)
                        new_ti = max(0.0, est["taxable_income"] - extra)
                        new_tax = calc_total_tax_from_ti(new_ti)
                        tax_saved = base_tax - new_tax
                        net_cost = extra - tax_saved
                        results.append({
                            "Allocation": alloc,
                            "Extra": extra,
                            "Tax saved": tax_saved,
                            "Net cost": net_cost,
                            "Tax after": new_tax
                        })

                    if not results:
                        st.warning("No feasible allocations found (maybe budget = 0 or ranges empty).")
                    else:
                        df = pd.DataFrame(results)
                        df_sorted = df.sort_values(by="Net cost").reset_index(drop=True)
                        top_n = min(10, len(df_sorted))
                        st.subheader(f"Top {top_n} strategies by net cost")
                        st.dataframe(df_sorted.head(top_n).style.format({"Extra": "{:.0f}", "Tax saved": "{:.2f}", "Net cost": "{:.2f}", "Tax after": "{:.2f}"}))

                        best = df_sorted.iloc[0]
                        st.success(f"Best strategy: {best['Allocation']} → Extra CHF {best['Extra']:.0f}, Tax saved CHF {best['Tax saved']:.2f}, Net cost CHF {best['Net cost']:.2f}")

                        # Visualization: bar chart of top strategies
                        viz = df_sorted.head(top_n).copy()
                        viz["label"] = viz["Allocation"].apply(lambda x: ", ".join([f"{k}:{v}" for k, v in x.items()]))
                        viz_plot = viz.set_index("label")[["Tax saved", "Net cost"]]
                        st.bar_chart(viz_plot)

                        st.info("Notes: - Pillar 3a allocations are capped by the remaining legal allowance. - This optimizer treats all allocations as immediately deductible in the current tax year. Validate with a tax advisor before acting.")

st.markdown("---")
st.caption("This app is an estimator for exploration and optimization. Tax rules and caps change — always verify with official sources or a qualified tax professional before making tax decisions.")
