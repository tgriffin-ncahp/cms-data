"""Generate comprehensive PDF + CSV report for NC Medicaid April 2026 PDL Impact Analysis.

Data-driven report pulling from drugs_data.db (CMS SDU + NADAC) and
pdl_impact_results.json (pre-computed analysis from analyze_pdl_impact.py).

Usage:
    .venv/bin/python generate_pdl_report.py
"""

import csv
import json
import os
from datetime import date
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from fpdf import FPDF

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_PATH = Path(__file__).parent / "pdl_impact_results.json"


def load_results():
    with open(RESULTS_PATH) as f:
        return json.load(f)


def fmt_dollars(val):
    val = float(val)
    if abs(val) >= 1_000_000:
        return f"${val:,.0f}"
    if abs(val) >= 1:
        return f"${val:,.2f}"
    return "$0"


def fmt_millions(val):
    val = float(val)
    return f"${val / 1e6:,.1f}M"


# ─── CHARTS ──────────────────────────────────────────────────────────────────


def generate_charts(results):
    chart_paths = {}
    util = results["utilization"]
    scenarios = results["humira_scenarios"]
    swaps = results["swaps"]

    # Chart 1: Multi-drug spend overview (top affected drugs)
    fig, ax = plt.subplots(figsize=(10, 5))
    drugs_ranked = [
        ("Humira", util["Humira"]["cy2024_total"]),
        ("Dupixent*", util["Dupixent"]["cy2024_total"]),
        ("Cosentyx", util["Cosentyx"]["cy2024_total"]),
        ("Stelara", util["Stelara"]["cy2024_total"]),
        ("Wegovy", util["Wegovy Tablet"]["cy2024_total"]),
        ("Taltz", util["Taltz"]["cy2024_total"]),
        ("Skytrofa", util["Skytrofa"]["cy2024_total"]),
        ("Actemra", util["Actemra"]["cy2024_total"]),
    ]
    drugs_ranked.sort(key=lambda x: x[1], reverse=True)
    names = [d[0] for d in drugs_ranked]
    vals = [d[1] / 1e6 for d in drugs_ranked]

    # Color by PDL action
    demoted = {"Humira", "Cosentyx"}
    promoted = {"Taltz", "Skytrofa"}
    context = {"Dupixent*", "Wegovy", "Stelara", "Actemra"}
    colors = []
    for n in names:
        if n in demoted:
            colors.append("#c44e52")  # red = moved to non-preferred
        elif n in promoted:
            colors.append("#4c9a6e")  # green = moved to preferred
        else:
            colors.append("#2c5f8a")  # blue = context/reference

    bars = ax.barh(names[::-1], vals[::-1], color=colors[::-1])
    ax.set_xlabel("CY2024 NC Medicaid Gross Reimbursement ($ Millions)", fontsize=11)
    ax.set_title("NC Medicaid: Key Specialty Drug Spend Affected by April 2026 PDL",
                 fontsize=12, fontweight="bold")
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"${v:,.0f}M"))

    for bar, val in zip(bars, vals[::-1]):
        ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height() / 2,
                f"${val:,.0f}M", va="center", fontsize=9)

    # Legend
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor="#c44e52", label="Moved to Non-Preferred"),
        Patch(facecolor="#4c9a6e", label="Moved to Preferred"),
        Patch(facecolor="#2c5f8a", label="Reference/Context"),
    ]
    ax.legend(handles=legend_elements, loc="lower right", fontsize=8)

    plt.tight_layout()
    p1 = os.path.join(OUTPUT_DIR, "_chart_drug_spend.png")
    fig.savefig(p1, dpi=150)
    plt.close(fig)
    chart_paths["drug_spend"] = p1

    # Chart 2: NADAC comparison for adalimumab products
    fig2, ax2 = plt.subplots(figsize=(9, 4.5))
    adalimumab_nadac = [
        ("Humira(CF) 40mg", 3362.68, "#c44e52"),
        ("Hyrimoz (adaz) 40mg", 1590.28, "#e8a852"),
        ("Hadlima 40mg", 1259.05, "#e8a852"),
        ("Cyltezo (adbm) 40mg", 636.04, "#4c9a6e"),
        ("Yusimry 40mg", 604.15, "#4c9a6e"),
        ("Adalimumab-aaty 40mg", 493.15, "#4c9a6e"),
        ("Simlandi 40mg", 483.07, "#4c9a6e"),
    ]
    names2 = [p[0] for p in adalimumab_nadac]
    prices2 = [p[1] for p in adalimumab_nadac]
    colors2 = [p[2] for p in adalimumab_nadac]

    bars2 = ax2.barh(names2[::-1], prices2[::-1], color=colors2[::-1])
    ax2.set_xlabel("NADAC Per Unit ($)", fontsize=11)
    ax2.set_title("NADAC Pricing: Humira vs. Adalimumab Biosimilars (2026)",
                  fontsize=12, fontweight="bold")
    ax2.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"${v:,.0f}"))

    for bar, price in zip(bars2, prices2[::-1]):
        disc = (1 - price / 3362.68) * 100 if price < 3362.68 else 0
        label = f"${price:,.0f}" + (f" (-{disc:.0f}%)" if disc > 0 else "")
        ax2.text(bar.get_width() + 30, bar.get_y() + bar.get_height() / 2,
                 label, va="center", fontsize=9)

    legend2 = [
        Patch(facecolor="#c44e52", label="Non-Preferred (Apr 2026)"),
        Patch(facecolor="#e8a852", label="Non-Preferred Biosimilar"),
        Patch(facecolor="#4c9a6e", label="Preferred Biosimilar"),
    ]
    ax2.legend(handles=legend2, loc="lower right", fontsize=8)
    plt.tight_layout()
    p2 = os.path.join(OUTPUT_DIR, "_chart_nadac_adalimumab.png")
    fig2.savefig(p2, dpi=150)
    plt.close(fig2)
    chart_paths["nadac_adalimumab"] = p2

    # Chart 3: Humira adoption scenarios - cumulative savings
    fig3, ax3 = plt.subplots(figsize=(8, 4.5))
    sc_names = [s["name"] for s in scenarios]
    sfy26_vals = [s["sfy26_state_savings"] / 1e6 for s in scenarios]
    sfy27_vals = [s["sfy27_state_savings"] / 1e6 for s in scenarios]

    x3 = range(len(sc_names))
    b3a = ax3.bar([i - 0.18 for i in x3], sfy26_vals, 0.35,
                  label="SFY26 State Savings", color="#4c9a6e")
    b3b = ax3.bar([i + 0.18 for i in x3], sfy27_vals, 0.35,
                  label="SFY27 State Savings", color="#2c5f8a")

    for bar, val in zip(b3a, sfy26_vals):
        ax3.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.2,
                 f"${val:.1f}M", ha="center", va="bottom", fontsize=9, fontweight="bold")
    for bar, val in zip(b3b, sfy27_vals):
        ax3.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.2,
                 f"${val:.1f}M", ha="center", va="bottom", fontsize=9, fontweight="bold")

    for i in range(len(sc_names)):
        total = sfy26_vals[i] + sfy27_vals[i]
        ax3.text(i, max(sfy26_vals[i], sfy27_vals[i]) + 1.5,
                 f"Total: ${total:.1f}M", ha="center", fontsize=8, style="italic")

    ax3.set_ylabel("State Savings ($ Millions)", fontsize=11)
    ax3.set_title("Humira Biosimilar: Projected State Savings by Scenario\n"
                  "(Non-Preferred effective Apr 2026, FMAP-adjusted)",
                  fontsize=11, fontweight="bold")
    ax3.set_xticks(list(x3))
    ax3.set_xticklabels(sc_names, fontsize=10)
    ax3.legend(fontsize=9)
    ax3.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"${v:,.0f}M"))
    ax3.set_ylim(0, max(sfy27_vals) * 1.35)

    plt.tight_layout()
    p3 = os.path.join(OUTPUT_DIR, "_chart_humira_scenarios.png")
    fig3.savefig(p3, dpi=150)
    plt.close(fig3)
    chart_paths["humira_scenarios"] = p3

    # Chart 4: Wegovy injectable vs tablet pricing
    fig4, ax4 = plt.subplots(figsize=(7, 3.5))
    wegovy_data = [
        ("Injectable Pen\n(0.25-2.4mg)", 535.0, "#c44e52"),
        ("Oral Tablet\n(1.5-25mg)", 43.2, "#4c9a6e"),
    ]
    names4 = [w[0] for w in wegovy_data]
    prices4 = [w[1] for w in wegovy_data]
    colors4 = [w[2] for w in wegovy_data]

    bars4 = ax4.bar(names4, prices4, color=colors4, width=0.5)
    ax4.set_ylabel("NADAC Per Unit ($)", fontsize=11)
    ax4.set_title("Wegovy: Injectable vs. Tablet NADAC Per Unit\n(92% cost reduction per unit)",
                  fontsize=11, fontweight="bold")
    ax4.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"${v:,.0f}"))

    for bar, val in zip(bars4, prices4):
        ax4.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 10,
                 f"${val:,.0f}", ha="center", va="bottom", fontsize=12, fontweight="bold")

    plt.tight_layout()
    p4 = os.path.join(OUTPUT_DIR, "_chart_wegovy_pricing.png")
    fig4.savefig(p4, dpi=150)
    plt.close(fig4)
    chart_paths["wegovy"] = p4

    # Chart 5: Aggregate impact waterfall
    fig5, ax5 = plt.subplots(figsize=(10, 5))
    categories = [
        "Humira\n(Moderate)",
        "Wegovy\nTablet (50%)",
        "Actemra→\nTyenne (50%)",
        "Cosentyx→\nTaltz*",
        "Stelara→\nStarjemza*",
    ]
    # Use moderate Humira scenario, 50% swap conversion
    humira_mod = next(s for s in scenarios if s["name"] == "Moderate")
    values = [
        humira_mod["two_year_gross"] / 1e6,
        next(s["potential_savings_50pct"] for s in swaps if s["category"] == "GLP-1 Weight Management") / 1e6,
        next(s["potential_savings_50pct"] for s in swaps if s["category"] == "IL-6 (Tocilizumab/RA)") / 1e6,
        0,  # TBD - rebate driven
        0,  # TBD - no NADAC yet
    ]

    bar_colors = ["#2c5f8a" if v > 0 else "#999999" for v in values]
    bars5 = ax5.bar(categories, values, color=bar_colors, width=0.6)

    for bar, val in zip(bars5, values):
        label = f"${val:,.1f}M" if val > 0 else "Rebate-\nDriven"
        y_pos = bar.get_height() + 0.5 if val > 0 else 2
        ax5.text(bar.get_x() + bar.get_width() / 2, y_pos,
                 label, ha="center", va="bottom", fontsize=10, fontweight="bold")

    total_quantified = sum(v for v in values if v > 0)
    ax5.axhline(y=0, color="black", linewidth=0.5)
    ax5.set_ylabel("Potential Gross Savings ($ Millions, Annual)", fontsize=11)
    ax5.set_title(f"Aggregate PDL Impact: Quantifiable NADAC-Based Savings\n"
                  f"Total Quantified: ${total_quantified:,.1f}M/year (+ rebate-driven categories)",
                  fontsize=11, fontweight="bold")
    ax5.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"${v:,.0f}M"))

    ax5.annotate("* Savings from Cosentyx→Taltz and Stelara→Starjemza are primarily\n"
                 "  rebate-driven; NADAC comparison not meaningful for these categories.",
                 xy=(0.02, 0.02), xycoords="axes fraction", fontsize=7, color="#666",
                 style="italic")

    plt.tight_layout()
    p5 = os.path.join(OUTPUT_DIR, "_chart_aggregate_impact.png")
    fig5.savefig(p5, dpi=150)
    plt.close(fig5)
    chart_paths["aggregate"] = p5

    return chart_paths


# ─── PDF REPORT ──────────────────────────────────────────────────────────────


class ReportPDF(FPDF):
    def header(self):
        if self.page_no() > 1:
            self.set_font("Helvetica", "I", 8)
            self.cell(0, 5, "NC Medicaid April 2026 PDL Impact Analysis | CONFIDENTIAL DRAFT", align="C")
            self.ln(8)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}  |  Generated {date.today().isoformat()}", align="C")

    def section_title(self, title):
        self.set_font("Helvetica", "B", 14)
        self.set_fill_color(44, 95, 138)
        self.set_text_color(255, 255, 255)
        self.cell(0, 10, f"  {title}", fill=True, new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(0, 0, 0)
        self.ln(3)

    def subsection(self, title):
        self.set_font("Helvetica", "B", 11)
        self.cell(0, 7, title, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def body_text(self, text):
        self.set_font("Helvetica", "", 9)
        text = text.replace("\u2014", "--").replace("\u2013", "-").replace("\u2018", "'").replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
        self.multi_cell(0, 5, text)
        self.ln(2)

    def metric_row(self, label, value, bold_value=False):
        self.set_font("Helvetica", "", 9)
        self.cell(100, 5, label)
        self.set_font("Helvetica", "B" if bold_value else "", 9)
        self.cell(0, 5, str(value), new_x="LMARGIN", new_y="NEXT")

    def add_table(self, headers, rows, col_widths=None):
        if col_widths is None:
            col_widths = [190 // len(headers)] * len(headers)

        self.set_font("Helvetica", "B", 8)
        self.set_fill_color(220, 220, 220)
        for i, h in enumerate(headers):
            self.cell(col_widths[i], 6, h, border=1, fill=True)
        self.ln()

        self.set_font("Helvetica", "", 8)
        for row in rows:
            for i, cell in enumerate(row):
                self.cell(col_widths[i], 5, str(cell), border=1)
            self.ln()
        self.ln(2)


def generate_pdf(results, chart_paths):
    pdf = ReportPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)

    util = results["utilization"]
    scenarios = results["humira_scenarios"]
    swaps = results["swaps"]
    risks = results["risks"]
    fmap = results["fmap_rates"]
    state_share = results["state_share"]

    # ── Title Page ──
    pdf.add_page()
    pdf.ln(40)
    pdf.set_font("Helvetica", "B", 24)
    pdf.cell(0, 15, "NC Medicaid", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 15, "April 2026 PDL Impact Analysis", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(10)
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 8, "Off-Cycle Preferred Drug List Changes Effective April 1, 2026", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(15)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Report Date: {date.today().strftime('%B %d, %Y')}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, "Data Sources: CMS State Drug Utilization (CY2024, H1-2025)", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, "NADAC (National Average Drug Acquisition Cost) as of 04/01/2026", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, "NC DHHS PDL Change Notification 04/02/2026", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(20)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(196, 78, 82)
    pdf.cell(0, 6, "CONFIDENTIAL DRAFT -- FOR INTERNAL USE ONLY", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, "GROSS REIMBURSEMENT ANALYSIS (PRE-REBATE)", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)

    # ── Executive Summary ──
    pdf.add_page()
    pdf.section_title("1. Executive Summary")

    moderate = next(s for s in scenarios if s["name"] == "Moderate")
    total_affected = results["total_affected_spend"]

    pdf.body_text(
        "On April 2, 2026, NC DHHS issued off-cycle Preferred Drug List changes effective "
        "April 1, 2026, citing 'significant fiscal impact.' The most consequential change: "
        "Humira (adalimumab) moved from co-preferred to NON-PREFERRED status across all "
        "dosage forms, representing a significant escalation from the January 2026 PDL approach.\n\n"
        "Additional high-impact changes include Cosentyx moved to non-preferred (replaced by "
        "Taltz), Starjemza promoted as preferred ustekinumab biosimilar, Tyenne promoted as "
        "preferred tocilizumab biosimilar, and Wegovy oral tablet added as preferred."
    )

    pdf.subsection("Key Financial Metrics")
    pdf.metric_row("Total CY2024 Spend on Affected Drugs:", fmt_dollars(total_affected), bold_value=True)
    pdf.metric_row("Annualized H1-2025 Wegovy Spend:", fmt_dollars(util["Wegovy Tablet"]["h1_2025_total"] * 2), bold_value=True)
    pdf.metric_row("", "")
    pdf.metric_row("Humira 2-Year Gross Savings (Moderate):", fmt_dollars(moderate["two_year_gross"]), bold_value=True)
    pdf.metric_row("Humira 2-Year State Savings (Moderate):", fmt_dollars(moderate["two_year_state"]), bold_value=True)
    ss26 = state_share["2026"]["non_expansion"]
    ss27 = state_share["2027"]["non_expansion"]
    pdf.metric_row("SFY26 State Share (non-expansion):", f"{ss26:.2%} (FMAP {fmap['2026']})")
    pdf.metric_row("SFY27 State Share (non-expansion):", f"{ss27:.2%} (FMAP {fmap['2027']})")

    pdf.body_text(
        "\nIMPORTANT: This analysis uses GROSS reimbursement only (pre-rebate). Humira carries "
        "substantial MDRP (Medicaid Drug Rebate Program) rebates estimated at ~23.1%, while "
        "biosimilars have lower rebates (~13%) and minimal CPI penalties. The Cosentyx-to-Taltz "
        "and Stelara-to-Starjemza swaps are believed to be primarily rebate-driven. "
        "Complete net fiscal analysis requires confidential supplemental rebate data."
    )

    # ── Drug Spend Overview Chart ──
    if "drug_spend" in chart_paths:
        pdf.add_page()
        pdf.section_title("2. Affected Drug Spend Overview")
        pdf.image(chart_paths["drug_spend"], x=10, w=190)
        pdf.ln(5)
        pdf.body_text(
            "The chart above shows CY2024 NC Medicaid gross reimbursement for the major "
            "specialty drugs affected by the April 2026 PDL change. Red bars indicate drugs "
            "moved to non-preferred status; green bars indicate drugs promoted to preferred. "
            "Blue bars are reference drugs providing context.\n\n"
            "* Dupixent is shown for context as the atopic dermatitis market leader. "
            "Ebglyss (lebrikizumab), newly preferred for atopic dermatitis, is actually "
            "more expensive per unit than Dupixent by NADAC ($1,710 vs $1,010), suggesting "
            "the preferred status is rebate-negotiated."
        )

    # ── PDL Change Summary Table ──
    pdf.add_page()
    pdf.section_title("3. PDL Change Summary")

    pdf.subsection("Moved to Non-Preferred")
    pdf.add_table(
        ["Drug", "Category", "Previous Status", "CY2024 Spend"],
        [
            ["Humira (all forms)", "TNF-alpha", "Co-Preferred", fmt_dollars(util["Humira"]["cy2024_total"])],
            ["Adalimumab-adaz", "TNF-alpha Biosimilar", "Preferred", "Minimal"],
            ["Adalimumab-adbm", "TNF-alpha Biosimilar", "Preferred", "Minimal"],
            ["Cosentyx", "IL-17 Inhibitor", "Preferred", fmt_dollars(util["Cosentyx"]["cy2024_total"])],
            ["Steqeyma", "IL-12/23 Biosimilar", "Preferred", "New Product"],
        ],
        col_widths=[45, 40, 35, 70],
    )

    pdf.subsection("Moved to Preferred")
    pdf.add_table(
        ["Drug", "Category", "Replaces", "NADAC/Unit"],
        [
            ["Taltz (ixekizumab)", "IL-17 Inhibitor", "Cosentyx", f"${util['Taltz']['nadac_per_unit']:,.2f}"],
            ["Starjemza", "IL-12/23 Biosimilar", "Stelara", "No NADAC Yet"],
            ["Tyenne", "IL-6 Biosimilar", "Actemra", f"${util.get('Tyenne', {}).get('nadac_per_unit', 819.74):,.2f}"],
            ["Skytrofa", "Growth Hormone", "Various", "No NADAC"],
            ["Ebglyss", "IL-13 (Atopic Derm)", "Dupixent", f"${util.get('Ebglyss', {}).get('nadac_per_unit', 1710.29):,.2f}"],
            ["Wegovy Tablet", "GLP-1 Weight Mgmt", "Injectable Wegovy", "$43.22"],
            ["Vtama Cream", "Topical Psoriasis", "Various", f"${util.get('Vtama', {}).get('nadac_per_unit', 24.14):,.2f}"],
        ],
        col_widths=[40, 40, 35, 75],
    )

    # ── Humira Deep Dive ──
    pdf.add_page()
    pdf.section_title("4. Humira Deep Dive: Co-Preferred to Non-Preferred")

    pdf.body_text(
        "The January 2026 PDL made adalimumab biosimilars co-preferred with Humira. "
        "The April 2026 change escalates this to making Humira fully NON-PREFERRED, "
        "which is a significantly stronger signal. Non-preferred status typically requires "
        "prior authorization, creating a direct mechanism to drive biosimilar adoption.\n\n"
        "However, as of April 2, 2026, NC DHB has NOT updated Humira PA criteria to "
        "require biosimilar trial/failure first (unlike Stelara, which has updated criteria). "
        "This is a critical gap identified by Standard Plan pharmacy directors."
    )

    pdf.subsection("CY2024 Baseline Utilization")
    humira = util["Humira"]
    pdf.metric_row("Total Units Reimbursed:", f"{humira['cy2024_units']:,.0f}")
    pdf.metric_row("Total Prescriptions:", f"{humira['cy2024_rx']:,}")
    pdf.metric_row("Gross Total Reimbursed:", fmt_dollars(humira["cy2024_total"]))
    pdf.metric_row("Medicaid Amount:", fmt_dollars(humira["cy2024_medicaid"]))
    pdf.metric_row("Cost Per Unit (Actual):", fmt_dollars(humira["cost_per_unit_actual"]))
    pdf.metric_row("NADAC Per Unit (Humira 40mg):", "$3,362.68")
    pdf.metric_row("Current Biosimilar Adoption:", "<1% (NC Medicaid)")

    pdf.subsection("H1-2025 Trend")
    pdf.metric_row("H1-2025 Units:", f"{humira['h1_2025_units']:,.0f}")
    pdf.metric_row("H1-2025 Total:", fmt_dollars(humira["h1_2025_total"]))
    yoy_pct = humira.get("yoy_growth", 0)
    pdf.metric_row("YoY Growth (annualized):", f"{yoy_pct:.1%}")

    if "nadac_adalimumab" in chart_paths:
        pdf.add_page()
        pdf.subsection("NADAC Pricing: Humira vs. Biosimilars")
        pdf.image(chart_paths["nadac_adalimumab"], x=10, w=185)
        pdf.ln(5)
        pdf.body_text(
            "The cheapest biosimilar (Simlandi) offers an 86% NADAC discount vs. Humira. "
            "The blended average across available biosimilars is approximately 73% discount. "
            "Note: NADAC reflects acquisition cost only; actual reimbursement includes "
            "dispensing fees and varies by plan contract."
        )

    # Humira scenarios
    if "humira_scenarios" in chart_paths:
        pdf.add_page()
        pdf.subsection("Adoption Scenarios & State Savings")
        pdf.image(chart_paths["humira_scenarios"], x=10, w=185)
        pdf.ln(5)

    pdf.add_table(
        ["Scenario", "SFY26 Gross", "SFY27 Gross", "SFY26 State", "SFY27 State", "2-Year State"],
        [
            [
                s["name"],
                fmt_millions(s["sfy26_gross_savings"]),
                fmt_millions(s["sfy27_gross_savings"]),
                fmt_millions(s["sfy26_state_savings"]),
                fmt_millions(s["sfy27_state_savings"]),
                fmt_millions(s["two_year_state"]),
            ]
            for s in scenarios
        ],
        col_widths=[30, 32, 32, 32, 32, 32],
    )

    pdf.body_text(
        f"State savings use FMAP-derived non-expansion state share: "
        f"SFY26 = {ss26:.2%}, SFY27 = {ss27:.2%}. "
        f"Expansion population (10% state share) would reduce blended state share. "
        f"SFY26 impact is limited to Q4 only (Apr-Jun 2026) due to April 1 effective date. "
        f"Non-preferred status accelerates adoption curves compared to prior co-preferred "
        f"analysis (Jan 2026 PDL)."
    )

    # ── Wegovy ──
    pdf.add_page()
    pdf.section_title("5. Wegovy: Injectable to Tablet Transition")

    pdf.body_text(
        "Wegovy (semaglutide) for weight management represents the fastest-growing drug "
        "category in NC Medicaid. CY2024 spend was $46.5M; H1-2025 annualized is "
        f"${util['Wegovy Tablet']['annualized_2025_total']:,.0f} — "
        f"representing {util['Wegovy Tablet']['yoy_growth']:.0%} year-over-year growth.\n\n"
        "The April 2026 PDL adds Wegovy oral tablet as preferred. The tablet's NADAC "
        "is approximately $43/unit vs. $434-651/unit for injectable pens — a 92-93% "
        "reduction per unit. However, dosing equivalence and patient compliance may differ "
        "between oral and injectable formulations."
    )

    if "wegovy" in chart_paths:
        pdf.image(chart_paths["wegovy"], x=25, w=150)
        pdf.ln(5)

    wegovy_swap = next((s for s in swaps if s["category"] == "GLP-1 Weight Management"), None)
    if wegovy_swap:
        pdf.subsection("Potential Savings (NADAC-Based)")
        pdf.add_table(
            ["Conversion Rate", "Annual Gross Savings"],
            [
                ["25%", fmt_dollars(wegovy_swap["potential_savings_25pct"])],
                ["50%", fmt_dollars(wegovy_swap["potential_savings_50pct"])],
                ["75%", fmt_dollars(wegovy_swap["potential_savings_75pct"])],
            ],
            col_widths=[95, 95],
        )
        pdf.body_text(
            "CRITICAL CAVEAT: These savings estimates assume unit-for-unit substitution. "
            "Oral semaglutide has different bioavailability and dosing requirements. "
            "The actual savings depend on equivalent therapeutic dosing, which may require "
            "different unit quantities. The $43/unit tablet pricing reflects newly published "
            "NADAC as of March 18, 2026."
        )

    # ── Other Swap Categories ──
    pdf.add_page()
    pdf.section_title("6. Other Therapeutic Category Impacts")

    pdf.subsection("Cosentyx -> Taltz (IL-17 Inhibitor)")
    pdf.body_text(
        f"CY2024 Cosentyx NC Medicaid spend: {fmt_dollars(util['Cosentyx']['cy2024_total'])}. "
        f"Taltz is 7-8% cheaper per NADAC for comparable dosing (150mg maintenance: "
        f"Cosentyx $7,209 vs Taltz $6,682). However, this swap is likely driven primarily "
        f"by supplemental rebate negotiations rather than NADAC savings alone. "
        f"The NADAC-based savings are modest; the real fiscal impact depends on "
        f"confidential rebate terms."
    )

    pdf.subsection("Stelara -> Starjemza (IL-12/23 Biosimilar)")
    pdf.body_text(
        f"CY2024 Stelara NC Medicaid spend: {fmt_dollars(util['Stelara']['cy2024_total'])}. "
        f"Starjemza (ustekinumab-aekn) is a biosimilar to Stelara. No NADAC pricing is "
        f"available yet (too new for CMS NADAC survey). Typical specialty biosimilar "
        f"discounts range 30-50% initially. At 40% discount with 50% conversion, the "
        f"potential gross savings would be approximately "
        f"${util['Stelara']['cy2024_total'] * 0.40 * 0.50:,.0f}/year."
    )

    pdf.subsection("Actemra -> Tyenne (IL-6 Biosimilar)")
    actemra_swap = next((s for s in swaps if s["category"] == "IL-6 (Tocilizumab/RA)"), None)
    pdf.body_text(
        f"CY2024 Actemra NC Medicaid spend: {fmt_dollars(util['Actemra']['cy2024_total'])}. "
        f"Tyenne offers a 36% NADAC discount ($820 vs $1,273/unit). "
        f"At 50% conversion: {fmt_dollars(actemra_swap['potential_savings_50pct'])}/year savings. "
        f"Smaller category but straightforward biosimilar substitution."
    )

    pdf.subsection("Ebglyss (Atopic Dermatitis)")
    pdf.body_text(
        f"Ebglyss (lebrikizumab) promoted to preferred for atopic dermatitis. "
        f"NADAC is $1,710/unit vs Dupixent at $917-1,615/unit. Ebglyss is NOT cheaper "
        f"by NADAC — this is entirely a rebate-negotiated placement. "
        f"CY2024 Dupixent NC Medicaid spend: {fmt_dollars(util['Dupixent']['cy2024_total'])}. "
        f"Any conversion from Dupixent to Ebglyss would increase NADAC-based costs but "
        f"presumably decrease net costs after manufacturer rebates."
    )

    # ── Aggregate Waterfall ──
    if "aggregate" in chart_paths:
        pdf.add_page()
        pdf.section_title("7. Aggregate Financial Impact")
        pdf.image(chart_paths["aggregate"], x=10, w=190)
        pdf.ln(5)

    total_swap = sum(s["potential_savings_50pct"] for s in swaps if s["potential_savings_50pct"] > 0)
    stelara_est = util["Stelara"]["cy2024_total"] * 0.40 * 0.50

    pdf.body_text(
        f"NADAC-quantifiable annual gross savings (at moderate adoption):\n"
        f"  - Humira biosimilar (Moderate, SFY27 run-rate): ~{fmt_millions(moderate['sfy27_gross_savings'])}\n"
        f"  - Wegovy tablet (50% conversion): ~{fmt_millions(next(s['potential_savings_50pct'] for s in swaps if s['category'] == 'GLP-1 Weight Management'))}\n"
        f"  - Actemra->Tyenne (50%): ~{fmt_millions(next(s['potential_savings_50pct'] for s in swaps if s['category'] == 'IL-6 (Tocilizumab/RA)'))}\n"
        f"  - Stelara->Starjemza (est. 40% disc, 50% conv.): ~{fmt_millions(stelara_est)}\n\n"
        f"Rebate-driven (not NADAC-quantifiable):\n"
        f"  - Cosentyx->Taltz: CY2024 baseline {fmt_dollars(util['Cosentyx']['cy2024_total'])}\n"
        f"  - Dupixent->Ebglyss: CY2024 baseline {fmt_dollars(util['Dupixent']['cy2024_total'])}\n\n"
        f"NOTE: Gross savings do not account for Medicaid Drug Rebate Program (MDRP) "
        f"offsets. Humira's rebate rate (~23.1% + CPI penalties) is substantially higher "
        f"than biosimilar rebates (~13%). Net savings will be lower than gross estimates."
    )

    # ── Implementation Risks ──
    pdf.add_page()
    pdf.section_title("8. Implementation Risk Assessment")

    pdf.body_text(
        "Standard Plan (SP) pharmacy directors raised the following concerns in a letter "
        "dated March 31, 2026, regarding the April 1, 2026 PDL changes:"
    )

    for risk in risks:
        pdf.subsection(f"{risk['risk']} [{risk['severity']}]")
        pdf.body_text(risk["description"])
        if "exposure" in risk:
            pdf.set_font("Helvetica", "I", 8)
            pdf.multi_cell(0, 4, f"Exposure: {risk['exposure']}")
            pdf.ln(2)

    pdf.body_text(
        "\nThe PA criteria gap is the most critical risk. Without updated PA criteria "
        "requiring biosimilar trial/failure for Humira, the non-preferred designation "
        "lacks an enforcement mechanism. All savings projections in this report assume "
        "PA enforcement will be implemented. If the PA criteria gap persists, actual "
        "biosimilar adoption rates could be significantly lower than projected."
    )

    # ── Assumptions & Limitations ──
    pdf.add_page()
    pdf.section_title("9. Key Assumptions & Limitations")

    assumptions = [
        ("Data Currency", "SDU 2025 covers Q1-Q2 only (Jan-Jun 2025). CY2024 used as "
         "full-year baseline. NADAC pricing as of 04/01/2026."),
        ("FMAP Rates", f"Non-expansion: SFY26 FMAP={fmap['2026']}, SFY27 FMAP={fmap['2027']}. "
         f"Expansion FMAP=0.90. Analysis uses non-expansion state share as conservative estimate."),
        ("Biosimilar Adoption", "Assumes PA enforcement is implemented for Humira. "
         "Conservative/Moderate/Aggressive scenarios based on other states' experience with "
         "non-preferred biologic conversions (OR, WA, NY)."),
        ("Gross vs Net", "ALL estimates are gross reimbursement (pre-rebate). Humira MDRP "
         "base rebate is 23.1% plus substantial CPI penalties. Biosimilars have ~13% rebate "
         "with minimal CPI penalties. Net savings will be materially lower."),
        ("Wegovy Tablet", "Unit-for-unit pricing comparison. Oral vs injectable bioavailability "
         "differences may require different unit volumes for therapeutic equivalence."),
        ("Starjemza/Steqeyma", "No NADAC pricing available for Starjemza (too new). "
         "Estimated 30-50% biosimilar discount based on specialty drug market norms."),
        ("Rebate-Driven Swaps", "Cosentyx->Taltz and Dupixent->Ebglyss swaps likely driven "
         "by supplemental rebate negotiations. NADAC-based comparison not meaningful."),
        ("PDL Effective Date", "April 1, 2026. SFY26 Q4 (Apr-Jun 2026) is the only impacted "
         "quarter in SFY26. Full-year impact begins SFY27."),
    ]

    for title, text in assumptions:
        pdf.subsection(title)
        pdf.body_text(text)

    # ── Output ──
    pdf_path = os.path.join(OUTPUT_DIR, "nc_pdl_april2026_impact_analysis.pdf")
    pdf.output(pdf_path)
    return pdf_path


# ─── CSV ─────────────────────────────────────────────────────────────────────


def generate_csv(results):
    csv_path = os.path.join(OUTPUT_DIR, "nc_pdl_april2026_impact_analysis.csv")
    util = results["utilization"]
    scenarios = results["humira_scenarios"]
    swaps = results["swaps"]

    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)

        w.writerow(["NC Medicaid April 2026 PDL Impact Analysis"])
        w.writerow(["Generated", date.today().isoformat()])
        w.writerow(["Data Sources", "CMS SDU CY2024/H1-2025; NADAC 04/01/2026; NC DHHS PDL 04/01/2026"])
        w.writerow([])

        # Drug utilization summary
        w.writerow(["AFFECTED DRUG UTILIZATION SUMMARY"])
        w.writerow(["Drug", "Category", "CY2024 Units", "CY2024 Rx", "CY2024 Total",
                     "CY2024 Medicaid", "H1-2025 Total", "Annualized 2025",
                     "NADAC/Unit", "Cost/Unit (Actual)", "YoY Growth"])
        for drug_name, d in util.items():
            w.writerow([
                drug_name, d["category"],
                round(d["cy2024_units"], 0), d["cy2024_rx"],
                round(d["cy2024_total"], 2), round(d["cy2024_medicaid"], 2),
                round(d["h1_2025_total"], 2), round(d["annualized_2025_total"], 2),
                round(d["nadac_per_unit"], 2), round(d["cost_per_unit_actual"], 2),
                f"{d['yoy_growth']:.2%}" if d["yoy_growth"] != 0 else "N/A",
            ])
        w.writerow([])

        # Humira scenarios
        w.writerow(["HUMIRA BIOSIMILAR ADOPTION SCENARIOS"])
        w.writerow(["Scenario", "SFY26 Gross Savings", "SFY27 Gross Savings",
                     "SFY26 State Savings", "SFY27 State Savings", "2-Year State Total"])
        for s in scenarios:
            w.writerow([
                s["name"],
                round(s["sfy26_gross_savings"], 2), round(s["sfy27_gross_savings"], 2),
                round(s["sfy26_state_savings"], 2), round(s["sfy27_state_savings"], 2),
                round(s["two_year_state"], 2),
            ])
        w.writerow([])

        # Humira quarterly detail
        w.writerow(["HUMIRA ADOPTION BY QUARTER (MODERATE SCENARIO)"])
        w.writerow(["Quarter", "Biosimilar %"])
        moderate = next(s for s in scenarios if s["name"] == "Moderate")
        for q, pct in sorted(moderate["adoption_by_quarter"].items()):
            w.writerow([q, f"{pct:.0%}"])
        w.writerow([])

        # Swap pairs
        w.writerow(["THERAPEUTIC SWAP ANALYSIS"])
        w.writerow(["Category", "From Drug", "To Drug", "From NADAC", "To NADAC",
                     "Discount %", "CY2024 Baseline", "Savings @25%", "Savings @50%", "Savings @75%"])
        for s in swaps:
            w.writerow([
                s["category"], s["from_drug"], s["to_drug"],
                round(s["from_nadac"], 2), round(s["to_nadac"], 2),
                f"{s['discount_pct']:.1%}" if s["discount_pct"] > 0 else "TBD",
                round(s["baseline_annual_spend"], 2),
                round(s["potential_savings_25pct"], 2),
                round(s["potential_savings_50pct"], 2),
                round(s["potential_savings_75pct"], 2),
            ])
        w.writerow([])

        # FMAP
        w.writerow(["FMAP AND STATE SHARE"])
        w.writerow(["SFY", "FMAP (Non-Exp)", "State Share (Non-Exp)", "FMAP (Exp)", "State Share (Exp)"])
        for sfy_str, fmap_val in results["fmap_rates"].items():
            w.writerow([f"SFY{sfy_str[-2:]}", fmap_val, f"{1-fmap_val:.4f}", 0.90, 0.10])
        w.writerow([])

        # Implementation risks
        w.writerow(["IMPLEMENTATION RISKS"])
        w.writerow(["Risk", "Severity", "Description"])
        for r in results["risks"]:
            w.writerow([r["risk"], r["severity"], r["description"]])
        w.writerow([])

        # Key assumptions
        w.writerow(["KEY ASSUMPTIONS"])
        w.writerow(["All estimates are GROSS reimbursement (pre-rebate)"])
        w.writerow(["Humira MDRP base rebate: ~23.1% + CPI penalties"])
        w.writerow(["Biosimilar rebates: ~13%, minimal CPI penalties"])
        w.writerow(["Non-expansion FMAP used as conservative state share estimate"])
        w.writerow(["PA enforcement assumed for adoption scenarios"])
        w.writerow(["SDU 2025 data covers Q1-Q2 only"])

    return csv_path


# ─── MAIN ────────────────────────────────────────────────────────────────────


def main():
    print("Loading analysis results...")
    results = load_results()

    print("Generating charts...")
    chart_paths = generate_charts(results)

    print("Generating PDF report...")
    pdf_path = generate_pdf(results, chart_paths)
    print(f"  PDF: {pdf_path}")

    print("Generating CSV...")
    csv_path = generate_csv(results)
    print(f"  CSV: {csv_path}")

    # Cleanup chart files
    for name, path in chart_paths.items():
        if os.path.exists(path):
            os.remove(path)
    print("Done. Chart temp files cleaned up.")


if __name__ == "__main__":
    main()
