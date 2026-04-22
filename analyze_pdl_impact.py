"""Analyze financial impact of NC Medicaid April 2026 PDL changes.

Queries drugs_data.db for NC utilization and NADAC pricing, cross-references
with rate_analysis_suite FMAP rates, and produces structured impact data for
each affected drug category.

Usage:
    .venv/bin/python analyze_pdl_impact.py
"""

import json
import sqlite3
from dataclasses import dataclass, field, asdict
from pathlib import Path

DB_PATH = Path(__file__).parent / "drugs_data.db"
RATE_DB_PATH = Path("/home/orthel/workspace/rate_analyis_suite/rate_analysis.db")

# FMAP rates from rate_analysis_suite/core/config.py
FMAP_BY_SFY = {2025: 0.6506, 2026: 0.6462, 2027: 0.6416}
EXPANSION_FMAP = 0.90

# Blended state share for specialty drugs (mix of non-expansion ABD + expansion)
# ABD population ~60% of specialty drug users, expansion ~40%
# SFY26: 0.3538 * 0.6 + 0.10 * 0.4 = 0.2523 + 0.04 = 0.2923
# SFY27: 0.3584 * 0.6 + 0.10 * 0.4 = 0.2150 + 0.04 = 0.2550
# We'll use non-expansion state share as the conservative estimate,
# and show blended separately
STATE_SHARE = {
    2026: {"non_expansion": 1 - FMAP_BY_SFY[2026], "expansion": 1 - EXPANSION_FMAP},
    2027: {"non_expansion": 1 - FMAP_BY_SFY[2027], "expansion": 1 - EXPANSION_FMAP},
}


@dataclass
class DrugUtilization:
    drug: str
    category: str
    cy2024_units: float = 0
    cy2024_rx: int = 0
    cy2024_total: float = 0
    cy2024_medicaid: float = 0
    h1_2025_units: float = 0
    h1_2025_rx: int = 0
    h1_2025_total: float = 0
    h1_2025_medicaid: float = 0
    annualized_2025_total: float = 0
    nadac_per_unit: float = 0
    nadac_source: str = ""
    cost_per_unit_actual: float = 0
    yoy_growth: float = 0


@dataclass
class SwapAnalysis:
    category: str
    from_drug: str
    to_drug: str
    from_nadac: float = 0
    to_nadac: float = 0
    discount_pct: float = 0
    baseline_annual_spend: float = 0
    baseline_annual_units: float = 0
    potential_savings_25pct: float = 0
    potential_savings_50pct: float = 0
    potential_savings_75pct: float = 0
    note: str = ""


@dataclass
class HumiraScenario:
    name: str
    adoption_by_quarter: dict = field(default_factory=dict)
    sfy26_gross_savings: float = 0
    sfy27_gross_savings: float = 0
    sfy26_state_savings: float = 0
    sfy27_state_savings: float = 0
    two_year_gross: float = 0
    two_year_state: float = 0


def get_conn():
    return sqlite3.connect(DB_PATH)


def query_utilization(conn, sdu_pattern: str, table: str) -> dict:
    """Query aggregated utilization for a drug pattern from SDU table."""
    cur = conn.execute(f"""
        SELECT
            SUM("Units Reimbursed") as units,
            SUM("Number of Prescriptions") as rx,
            SUM("Total Amount Reimbursed") as total,
            SUM("Medicaid Amount Reimbursed") as medicaid
        FROM {table}
        WHERE "Product Name" LIKE ?
    """, (sdu_pattern,))
    row = cur.fetchone()
    return {
        "units": row[0] or 0,
        "rx": int(row[1] or 0),
        "total": row[2] or 0,
        "medicaid": row[3] or 0,
    }


def query_nadac(conn, nadac_pattern: str) -> list[dict]:
    """Query NADAC pricing for a drug pattern. Returns list of products."""
    cur = conn.execute("""
        SELECT "NDC Description", "NADAC Per Unit", "Effective Date",
               "Classification for Rate Setting"
        FROM nadac_2026
        WHERE "NDC Description" LIKE ?
        ORDER BY "NADAC Per Unit" DESC
    """, (nadac_pattern,))
    return [
        {"description": r[0], "nadac": r[1], "date": r[2], "classification": r[3]}
        for r in cur.fetchall()
    ]


def analyze_drug(conn, drug_def: dict) -> DrugUtilization:
    """Build utilization profile for a single drug."""
    sdu_pat = drug_def["sdu_pattern"]
    nadac_pat = drug_def.get("nadac_pattern", "")

    cy2024 = query_utilization(conn, sdu_pat, "sdu_2024")
    h1_2025 = query_utilization(conn, sdu_pat, "sdu_2025")

    nadac_results = query_nadac(conn, nadac_pat) if nadac_pat else []
    # Use the most common dosage form (typically 40mg for adalimumab, etc.)
    # Pick the middle-priced option as representative
    nadac_price = 0
    nadac_desc = ""
    if nadac_results:
        mid = len(nadac_results) // 2
        nadac_price = nadac_results[mid]["nadac"]
        nadac_desc = nadac_results[mid]["description"]

    annualized = h1_2025["total"] * 2 if h1_2025["total"] > 0 else cy2024["total"]
    cpu = cy2024["total"] / cy2024["units"] if cy2024["units"] > 0 else 0
    yoy = ((h1_2025["total"] * 2) / cy2024["total"] - 1) if cy2024["total"] > 0 and h1_2025["total"] > 0 else 0

    return DrugUtilization(
        drug=drug_def["drug"],
        category=drug_def.get("category", ""),
        cy2024_units=cy2024["units"],
        cy2024_rx=cy2024["rx"],
        cy2024_total=cy2024["total"],
        cy2024_medicaid=cy2024["medicaid"],
        h1_2025_units=h1_2025["units"],
        h1_2025_rx=h1_2025["rx"],
        h1_2025_total=h1_2025["total"],
        h1_2025_medicaid=h1_2025["medicaid"],
        annualized_2025_total=annualized,
        nadac_per_unit=nadac_price,
        nadac_source=nadac_desc,
        cost_per_unit_actual=cpu,
        yoy_growth=yoy,
    )


def analyze_humira_scenarios(conn) -> list[HumiraScenario]:
    """Model Humira->biosimilar conversion under non-preferred PDL status.

    April 2026 effective date means SFY26 Q4 (Apr-Jun 2026) is the first
    impacted quarter. Non-preferred status drives faster adoption than
    the January 2026 co-preferred assumption.
    """
    cy2024 = query_utilization(conn, "%Humira%", "sdu_2024")
    h1_2025 = query_utilization(conn, "%Humira%", "sdu_2025")

    # Use H1 2025 annualized as baseline (more current)
    annual_units = h1_2025["units"] * 2 if h1_2025["units"] > 0 else cy2024["units"]
    annual_spend = h1_2025["total"] * 2 if h1_2025["total"] > 0 else cy2024["total"]
    quarterly_units = annual_units / 4
    quarterly_spend = annual_spend / 4

    humira_nadac = 3362.68  # NADAC Per Unit for Humira(CF) 40mg
    # Blended biosimilar NADAC (weighted by market availability)
    biosimilar_nadacs = {
        "adalimumab-aaty(CF)": 493.15,  # Newest, cheapest
        "adalimumab-adbm(CF)": 636.04,  # Cyltezo
        "adalimumab-aacf(CF)": 871.45,
        "adalimumab-adaz(CF)": 1590.28,  # Hyrimoz
    }
    avg_biosimilar_nadac = sum(biosimilar_nadacs.values()) / len(biosimilar_nadacs)
    nadac_discount = 1 - (avg_biosimilar_nadac / humira_nadac)

    # Actual reimbursed cost per unit (higher than NADAC due to dispensing fees, etc.)
    cpu_actual = annual_spend / annual_units if annual_units > 0 else 3868.05
    biosimilar_cpu = cpu_actual * (1 - nadac_discount)

    # Non-preferred adoption scenarios (faster than co-preferred)
    # Effective April 1, 2026 = SFY26 Q4 only, then full SFY27
    scenarios = {
        "Conservative": {
            # SFY26: only Q4 impacted (Apr-Jun 2026)
            "SFY26_Q1": 0.00, "SFY26_Q2": 0.00, "SFY26_Q3": 0.00, "SFY26_Q4": 0.10,
            # SFY27: gradual ramp
            "SFY27_Q1": 0.20, "SFY27_Q2": 0.30, "SFY27_Q3": 0.38, "SFY27_Q4": 0.45,
        },
        "Moderate": {
            "SFY26_Q1": 0.00, "SFY26_Q2": 0.00, "SFY26_Q3": 0.00, "SFY26_Q4": 0.20,
            "SFY27_Q1": 0.35, "SFY27_Q2": 0.45, "SFY27_Q3": 0.55, "SFY27_Q4": 0.65,
        },
        "Aggressive": {
            "SFY26_Q1": 0.00, "SFY26_Q2": 0.00, "SFY26_Q3": 0.00, "SFY26_Q4": 0.30,
            "SFY27_Q1": 0.50, "SFY27_Q2": 0.60, "SFY27_Q3": 0.70, "SFY27_Q4": 0.80,
        },
    }

    results = []
    for name, adoption in scenarios.items():
        sfy26_savings = 0
        sfy27_savings = 0

        for q_key, bio_pct in adoption.items():
            savings_per_unit = cpu_actual - biosimilar_cpu
            q_savings = quarterly_units * bio_pct * savings_per_unit
            if q_key.startswith("SFY26"):
                sfy26_savings += q_savings
            else:
                sfy27_savings += q_savings

        ss26 = STATE_SHARE[2026]["non_expansion"]
        ss27 = STATE_SHARE[2027]["non_expansion"]

        results.append(HumiraScenario(
            name=name,
            adoption_by_quarter=adoption,
            sfy26_gross_savings=sfy26_savings,
            sfy27_gross_savings=sfy27_savings,
            sfy26_state_savings=sfy26_savings * ss26,
            sfy27_state_savings=sfy27_savings * ss27,
            two_year_gross=sfy26_savings + sfy27_savings,
            two_year_state=sfy26_savings * ss26 + sfy27_savings * ss27,
        ))

    return results


def analyze_swap_pairs(conn) -> list[SwapAnalysis]:
    """Analyze cost impact of therapeutic swap pairs."""
    pairs = [
        {
            "category": "IL-17 (Psoriasis/SpA)",
            "from_drug": "Cosentyx",
            "from_pattern": "%Cosentyx%",
            "from_nadac_pattern": "%COSENTYX%",
            "to_drug": "Taltz",
            "to_nadac_pattern": "%TALTZ%",
            "note": "Similar efficacy; Taltz 7-8% cheaper per NADAC. Dosing frequency comparable.",
        },
        {
            "category": "IL-12/23 (Ustekinumab)",
            "from_drug": "Stelara",
            "from_pattern": "%Stelara%",
            "from_nadac_pattern": "%STELARA%",
            "to_drug": "Starjemza",
            "to_nadac_pattern": "%STARJEMZA%",
            "note": "Biosimilar to Stelara. No NADAC pricing yet (too new for CMS survey). "
                    "Typical biosimilar discount for specialty drugs: 30-50%.",
        },
        {
            "category": "IL-6 (Tocilizumab/RA)",
            "from_drug": "Actemra",
            "from_pattern": "%Actemra%",
            "from_nadac_pattern": "%ACTEMRA%",
            "to_drug": "Tyenne",
            "to_nadac_pattern": "%TYENNE%",
            "note": "Biosimilar to Actemra. 36% NADAC discount.",
        },
        {
            "category": "GLP-1 Weight Management",
            "from_drug": "Wegovy Injectable",
            "from_pattern": "%Wegovy%",
            "from_nadac_pattern": "%WEGOVY%MG%PEN%",
            "to_drug": "Wegovy Tablet",
            "to_nadac_pattern": "%WEGOVY%TABLET%",
            "note": "Same drug, oral formulation. 90%+ NADAC reduction per unit. "
                    "Dosing equivalence and compliance may differ.",
        },
    ]

    results = []
    for pair in pairs:
        cy2024 = query_utilization(conn, pair["from_pattern"], "sdu_2024")

        from_nadacs = query_nadac(conn, pair["from_nadac_pattern"])
        to_nadacs = query_nadac(conn, pair["to_nadac_pattern"])

        from_price = from_nadacs[len(from_nadacs) // 2]["nadac"] if from_nadacs else 0
        to_price = to_nadacs[len(to_nadacs) // 2]["nadac"] if to_nadacs else 0

        discount = (1 - to_price / from_price) if from_price > 0 and to_price > 0 else 0
        baseline = cy2024["total"]
        units = cy2024["units"]

        results.append(SwapAnalysis(
            category=pair["category"],
            from_drug=pair["from_drug"],
            to_drug=pair["to_drug"],
            from_nadac=from_price,
            to_nadac=to_price,
            discount_pct=discount,
            baseline_annual_spend=baseline,
            baseline_annual_units=units,
            potential_savings_25pct=baseline * discount * 0.25 if discount > 0 else 0,
            potential_savings_50pct=baseline * discount * 0.50 if discount > 0 else 0,
            potential_savings_75pct=baseline * discount * 0.75 if discount > 0 else 0,
            note=pair["note"],
        ))

    return results


def analyze_implementation_risks() -> list[dict]:
    """Summarize implementation concerns from pharmacy directors."""
    return [
        {
            "risk": "Claims System Lag",
            "description": "PDL effective 04/01, but claims system not updated until 04/03/2026. "
                          "Two-day window of incorrect adjudication.",
            "exposure": "Estimated 2 days × average daily Humira/Cosentyx/Stelara claims",
            "severity": "High",
        },
        {
            "risk": "PA Criteria Gap",
            "description": "NC DHB has not updated Humira PA criteria to require biosimilar "
                          "trial/failure first (as done for Stelara). Plans cannot enforce "
                          "non-preferred status without updated PA criteria.",
            "severity": "Critical",
            "exposure": "Without PA enforcement, the non-preferred designation has no mechanism "
                       "to drive biosimilar adoption. Savings projections assume PA is in place.",
        },
        {
            "risk": "Member Notification",
            "description": "PHPs received notification on 04/01 at 2:24 PM, formal notice on "
                          "04/02 at 9:30 AM. No time for required member notification on complex "
                          "medication changes.",
            "severity": "High",
            "exposure": "Potential member access issues and regulatory compliance concerns.",
        },
        {
            "risk": "Existing PA Management",
            "description": "Request to end-date existing Humira PAs on 03/31/2026 to force "
                          "conversion. Abrupt PA termination for established specialty drug "
                          "patients raises clinical transition concerns.",
            "severity": "Medium",
            "exposure": "Patient disruption; potential for adverse outcomes during transition.",
        },
    ]


def get_pharmacy_capitation_context():
    """Pull pharmacy line 40 context from rate_analysis_suite if available."""
    if not RATE_DB_PATH.exists():
        return None

    try:
        conn = sqlite3.connect(RATE_DB_PATH)
        # Query total pharmacy expected PMPM
        cur = conn.execute("""
            SELECT sfy, SUM(expected_pmpm) as total_pharmacy_pmpm
            FROM service_line_rates
            WHERE line_number = 40
            GROUP BY sfy
            ORDER BY sfy
        """)
        rows = cur.fetchall()
        conn.close()
        return {str(r[0]): r[1] for r in rows} if rows else None
    except Exception:
        return None


def run_full_analysis():
    """Run complete PDL impact analysis and return structured results."""
    conn = get_conn()

    from pdl_april_2026 import PDL_CHANGES, REFERENCE_DRUGS, SWAP_PAIRS

    # 1. Drug-level utilization profiles
    print("Analyzing drug utilization profiles...")
    utilization = {}
    for drug_def in PDL_CHANGES + REFERENCE_DRUGS:
        profile = analyze_drug(conn, drug_def)
        utilization[drug_def["drug"]] = profile
        total_str = f"${profile.cy2024_total:,.0f}" if profile.cy2024_total > 0 else "N/A"
        print(f"  {drug_def['drug']:30s}  CY2024: {total_str:>15s}  "
              f"NADAC: ${profile.nadac_per_unit:,.2f}")

    # 2. Humira conversion scenarios
    print("\nModeling Humira biosimilar adoption scenarios...")
    humira_scenarios = analyze_humira_scenarios(conn)
    for s in humira_scenarios:
        print(f"  {s.name:15s}  2-year gross: ${s.two_year_gross:>12,.0f}  "
              f"state: ${s.two_year_state:>12,.0f}")

    # 3. Therapeutic swap analysis
    print("\nAnalyzing therapeutic swap pairs...")
    swaps = analyze_swap_pairs(conn)
    for s in swaps:
        pct = f"{s.discount_pct:.1%}" if s.discount_pct > 0 else "TBD"
        print(f"  {s.from_drug:20s} -> {s.to_drug:20s}  "
              f"NADAC discount: {pct:>6s}  "
              f"Baseline: ${s.baseline_annual_spend:>12,.0f}")

    # 4. Implementation risks
    risks = analyze_implementation_risks()

    # 5. Capitation context
    cap_context = get_pharmacy_capitation_context()

    # 6. Aggregate summary
    print("\n" + "=" * 70)
    print("AGGREGATE FINANCIAL IMPACT SUMMARY")
    print("=" * 70)

    # Total affected drug spend
    affected_drugs = ["Humira", "Cosentyx", "Stelara", "Actemra", "Wegovy"]
    total_affected = sum(
        utilization[d].cy2024_total for d in affected_drugs if d in utilization
    )
    print(f"\nTotal CY2024 spend on directly affected drugs: ${total_affected:,.0f}")

    # Humira moderate scenario
    moderate = next(s for s in humira_scenarios if s.name == "Moderate")
    print(f"\nHumira (Moderate scenario):")
    print(f"  SFY26 gross savings: ${moderate.sfy26_gross_savings:>12,.0f}")
    print(f"  SFY27 gross savings: ${moderate.sfy27_gross_savings:>12,.0f}")
    print(f"  2-year state savings: ${moderate.two_year_state:>12,.0f}")

    # Swap pair savings at 50% conversion
    total_swap_savings = sum(s.potential_savings_50pct for s in swaps)
    print(f"\nOther swap pairs (50% conversion, annual):")
    for s in swaps:
        if s.potential_savings_50pct > 0:
            print(f"  {s.category:35s}  ${s.potential_savings_50pct:>12,.0f}")
    print(f"  {'Total swap savings':35s}  ${total_swap_savings:>12,.0f}")

    conn.close()

    return {
        "utilization": {k: asdict(v) for k, v in utilization.items()},
        "humira_scenarios": [asdict(s) for s in humira_scenarios],
        "swaps": [asdict(s) for s in swaps],
        "risks": risks,
        "capitation_context": cap_context,
        "total_affected_spend": total_affected,
        "fmap_rates": FMAP_BY_SFY,
        "state_share": STATE_SHARE,
    }


if __name__ == "__main__":
    results = run_full_analysis()
    # Save intermediate results for report generation
    output_path = Path(__file__).parent / "pdl_impact_results.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to {output_path}")
