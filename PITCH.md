# The Pitch — Carbon-Cost Estimator

## 30-second version (interview / scholarship intro)

> "I built a tool that reads a construction Bill of Quantities and prices two things
> at once — the project cost in dirhams and its embodied carbon in tonnes of CO₂.
> You can swap conventional concrete or steel for low-carbon alternatives and
> instantly see the cost premium against carbon-tax savings, including the carbon
> price at which going green breaks even. It turns decarbonisation from a slogan
> into a line-item decision an estimator can defend."

---

## Why it maps to GARP SCR

### Chapter 9 — Climate and Nature Risk Assessment
- **Transition risk, quantified:** the model attaches a shadow carbon price (slider,
  AED/tCO₂e) to a real asset's emissions inventory and reports exposure — exactly how
  transition-risk channels (policy/legal → carbon pricing) are assessed.
- **Physical + transition exposure of the built environment:** the baseline inventory
  (8,817 tCO₂e ≈ 882 kgCO₂e/m² for a 10,000 m² Dubai commercial building) is the
  starting point for any climate risk assessment of a real-estate portfolio.
- **Data quality discipline:** every emission factor carries its source
  (ICE Database v3, Worldsteel LCI, manufacturer EPDs, EN 15804 A1–A3 scope) —
  traceability is a SCR data-governance expectation.

### Chapter 10 — Transition Planning
- **Marginal Abatement Cost Curve (MACC):** the dashboard ranks every decarbonisation
  lever by AED per tonne avoided — the standard artefact for prioritising a transition
  pathway (do the negative-cost measures first).
- **Breakeven carbon price:** states the policy threshold at which each measure pays
  back — i.e., planning under carbon-price uncertainty.
- **Target setting with trade-offs:** "swap everything" scenario shows −64.7% carbon
  for +0.78% capex — a defensible interim decarbonisation target with costed levers,
  not an unsubstantiated net-zero pledge.

---

## Numbers to quote

| Metric | Value |
|---|---|
| Baseline project cost | AED 24,950,250 |
| Baseline embodied carbon | 8,817 tCO₂e (882 kgCO₂e/m²) |
| Full low-carbon swap | −64.7% carbon for +0.78% cost |
| Breakeven carbon price (full set) | ≈ 34 AED/tCO₂e |
| Breakeven (geopolymer concrete only) | ≈ 405 AED/tCO₂e |
| Swappable materials | 18 alternatives across concrete, steel, aluminium, glass, MEP |
| Test coverage | 15 automated tests (engine + full dashboard render) |

## Resume bullet (ready to paste)

> **Carbon-Cost Estimator — AI-driven embodied-carbon accounting for construction BOQs**
> Built a Streamlit/Pandas dashboard that prices a commercial-building BOQ on two axes
> (AED cost + tCO₂e per EN 15804/ICE factors) and models low-carbon material swaps,
> reporting cost-per-tonne abatement, carbon-tax impact and breakeven carbon price;
> outputs a Marginal Abatement Cost Curve for transition planning (GARP SCR Ch. 9–10).
> Full test suite (15 tests). Result: −64.7% embodied carbon at +0.78% cost.

## One-liner for a scholarship essay

> "Decarbonising the built environment is an estimation problem before it is an
> engineering problem — I built the tool that puts riyals and tonnes of CO₂ on the
> same line of the Bill of Quantities."
