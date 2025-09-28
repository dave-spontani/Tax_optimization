import streamlit as st
import pandas as pd

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
    "Dübendorf": {"commune_multiplier": 1.08, "church_tax_percent": 0.5},
    "Uster": {"commune_multiplier": 1.15, "church_tax_percent": 0.5},
    "Wiedikon": {"commune_multiplier": 1.19, "church_tax_percent": 0.5},  # Uses Zurich City rates
}

# --- Tabs ---
tab1, tab2 = st.tabs(["Questionnaire & Estimate", "Optimizer"])

with tab1:
    st.header("Part 1 — Questionnaire")

    full_name = st.text_input("Full name")
    age = st.number_input("Age", min_value=18, max_value=100, value=30)
    marital_status = st.selectbox("Marital status", ["Single", "Married"])
    has_children = st.checkbox("Do you have children?")
    employment_type = st.selectbox("Employment type", ["Employee with pension fund", "Self-employed or employee w/o pension fund"])
    municipality = st.selectbox("Municipality", list(MUNICIPALITIES.keys()), index=0)

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
            default_pillar2 = 0.0
    else:
        default_pillar2 = 0.0
    pillar2_contrib = st.number_input("2nd pillar contributions (CHF)", min_value=0.0, value=default_pillar2)

    net_income_override = st.number_input("Net income (after any additional deductions, optional override)", min_value=0.0, value=gross_income - pillar2_contrib)

    other_income = st.number_input("Other taxable income (CHF)", min_value=0.0, value=0.0)
    securities_value = st.number_input("Value of securities portfolio (CHF)", min_value=0.0, value=0.0)

    # --- Pauschalen defaults ---
    default_berufskosten = max(2000, min(gross_income * 0.03, 4000))
    berufskosten = st.number_input("Professional expenses (Berufskosten)", min_value=0.0, value=default_berufskosten)

    default_vm = securities_value * 0.003
    vermoegensverwaltung = st.number_input("Asset management costs (Vermögensverwaltungskosten)", min_value=0.0, value=default_vm)

    max_health_adult = 2900
    max_health_child = 1300
    default_health = max_health_adult if marital_status == "Single" else 2 * max_health_adult
    if has_children:
        default_health += max_health_child
    health_insurance = st.number_input(label= "Deductions here",min_value = 0.0, value=float(default_health))
    st.caption("Note: Only mandatory basic insurance premiums are deductible. Supplementary/private insurance is not deductible.")

    default_child_deduction = 9400 if has_children else 0
    child_deduction = st.number_input(label= "Child deductions", min_value=0.0, value=float(default_child_deduction))

    pillar3a = st.number_input("Voluntary Pillar 3a contributions (CHF)", min_value=0.0, value=0.0)
    charitable = st.number_input("Charitable donations (CHF)", min_value=0.0, value=0.0)

    # --- Tax calculation ---
    muni_info = MUNICIPALITIES[municipality]
    commune_multiplier = muni_info["commune_multiplier"]
    church_percent = muni_info["church_tax_percent"]

    total_income = gross_income + other_income
    deductions = berufskosten + vermoegensverwaltung + health_insurance + child_deduction + pillar2_contrib + pillar3a + charitable
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

with tab2:
    st.header("Part 2 — Budget Optimizer")
    if "estimate" not in st.session_state:
        st.info("Please first fill out the questionnaire and calculate an estimate in Tab 1.")
    else:
        est = st.session_state["estimate"]
        max_budget = st.number_input("Maximum extra deduction budget (CHF)", min_value=0.0, value=5000.0, step=100.0)
        categories = [
            st.checkbox("Pillar 3a"),
            st.checkbox("Pillar 2 buy-in"),
            st.checkbox("Charitable donations"),
            st.checkbox("Moving costs")
        ]
        labels = ["Pillar 3a", "Pillar 2", "Donations", "Moving"]
        selected = [labels[i] for i, c in enumerate(categories) if c]

        if st.button("Run Optimizer"):
            results = []
            step = 100

            def calc_total_tax(ti):
                basic = zurich_basic_tax(ti)
                cant = basic * est["canton_factor"] * est["commune_multiplier"]
                ch = cant * (est["church_percent"] / 100.0)
                fed = federal_tax(ti)
                return cant + ch + fed

            base_tax = est["total_tax"]

            for a in range(0, int(max_budget)+1, step):
                for b in range(0, int(max_budget)+1-a, step):
                    for c in range(0, int(max_budget)+1-a-b, step):
                        d = max_budget - (a+b+c)
                        alloc = {"Pillar 3a":a, "Pillar 2":b, "Donations":c, "Moving":d}
                        alloc = {k:v for k,v in alloc.items() if k in selected}
                        extra = sum(alloc.values())
                        if extra == 0:
                            continue
                        ti = max(0.0, est["taxable_income"] - extra)
                        tax = calc_total_tax(ti)
                        tax_saved = base_tax - tax
                        net_cost = extra - tax_saved
                        results.append({"Allocation": str(alloc), "Extra": extra, "Tax saved": tax_saved, "Net cost": net_cost})

            if results:
                df = pd.DataFrame(results).sort_values("Net cost").head(5)
                st.subheader("Top strategies")
                st.dataframe(df.style.format({"Extra":"{:.0f}", "Tax saved":"{:.0f}", "Net cost":"{:.0f}"}))
                best = df.iloc[0]
                st.success(f"Best strategy: {best['Allocation']} — Net cost {best['Net cost']:.2f} CHF, Tax saved {best['Tax saved']:.2f} CHF")
            else:
                st.warning("No allocations tested. Please select at least one category.")