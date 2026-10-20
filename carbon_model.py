"""Core calculation engine for the Carbon-Cost Estimation Model.

Loads a Bill of Quantities (BOQ) and a materials database (cost + embodied
carbon factors), then computes the financial cost and embodied carbon footprint
of a commercial building project. Supports dynamic material swaps (e.g.
OPC concrete -> geopolymer, BF-BOF steel -> recycled EAF steel) and evaluates
the cost-vs-carbon-tax trade-off.

Carbon factors are aligned with EN 15804 / ICE Database conventions
(A1-A3 cradle-to-gate, kgCO2e per functional unit).
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).parent / "data"

# Default gross floor area (m2) used for intensity metrics (typical Dubai
# mid-rise commercial tower). Override per project.
DEFAULT_GFA_M2 = 10_000.0


@dataclass
class SwapResult:
    """Result of applying a single material swap."""

    material_id: str
    material_name: str
    alt_name: str
    quantity: float
    unit: str
    baseline_unit_cost: float
    alt_unit_cost: float
    baseline_cf: float
    alt_cf: float
    baseline_cost: float
    alt_cost: float
    baseline_carbon: float  # tonnes CO2e
    alt_carbon: float  # tonnes CO2e
    delta_cost: float  # AED (+ = premium)
    delta_carbon: float  # tCO2e (- = saving)

    @property
    def cost_per_tco2e_saved(self) -> float | None:
        """AED premium per tonne of CO2e avoided (negative = net saving)."""
        saving = -self.delta_carbon
        if saving <= 0:
            return None
        return self.delta_cost / saving


@dataclass
class ScenarioResult:
    """Aggregated result for a full BOQ under a set of swaps."""

    baseline_cost: float
    baseline_carbon: float  # tCO2e
    scenario_cost: float
    scenario_carbon: float  # tCO2e
    swaps: list[SwapResult] = field(default_factory=list)
    gfa_m2: float = DEFAULT_GFA_M2

    @property
    def delta_cost(self) -> float:
        return self.scenario_cost - self.baseline_cost

    @property
    def delta_carbon(self) -> float:
        return self.scenario_carbon - self.baseline_carbon

    @property
    def carbon_reduction_pct(self) -> float:
        if self.baseline_carbon == 0:
            return 0.0
        return -self.delta_carbon / self.baseline_carbon * 100.0

    @property
    def cost_change_pct(self) -> float:
        if self.baseline_cost == 0:
            return 0.0
        return self.delta_cost / self.baseline_cost * 100.0

    def carbon_intensity(self, carbon: float | None = None) -> float:
        """kgCO2e per m2 of GFA."""
        c = self.baseline_carbon if carbon is None else carbon
        return c * 1000.0 / self.gfa_m2

    def carbon_tax_impact(self, carbon_price_aed_per_t: float) -> float:
        """Carbon-tax cost difference (AED). Negative = tax saving."""
        return self.delta_carbon * carbon_price_aed_per_t

    def net_financial_impact(self, carbon_price_aed_per_t: float) -> float:
        """Delta cost net of avoided carbon tax (positive = net cost)."""
        return self.delta_cost + self.carbon_tax_impact(carbon_price_aed_per_t)

    def breakeven_carbon_price(self) -> float | None:
        """Carbon price (AED/tCO2e) at which the swap set becomes net-neutral.

        Solves delta_cost + delta_carbon * P = 0  ->  P = -delta_cost / delta_carbon.
        Returns None if the scenario has no carbon saving.
        """
        if self.delta_carbon >= 0:
            return None
        return -self.delta_cost / self.delta_carbon

    def swaps_frame(self) -> pd.DataFrame:
        rows = [
            {
                "Material": s.material_name,
                "Alternative": s.alt_name,
                "Qty": s.quantity,
                "Unit": s.unit,
                "Base Cost (AED)": s.baseline_cost,
                "Alt Cost (AED)": s.alt_cost,
                "Delta Cost (AED)": s.delta_cost,
                "Base Carbon (tCO2e)": s.baseline_carbon,
                "Alt Carbon (tCO2e)": s.alt_carbon,
                "Delta Carbon (tCO2e)": s.delta_carbon,
                "AED / tCO2e saved": s.cost_per_tco2e_saved,
            }
            for s in self.swaps
        ]
        return pd.DataFrame(rows)


class CarbonCostModel:
    """BOQ cost + embodied-carbon calculator with dynamic material swaps."""

    def __init__(
        self,
        boq_path: Path | None = None,
        materials_path: Path | None = None,
        gfa_m2: float = DEFAULT_GFA_M2,
    ):
        self.boq_path = boq_path or DATA_DIR / "boq.csv"
        self.materials_path = materials_path or DATA_DIR / "materials.csv"
        self.gfa_m2 = gfa_m2
        self.boq: pd.DataFrame = pd.read_csv(self.boq_path)
        self._default_boq: pd.DataFrame = self.boq.copy()
        self.materials: pd.DataFrame = pd.read_csv(self.materials_path)
        self.materials = self.materials.dropna(subset=["material_id"])
        self._mat = self.materials.set_index("material_id")

    # ------------------------------------------------------------------ #
    # BOQ upload / validation
    # ------------------------------------------------------------------ #
    REQUIRED_BOQ_COLUMNS = ("description", "material_id", "quantity", "unit")

    @classmethod
    def validate_boq_df(
        cls, df: pd.DataFrame, known_material_ids: set[str]
    ) -> tuple[pd.DataFrame, list[str]]:
        """Validate an uploaded BOQ. Returns (clean_df, list_of_messages).

        Required columns: description, material_id, quantity, unit
        (category / element / item_no are optional). Rows with unknown
        material_ids or non-positive quantities are dropped and reported.
        """
        messages: list[str] = []
        missing = [c for c in cls.REQUIRED_BOQ_COLUMNS if c not in df.columns]
        if missing:
            raise ValueError(
                f"Missing required column(s): {', '.join(missing)}. "
                f"Expected at least: {', '.join(cls.REQUIRED_BOQ_COLUMNS)}"
            )
        clean = df.copy()
        for opt, fill in (("item_no", ""), ("category", "Other"), ("element", "")):
            if opt not in clean.columns:
                clean[opt] = fill
        clean["quantity"] = pd.to_numeric(clean["quantity"], errors="coerce")
        bad_qty = clean["quantity"].isna() | (clean["quantity"] <= 0)
        if bad_qty.any():
            messages.append(f"Dropped {int(bad_qty.sum())} row(s) with missing/non-numeric/non-positive quantity.")
            clean = clean[~bad_qty]
        clean["material_id"] = clean["material_id"].astype(str).str.strip()
        unknown = ~clean["material_id"].isin(known_material_ids)
        if unknown.any():
            ids = sorted(clean.loc[unknown, "material_id"].unique())
            messages.append(
                f"Dropped {int(unknown.sum())} row(s) with material_id not in the "
                f"materials database: {', '.join(ids[:8])}{'…' if len(ids) > 8 else ''}"
            )
            clean = clean[~unknown]
        if clean.empty:
            raise ValueError("No valid BOQ rows remaining after validation.")
        clean = clean[
            ["item_no", "description", "category", "material_id", "quantity", "unit", "element"]
        ].reset_index(drop=True)
        messages.append(f"{len(clean)} BOQ line(s) accepted.")
        return clean, messages

    def set_boq(self, df: pd.DataFrame) -> list[str]:
        """Replace the active BOQ with a user-uploaded one. Returns messages."""
        clean, messages = self.validate_boq_df(df, set(self._mat.index))
        self.boq = clean
        return messages

    def reset_boq(self) -> None:
        """Restore the built-in demo BOQ."""
        self.boq = self._default_boq.copy()

    # ------------------------------------------------------------------ #
    # Material lookups
    # ------------------------------------------------------------------ #
    def material(self, material_id: str) -> pd.Series:
        try:
            return self._mat.loc[material_id]
        except KeyError as exc:
            raise KeyError(f"Unknown material_id: {material_id}") from exc

    def has_alternative(self, material_id: str) -> bool:
        row = self._mat.loc[material_id]
        return (
            pd.notna(row.get("low_carbon_alternative_id"))
            and str(row.get("low_carbon_alternative_id")).strip() != ""
        )

    def alternatives_map(self) -> dict[str, dict]:
        """material_id -> alternative details, for materials that have one."""
        out = {}
        for mid, row in self._mat.iterrows():
            if self.has_alternative(mid):
                out[mid] = {
                    "material_name": row["material_name"],
                    "alt_id": row["low_carbon_alternative_id"],
                    "alt_name": row["alt_material_name"],
                    "alt_unit_cost": float(row["alt_unit_cost_aed"]),
                    "alt_cf": float(row["alt_carbon_factor_kgco2e_per_unit"]),
                    "unit": row["unit"],
                    "category": row["category"],
                    "cost_premium_pct": float(row.get("cost_premium_pct", 0) or 0),
                }
        return out

    # ------------------------------------------------------------------ #
    # Core calculation
    # ------------------------------------------------------------------ #
    def baseline(self) -> ScenarioResult:
        """Cost + carbon with no swaps applied."""
        return self._compute({})

    def _compute(self, swaps: dict[str, str]) -> ScenarioResult:
        """swaps: material_id -> 'alt' (use the built-in alternative) or a
        specific replacement material_id present in the materials table."""
        boq = self.boq.copy()
        boq = boq[boq["material_id"].notna()]

        # Resolve per-line unit cost / carbon factor
        base_costs, base_carbons, alt_costs, alt_carbons = [], [], [], []
        swap_details: dict[str, SwapResult] = {}

        for _, row in boq.iterrows():
            mid = row["material_id"]
            qty = float(row["quantity"])
            m = self.material(mid)

            b_cost = float(m["unit_cost_aed"])
            b_cf = float(m["carbon_factor_kgco2e_per_unit"])

            mode = swaps.get(mid)
            if mode is None:
                a_cost, a_cf = b_cost, b_cf
            elif mode == "alt":
                if not self.has_alternative(mid):
                    raise ValueError(f"No low-carbon alternative for {mid}")
                a_cost = float(m["alt_unit_cost_aed"])
                a_cf = float(m["alt_carbon_factor_kgco2e_per_unit"])
            else:
                alt_row = self.material(mode)
                a_cost = float(alt_row["unit_cost_aed"])
                a_cf = float(alt_row["carbon_factor_kgco2e_per_unit"])

            base_costs.append(b_cost * qty)
            base_carbons.append(b_cf * qty / 1000.0)  # kg -> tonnes
            alt_costs.append(a_cost * qty)
            alt_carbons.append(a_cf * qty / 1000.0)

            if mode is not None and (a_cost != b_cost or a_cf != b_cf):
                # Aggregate identical material swaps across BOQ lines
                if mid in swap_details:
                    prev = swap_details[mid]
                    prev.quantity += qty
                    prev.baseline_cost += b_cost * qty
                    prev.alt_cost += a_cost * qty
                    prev.baseline_carbon += b_cf * qty / 1000.0
                    prev.alt_carbon += a_cf * qty / 1000.0
                    prev.delta_cost = prev.alt_cost - prev.baseline_cost
                    prev.delta_carbon = prev.alt_carbon - prev.baseline_carbon
                else:
                    alt_name = (
                        str(m["alt_material_name"])
                        if mode == "alt"
                        else str(self.material(mode)["material_name"])
                    )
                    swap_details[mid] = SwapResult(
                        material_id=mid,
                        material_name=str(m["material_name"]),
                        alt_name=alt_name,
                        quantity=qty,
                        unit=str(row["unit"]),
                        baseline_unit_cost=b_cost,
                        alt_unit_cost=a_cost,
                        baseline_cf=b_cf,
                        alt_cf=a_cf,
                        baseline_cost=b_cost * qty,
                        alt_cost=a_cost * qty,
                        baseline_carbon=b_cf * qty / 1000.0,
                        alt_carbon=a_cf * qty / 1000.0,
                        delta_cost=a_cost * qty - b_cost * qty,
                        delta_carbon=(a_cf - b_cf) * qty / 1000.0,
                    )

        boq["baseline_cost_aed"] = base_costs
        boq["baseline_carbon_tco2e"] = base_carbons
        boq["scenario_cost_aed"] = alt_costs
        boq["scenario_carbon_tco2e"] = alt_carbons

        return ScenarioResult(
            baseline_cost=sum(base_costs),
            baseline_carbon=sum(base_carbons),
            scenario_cost=sum(alt_costs),
            scenario_carbon=sum(alt_carbons),
            swaps=list(swap_details.values()),
            gfa_m2=self.gfa_m2,
        )

    def scenario(self, swap_material_ids: list[str]) -> ScenarioResult:
        """Apply the built-in low-carbon alternative for each listed id."""
        return self._compute({mid: "alt" for mid in swap_material_ids})

    def swap_all_alternatives(self) -> ScenarioResult:
        """Apply every available low-carbon alternative (maximum abatement)."""
        return self._compute({mid: "alt" for mid in self.alternatives_map()})

    def detailed_boq(self, swaps: dict[str, str] | None = None) -> pd.DataFrame:
        """Line-by-line BOQ with cost & carbon columns for export."""
        res = self._compute(swaps or {})
        boq = self.boq.copy()
        boq = boq[boq["material_id"].notna()].copy()
        # Recompute per-line (same logic as _compute, for export clarity)
        base_c, base_k, alt_c, alt_k = [], [], [], []
        for _, row in boq.iterrows():
            mid = row["material_id"]
            qty = float(row["quantity"])
            m = self.material(mid)
            b_c, b_k = float(m["unit_cost_aed"]), float(m["carbon_factor_kgco2e_per_unit"])
            mode = (swaps or {}).get(mid)
            if mode == "alt":
                a_c = float(m["alt_unit_cost_aed"])
                a_k = float(m["alt_carbon_factor_kgco2e_per_unit"])
            elif mode:
                a_row = self.material(mode)
                a_c, a_k = float(a_row["unit_cost_aed"]), float(a_row["carbon_factor_kgco2e_per_unit"])
            else:
                a_c, a_k = b_c, b_k
            base_c.append(b_c * qty)
            base_k.append(b_k * qty / 1000)
            alt_c.append(a_c * qty)
            alt_k.append(a_k * qty / 1000)
        boq["Baseline Cost (AED)"] = base_c
        boq["Scenario Cost (AED)"] = alt_c
        boq["Baseline Carbon (tCO2e)"] = base_k
        boq["Scenario Carbon (tCO2e)"] = alt_k
        boq["Delta Cost (AED)"] = boq["Scenario Cost (AED)"] - boq["Baseline Cost (AED)"]
        boq["Delta Carbon (tCO2e)"] = boq["Scenario Carbon (tCO2e)"] - boq["Baseline Carbon (tCO2e)"]
        return boq.drop(columns=["material_id"], errors="ignore")

    # ------------------------------------------------------------------ #
    # Marginal abatement analysis
    # ------------------------------------------------------------------ #
    def abatement_curve(self) -> pd.DataFrame:
        """Cost-effectiveness of every available swap (AED per tCO2e).

        Sorted ascending (cheapest abatement first) — the classic MACC
        (Marginal Abatement Cost Curve) input, per GARP SCR transition
        planning / decarbonisation pathway framing.
        """
        rows = []
        for mid in self.alternatives_map():
            res = self.scenario([mid])
            s = res.swaps[0] if res.swaps else None
            if s is None:
                continue
            saving = -s.delta_carbon
            if saving <= 0:
                continue
            rows.append(
                {
                    "Material swap": f"{s.material_name} -> {s.alt_name}",
                    "Carbon saving (tCO2e)": saving,
                    "Cost delta (AED)": s.delta_cost,
                    "AED per tCO2e saved": s.delta_cost / saving,
                    "Category": self.material(mid)["category"],
                }
            )
        df = pd.DataFrame(rows)
        if not df.empty:
            df = df.sort_values("AED per tCO2e saved").reset_index(drop=True)
        return df

    # ------------------------------------------------------------------ #
    # Reporting helpers
    # ------------------------------------------------------------------ #
    def summary(self, res: ScenarioResult, carbon_price_aed_per_t: float) -> dict:
        be = res.breakeven_carbon_price()
        return {
            "Baseline cost (AED)": res.baseline_cost,
            "Scenario cost (AED)": res.scenario_cost,
            "Delta cost (AED)": res.delta_cost,
            "Cost change (%)": res.cost_change_pct,
            "Baseline carbon (tCO2e)": res.baseline_carbon,
            "Scenario carbon (tCO2e)": res.scenario_carbon,
            "Carbon saving (tCO2e)": -res.delta_carbon,
            "Carbon reduction (%)": res.carbon_reduction_pct,
            "Baseline intensity (kgCO2e/m2)": res.carbon_intensity(),
            "Scenario intensity (kgCO2e/m2)": res.carbon_intensity(res.scenario_carbon),
            "Carbon price (AED/tCO2e)": carbon_price_aed_per_t,
            "Carbon tax impact (AED)": res.carbon_tax_impact(carbon_price_aed_per_t),
            "Net financial impact (AED)": res.net_financial_impact(carbon_price_aed_per_t),
            "Breakeven carbon price (AED/tCO2e)": be,
        }

    def to_excel(self, res: ScenarioResult, carbon_price_aed_per_t: float) -> bytes:
        """Multi-sheet Excel workbook: Summary, Detailed BOQ, Swap analysis."""
        swaps = {s.material_id: "alt" for s in res.swaps}
        summary = pd.DataFrame(
            [{"Metric": k, "Value": v} for k, v in self.summary(res, carbon_price_aed_per_t).items()]
        )
        swaps_df = res.swaps_frame()
        curve = self.abatement_curve()
        detail = self.detailed_boq(swaps)

        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as xl:
            summary.to_excel(xl, sheet_name="Summary", index=False)
            detail.to_excel(xl, sheet_name="Detailed BOQ", index=False)
            if not swaps_df.empty:
                swaps_df.to_excel(xl, sheet_name="Swap Analysis", index=False)
            if not curve.empty:
                curve.to_excel(xl, sheet_name="Abatement Curve", index=False)
        return buf.getvalue()


if __name__ == "__main__":
    model = CarbonCostModel()
    base = model.baseline()
    print(f"Baseline cost:  AED {base.baseline_cost:,.0f}")
    print(f"Baseline carbon: {base.baseline_carbon:,.0f} tCO2e")
    print(f"Intensity: {base.carbon_intensity():.1f} kgCO2e/m2")
    print("\nAlternatives available:", list(model.alternatives_map()))
    full = model.swap_all_alternatives()
    print(f"\nMax abatement scenario: -{full.carbon_reduction_pct:.1f}% carbon, "
          f"{full.cost_change_pct:+.2f}% cost, breakeven "
          f"{full.breakeven_carbon_price()} AED/t")
