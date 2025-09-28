# zurich_tax_deductions_app.py
import streamlit as st
import pandas as pd
import numpy as np
import itertools
from datetime import date

st.set_page_config(page_title="Zürich Tax Deductions & Optimizer", layout="wide")

st.title("Zürich — Tax Deduction Questionnaire & Optimizer")
st.caption("Questionnaire (Zurich-focused) + estimate + separate Optimizer tab (100 CHF increments). This is an estimator — verify final numbers with official sources or your tax advisor.")

# ----------------------
# Tax helper functions
# ----------------------
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


# ----------------------
# Municipality defaults (example values; update if needed)
# ----------------------
MUNICIPALITIES = {
    "Zurich City": {"commune_multiplier": 1.19, "church_tax_percent": 0.50},
    "Kloten": {"commune_multiplier": 1.10, "church_tax_percent": 0.50},
    "Opfikon": {"commune_multiplier": 1.12, "church_tax_percent": 0.50},
    "Winterthur": {"commune_multiplier": 1.18, "church_tax_percent": 0.50},
    "Uster": {"commune_multiplier": 1.16, "church_tax_percent": 0.50},
    "Dübendorf": {"commune_multiplier": 1.17, "church_tax_percent": 0.50},
}

# ----------------------
# Pillar 3a caps (example values) — update per tax year
# ----------------------
PILLAR3A_CAP_EMPLOYED = 7056  # example cap for employees with pension fund
PILLAR3A_CAP_SELFEMPLOYED_PERCENT = 0.20  # example: 20% of net income (approx)

# ----------------------
# UI: Tabs
# ----------------------
tab1, tab2 = st.tabs(["Questionnaire & Estimate", "Optimizer"])

# ----------------------
# Tab 1: Questionnaire & Estimate (keeps original layout; live recalculation)
# ----------------------
with tab1:
    st.header("Part 1 — Questionnaire")

    # Use the same form layout as original, but we'll compute immediately (submit triggers saving & summary)
    with st.form("qform"):
        st.subheader("Personal & Household")
        col1, col2 = st.columns(2)
        with col1:
            full_name = st.text_input("Full name")
            birth_date = st.date_input("Birth date", value=date(1990, 1, 1))
            marital_status = st.selectbox("Marital status", ["Single", "Married / Registered partnership", "Divorced", "Widowed"])
        with col2:
            resident_since = st.date_input("Resident in Zürich since", value=date(2010, 1, 1))
            municipality = st.selectbox("Municipality (Gemeinde)", list(MUNICIPALITIES.keys()), index=0)

        st.markdown("---")
        st.subheader("Dependents")
        has_children = st.radio("Do you have children or dependents?", ["No", "Yes"], index=0)
        dependents = []
        if has_children == "Yes":
            n_children = st.number_input("Number of children/dependants", min_value=1, max_value=10, value=1)
            for i in range(int(n_children)):
                st.markdown(f"**Child / Dependent #{i+1}**")
                name_i = st.text_input(f"Name #{i+1}", key=f"child_name_{i}")
                dob_i = st.date_input(f"Birth date #{i+1}", key=f"child_dob_{i}")
                lives_with_you = st.checkbox(f"#{i+1} Lives with you?", key=f"child_live_{i}")
                support_amount = st.number_input(f"Annual support amount for #{i+1} (CHF)", min_value=0.0, value=0.0, key=f"child_support_{i}")
                dependents.append({"name": name_i, "dob": str(dob_i), "lives_with_you": lives_with_you, "support_amount": support_amount})

        st.markdown("---")
        st.subheader("Income details")
        # Gross salary (brutto) is primary
        salary = st.number_input("Employment / Salary income (CHF gross)", min_value=0.0, value=80000.0)
        other_income = st.number_input("Other taxable income (rental, investment) (CHF)", min_value=0.0, value=0.0)
        foreign_income = st.number_input("Foreign taxable income (CHF)", min_value=0.0, value=0.0)
        benefits = st.number_input("Benefits / allowances received (CHF)", min_value=0.0, value=0.0)

        st.markdown("---")
        st.subheader("Work / Employment-related costs")
        commute_mode = st.selectbox("Main commute mode", ["Public transport", "Car", "Bike / Walk", "Mixed"])
        commute_km_oneway = st.number_input("One-way commute distance (km)", min_value=0.0, value=10.0)
        work_days_per_week = st.number_input("Work days per week", min_value=1, max_value=7, value=5)
        home_office = st.radio("Do you use a home office (regularly)?", ["No", "Yes"], index=0)
        if home_office == "Yes":
            ho_area = st.number_input("Home office area (m²)", min_value=1.0, value=10.0)
            total_area = st.number_input("Total home area (m²)", min_value=10.0, value=80.0)
        else:
            ho_area = 0.0
            total_area = 0.0
        business_travel_costs = st.number_input("Business travel & overnight costs (CHF)", min_value=0.0, value=0.0)

        st.markdown("---")
        st.subheader("Insurance, Social Contributions & Pension")
        employment_type = st.selectbox("Employment type", ["Employee with pension fund", "Self-employed or employee w/o pension fund"])
        # Auto-suggest Pillar 2 from age & gross salary: show editable default
        age = st.number_input("Age", min_value=18, max_value=100, value=35)
        if employment_type == "Employee with pension fund":
            if age < 25:
                default_pillar2 = salary * 0.07
            elif age < 35:
                default_pillar2 = salary * 0.10
            elif age < 45:
                default_pillar2 = salary * 0.15
            elif age < 55:
                default_pillar2 = salary * 0.18
            elif age < 65:
                default_pillar2 = salary * 0.20
            else:
                default_pillar2 = 0.0
        else:
            default_pillar2 = 0.0
        pillar2_contrib = st.number_input("Mandatory 2nd pillar contributions (CHF)", min_value=0.0, value=round(default_pillar2, 0))
        pillar3a_current = st.number_input("Voluntary Pillar 3a contributions already this year (CHF)", min_value=0.0, value=0.0)
        # Add field for Pillar3a assets (so Vermögensverwaltung excludes these)
        pillar3a_assets = st.number_input("Value of Pillar 3a assets (CHF) — NOT included in securities for Vermögensverwaltung", min_value=0.0, value=0.0)
        private_insurance_premiums = st.number_input("Private insurance premiums (annual) (CHF) — supplementary (non-deductible)", min_value=0.0, value=300.0)

        st.markdown("---")
        st.subheader("Health, Medical & Personal Support")
        unreimbursed_medical = st.number_input("Unreimbursed medical/dental expenses (CHF)", min_value=0.0, value=0.0)
        disability_costs = st.number_input("Extra costs for disability / special care (CHF)", min_value=0.0, value=0.0)
        home_help_costs = st.number_input("Home help / nursing care costs (CHF)", min_value=0.0, value=0.0)
        childcare_costs = st.number_input("Childcare / daycare costs (CHF)", min_value=0.0, value=0.0)

        st.markdown("---")
        st.subheader("Education & Training")
        training_costs = st.number_input("Further education / professional training costs (CHF)", min_value=0.0, value=0.0)
        children_school_fees = st.number_input("Children's school / tuition fees (CHF)", min_value=0.0, value=0.0)

        st.markdown("---")
        st.subheader("Housing")
        rent_paid = st.number_input("Rent paid this year (CHF)", min_value=0.0, value=24000.0)
        mortgage_interest = st.number_input("Mortgage interest paid (CHF)", min_value=0.0, value=0.0)
        home_maintenance = st.number_input("Maintenance / renovations (deductible) (CHF)", min_value=0.0, value=0.0)
        energy_efficiency_costs = st.number_input("Energy-saving improvements (CHF)", min_value=0.0, value=0.0)

        st.markdown("---")
        st.subheader("Other deductions")
        charitable = st.number_input("Charitable donations to registered Swiss charities (CHF)", min_value=0.0, value=0.0)
        union_fees = st.number_input("Professional association / union fees (CHF)", min_value=0.0, value=0.0)
        legal_expenses = st.number_input("Legal / defense costs (CHF)", min_value=0.0, value=0.0)
        moving_costs = st.number_input("Moving costs related to new job (CHF)", min_value=0.0, value=0.0)
        municipal_fees = st.number_input("Municipal / garbage / water fees (CHF)", min_value=0.0, value=0.0)
        foreign_taxes = st.number_input("Foreign taxes paid (CHF)", min_value=0.0, value=0.0)

        st.markdown("---")
        # Pauschalen defaults (pre-filled but editable)
        st.subheader("Pauschalabzüge (defaults — editable)")
        # Berufskosten: 3% of gross salary, min 2'000, max 4'000
        default_berufskosten = max(2000, min(salary * 0.03, 4000))
        berufskosten = st.number_input("Berufskosten Pauschale (CHF)", min_value=0.0, value=round(default_berufskosten, 0))
        # Vermögensverwaltung: 0.3% of securities (exclude pillar3a assets)
        securities_total = st.number_input("Value of securities portfolio (CHF) — EXCLUDING Pillar 3a", min_value=0.0, value=0.0)
        default_vm = securities_total * 0.003
        vermoegensverwaltung = st.number_input("Vermögensverwaltungskosten Pauschale (CHF, 0.3%)", min_value=0.0, value=round(default_vm, 0))
        # Health premium caps
        max_health_adult = 2900
        max_health_child = 1300
        # count adults: married => 2 adults assumed; otherwise 1
        adults = 2 if ("Married" in marital_status) else 1
        default_health_total = adults * max_health_adult + (int(n_children) * max_health_child if has_children == "Yes" else 0)
        # input capped at default_health_total
        health_insurance = st.number_input(f"Health insurance premiums deductible (CHF) — capped at CHF {default_health_total}", min_value=0.0, value=float(default_health_total), max_value=float(default_health_total))
        st.caption("Only mandatory basic insurance premiums are deductible; supplementary/private policies are not.")

        # Child deduction default
        default_child_deduction = (9400 * int(n_children)) if has_children == "Yes" else 0
        child_deduction = st.number_input("Child deduction (CHF)", min_value=0.0, value=float(default_child_deduction))

        # Net income override
        net_income_override = st.number_input("Net income override (optional) — put final taxable income if you prefer", min_value=0.0, value=0.0)

        submitted = st.form_submit_button("Save & Estimate")

    # end of form

    if not submitted:
        st.info("Fill the form and press 'Save & Estimate' to compute deductions and run simulations.")
    else:
        # Municipality info
        muni_info = MUNICIPALITIES.get(municipality, {"commune_multiplier": 1.0, "church_tax_percent": 0.0})
        commune_multiplier = muni_info["commune_multiplier"]
        church_percent = muni_info["church_tax_percent"]

        # enforce Pillar 3a cap
        gross_income = salary + other_income + foreign_income
        if employment_type == "Employee with pension fund":
            pillar3a_cap = PILLAR3A_CAP_EMPLOYED
        else:
            pillar3a_cap = max(0.0, gross_income * PILLAR3A_CAP_SELFEMPLOYED_PERCENT)

        if pillar3a_current > pillar3a_cap:
            st.warning(f"Pillar 3a you entered ({pillar3a_current:.2f} CHF) exceeds the estimated cap ({pillar3a_cap:.2f} CHF). We'll use the cap in estimates.")
            pillar3a_used = pillar3a_cap
        else:
            pillar3a_used = pillar3a_current

        # Calculate common deductions (conservative approximations)
        deductions = {}

        # Commute
        work_days_year = work_days_per_week * 52
        daily_commute_km = commute_km_oneway * 2
        annual_commute_km = daily_commute_km * work_days_year
        if commute_mode == "Car":
            commute_ded = min(annual_commute_km * 0.7, 3000.0)
        elif commute_mode == "Bike / Walk":
            commute_ded = min(annual_commute_km * 0.2, 1000.0)
        elif commute_mode == "Mixed":
            commute_ded = min(annual_commute_km * 0.35, 2500.0)
        else:  # Public transport — user should enter actual ticket costs in 'other' if needed
            commute_ded = 0.0
        if commute_ded > 0:
            deductions["Commute (approx)"] = round(commute_ded, 2)

        # Home office
        if home_office == "Yes" and total_area and total_area > 0:
            prop = ho_area / total_area
            ho_ded = prop * rent_paid * 0.4
            deductions["Home office (pro rata)"] = round(ho_ded, 2)

        # Pension/insurance
        if pillar3a_used > 0:
            deductions["Pillar 3a (used, capped)"] = round(pillar3a_used, 2)
        if pillar2_contrib > 0:
            deductions["Pillar 2 (mandatory)"] = round(pillar2_contrib, 2)
        if private_insurance_premiums > 0:
            # note: we store but these are typically NOT deductible except specific components
            deductions["Private insurance premiums (entered, usually not deductible)"] = round(private_insurance_premiums, 2)

        # Health & care
        if unreimbursed_medical > 0:
            deductions["Unreimbursed medical"] = round(unreimbursed_medical, 2)
        if disability_costs > 0:
            deductions["Disability / special care"] = round(disability_costs, 2)
        if home_help_costs > 0:
            deductions["Home help / nursing care"] = round(home_help_costs, 2)
        if childcare_costs > 0:
            deductions["Childcare costs"] = round(childcare_costs, 2)

        # Education
        if training_costs > 0:
            deductions["Further training"] = round(training_costs, 2)
        if children_school_fees > 0:
            deductions["Children school fees"] = round(children_school_fees, 2)

        # Housing
        if rent_paid > 0:
            deductions["Rent (info for pro rata HO)"] = round(rent_paid, 2)
        if mortgage_interest > 0:
            deductions["Mortgage interest"] = round(mortgage_interest, 2)
        if home_maintenance > 0:
            deductions["Home maintenance"] = round(home_maintenance, 2)
        if energy_efficiency_costs > 0:
            deductions["Energy improvements"] = round(energy_efficiency_costs, 2)

        # Other
        if charitable > 0:
            deductions["Charitable donations"] = round(charitable, 2)
        if union_fees > 0:
            deductions["Union / professional fees"] = round(union_fees, 2)
        if legal_expenses > 0:
            deductions["Legal expenses"] = round(legal_expenses, 2)
        if moving_costs > 0:
            deductions["Moving costs"] = round(moving_costs, 2)
        if municipal_fees > 0:
            deductions["Municipal fees"] = round(municipal_fees, 2)
        if foreign_taxes > 0:
            deductions["Foreign taxes paid"] = round(foreign_taxes, 2)
        if business_travel_costs > 0:
            deductions["Business travel & overnight"] = round(business_travel_costs, 2)

        # Pauschalen we included as inputs: Berufskosten, Vermögensverwaltung, Health, Child deduction
        if berufskosten > 0:
            deductions["Berufskosten Pauschale"] = round(berufskosten, 2)
        # Vermögensverwaltung: ensure we used securities_total EXCLUDING pillar3a_assets
        if vermoegensverwaltung > 0:
            deductions["Vermögensverwaltungskosten (Pausschale 0.3%)"] = round(vermoegensverwaltung, 2)
        if health_insurance > 0:
            deductions["Health insurance premiums (capped)"] = round(health_insurance, 2)
        if child_deduction > 0:
            deductions["Child deduction"] = round(child_deduction, 2)

        # Dependents support
        dep_support_total = sum(d.get("support_amount", 0.0) for d in dependents)
        if dep_support_total > 0:
            deductions["Dependent support (declared)"] = round(dep_support_total, 2)

        # Aggregate
        total_deductions = sum(deductions.values())
        total_income = salary + other_income + foreign_income + benefits
        taxable_income = net_income_override if net_income_override and net_income_override > 0 else max(0.0, total_income - total_deductions)

        # Canton/commune/federal tax
        canton_factor = 0.98  # default; user may change later
        basic_tax = zurich_basic_tax(taxable_income)
        cantonal_tax = basic_tax * canton_factor * commune_multiplier
        church_tax = cantonal_tax * (church_percent / 100.0)
        federal = federal_tax(taxable_income)
        total_tax = cantonal_tax + church_tax + federal

        # Display results
        st.subheader("Deductions summary")
        df_ded = pd.DataFrame([{"Deduction": k, "Amount_CHF": v} for k, v in deductions.items() if v and v > 0.0])
        if df_ded.empty:
            st.write("No deductions entered (or all values were zero).")
        else:
            st.dataframe(df_ded.style.format({"Amount_CHF": "{:.2f}"}), height=300)

        st.markdown(f"**Total estimated deductions:** CHF {total_deductions:,.2f}")
        st.markdown(f"**Total income (gross):** CHF {total_income:,.2f}")
        st.markdown(f"**Estimated taxable income (income − deductions):** CHF {taxable_income:,.2f}")

        st.subheader("Tax estimate (Federal + Cantonal + Communal + Church)")
        st.markdown(f"Municipality: **{municipality}** → Commune multiplier = {commune_multiplier:.4f}, Church tax = {church_percent:.2f}%")
        st.markdown(f"Basic canton tax (Zurich table): CHF {basic_tax:,.2f}")
        st.markdown(f"Cantonal + communal tax (after factor {canton_factor:.2f}): CHF {cantonal_tax:,.2f}")
        if church_percent > 0:
            st.markdown(f"Church tax: CHF {church_tax:,.2f}")
        st.markdown(f"Federal tax (estimate): CHF {federal:,.2f}")
        st.success(f"Estimated total tax: CHF {total_tax:,.2f}")

        # Save to session for optimizer
        st.session_state["estimate"] = {
            "taxable_income": taxable_income,
            "total_tax": total_tax,
            "basic_tax": basic_tax,
            "cantonal_tax": cantonal_tax,
            "federal": federal,
            "commune_multiplier": commune_multiplier,
            "church_percent": church_percent,
            "canton_factor": canton_factor,
            "total_income": total_income,
            "total_deductions": total_deductions,
            "pillar3a_current": pillar3a_used,
            "pillar3a_cap": pillar3a_cap,
        }

# ----------------------
# Tab 2: Optimizer (unchanged logic, uses session_state["estimate"])
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
        inc_pillar2 = st.checkbox("Pillar 2 buy-in (voluntary)", value=True)
        inc_donations = st.checkbox("Charitable donations", value=True)
        inc_moving = st.checkbox("Moving costs (job-related)", value=False)

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
                        viz["label"] = viz["Allocation"].apply(lambda x: ", ".join([f'{k}:{v}' for k, v in x.items()]))
                        viz_plot = viz.set_index("label")[["Tax saved", "Net cost"]]
                        st.bar_chart(viz_plot)

                        st.info("Notes: - Pillar 3a allocations are capped by the remaining legal allowance.\n- This optimizer treats all allocations as immediately deductible in the current tax year. Validate with a tax advisor before acting.")
