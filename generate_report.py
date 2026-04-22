"""Generate PDF report and CSV for NC Medicaid Humira Biosimilar Cost Analysis."""

import csv
import os
from datetime import date

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from fpdf import FPDF


# ─── DATA ────────────────────────────────────────────────────────────────────

HUMIRA_UNITS = 44_310
HUMIRA_RX = 16_238
HUMIRA_GROSS_TOTAL = 171_393_345.13
HUMIRA_GROSS_MEDICAID = 167_145_048.75
HUMIRA_COST_PER_UNIT = HUMIRA_GROSS_TOTAL / HUMIRA_UNITS

NADAC_HUMIRA = 3362.70

BIOSIMILAR_NADAC = {
    "Simlandi(CF) 40mg": 479.27,
    "Yusimry(CF) 40mg": 604.15,
    "Adalimumab-adbm (generic Cyltezo)": 636.04,
    "Hadlima(CF) 40mg": 1260.33,
}

# ─── HISTORICAL TREND DATA ───────────────────────────────────────────────────

HISTORICAL = {
    "CY2022": {"units": 38_450, "rx": 14_665, "total": 141_132_925, "medicaid": 139_855_696, "cpu": 3670.60},
    "CY2023": {"units": 45_213, "rx": 16_482, "total": 175_443_208, "medicaid": 172_953_312, "cpu": 3880.35},
    "CY2024": {"units": 44_310, "rx": 16_238, "total": 171_393_345, "medicaid": 167_145_049, "cpu": 3868.05},
}

# ─── SFY PROJECTION DATA ────────────────────────────────────────────────────
# NC SFY runs July 1 - June 30
# PDL change effective January 1, 2026
# Base quarterly run rate from CY2024

QUARTERLY_UNITS = HUMIRA_UNITS / 4  # ~11,078 units/quarter
QUARTERLY_SPEND = HUMIRA_GROSS_TOTAL / 4  # ~$42.85M/quarter
HUMIRA_ANNUAL_INFLATION = 0.02  # 2% annual price growth for Humira
BIOSIMILAR_ANNUAL_DEFLATION = 0.05  # 5% annual price decline for biosimilars (competition)

# Biosimilar adoption ramp by quarter (% of adalimumab volume)
# Three scenarios based on other states' PDL change experiences
ADOPTION_SCENARIOS = {
    "Conservative": {
        # SFY26 (Jul 2025 - Jun 2026)
        "SFY26_Q1": 0.00,  # Jul-Sep 2025: pre-PDL change
        "SFY26_Q2": 0.00,  # Oct-Dec 2025: pre-PDL change
        "SFY26_Q3": 0.05,  # Jan-Mar 2026: PDL change, early adopters
        "SFY26_Q4": 0.10,  # Apr-Jun 2026: slow ramp
        # SFY27 (Jul 2026 - Jun 2027)
        "SFY27_Q1": 0.15,
        "SFY27_Q2": 0.20,
        "SFY27_Q3": 0.25,
        "SFY27_Q4": 0.30,
    },
    "Moderate": {
        "SFY26_Q1": 0.00,
        "SFY26_Q2": 0.00,
        "SFY26_Q3": 0.10,
        "SFY26_Q4": 0.20,
        "SFY27_Q1": 0.30,
        "SFY27_Q2": 0.40,
        "SFY27_Q3": 0.50,
        "SFY27_Q4": 0.55,
    },
    "Aggressive": {
        "SFY26_Q1": 0.00,
        "SFY26_Q2": 0.00,
        "SFY26_Q3": 0.15,
        "SFY26_Q4": 0.30,
        "SFY27_Q1": 0.45,
        "SFY27_Q2": 0.55,
        "SFY27_Q3": 0.65,
        "SFY27_Q4": 0.75,
    },
}

SFY_QUARTERS = [
    ("SFY26_Q1", "Jul-Sep 2025", "SFY26"),
    ("SFY26_Q2", "Oct-Dec 2025", "SFY26"),
    ("SFY26_Q3", "Jan-Mar 2026", "SFY26"),
    ("SFY26_Q4", "Apr-Jun 2026", "SFY26"),
    ("SFY27_Q1", "Jul-Sep 2026", "SFY27"),
    ("SFY27_Q2", "Oct-Dec 2026", "SFY27"),
    ("SFY27_Q3", "Jan-Mar 2027", "SFY27"),
    ("SFY27_Q4", "Apr-Jun 2027", "SFY27"),
]


def compute_sfy_quarter(q_key, bio_pct, quarters_from_base=0):
    """Compute costs for a single SFY quarter with price inflation/deflation."""
    years_out = quarters_from_base / 4
    humira_cpu = HUMIRA_COST_PER_UNIT * (1 + HUMIRA_ANNUAL_INFLATION) ** years_out
    bio_cpu = BIOSIMILAR_COST_PER_UNIT * (1 - BIOSIMILAR_ANNUAL_DEFLATION) ** years_out

    humira_u = QUARTERLY_UNITS * (1 - bio_pct)
    bio_u = QUARTERLY_UNITS * bio_pct

    gross_humira = humira_u * humira_cpu
    gross_bio = bio_u * bio_cpu
    gross_total = gross_humira + gross_bio
    # Baseline = no biosimilar shift, same quarter inflation
    baseline = QUARTERLY_UNITS * humira_cpu
    savings = baseline - gross_total

    return {
        "q_key": q_key,
        "bio_pct": bio_pct,
        "humira_cpu": humira_cpu,
        "bio_cpu": bio_cpu,
        "humira_units": humira_u,
        "bio_units": bio_u,
        "gross_humira": gross_humira,
        "gross_bio": gross_bio,
        "gross_total": gross_total,
        "baseline": baseline,
        "savings": savings,
        "state_cost": gross_total * STATE_SHARE,
        "state_savings": savings * STATE_SHARE,
    }


def compute_sfy_projection(scenario_name):
    """Compute full SFY26+SFY27 projection for a given adoption scenario."""
    adoption = ADOPTION_SCENARIOS[scenario_name]
    quarters = []
    for i, (q_key, q_label, sfy) in enumerate(SFY_QUARTERS):
        bio_pct = adoption[q_key]
        q = compute_sfy_quarter(q_key, bio_pct, quarters_from_base=i)
        q["label"] = q_label
        q["sfy"] = sfy
        quarters.append(q)
    return quarters

AVG_BIOSIMILAR_NADAC = sum(BIOSIMILAR_NADAC.values()) / len(BIOSIMILAR_NADAC)
NADAC_DISCOUNT = 1 - (AVG_BIOSIMILAR_NADAC / NADAC_HUMIRA)
BIOSIMILAR_COST_PER_UNIT = HUMIRA_COST_PER_UNIT * (AVG_BIOSIMILAR_NADAC / NADAC_HUMIRA)

STATE_SHARE = 0.30

SCENARIOS = [
    ("0% Biosimilar (Baseline)", 0.00),
    ("25% Biosimilar Shift", 0.25),
    ("50% Biosimilar Shift", 0.50),
    ("75% Biosimilar Shift", 0.75),
]

PDL_PREFERRED_BIOSIMILARS = [
    ("adalimumab-adbm", "Cyltezo (generic)", "Pen / Syringe"),
    ("adalimumab-afzb", "Abrilada", "Pen / Syringe"),
    ("adalimumab-bwwd", "Hadlima", "Syringe / PushTouch"),
    ("adalimumab-advo", "Pyzchiva", "Syringe / Vial"),
    ("adalimumab-ryvk", "Simlandi", "Autoinjector / Vial"),
]

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))


def fmt_dollars(val):
    if abs(val) >= 1_000_000:
        return f"${val:,.0f}"
    return f"${val:,.2f}"


def compute_scenario(bio_pct):
    humira_pct = 1 - bio_pct
    humira_u = HUMIRA_UNITS * humira_pct
    bio_u = HUMIRA_UNITS * bio_pct
    gross_humira = humira_u * HUMIRA_COST_PER_UNIT
    gross_bio = bio_u * BIOSIMILAR_COST_PER_UNIT
    gross_total = gross_humira + gross_bio
    state_cost = gross_total * STATE_SHARE
    savings = HUMIRA_GROSS_TOTAL - gross_total
    state_savings = savings * STATE_SHARE
    return {
        "humira_units": humira_u,
        "bio_units": bio_u,
        "gross_humira": gross_humira,
        "gross_bio": gross_bio,
        "gross_total": gross_total,
        "state_cost": state_cost,
        "savings": savings,
        "state_savings": state_savings,
        "pct_savings": (savings / HUMIRA_GROSS_TOTAL * 100) if savings > 0 else 0,
    }


# ─── CHARTS ──────────────────────────────────────────────────────────────────

def generate_charts():
    chart_paths = {}

    # Chart 1: Scenario comparison bar chart
    fig, ax = plt.subplots(figsize=(8, 4.5))
    labels = []
    gross_vals = []
    state_vals = []
    for label, bio_pct in SCENARIOS:
        s = compute_scenario(bio_pct)
        short = label.replace(" (Baseline)", "").replace(" Shift", "")
        labels.append(short)
        gross_vals.append(s["gross_total"] / 1e6)
        state_vals.append(s["state_cost"] / 1e6)

    x = range(len(labels))
    bars1 = ax.bar([i - 0.18 for i in x], gross_vals, 0.35, label="Total Gross Cost", color="#2c5f8a")
    bars2 = ax.bar([i + 0.18 for i in x], state_vals, 0.35, label="State Share (30%)", color="#c44e52")

    ax.set_ylabel("Cost ($ Millions)", fontsize=11)
    ax.set_title("NC Medicaid Adalimumab Cost by Biosimilar Adoption Scenario", fontsize=12, fontweight="bold")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, fontsize=9)
    ax.legend(fontsize=9)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"${v:,.0f}M"))
    ax.set_ylim(0, max(gross_vals) * 1.15)

    for bar, val in zip(bars1, gross_vals):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 2,
                f"${val:.0f}M", ha="center", va="bottom", fontsize=8, fontweight="bold")
    for bar, val in zip(bars2, state_vals):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 2,
                f"${val:.0f}M", ha="center", va="bottom", fontsize=8, fontweight="bold")

    plt.tight_layout()
    p1 = os.path.join(OUTPUT_DIR, "_chart_scenarios.png")
    fig.savefig(p1, dpi=150)
    plt.close(fig)
    chart_paths["scenarios"] = p1

    # Chart 2: NADAC pricing comparison
    fig2, ax2 = plt.subplots(figsize=(8, 3.8))
    products = list(BIOSIMILAR_NADAC.keys()) + ["Humira(CF) Pen 40mg"]
    prices = list(BIOSIMILAR_NADAC.values()) + [NADAC_HUMIRA]
    colors = ["#4c9a6e"] * len(BIOSIMILAR_NADAC) + ["#c44e52"]

    bars = ax2.barh(products, prices, color=colors)
    ax2.set_xlabel("NADAC per Unit ($)", fontsize=11)
    ax2.set_title("NADAC Pricing: Humira vs. Co-Preferred Biosimilars", fontsize=12, fontweight="bold")
    ax2.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"${v:,.0f}"))

    for bar, price in zip(bars, prices):
        ax2.text(bar.get_width() + 50, bar.get_y() + bar.get_height() / 2,
                 f"${price:,.0f}", va="center", fontsize=9)

    plt.tight_layout()
    p2 = os.path.join(OUTPUT_DIR, "_chart_nadac.png")
    fig2.savefig(p2, dpi=150)
    plt.close(fig2)
    chart_paths["nadac"] = p2

    # Chart 3: State savings by scenario
    fig3, ax3 = plt.subplots(figsize=(7, 4))
    pcts = [s[1] * 100 for s in SCENARIOS]
    state_savings = [compute_scenario(s[1])["state_savings"] / 1e6 for s in SCENARIOS]

    ax3.fill_between(pcts, state_savings, alpha=0.3, color="#2c5f8a")
    ax3.plot(pcts, state_savings, "o-", color="#2c5f8a", linewidth=2, markersize=8)

    for p, sv in zip(pcts, state_savings):
        if sv > 0:
            ax3.annotate(f"${sv:.1f}M", (p, sv), textcoords="offset points",
                         xytext=(0, 12), ha="center", fontsize=10, fontweight="bold")

    ax3.set_xlabel("% of Humira Volume Shifted to Biosimilars", fontsize=11)
    ax3.set_ylabel("Estimated State Gross Savings ($ Millions)", fontsize=11)
    ax3.set_title("Potential State Share Savings by Biosimilar Adoption Rate", fontsize=12, fontweight="bold")
    ax3.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"${v:,.0f}M"))
    ax3.set_xlim(-5, 80)
    ax3.set_ylim(bottom=-1)

    plt.tight_layout()
    p3 = os.path.join(OUTPUT_DIR, "_chart_state_savings.png")
    fig3.savefig(p3, dpi=150)
    plt.close(fig3)
    chart_paths["state_savings"] = p3

    # Chart 4: Historical trend
    fig4, ax4 = plt.subplots(figsize=(7, 4))
    years = list(HISTORICAL.keys())
    totals = [HISTORICAL[y]["total"] / 1e6 for y in years]
    units = [HISTORICAL[y]["units"] / 1000 for y in years]

    ax4b = ax4.twinx()
    bars4 = ax4.bar(years, totals, color="#2c5f8a", alpha=0.7, label="Gross Spend ($M)")
    line4 = ax4b.plot(years, units, "o-", color="#c44e52", linewidth=2, markersize=8, label="Units (thousands)")

    ax4.set_ylabel("Gross Spend ($ Millions)", fontsize=10, color="#2c5f8a")
    ax4b.set_ylabel("Units Reimbursed (thousands)", fontsize=10, color="#c44e52")
    ax4.set_title("NC Medicaid Humira: Historical Utilization & Spend", fontsize=12, fontweight="bold")
    ax4.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"${v:,.0f}M"))

    for bar, val in zip(bars4, totals):
        ax4.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 2,
                 f"${val:.0f}M", ha="center", va="bottom", fontsize=9, fontweight="bold")
    for yr, u in zip(years, units):
        ax4b.annotate(f"{u:.1f}K", (yr, u), textcoords="offset points",
                      xytext=(0, 10), ha="center", fontsize=9, color="#c44e52", fontweight="bold")

    ax4.set_ylim(0, max(totals) * 1.2)
    ax4b.set_ylim(0, max(units) * 1.3)
    lines_labels = [bars4] + line4
    labels_leg = ["Gross Spend ($M)", "Units (thousands)"]
    ax4.legend(lines_labels, labels_leg, loc="upper left", fontsize=8)

    plt.tight_layout()
    p4 = os.path.join(OUTPUT_DIR, "_chart_historical.png")
    fig4.savefig(p4, dpi=150)
    plt.close(fig4)
    chart_paths["historical"] = p4

    # Chart 5: SFY Quarterly Projection - Gross Cost by Scenario
    fig5, (ax5a, ax5b) = plt.subplots(1, 2, figsize=(11, 4.5))

    q_labels = [q[1] for q in SFY_QUARTERS]
    colors_sc = {"Conservative": "#4c9a6e", "Moderate": "#2c5f8a", "Aggressive": "#c44e52"}

    for sc_name, color in colors_sc.items():
        proj = compute_sfy_projection(sc_name)
        costs = [q["gross_total"] / 1e6 for q in proj]
        savings = [q["state_savings"] / 1e6 for q in proj]
        ax5a.plot(range(len(q_labels)), costs, "o-", color=color, linewidth=2, markersize=5, label=sc_name)
        ax5b.plot(range(len(q_labels)), savings, "o-", color=color, linewidth=2, markersize=5, label=sc_name)

    # Baseline (no shift)
    baseline_costs = [QUARTERLY_UNITS * HUMIRA_COST_PER_UNIT * (1 + HUMIRA_ANNUAL_INFLATION) ** (i / 4) / 1e6
                      for i in range(8)]
    ax5a.plot(range(8), baseline_costs, "--", color="gray", linewidth=1.5, label="No Shift (Baseline)")

    ax5a.set_xticks(range(len(q_labels)))
    ax5a.set_xticklabels(q_labels, rotation=45, ha="right", fontsize=7)
    ax5a.set_ylabel("Quarterly Gross Cost ($M)", fontsize=10)
    ax5a.set_title("Projected Quarterly Gross Cost", fontsize=11, fontweight="bold")
    ax5a.legend(fontsize=7)
    ax5a.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"${v:,.0f}M"))
    ax5a.axvline(x=1.5, color="orange", linestyle=":", alpha=0.7)
    ax5a.text(1.7, ax5a.get_ylim()[1] * 0.95, "PDL\nChange", fontsize=7, color="orange", va="top")
    ax5a.axvline(x=3.5, color="gray", linestyle=":", alpha=0.5)
    ax5a.text(3.7, ax5a.get_ylim()[1] * 0.05, "SFY27\nStart", fontsize=7, color="gray", va="bottom")

    ax5b.set_xticks(range(len(q_labels)))
    ax5b.set_xticklabels(q_labels, rotation=45, ha="right", fontsize=7)
    ax5b.set_ylabel("Quarterly State Savings ($M)", fontsize=10)
    ax5b.set_title("Projected Quarterly State Savings (30%)", fontsize=11, fontweight="bold")
    ax5b.legend(fontsize=7)
    ax5b.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"${v:,.1f}M"))
    ax5b.axvline(x=1.5, color="orange", linestyle=":", alpha=0.7)
    ax5b.axvline(x=3.5, color="gray", linestyle=":", alpha=0.5)

    plt.tight_layout()
    p5 = os.path.join(OUTPUT_DIR, "_chart_sfy_projection.png")
    fig5.savefig(p5, dpi=150)
    plt.close(fig5)
    chart_paths["sfy_projection"] = p5

    # Chart 6: Cumulative savings SFY26+SFY27 bar chart
    fig6, ax6 = plt.subplots(figsize=(8, 4.5))
    sc_names = list(ADOPTION_SCENARIOS.keys())
    sfy26_savings = []
    sfy27_savings = []
    for sc in sc_names:
        proj = compute_sfy_projection(sc)
        s26 = sum(q["state_savings"] for q in proj if q["sfy"] == "SFY26") / 1e6
        s27 = sum(q["state_savings"] for q in proj if q["sfy"] == "SFY27") / 1e6
        sfy26_savings.append(s26)
        sfy27_savings.append(s27)

    x6 = range(len(sc_names))
    b6a = ax6.bar([i - 0.18 for i in x6], sfy26_savings, 0.35, label="SFY26 State Savings", color="#4c9a6e")
    b6b = ax6.bar([i + 0.18 for i in x6], sfy27_savings, 0.35, label="SFY27 State Savings", color="#2c5f8a")

    for bar, val in zip(b6a, sfy26_savings):
        ax6.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.2,
                 f"${val:.1f}M", ha="center", va="bottom", fontsize=9, fontweight="bold")
    for bar, val in zip(b6b, sfy27_savings):
        ax6.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.2,
                 f"${val:.1f}M", ha="center", va="bottom", fontsize=9, fontweight="bold")

    # Add cumulative labels
    for i, sc in enumerate(sc_names):
        cumul = sfy26_savings[i] + sfy27_savings[i]
        ax6.text(i, max(sfy26_savings[i], sfy27_savings[i]) + 1.5,
                 f"Total: ${cumul:.1f}M", ha="center", fontsize=8, style="italic", color="#333")

    ax6.set_ylabel("State Gross Savings ($ Millions)", fontsize=11)
    ax6.set_title("Cumulative State Savings by Adoption Scenario (SFY26 + SFY27)", fontsize=12, fontweight="bold")
    ax6.set_xticks(list(x6))
    ax6.set_xticklabels(sc_names, fontsize=10)
    ax6.legend(fontsize=9)
    ax6.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"${v:,.0f}M"))
    ax6.set_ylim(0, max(sfy27_savings) * 1.35)

    plt.tight_layout()
    p6 = os.path.join(OUTPUT_DIR, "_chart_cumulative_savings.png")
    fig6.savefig(p6, dpi=150)
    plt.close(fig6)
    chart_paths["cumulative_savings"] = p6

    return chart_paths


# ─── CSV ─────────────────────────────────────────────────────────────────────

def generate_csv():
    csv_path = os.path.join(OUTPUT_DIR, "nc_humira_biosimilar_analysis.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)

        w.writerow(["NC Medicaid Humira Biosimilar Cost Analysis"])
        w.writerow(["Generated", date.today().isoformat()])
        w.writerow(["Data Sources", "CMS State Drug Utilization Data CY2024; NADAC CY2025; NC PDL Effective 01/01/2026 (rev 03/18/2026)"])
        w.writerow([])

        # Baseline data
        w.writerow(["BASELINE UTILIZATION DATA (CY2024)"])
        w.writerow(["Metric", "Value"])
        w.writerow(["Total Humira Units Reimbursed", HUMIRA_UNITS])
        w.writerow(["Total Humira Prescriptions", HUMIRA_RX])
        w.writerow(["Gross Total Reimbursed", round(HUMIRA_GROSS_TOTAL, 2)])
        w.writerow(["Gross Medicaid Reimbursed", round(HUMIRA_GROSS_MEDICAID, 2)])
        w.writerow(["Avg Reimbursed Cost per Unit", round(HUMIRA_COST_PER_UNIT, 2)])
        w.writerow(["Avg Reimbursed Cost per Rx", round(HUMIRA_GROSS_TOTAL / HUMIRA_RX, 2)])
        w.writerow(["Existing Biosimilar Units (CY2024)", 162])
        w.writerow(["Existing Biosimilar Share", "<0.4%"])
        w.writerow([])

        # NADAC pricing
        w.writerow(["NADAC PRICING COMPARISON (2025)"])
        w.writerow(["Product", "NADAC per Unit", "Discount vs Humira"])
        w.writerow(["Humira(CF) Pen 40mg/0.4mL", NADAC_HUMIRA, "0%"])
        for name, price in sorted(BIOSIMILAR_NADAC.items(), key=lambda x: x[1]):
            disc = (1 - price / NADAC_HUMIRA) * 100
            w.writerow([name, price, f"{disc:.1f}%"])
        w.writerow(["Blended Biosimilar Average", round(AVG_BIOSIMILAR_NADAC, 2), f"{NADAC_DISCOUNT * 100:.1f}%"])
        w.writerow([])

        # PDL preferred biosimilars
        w.writerow(["NC PDL CO-PREFERRED BIOSIMILARS (Effective 01/01/2026)"])
        w.writerow(["Non-proprietary Name", "Brand Name", "Dosage Forms"])
        for nonprop, brand, forms in PDL_PREFERRED_BIOSIMILARS:
            w.writerow([nonprop, brand, forms])
        w.writerow([])

        # Scenario analysis
        w.writerow(["SCENARIO ANALYSIS"])
        w.writerow([
            "Scenario",
            "Biosimilar %",
            "Humira Units",
            "Biosimilar Units",
            "Total Units",
            "Gross Humira Cost",
            "Gross Biosimilar Cost",
            "Gross Total Cost",
            "State Share (30%)",
            "Gross Savings vs Baseline",
            "State Savings",
            "% Savings",
        ])
        for label, bio_pct in SCENARIOS:
            s = compute_scenario(bio_pct)
            w.writerow([
                label,
                f"{bio_pct * 100:.0f}%",
                round(s["humira_units"]),
                round(s["bio_units"]),
                HUMIRA_UNITS,
                round(s["gross_humira"], 2),
                round(s["gross_bio"], 2),
                round(s["gross_total"], 2),
                round(s["state_cost"], 2),
                round(s["savings"], 2),
                round(s["state_savings"], 2),
                f"{s['pct_savings']:.1f}%",
            ])
        w.writerow([])

        # Key assumptions
        w.writerow(["KEY ASSUMPTIONS"])
        w.writerow(["Assumption", "Value", "Basis"])
        w.writerow(["State Share (blended FMAP)", "30%", "User-specified blended FMAP estimate"])
        w.writerow(["Humira Reimbursed Cost/Unit", round(HUMIRA_COST_PER_UNIT, 2), "CMS SDU CY2024 actual NC data"])
        w.writerow(["Biosimilar Reimbursed Cost/Unit", round(BIOSIMILAR_COST_PER_UNIT, 2), "NADAC ratio applied to actual Humira rate"])
        w.writerow(["Total Utilization", HUMIRA_UNITS, "Held constant across scenarios (units)"])
        w.writerow(["Analysis Type", "Gross reimbursement (pre-rebate)", "Does not reflect MDRP rebates"])
        w.writerow([])

        # Historical trend
        w.writerow(["HISTORICAL TREND (CY2022-CY2024)"])
        w.writerow(["Year", "Units", "Prescriptions", "Gross Total", "Medicaid Total", "Avg Cost/Unit"])
        for yr, d in HISTORICAL.items():
            w.writerow([yr, d["units"], d["rx"], d["total"], d["medicaid"], d["cpu"]])
        w.writerow([])

        # SFY Projection - Quarterly detail for each scenario
        for sc_name in ADOPTION_SCENARIOS:
            w.writerow([f"SFY PROJECTION: {sc_name.upper()} ADOPTION SCENARIO"])
            w.writerow([
                "Quarter", "Period", "SFY", "Biosimilar %",
                "Humira Units", "Biosimilar Units",
                "Humira Cost/Unit", "Biosimilar Cost/Unit",
                "Gross Total", "Baseline (No Shift)", "Gross Savings",
                "State Cost (30%)", "State Savings (30%)",
            ])
            proj = compute_sfy_projection(sc_name)
            sfy26_total = {"gross": 0, "baseline": 0, "savings": 0, "state_cost": 0, "state_savings": 0}
            sfy27_total = {"gross": 0, "baseline": 0, "savings": 0, "state_cost": 0, "state_savings": 0}
            for q in proj:
                w.writerow([
                    q["q_key"], q["label"], q["sfy"], f"{q['bio_pct'] * 100:.0f}%",
                    round(q["humira_units"]), round(q["bio_units"]),
                    round(q["humira_cpu"], 2), round(q["bio_cpu"], 2),
                    round(q["gross_total"], 2), round(q["baseline"], 2), round(q["savings"], 2),
                    round(q["state_cost"], 2), round(q["state_savings"], 2),
                ])
                bucket = sfy26_total if q["sfy"] == "SFY26" else sfy27_total
                bucket["gross"] += q["gross_total"]
                bucket["baseline"] += q["baseline"]
                bucket["savings"] += q["savings"]
                bucket["state_cost"] += q["state_cost"]
                bucket["state_savings"] += q["state_savings"]

            w.writerow(["SFY26 TOTAL", "", "SFY26", "",
                        "", "", "", "",
                        round(sfy26_total["gross"], 2), round(sfy26_total["baseline"], 2),
                        round(sfy26_total["savings"], 2),
                        round(sfy26_total["state_cost"], 2), round(sfy26_total["state_savings"], 2)])
            w.writerow(["SFY27 TOTAL", "", "SFY27", "",
                        "", "", "", "",
                        round(sfy27_total["gross"], 2), round(sfy27_total["baseline"], 2),
                        round(sfy27_total["savings"], 2),
                        round(sfy27_total["state_cost"], 2), round(sfy27_total["state_savings"], 2)])
            cumul = {k: sfy26_total[k] + sfy27_total[k] for k in sfy26_total}
            w.writerow(["CUMULATIVE", "", "SFY26+27", "",
                        "", "", "", "",
                        round(cumul["gross"], 2), round(cumul["baseline"], 2),
                        round(cumul["savings"], 2),
                        round(cumul["state_cost"], 2), round(cumul["state_savings"], 2)])
            w.writerow([])

        # Projection assumptions
        w.writerow(["SFY PROJECTION ASSUMPTIONS"])
        w.writerow(["Assumption", "Value", "Basis"])
        w.writerow(["Quarterly base units", round(QUARTERLY_UNITS), "CY2024 annual / 4"])
        w.writerow(["Humira annual price inflation", f"{HUMIRA_ANNUAL_INFLATION*100:.0f}%", "Conservative estimate based on CY2022-2024 trend"])
        w.writerow(["Biosimilar annual price deflation", f"{BIOSIMILAR_ANNUAL_DEFLATION*100:.0f}%", "Expected competitive price erosion"])
        w.writerow(["PDL change effective date", "January 1, 2026", "NC PDL revision"])
        w.writerow(["NC SFY", "July 1 - June 30", ""])

    return csv_path


# ─── PDF ─────────────────────────────────────────────────────────────────────

class ReportPDF(FPDF):

    def header(self):
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(120, 120, 120)
        self.cell(0, 5, "NC Medicaid Humira Biosimilar Transition Cost Analysis", align="L")
        self.cell(0, 5, f"Prepared {date.today().strftime('%B %d, %Y')}", align="R", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(180, 180, 180)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(3)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")

    def section_title(self, title):
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(30, 60, 110)
        self.cell(0, 9, title, new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(30, 60, 110)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)

    def sub_title(self, title):
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(60, 60, 60)
        self.cell(0, 7, title, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def body_text(self, text):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(40, 40, 40)
        self.multi_cell(0, 5, text)
        self.ln(2)

    def kv_row(self, key, value, bold_val=False):
        self.set_font("Helvetica", "", 9)
        self.set_text_color(60, 60, 60)
        self.cell(90, 5.5, f"  {key}", border=0)
        self.set_font("Helvetica", "B" if bold_val else "", 9)
        self.set_text_color(30, 30, 30)
        self.cell(0, 5.5, str(value), new_x="LMARGIN", new_y="NEXT")

    def table_header(self, cols, widths):
        self.set_font("Helvetica", "B", 8)
        self.set_fill_color(30, 60, 110)
        self.set_text_color(255, 255, 255)
        for col, w in zip(cols, widths):
            self.cell(w, 6, col, border=1, fill=True, align="C")
        self.ln()

    def table_row(self, vals, widths, aligns=None, highlight=False):
        self.set_font("Helvetica", "B" if highlight else "", 8)
        if highlight:
            self.set_fill_color(235, 245, 255)
        else:
            self.set_fill_color(255, 255, 255)
        self.set_text_color(30, 30, 30)
        if aligns is None:
            aligns = ["L"] * len(vals)
        for val, w, a in zip(vals, widths, aligns):
            self.cell(w, 5.5, str(val), border=1, fill=highlight, align=a)
        self.ln()


def generate_pdf(chart_paths):
    pdf = ReportPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)

    # ── Page 1: Title + Executive Summary ────────────────────────────────
    pdf.add_page()
    pdf.ln(15)
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(30, 60, 110)
    pdf.cell(0, 12, "NC Medicaid", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 12, "Humira Biosimilar Transition", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 12, "Cost Analysis", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 7, "Evaluating the Fiscal Impact of NC PDL Policy Change", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, "Making Adalimumab Biosimilars Co-Preferred", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(10)
    pdf.set_draw_color(30, 60, 110)
    pdf.line(60, pdf.get_y(), 150, pdf.get_y())
    pdf.ln(10)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(60, 60, 60)
    pdf.cell(0, 6, f"Report Date: {date.today().strftime('%B %d, %Y')}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, "Data Sources: CMS State Drug Utilization Data CY2024, NADAC CY2025", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, "NC PDL Effective January 1, 2026 (revised 03/18/2026)", align="C", new_x="LMARGIN", new_y="NEXT")

    # ── Page 2: Executive Summary ────────────────────────────────────────
    pdf.add_page()
    pdf.section_title("Executive Summary")
    pdf.body_text(
        "The North Carolina Division of Health Benefits revised its Preferred Drug List (PDL) "
        "effective January 1, 2026 to make multiple adalimumab biosimilars co-preferred alongside "
        "Humira in the Cytokine and CAM Antagonists therapeutic class. This analysis estimates "
        "the gross reimbursement impact of shifting Humira utilization to biosimilars at varying "
        "adoption rates using CMS State Drug Utilization Data (CY2024) and NADAC pricing (CY2025)."
    )
    pdf.body_text(
        "Key findings: NC Medicaid spent $171.4 million (gross) on Humira in CY2024 across "
        "44,310 units and 16,238 prescriptions. Biosimilar utilization was negligible (<0.4% of "
        "the adalimumab market). Co-preferred biosimilars carry NADAC prices 63-86% below Humira, "
        "with a blended average discount of 78%. At a 50% biosimilar adoption rate, estimated "
        "gross savings would be $66.7 million annually ($20.0 million state share at 30% FMAP)."
    )
    pdf.body_text(
        "IMPORTANT: These estimates reflect gross reimbursement costs only. Humira's lengthy "
        "market tenure (since 2002) generates substantial CPI-based Medicaid Drug Rebate Program "
        "(MDRP) rebates that significantly reduce its net cost. Biosimilars carry lower basic "
        "rebates (13% vs. 23.1%) and minimal CPI penalties. A complete net fiscal analysis "
        "requires confidential supplemental rebate data not available in public CMS datasets."
    )

    # Key metrics box
    pdf.ln(2)
    pdf.sub_title("Key Metrics at a Glance")
    pdf.kv_row("Annual Humira Gross Spend (CY2024)", "$171.4 million", bold_val=True)
    pdf.kv_row("State Share at 30% FMAP", "$51.4 million", bold_val=True)
    pdf.kv_row("Blended Biosimilar NADAC Discount", "78%", bold_val=True)
    pdf.kv_row("Potential Gross Savings at 50% Shift", "$66.7M total / $20.0M state", bold_val=True)
    pdf.kv_row("Potential Gross Savings at 75% Shift", "$100.1M total / $30.0M state", bold_val=True)
    pdf.kv_row("Current Biosimilar Market Share (NC)", "<0.4%", bold_val=True)

    # ── Page 3: PDL Policy Change + Baseline ─────────────────────────────
    pdf.add_page()
    pdf.section_title("1. Policy Change: NC PDL Revision")
    pdf.body_text(
        "The NC PDL (effective January 1, 2026, revised March 18, 2026) designates the following "
        "adalimumab biosimilars as co-preferred with Humira in the Cytokine and CAM Antagonists "
        "class. Prior authorization clinical criteria apply to all drugs in this class. Trial and "
        "failure (T/F) of one preferred drug is required."
    )

    # PDL biosimilars table
    widths_pdl = [55, 40, 45, 50]
    pdf.table_header(["Non-proprietary Name", "Brand", "Dosage Forms", "PDL Status"], widths_pdl)
    pdf.table_row(["adalimumab (Humira)", "Humira", "Pen / Syringe / Starter", "Preferred"], widths_pdl,
                  aligns=["L", "L", "L", "C"])
    for nonprop, brand, forms in PDL_PREFERRED_BIOSIMILARS:
        pdf.table_row([nonprop, brand, forms, "Preferred"], widths_pdl,
                      aligns=["L", "L", "L", "C"], highlight=True)

    pdf.ln(5)
    pdf.section_title("2. Baseline Utilization (CY2024)")
    pdf.body_text(
        "North Carolina Medicaid utilization of adalimumab products in calendar year 2024, "
        "as reported in the CMS State Drug Utilization Data, is overwhelmingly concentrated "
        "in brand Humira. Biosimilar adoption has been minimal."
    )

    pdf.sub_title("Humira Utilization Summary")
    pdf.kv_row("Total Units Reimbursed", f"{HUMIRA_UNITS:,}")
    pdf.kv_row("Total Prescriptions", f"{HUMIRA_RX:,}")
    pdf.kv_row("Gross Total Reimbursed", f"${HUMIRA_GROSS_TOTAL:,.0f}")
    pdf.kv_row("Gross Medicaid Reimbursed", f"${HUMIRA_GROSS_MEDICAID:,.0f}")
    pdf.kv_row("Avg Reimbursed Cost/Unit", f"${HUMIRA_COST_PER_UNIT:,.2f}")
    pdf.kv_row("Avg Reimbursed Cost/Rx", f"${HUMIRA_GROSS_TOTAL / HUMIRA_RX:,.2f}")

    pdf.ln(3)
    pdf.sub_title("Existing Biosimilar Utilization (CY2024)")
    widths_bio = [50, 30, 35, 40, 35]
    pdf.table_header(["Product", "Units", "Rx", "Total Reimbursed", "Avg/Unit"], widths_bio)
    pdf.table_row(["Generic adalimumab", "148", "116", "$235,021", "$1,588"], widths_bio,
                  aligns=["L", "R", "R", "R", "R"])
    pdf.table_row(["Hadlima", "14", "13", "$18,182", "$1,263"], widths_bio,
                  aligns=["L", "R", "R", "R", "R"])
    pdf.table_row(["Hyrimoz", "38", "27", "$315,830", "$8,225"], widths_bio,
                  aligns=["L", "R", "R", "R", "R"])
    pdf.ln(2)
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 5, "Biosimilars represent <0.4% of NC's total adalimumab utilization in CY2024.",
             new_x="LMARGIN", new_y="NEXT")

    # ── Page 4: NADAC Pricing ────────────────────────────────────────────
    pdf.add_page()
    pdf.section_title("3. NADAC Pricing Comparison")
    pdf.body_text(
        "The National Average Drug Acquisition Cost (NADAC) provides a benchmark for pharmacy "
        "acquisition costs. The table and chart below compare Humira and its co-preferred "
        "biosimilars at the standard 40mg dose. Biosimilar NADAC prices range from $479 to "
        "$1,260 per unit, representing discounts of 63% to 86% versus Humira."
    )

    widths_nadac = [65, 35, 30, 30, 30]
    pdf.table_header(["Product", "NADAC/Unit", "Discount", "Est. Reimb.", "Source Date"], widths_nadac)
    pdf.table_row(["Humira(CF) Pen 40mg/0.4mL", f"${NADAC_HUMIRA:,.2f}", "---",
                   f"${HUMIRA_COST_PER_UNIT:,.0f}", "2025-06"], widths_nadac,
                  aligns=["L", "R", "R", "R", "C"])
    for name, price in sorted(BIOSIMILAR_NADAC.items(), key=lambda x: x[1]):
        disc = (1 - price / NADAC_HUMIRA) * 100
        est_reimb = HUMIRA_COST_PER_UNIT * (price / NADAC_HUMIRA)
        pdf.table_row([name, f"${price:,.2f}", f"{disc:.0f}%", f"${est_reimb:,.0f}", "2025"],
                      widths_nadac, aligns=["L", "R", "R", "R", "C"], highlight=True)
    pdf.table_row(["Blended Biosimilar Average", f"${AVG_BIOSIMILAR_NADAC:,.2f}",
                   f"{NADAC_DISCOUNT * 100:.0f}%", f"${BIOSIMILAR_COST_PER_UNIT:,.0f}", "---"],
                  widths_nadac, aligns=["L", "R", "R", "R", "C"])

    pdf.ln(3)
    if "nadac" in chart_paths:
        pdf.image(chart_paths["nadac"], x=15, w=180)

    # ── Page 5: Scenario Analysis ────────────────────────────────────────
    pdf.add_page()
    pdf.section_title("4. Scenario Analysis: Gross Reimbursement Impact")
    pdf.body_text(
        "The following scenarios model the gross reimbursement impact of shifting Humira "
        "utilization to biosimilars at 0%, 25%, 50%, and 75% adoption rates. Total utilization "
        "is held constant at the CY2024 level (44,310 units). The biosimilar reimbursed cost "
        "per unit is estimated by applying the NADAC discount ratio to the actual NC Humira "
        "reimbursement rate. State share is calculated at 30% (blended FMAP)."
    )

    widths_sc = [42, 22, 30, 30, 30, 25, 11]
    pdf.table_header(["Scenario", "Bio %", "Gross Total", "State (30%)", "Gross Savings", "State Savings", "% Sav"],
                     widths_sc)
    for label, bio_pct in SCENARIOS:
        s = compute_scenario(bio_pct)
        short = label.replace(" (Baseline)", "")
        pdf.table_row([
            short,
            f"{bio_pct * 100:.0f}%",
            f"${s['gross_total'] / 1e6:.1f}M",
            f"${s['state_cost'] / 1e6:.1f}M",
            f"${s['savings'] / 1e6:.1f}M" if s["savings"] > 0 else "---",
            f"${s['state_savings'] / 1e6:.1f}M" if s["state_savings"] > 0 else "---",
            f"{s['pct_savings']:.0f}%" if s["pct_savings"] > 0 else "---",
        ], widths_sc, aligns=["L", "C", "R", "R", "R", "R", "C"],
            highlight=(bio_pct == 0.50))

    pdf.ln(5)
    if "scenarios" in chart_paths:
        pdf.image(chart_paths["scenarios"], x=12, w=185)

    # ── Page 6: State savings chart + detailed breakdown ─────────────────
    pdf.add_page()
    pdf.sub_title("State Share Savings by Adoption Rate")
    if "state_savings" in chart_paths:
        pdf.image(chart_paths["state_savings"], x=20, w=170)

    pdf.ln(5)
    pdf.sub_title("Detailed Scenario Breakdown")
    for label, bio_pct in SCENARIOS:
        s = compute_scenario(bio_pct)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(30, 60, 110)
        pdf.cell(0, 5.5, f"  {label}:", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 8.5)
        pdf.set_text_color(40, 40, 40)
        pdf.cell(0, 4.5,
                 f"    Humira: {s['humira_units']:,.0f} units x ${HUMIRA_COST_PER_UNIT:,.2f} = ${s['gross_humira']:,.0f}",
                 new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 4.5,
                 f"    Biosimilar: {s['bio_units']:,.0f} units x ${BIOSIMILAR_COST_PER_UNIT:,.2f} = ${s['gross_bio']:,.0f}",
                 new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 4.5,
                 f"    Total: ${s['gross_total']:,.0f}  |  State: ${s['state_cost']:,.0f}  |  Savings: ${s['savings']:,.0f}",
                 new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1.5)

    # ── Page 7: Rebate Considerations + Methodology ──────────────────────
    pdf.add_page()
    pdf.section_title("5. Important Caveats: Medicaid Rebate Dynamics")
    pdf.body_text(
        "The scenario analysis above reflects gross reimbursement costs. Actual Medicaid net "
        "costs are substantially affected by manufacturer rebates under the Medicaid Drug Rebate "
        "Program (MDRP). The rebate dynamics between brand and biosimilar products create a "
        "well-documented 'rebate trap' that can invert the expected cost relationship."
    )

    pdf.sub_title("Humira (Brand, on market since 2002)")
    pdf.body_text(
        "- Basic rebate: 23.1% of Average Manufacturer Price (AMP)\n"
        "- CPI penalty: Likely very large. Humira has been on the market for 20+ years with "
        "significant price increases above the Consumer Price Index. The CPI-based additional "
        "rebate accumulates over time, potentially pushing the total unit rebate amount to "
        "80-100% of AMP.\n"
        "- Net cost to Medicaid may approach near-zero after rebates."
    )

    pdf.sub_title("Biosimilars (Recently Launched)")
    pdf.body_text(
        "- Basic rebate: 13% of AMP (lower statutory rate for biosimilars)\n"
        "- CPI penalty: Minimal, as these products have been on the market only 1-3 years "
        "with limited price inflation.\n"
        "- Net cost remains close to the gross reimbursement amount."
    )

    pdf.sub_title("Implications for NC")
    pdf.body_text(
        "Shifting from Humira to biosimilars may increase net Medicaid costs in the short term "
        "due to loss of Humira's accumulated CPI rebates. However, NC's PDL decision may reflect: "
        "(1) negotiated supplemental rebates with biosimilar manufacturers that offset this gap; "
        "(2) a long-term market strategy to increase biosimilar competition and lower overall "
        "prices; (3) alignment with federal policy direction supporting biosimilar adoption; or "
        "(4) clinical policy goals around access and formulary modernization.\n\n"
        "A complete fiscal analysis requires access to North Carolina's confidential supplemental "
        "rebate data, which is not available in public CMS datasets."
    )

    # ── Page 8: Methodology ──────────────────────────────────────────────
    pdf.add_page()
    pdf.section_title("6. Methodology")

    pdf.sub_title("Data Sources")
    pdf.body_text(
        "1. CMS State Drug Utilization Data (CY2024): Quarterly utilization data reported by "
        "state Medicaid agencies to CMS, including units reimbursed, number of prescriptions, "
        "and total/Medicaid amounts reimbursed. Dataset ID: 61729e5a-7aa8-448c-8903-ba3e0cd0ea3c. "
        "Queried via the data.medicaid.gov DKAN datastore API.\n\n"
        "2. NADAC (National Average Drug Acquisition Cost) CY2025: CMS survey-based pricing "
        "reflecting the average acquisition cost paid by retail pharmacies. Dataset ID: "
        "f38d0706-1239-442c-a3cc-40ef1b686ac0. Used for biosimilar-to-brand price ratio.\n\n"
        "3. NC Preferred Drug List: 'NC PDL Effective January 1, 2026 revised 03.18.2026.pdf'. "
        "Page 23, Cytokine and CAM Antagonists class, identifies co-preferred biosimilars."
    )

    pdf.sub_title("Humira Baseline Calculation")
    pdf.body_text(
        "All CMS State Drug Utilization Data records for North Carolina with product_name "
        "containing 'HUMIRA' were aggregated across all four quarters of CY2024 and all "
        "utilization types (FFSU and MCOU). This includes Humira, Humira(CF), and Humira Pen "
        "across all NDCs and strengths. The average reimbursed cost per unit ($3,868.05) "
        "represents the actual blended rate paid by NC Medicaid across all Humira formulations."
    )

    pdf.sub_title("Biosimilar Cost Estimation")
    pdf.body_text(
        "Because NC had negligible biosimilar utilization in CY2024, the estimated biosimilar "
        "cost per unit was derived using NADAC pricing ratios rather than actual reimbursement "
        "data. The methodology:\n\n"
        "1. Identified the co-preferred biosimilars on the NC PDL with available NADAC data: "
        "Simlandi ($479/unit), Yusimry ($604/unit), adalimumab-adbm/generic Cyltezo ($636/unit), "
        "and Hadlima ($1,260/unit).\n\n"
        "2. Calculated a simple average (equal-weight) NADAC across these four products: "
        f"${AVG_BIOSIMILAR_NADAC:,.2f}/unit.\n\n"
        f"3. Computed the NADAC ratio: ${AVG_BIOSIMILAR_NADAC:,.2f} / ${NADAC_HUMIRA:,.2f} = "
        f"{AVG_BIOSIMILAR_NADAC / NADAC_HUMIRA:.4f}.\n\n"
        f"4. Applied this ratio to the actual NC Humira reimbursed cost per unit: "
        f"${HUMIRA_COST_PER_UNIT:,.2f} x {AVG_BIOSIMILAR_NADAC / NADAC_HUMIRA:.4f} = "
        f"${BIOSIMILAR_COST_PER_UNIT:,.2f}/unit."
    )

    pdf.sub_title("Scenario Modeling")
    pdf.body_text(
        "Each scenario holds total adalimumab utilization constant at 44,310 units (CY2024 "
        "Humira volume) and varies the proportion filled by biosimilars (0%, 25%, 50%, 75%). "
        "Gross reimbursement is calculated as:\n\n"
        "  Total Cost = (Humira units x $3,868.05) + (Biosimilar units x $856.90)\n\n"
        "State share is applied at 30% (user-specified blended FMAP for NC)."
    )

    pdf.sub_title("Limitations")
    pdf.body_text(
        "1. Gross costs only: Does not account for MDRP basic, CPI, or supplemental rebates. "
        "Net cost impact may differ substantially and could potentially be inverse.\n\n"
        "2. Static utilization: Assumes total adalimumab volume remains constant. Policy changes "
        "could increase or decrease total utilization.\n\n"
        "3. Equal-weight biosimilar pricing: Uses a simple average across four biosimilars. "
        "Actual market share distribution among biosimilars will affect the realized discount.\n\n"
        "4. NADAC-based estimation: Applies NADAC price ratios to estimate biosimilar "
        "reimbursement. Actual reimbursement rates will vary based on state-specific "
        "methodologies, dispensing fees, and contract terms.\n\n"
        "5. Data lag: CMS SDU data for CY2024 may not reflect the most recent quarter's "
        "revisions. NADAC rates are point-in-time and subject to weekly updates.\n\n"
        "6. Excludes managed care: MCOU records reflect managed care utilization but the "
        "rebate and cost-sharing structures within MCOs may differ from FFS."
    )

    # ── Page 9: Historical Trend ─────────────────────────────────────────
    pdf.add_page()
    pdf.section_title("7. Historical Utilization Trend (CY2022-CY2024)")
    pdf.body_text(
        "NC Medicaid Humira utilization grew significantly from CY2022 to CY2023 (+17.6% in units, "
        "+24.3% in gross spend), then stabilized in CY2024 (-2.0% in units, -2.3% in spend). "
        "Cost per unit has been relatively flat since CY2023 (~$3,870-$3,880). This trend informs "
        "the projection assumption of flat utilization and modest (~2%) annual price inflation."
    )

    widths_hist = [30, 25, 25, 35, 35, 30, 30]
    pdf.table_header(["Year", "Units", "Rx", "Gross Total", "Medicaid", "Avg/Unit", "YoY Chg"], widths_hist)
    prev_total = None
    for yr, d in HISTORICAL.items():
        yoy = f"{(d['total'] / prev_total - 1) * 100:+.1f}%" if prev_total else "---"
        pdf.table_row([yr, f"{d['units']:,}", f"{d['rx']:,}",
                       f"${d['total'] / 1e6:.1f}M", f"${d['medicaid'] / 1e6:.1f}M",
                       f"${d['cpu']:,.0f}", yoy],
                      widths_hist, aligns=["C", "R", "R", "R", "R", "R", "C"])
        prev_total = d["total"]

    pdf.ln(3)
    if "historical" in chart_paths:
        pdf.image(chart_paths["historical"], x=20, w=170)

    # ── Page 10: SFY Projection Overview ─────────────────────────────────
    pdf.add_page()
    pdf.section_title("8. SFY26-SFY27 Cost Savings Projection")
    pdf.body_text(
        "The following projections model gross cost savings through SFY27 (ending June 30, 2027) "
        "under three biosimilar adoption scenarios. The NC PDL change takes effect January 1, 2026, "
        "which falls in the second half of SFY26. Three adoption ramp scenarios reflect varying "
        "speed of biosimilar uptake after the PDL change:\n\n"
        "- Conservative: Slow adoption, reaching 30% biosimilar share by end of SFY27\n"
        "- Moderate: Steady adoption, reaching 55% by end of SFY27\n"
        "- Aggressive: Rapid adoption, reaching 75% by end of SFY27"
    )

    pdf.sub_title("Projection Assumptions")
    pdf.kv_row("Base quarterly utilization", f"{QUARTERLY_UNITS:,.0f} units (CY2024 annualized)")
    pdf.kv_row("Humira annual price inflation", f"{HUMIRA_ANNUAL_INFLATION * 100:.0f}%")
    pdf.kv_row("Biosimilar annual price deflation", f"{BIOSIMILAR_ANNUAL_DEFLATION * 100:.0f}% (competitive erosion)")
    pdf.kv_row("PDL change effective", "January 1, 2026 (SFY26 Q3)")
    pdf.kv_row("NC State Fiscal Year", "July 1 - June 30")
    pdf.kv_row("State share", f"{STATE_SHARE * 100:.0f}% (blended FMAP)")

    pdf.ln(3)
    if "sfy_projection" in chart_paths:
        pdf.image(chart_paths["sfy_projection"], x=5, w=200)

    # ── Page 11: SFY Summary Table ───────────────────────────────────────
    pdf.add_page()
    pdf.sub_title("SFY Annual Summary by Scenario")

    widths_sfy_sum = [35, 28, 28, 28, 28, 28, 15]
    pdf.table_header(["Scenario", "SFY26 Gross", "SFY26 State", "SFY27 Gross", "SFY27 State",
                       "Cumul. State", ""], widths_sfy_sum)

    for sc_name in ADOPTION_SCENARIOS:
        proj = compute_sfy_projection(sc_name)
        s26_gross = sum(q["gross_total"] for q in proj if q["sfy"] == "SFY26")
        s26_savings = sum(q["state_savings"] for q in proj if q["sfy"] == "SFY26")
        s27_gross = sum(q["gross_total"] for q in proj if q["sfy"] == "SFY27")
        s27_savings = sum(q["state_savings"] for q in proj if q["sfy"] == "SFY27")
        cumul = s26_savings + s27_savings
        pdf.table_row([
            sc_name,
            f"${s26_savings / 1e6:.1f}M",
            f"${s26_savings / 1e6:.1f}M",
            f"${s27_savings / 1e6:.1f}M",
            f"${s27_savings / 1e6:.1f}M",
            f"${cumul / 1e6:.1f}M",
            "",
        ], widths_sfy_sum, aligns=["L", "R", "R", "R", "R", "R", "C"],
            highlight=(sc_name == "Moderate"))

    # Baseline row
    proj_base = compute_sfy_projection("Moderate")
    s26_base = sum(q["baseline"] for q in proj_base if q["sfy"] == "SFY26")
    s27_base = sum(q["baseline"] for q in proj_base if q["sfy"] == "SFY27")
    pdf.table_row([
        "No Shift (Base)", f"${s26_base / 1e6:.1f}M", "---",
        f"${s27_base / 1e6:.1f}M", "---", "---", "",
    ], widths_sfy_sum, aligns=["L", "R", "R", "R", "R", "R", "C"])

    pdf.ln(3)
    if "cumulative_savings" in chart_paths:
        pdf.image(chart_paths["cumulative_savings"], x=12, w=185)

    # ── Page 12-13: Quarterly Detail ─────────────────────────────────────
    for sc_name in ADOPTION_SCENARIOS:
        pdf.add_page()
        pdf.sub_title(f"Quarterly Detail: {sc_name} Adoption Scenario")

        proj = compute_sfy_projection(sc_name)

        # Adoption ramp description
        adoption = ADOPTION_SCENARIOS[sc_name]
        ramp_desc = ", ".join(
            f"{adoption[q[0]] * 100:.0f}%" for q in SFY_QUARTERS
        )
        pdf.set_font("Helvetica", "I", 8.5)
        pdf.set_text_color(80, 80, 80)
        pdf.cell(0, 4.5, f"  Quarterly biosimilar share ramp: {ramp_desc}",
                 new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

        widths_qd = [24, 12, 24, 24, 24, 24, 24, 24]
        pdf.table_header(["Quarter", "Bio%", "Humira $", "Biosim $", "Gross Total",
                           "Baseline", "Savings", "State Sav"], widths_qd)

        sfy26_tot = {"gross": 0, "base": 0, "sav": 0, "st_sav": 0}
        sfy27_tot = {"gross": 0, "base": 0, "sav": 0, "st_sav": 0}

        for q in proj:
            is_sfy27_start = q["q_key"] == "SFY27_Q1"
            if is_sfy27_start and sfy26_tot["gross"] > 0:
                # Print SFY26 subtotal
                pdf.table_row([
                    "SFY26 Total", "", "", "",
                    f"${sfy26_tot['gross'] / 1e6:.1f}M",
                    f"${sfy26_tot['base'] / 1e6:.1f}M",
                    f"${sfy26_tot['sav'] / 1e6:.1f}M",
                    f"${sfy26_tot['st_sav'] / 1e6:.1f}M",
                ], widths_qd, aligns=["L", "C", "R", "R", "R", "R", "R", "R"], highlight=True)

            pdf.table_row([
                q["label"],
                f"{q['bio_pct'] * 100:.0f}%",
                f"${q['gross_humira'] / 1e6:.1f}M",
                f"${q['gross_bio'] / 1e6:.1f}M",
                f"${q['gross_total'] / 1e6:.1f}M",
                f"${q['baseline'] / 1e6:.1f}M",
                f"${q['savings'] / 1e6:.1f}M",
                f"${q['state_savings'] / 1e6:.1f}M",
            ], widths_qd, aligns=["L", "C", "R", "R", "R", "R", "R", "R"])

            bucket = sfy26_tot if q["sfy"] == "SFY26" else sfy27_tot
            bucket["gross"] += q["gross_total"]
            bucket["base"] += q["baseline"]
            bucket["sav"] += q["savings"]
            bucket["st_sav"] += q["state_savings"]

        # Print SFY27 subtotal
        pdf.table_row([
            "SFY27 Total", "", "", "",
            f"${sfy27_tot['gross'] / 1e6:.1f}M",
            f"${sfy27_tot['base'] / 1e6:.1f}M",
            f"${sfy27_tot['sav'] / 1e6:.1f}M",
            f"${sfy27_tot['st_sav'] / 1e6:.1f}M",
        ], widths_qd, aligns=["L", "C", "R", "R", "R", "R", "R", "R"], highlight=True)

        # Cumulative
        cumul_gross = sfy26_tot["gross"] + sfy27_tot["gross"]
        cumul_base = sfy26_tot["base"] + sfy27_tot["base"]
        cumul_sav = sfy26_tot["sav"] + sfy27_tot["sav"]
        cumul_st = sfy26_tot["st_sav"] + sfy27_tot["st_sav"]
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(30, 60, 110)
        pdf.ln(2)
        pdf.cell(0, 5.5,
                 f"  Cumulative State Savings (SFY26+SFY27): ${cumul_st / 1e6:.1f}M "
                 f"({cumul_sav / cumul_base * 100:.1f}% of baseline)",
                 new_x="LMARGIN", new_y="NEXT")

    # ── Final page: Projection Methodology ───────────────────────────────
    pdf.add_page()
    pdf.section_title("9. SFY Projection Methodology")
    pdf.body_text(
        "The SFY26-SFY27 projections extend the point-in-time scenario analysis into a "
        "time-series model that accounts for the PDL change timeline, gradual biosimilar "
        "adoption, and price dynamics."
    )

    pdf.sub_title("Adoption Curve Rationale")
    pdf.body_text(
        "Biosimilar adoption following a PDL co-preferred designation typically follows an "
        "S-curve pattern. New starts shift first, while existing patients on Humira convert "
        "more gradually. The three scenarios bracket the range of plausible outcomes:\n\n"
        "- Conservative (30% by SFY27 end): Reflects provider inertia, patient reluctance to "
        "switch, and limited plan-level enforcement of biosimilar preference.\n\n"
        "- Moderate (55% by SFY27 end): Consistent with states that have implemented co-preferred "
        "status with active utilization management (step therapy, prior authorization encouraging "
        "biosimilar starts).\n\n"
        "- Aggressive (75% by SFY27 end): Assumes strong plan-level enforcement, mandatory "
        "biosimilar-first policies for new starts, and active switching programs for stable patients."
    )

    pdf.sub_title("Price Dynamics")
    pdf.body_text(
        f"Humira's cost per unit is inflated at {HUMIRA_ANNUAL_INFLATION * 100:.0f}% annually, "
        "consistent with the modest year-over-year increases observed in CY2022-CY2024 NC data "
        f"(CY2022: $3,671 -> CY2024: $3,868, ~2.7% CAGR).\n\n"
        f"Biosimilar cost per unit is deflated at {BIOSIMILAR_ANNUAL_DEFLATION * 100:.0f}% annually, "
        "reflecting expected competitive pricing pressure as multiple biosimilars compete for "
        "market share following the PDL change. This is conservative relative to the 10-30% annual "
        "price erosion observed in mature biosimilar markets (e.g., infliximab biosimilars)."
    )

    pdf.sub_title("Key Projection Limitations")
    pdf.body_text(
        "1. Adoption ramps are illustrative, not predictive. Actual adoption depends on plan-level "
        "policies, provider behavior, patient preferences, and manufacturer contracting.\n\n"
        "2. Utilization volume is held flat. In practice, lower costs may increase utilization "
        "(demand elasticity), and the expanded preferred list may attract patients from competing "
        "biologics (e.g., etanercept).\n\n"
        "3. Rebate dynamics (Section 5) apply to projections as well. Projected gross savings "
        "may not translate to net savings without supplemental rebate offsets.\n\n"
        "4. MCO contracting: NC Medicaid managed care organizations may negotiate separate "
        "rebate and formulary arrangements that diverge from the state PDL."
    )

    # Save PDF
    pdf_path = os.path.join(OUTPUT_DIR, "nc_humira_biosimilar_analysis.pdf")
    pdf.output(pdf_path)
    return pdf_path


# ─── MAIN ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Generating charts...")
    chart_paths = generate_charts()

    print("Generating CSV...")
    csv_path = generate_csv()
    print(f"  -> {csv_path}")

    print("Generating PDF...")
    pdf_path = generate_pdf(chart_paths)
    print(f"  -> {pdf_path}")

    # Clean up chart images
    for p in chart_paths.values():
        os.remove(p)
    print("Done.")
