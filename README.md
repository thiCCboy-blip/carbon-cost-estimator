# AI-Driven Carbon-Accounting & Dynamic Cost Estimation Model for Commercial Real Estate

A Python + Streamlit dashboard that computes the **financial cost (AED)** *and* the
**embodied carbon footprint (tCO₂e)** of a commercial building project straight from its
Bill of Quantities (BOQ) — then lets you swap conventional materials for low-carbon
alternatives and instantly see the **cost trade-off vs. carbon-tax savings**.

Built around a realistic Dubai commercial-building BOQ (≈10,000 m² GFA, AED 24.95M,
8,817 tCO₂e baseline ≈ 882 kgCO₂e/m²).

---

## Why this project

- **GARP SCR Ch. 9 (Climate & Nature Risk Assessment):** measures physical/transition
  exposure of the built environment via a real emissions inventory with scenario analysis.
- **GARP SCR Ch. 10 (Transition Planning):** produces a **Marginal Abatement Cost Curve
  (MACC)** and a breakeven carbon price — the exact artefacts used to plan decarbonisation
  pathways.
- **Industry relevance:** the environmental-economic trade-off capability that
  Procore / Autodesk / Big-Four ESG arms need for scope-3 and CBAM-adjacent reporting.

---

## Quick start

```bash
cd carbon-cost-estimator
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Run tests (engine + full dashboard render via Streamlit AppTest):

```bash
python -m unittest test_engine test_dashboard -v
```

CLI smoke check (no UI):

```bash
python carbon_model.py
```

---

## Features

| Feature | What it does |
|---|---|
| **BOQ → cost + carbon** | Maps every BOQ line to a material's regional unit cost (AED) and embodied-carbon factor (kgCO₂e/unit, EN 15804 A1–A3) |
| **Dynamic material swaps** | Toggle conventional ↔ low-carbon per material (OPC → geopolymer/LC3 concrete, BF-BOF → EAF recycled steel, primary → recycled aluminium, etc.) |
| **Carbon-tax trade-off** | Configurable carbon price (AED/tCO₂e): tax impact, **net financial impact**, and **breakeven carbon price** for any swap set |
| **MACC chart** | Every swap ranked by AED per tCO₂e avoided — surfaces "no-regret" (negative-cost) abatement first |
| **Hotspot analysis** | Carbon by BOQ item and by category (pie/bar) to target the biggest emitters |
| **Excel export** | Multi-sheet workbook: Summary, Detailed BOQ (line-by-line deltas), Swap Analysis, Abatement Curve |
| **Scenario presets** | Single-material swaps, multiselect, or "swap everything" maximum-abatement case |

### Headline results (defaults: 350 AED/tCO₂e shadow price)

- Baseline: **AED 24,950,250** | **8,817 tCO₂e** | **882 kgCO₂e/m²**
- Max abatement (all swaps): **−64.7% carbon** at only **+0.78% cost**
- Breakeven carbon price of the full swap set: **≈ 34 AED/tCO₂e** → net-positive at any
  realistic carbon price; geopolymer-concrete-only swap breaks even at ≈ 405 AED/t

---

## Project structure

```
carbon-cost-estimator/
├── app.py               # Streamlit dashboard (KPIs, swap controls, MACC, export)
├── carbon_model.py      # Core engine: BOQ/cost/carbon math, swaps, scenarios
├── data/
│   ├── boq.csv          # Bill of Quantities (substructure → MEP/site)
│   └── materials.csv    # Costs, carbon factors, low-carbon alternatives + sources
├── test_engine.py       # Unit tests for the calculation engine
├── test_dashboard.py    # End-to-end dashboard test (streamlit.testing.v1 AppTest)
└── requirements.txt
```

## Data & methodology notes

- **Carbon factors:** cradle-to-gate (A1–A3), kgCO₂e per functional unit — ICE Database v3,
  Worldsteel LCI, IAI LCI, manufacturer EPDs. Each factor's source is recorded in
  `data/materials.csv` (`carbon_factor_source`).
- **Costs:** indicative Dubai 2024–25 supply-and-fix rates (AED); replace with your own
  rates in `materials.csv` — the engine re-derives everything from the table.
- **Carbon price:** the UAE has no federal carbon tax; the slider defaults to a
  350 AED/t *shadow* price (EU-ETS ≈ €90/t reference) for transition planning.
- **Units matter:** facade/glazing/finishes factors are per m², steel/copper per tonne,
  pipes per m, diesel per litre — always match `unit` in the BOQ to the factor's unit.

## Extending it

1. Add BOQ rows to `data/boq.csv` (reuse or add `material_id`s).
2. Add materials/alternatives to `data/materials.csv` — fill the `alt_*` columns to make a
   material swappable.
3. Adjust `Gross Floor Area` in the sidebar for intensity benchmarks.
