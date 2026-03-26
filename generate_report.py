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
