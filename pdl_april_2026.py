"""NC Medicaid PDL changes effective April 1, 2026.

Structured definitions of all drug categories affected by the off-cycle
PDL update. Each entry includes matching patterns for SDU product names
and NADAC NDC descriptions, plus the therapeutic context.

Source: NC DHHS PDL Change Email 4-2-26, PDL Effective April 2026_0.pdf
"""

PDL_CHANGES = [
    # ── MOVED TO NON-PREFERRED (expected utilization shift away) ──────────
    {
        "drug": "Humira",
        "generic": "adalimumab",
        "category": "TNF-alpha Inhibitor",
        "sdu_pattern": "%Humira%",
        "nadac_pattern": "%HUMIRA%",
        "old_status": "Co-Preferred",
        "new_status": "Non-Preferred",
        "effective": "2026-04-01",
        "direction": "demotion",
        "note": "ALL forms: Pen, Syringe, Crohn's/Psoriasis starter packs",
    },
    {
        "drug": "Adalimumab-adaz (Hyrimoz)",
        "generic": "adalimumab-adaz",
        "category": "TNF-alpha Biosimilar",
        "sdu_pattern": "%adalimumab-adaz%",
        "nadac_pattern": "%ADALIMUMAB-ADAZ%",
        "old_status": "Preferred",
        "new_status": "Non-Preferred",
        "effective": "2026-04-01",
        "direction": "demotion",
        "note": "Biosimilar also moved to non-preferred",
    },
    {
        "drug": "Adalimumab-adbm (Cyltezo)",
        "generic": "adalimumab-adbm",
        "category": "TNF-alpha Biosimilar",
        "sdu_pattern": "%adalimumab-adbm%",
        "nadac_pattern": "%ADALIMUMAB-ADBM%",
        "old_status": "Preferred",
        "new_status": "Non-Preferred",
        "effective": "2026-04-01",
        "direction": "demotion",
        "note": "Biosimilar also moved to non-preferred",
    },
    {
        "drug": "Cosentyx",
        "generic": "secukinumab",
        "category": "IL-17 Inhibitor",
        "sdu_pattern": "%Cosentyx%",
        "nadac_pattern": "%COSENTYX%",
        "old_status": "Preferred",
        "new_status": "Non-Preferred",
        "effective": "2026-04-01",
        "direction": "demotion",
        "note": "Replaced by Taltz as preferred IL-17",
    },
    {
        "drug": "Steqeyma",
        "generic": "ustekinumab-stba",
        "category": "IL-12/23 Biosimilar",
        "sdu_pattern": "%Steqeyma%",
        "nadac_pattern": "%STEQEYMA%",
        "old_status": "Preferred",
        "new_status": "Non-Preferred",
        "effective": "2026-04-01",
        "direction": "demotion",
        "note": "Replaced by Starjemza as preferred ustekinumab biosimilar",
    },

    # ── MOVED TO PREFERRED (state wants utilization to shift TO these) ────
    {
        "drug": "Taltz",
        "generic": "ixekizumab",
        "category": "IL-17 Inhibitor",
        "sdu_pattern": "%Taltz%",
        "nadac_pattern": "%TALTZ%",
        "old_status": "Non-Preferred",
        "new_status": "Preferred",
        "effective": "2026-04-01",
        "direction": "promotion",
        "note": "Replaces Cosentyx; auto-injector and syringe forms",
        "replaces": "Cosentyx",
    },
    {
        "drug": "Starjemza",
        "generic": "ustekinumab-aekn",
        "category": "IL-12/23 Biosimilar",
        "sdu_pattern": "%Starjemza%",
        "nadac_pattern": "%STARJEMZA%",
        "old_status": "Non-Preferred",
        "new_status": "Preferred",
        "effective": "2026-04-01",
        "direction": "promotion",
        "note": "Biosimilar to Stelara; vial and syringe forms",
        "replaces": "Stelara",
    },
    {
        "drug": "Tyenne",
        "generic": "tocilizumab-aazg",
        "category": "IL-6 Inhibitor",
        "sdu_pattern": "%Tyenne%",
        "nadac_pattern": "%TYENNE%",
        "old_status": "Non-Preferred",
        "new_status": "Preferred",
        "effective": "2026-04-01",
        "direction": "promotion",
        "note": "Biosimilar to Actemra; autoinjector, syringe, and vial forms",
        "replaces": "Actemra",
    },
    {
        "drug": "Skytrofa",
        "generic": "lonapegsomatropin-tcgd",
        "category": "Growth Hormone",
        "sdu_pattern": "%Skytrofa%",
        "nadac_pattern": "%SKYTROFA%",
        "old_status": "Non-Preferred",
        "new_status": "Preferred",
        "effective": "2026-04-01",
        "direction": "promotion",
        "note": "Cartridge form; replaces various growth hormones",
    },
    {
        "drug": "Ebglyss",
        "generic": "lebrikizumab-lbkz",
        "category": "IL-13 Inhibitor (Atopic Dermatitis)",
        "sdu_pattern": "%Ebglyss%",
        "nadac_pattern": "%EBGLYSS%",
        "old_status": "Non-Preferred",
        "new_status": "Preferred",
        "effective": "2026-04-01",
        "direction": "promotion",
        "note": "Syringe and pen forms for atopic dermatitis",
    },
    {
        "drug": "Wegovy Tablet",
        "generic": "semaglutide (oral)",
        "category": "GLP-1 Weight Management",
        "sdu_pattern": "%Wegovy%",
        "nadac_pattern": "%WEGOVY%",
        "old_status": "Non-Preferred",
        "new_status": "Preferred",
        "effective": "2026-04-01",
        "direction": "promotion",
        "note": "Tablet form for weight management; oral alternative to injectable",
    },
    {
        "drug": "Vtama",
        "generic": "tapinarof",
        "category": "Topical (Psoriasis)",
        "sdu_pattern": "%Vtama%",
        "nadac_pattern": "%VTAMA%",
        "old_status": "Non-Preferred",
        "new_status": "Preferred",
        "effective": "2026-04-01",
        "direction": "promotion",
        "note": "Cream for plaque psoriasis",
    },
]

# ── Related drugs whose utilization provides baseline context ─────────────

REFERENCE_DRUGS = [
    {
        "drug": "Stelara",
        "generic": "ustekinumab",
        "sdu_pattern": "%Stelara%",
        "nadac_pattern": "%STELARA%",
        "note": "Branded reference for Starjemza biosimilar",
    },
    {
        "drug": "Actemra",
        "generic": "tocilizumab",
        "sdu_pattern": "%Actemra%",
        "nadac_pattern": "%ACTEMRA%",
        "note": "Branded reference for Tyenne biosimilar",
    },
    {
        "drug": "Simlandi",
        "generic": "adalimumab-ryvk",
        "sdu_pattern": "%Simlandi%",
        "nadac_pattern": "%SIMLANDI%",
        "note": "Preferred adalimumab biosimilar (remains preferred)",
    },
    {
        "drug": "Yusimry",
        "generic": "adalimumab-aqvh",
        "sdu_pattern": "%Yusimry%",
        "nadac_pattern": "%YUSIMRY%",
        "note": "Preferred adalimumab biosimilar (remains preferred)",
    },
    {
        "drug": "Hadlima",
        "generic": "adalimumab-bwwd",
        "sdu_pattern": "%Hadlima%",
        "nadac_pattern": "%HADLIMA%",
        "note": "Adalimumab biosimilar",
    },
    {
        "drug": "Dupixent",
        "generic": "dupilumab",
        "sdu_pattern": "%Dupixent%",
        "nadac_pattern": "%DUPIXENT%",
        "note": "Context for Ebglyss (atopic dermatitis competitor)",
    },
]


def get_all_drugs():
    """Return all PDL changes plus reference drugs."""
    return PDL_CHANGES + REFERENCE_DRUGS


def get_demotions():
    """Drugs moved to non-preferred."""
    return [d for d in PDL_CHANGES if d.get("direction") == "demotion"]


def get_promotions():
    """Drugs moved to preferred."""
    return [d for d in PDL_CHANGES if d.get("direction") == "promotion"]


# ── Therapeutic swap pairs for cost comparison ────────────────────────────

SWAP_PAIRS = [
    {
        "category": "TNF-alpha (Adalimumab)",
        "from_drug": "Humira",
        "to_drugs": ["Simlandi", "Yusimry", "Hadlima"],
        "note": "Humira non-preferred -> preferred biosimilars",
    },
    {
        "category": "IL-17 (Psoriasis/SpA)",
        "from_drug": "Cosentyx",
        "to_drugs": ["Taltz"],
        "note": "Cosentyx non-preferred -> Taltz preferred",
    },
    {
        "category": "IL-12/23 (Ustekinumab)",
        "from_drug": "Stelara",
        "to_drugs": ["Starjemza"],
        "note": "Stelara -> Starjemza biosimilar preferred",
    },
    {
        "category": "IL-6 (Tocilizumab)",
        "from_drug": "Actemra",
        "to_drugs": ["Tyenne"],
        "note": "Actemra -> Tyenne biosimilar preferred",
    },
]
