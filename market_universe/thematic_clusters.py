# Thematic Cluster mapping — groups your existing `industry` values (from
# universe_seed.py) into finer-grained clusters, similar in spirit to the
# multi-cluster "Thematic" view pattern, built independently from your own
# 47 real industries (not copied from any third-party taxonomy).
#
# Each entry: industry_name -> cluster_name
# Anything not listed falls back to "Other" so nothing silently disappears.

THEMATIC_CLUSTERS = {
    # ── Banking & Financial Services ─────────────────────────────────────
    "Private Sector Bank":            "Banking & Financial Services",
    "Public Sector Bank":             "Banking & Financial Services",
    "Small Finance Bank":             "Banking & Financial Services",
    "NBFC":                           "Banking & Financial Services",
    "Housing Finance":                "Banking & Financial Services",
    "PSU Infra Finance":              "Banking & Financial Services",
    "Diversified Financial Services": "Banking & Financial Services",
    "Asset Management":               "Banking & Financial Services",
    "Brokerage & Wealth":             "Banking & Financial Services",
    "Exchanges & Platforms":          "Banking & Financial Services",
    "Depositories & Clearing":        "Banking & Financial Services",
    "Life Insurance":                 "Banking & Financial Services",
    "General Insurance":              "Banking & Financial Services",
    "Fintech Platforms":              "Banking & Financial Services",

    # ── Automotive & Components ──────────────────────────────────────────
    "Passenger Cars":                 "Automotive & Components",
    "Chassis & Metal Parts":          "Automotive & Components",
    "Batteries & Lighting":           "Automotive & Components",

    # ── Information Technology & Software ────────────────────────────────
    "IT Services":                    "Information Technology & Software",
    "ER&D / Product Software":        "Information Technology & Software",
    "Enterprise Platforms":           "Information Technology & Software",
    "Analytics & Data Services":      "Information Technology & Software",
    "BPO/ITeS":                       "Information Technology & Software",
    "Electronic Manufacturing Services": "Information Technology & Software",
    "Internet & E-Commerce":          "Information Technology & Software",
    "B2B Marketplaces":               "Information Technology & Software",
    "Digital Entertainment":          "Information Technology & Software",

    # ── Healthcare & Pharma ───────────────────────────────────────────────
    "Pharma - Formulators":           "Healthcare & Pharma",
    "Pharma - API & CRAMS":           "Healthcare & Pharma",
    "Pharma - API/Formulators":       "Healthcare & Pharma",
    "Specialty Chemicals - Pharma":   "Healthcare & Pharma",
    "Hospitals":                      "Healthcare & Pharma",
    "Pharmacy Retail":                "Healthcare & Pharma",

    # ── Metals & Mining ───────────────────────────────────────────────────
    "Iron & Steel Core":              "Metals & Mining",
    "Iron & Steel Products":          "Metals & Mining",
    "Iron Ore & Mineral Mining":      "Metals & Mining",
    "Steel Tubes & Pipes":            "Metals & Mining",
    "Diversified Metals":             "Metals & Mining",
    "Aluminium & Base Metals":        "Metals & Mining",
    "Copper & Specialty Metallurgy":  "Metals & Mining",
    "Coal & Mining":                  "Metals & Mining",
    "Carbon Black":                   "Metals & Mining",

    # ── Defense, Aerospace & Industrial Engineering ─────────────────────
    "Aerospace & Defense OEM":        "Defense, Aerospace & Engineering",
    "Construction & Engineering":     "Defense, Aerospace & Engineering",
    "Industrial Products":            "Defense, Aerospace & Engineering",
    "Cables & Wires":                 "Defense, Aerospace & Engineering",

    # ── Energy & Utilities ────────────────────────────────────────────────
    "Oil & Gas E&P":                  "Energy & Utilities",
    "Integrated Utilities":           "Energy & Utilities",
    "Renewable Energy":               "Energy & Utilities",

    # ── Lifestyle & Retail ────────────────────────────────────────────────
    "Apparel Retail Chains":          "Lifestyle & Retail",
}


def get_cluster(industry: str) -> str:
    """Look up an industry's thematic cluster, falling back to 'Other'."""
    return THEMATIC_CLUSTERS.get(industry, "Other")
