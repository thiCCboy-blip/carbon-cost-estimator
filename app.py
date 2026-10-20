"""Streamlit dashboard: AI-Driven Carbon-Accounting & Dynamic Cost Estimation
for Commercial Real Estate.

Run:  streamlit run app.py
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from carbon_model import CarbonCostModel

st.set_page_config(
    page_title="Carbon-Cost Estimator | CRE",
    page_icon="🏗️",
    layout="wide",
)

# --------------------------------------------------------------------------- #
# Cached model
# --------------------------------------------------------------------------- #
@st.cache_resource
def get_model() -> CarbonCostModel:
    return CarbonCostModel()


model = get_model()
alts = model.alternatives_map()

# --------------------------------------------------------------------------- #
# Sidebar controls
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.title("🏗️ Carbon-Cost Model")
    st.caption(
        "Embodied-carbon accounting + dynamic cost estimation for commercial "
        "real-estate BOQs (Dubai regional factors)."
    )
    st.divider()

    gfa = st.number_input(
        "Gross Floor Area (m²)",
        min_value=500.0,
        value=float(model.gfa_m2),
        step=500.0,
        help="Used for carbon-intensity (kgCO₂e/m²) metrics.",
    )
    model.gfa_m2 = gfa

    carbon_price = st.slider(
        "Carbon Price (AED / tCO₂e)",
        min_value=0,
        max_value=1000,
        value=350,
        step=10,
        help=(
            "Shadow or real carbon price. Reference points: EU-ETS ~€90/t "
            "(≈370 AED), UAE has no federal carbon tax yet — use a shadow "
            "price for transition planning (GARP SCR Ch.10)."
        ),
    )

    st.divider()
    st.subheader("♻️ Material Swaps")
    swap_all = st.toggle("Swap ALL available low-carbon alternatives", value=False)

    default_sel = list(alts) if swap_all else []
    selected = default_sel
    if not swap_all:
        options = {
            mid: f"{v['material_name']}  →  {v['alt_name']}"
            for mid, v in alts.items()
        }
        selected = st.multiselect(
            "Pick materials to swap",
            options=list(options),
            format_func=lambda x: options[x],
            default=[],
        )

    st.divider()
    st.subheader("📤 Your Own BOQ")
    uploaded_boq = st.file_uploader(
        "Upload BOQ (CSV)",
        type=["csv"],
        help=(
            "Required columns: description, material_id, quantity, unit. "
            "Optional: item_no, category, element. material_id must exist in "
            "the materials database."
        ),
    )
    st.download_button(
        "Download BOQ template",
        data=model._default_boq.to_csv(index=False).encode("utf-8"),
        file_name="boq_template.csv",
        mime="text/csv",
    )
    upload_status: list[str] = []
    if uploaded_boq is not None:
        try:
            upload_status = model.set_boq(pd.read_csv(uploaded_boq))
        except ValueError as exc:
            st.error(str(exc))
            model.reset_boq()
            upload_status = []
    else:
        model.reset_boq()

    for msg in upload_status:
        st.caption("✅ " + msg)

custom_boq = uploaded_boq is not None

# --------------------------------------------------------------------------- #
# Compute
# --------------------------------------------------------------------------- #
baseline = model.baseline()
scenario = model.scenario(selected)
summary = model.summary(scenario, float(carbon_price))

# --------------------------------------------------------------------------- #
# Header KPIs
# --------------------------------------------------------------------------- #
st.title("Carbon-Accounting & Dynamic Cost Estimation")
st.caption(
    "Commercial Real Estate | BOQ mapped to regional costs (AED) and "
    "embodied-carbon factors (EN 15804 / ICE Database, A1–A3)."
)
if custom_boq:
    st.info("📄 Custom BOQ in use — all figures below are computed from your uploaded file.")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Baseline Cost", f"AED {baseline.baseline_cost:,.0f}")
c2.metric("Baseline Carbon", f"{baseline.baseline_carbon:,.0f} tCO₂e")
c3.metric(
    "Carbon Intensity",
    f"{baseline.carbon_intensity():.0f} kgCO₂e/m²",
    help="Benchmark: typical Dubai commercial ~500–900 kgCO₂e/m² (structure+envelope).",
)
c4.metric("Low-Carbon Alternatives", f"{len(alts)} swaps")

st.divider()

# --------------------------------------------------------------------------- #
# Scenario comparison
# --------------------------------------------------------------------------- #
left, right = st.columns([3, 2])

with left:
    st.subheader("📊 Baseline vs. Scenario")
    comp = pd.DataFrame(
        {
            "Metric": [
                "Cost (AED m)",
                "Carbon (ktCO₂e)",
                "Intensity (kgCO₂e/m²)",
            ],
            "Baseline": [
                baseline.baseline_cost / 1e6,
                baseline.baseline_carbon / 1e3,
                baseline.carbon_intensity(),
            ],
            "Scenario": [
                scenario.scenario_cost / 1e6,
                scenario.scenario_carbon / 1e3,
                scenario.carbon_intensity(scenario.scenario_carbon),
            ],
        }
    )
    fig = go.Figure()
    for col, color in [("Baseline", "#636EFA"), ("Scenario", "#00CC96")]:
        fig.add_trace(
            go.Bar(
                name=col,
                x=comp["Metric"],
                y=comp[col],
                marker_color=color,
                text=comp[col].map(lambda v: f"{v:,.2f}"),
                textposition="outside",
            )
        )
    fig.update_layout(
        barmode="group",
        height=380,
        margin=dict(t=30, b=10),
        yaxis_title="Value",
        legend_title="",
    )
    st.plotly_chart(fig, width="stretch")

with right:
    st.subheader("💰 Trade-off Summary")
    if selected:
        st.metric(
            "Δ Cost",
            f"AED {scenario.delta_cost:+,.0f}",
            f"{scenario.cost_change_pct:+.2f}%",
            delta_color="inverse",
        )
        st.metric(
            "Δ Carbon",
            f"{scenario.delta_carbon:+,.0f} tCO₂e",
            f"{scenario.carbon_reduction_pct:+.1f}% reduction",
        )
        st.metric(
            "Carbon-Tax Impact",
            f"AED {scenario.carbon_tax_impact(float(carbon_price)):,.0f}",
            f"at {carbon_price} AED/tCO₂e",
            delta_color="inverse",
        )
        net = scenario.net_financial_impact(float(carbon_price))
        st.metric(
            "Net Financial Impact",
            f"AED {net:+,.0f}",
            "cost + carbon tax",
            delta_color="inverse",
        )
        be = scenario.breakeven_carbon_price()
        if be is not None:
            st.success(f"Breakeven carbon price: **{be:,.0f} AED/tCO₂e**")
            if be <= carbon_price:
                st.info("✅ At the current carbon price, the swap set is net-positive financially.")
            else:
                st.warning(
                    "Carbon price must rise above this level for the swap to pay back."
                )
        else:
            st.error("Selected swaps deliver no carbon saving.")
    else:
        st.info("Select material swaps in the sidebar to model a scenario.")
        st.metric("Δ Cost", "AED 0")
        st.metric("Δ Carbon", "0 tCO₂e")

st.divider()

# --------------------------------------------------------------------------- #
# Where the carbon is (baseline hotspots) + category breakdown
# --------------------------------------------------------------------------- #
h1, h2 = st.columns(2)

with h1:
    st.subheader("🔥 Baseline Carbon Hotspots")
    detail_base = model.detailed_boq({})
    hot = (
        detail_base.groupby("description")["Baseline Carbon (tCO2e)"]
        .sum()
        .sort_values(ascending=True)
        .tail(12)
    )
    fig = px.bar(
        x=hot.values,
        y=hot.index,
        orientation="h",
        labels={"x": "tCO₂e", "y": ""},
        color=hot.values,
        color_continuous_scale="Reds",
    )
    fig.update_layout(height=420, showlegend=False, margin=dict(t=10, b=10))
    st.plotly_chart(fig, width="stretch")

with h2:
    st.subheader("🧮 Carbon by Category (Baseline)")
    cat = (
        detail_base.groupby("category")["Baseline Carbon (tCO2e)"]
        .sum()
        .reset_index()
    )
    fig = px.pie(
        cat,
        values="Baseline Carbon (tCO2e)",
        names="category",
        hole=0.45,
        color_discrete_sequence=px.colors.qualitative.Safe,
    )
    fig.update_layout(height=420, margin=dict(t=10, b=10))
    st.plotly_chart(fig, width="stretch")

st.divider()

# --------------------------------------------------------------------------- #
# Marginal Abatement Cost Curve
# --------------------------------------------------------------------------- #
st.subheader("📉 Marginal Abatement Cost Curve (MACC)")
st.caption(
    "Every available low-carbon swap ranked by cost per tonne of CO₂e avoided. "
    "Bars below zero save money *and* carbon — the 'no-regret' abatement wedge."
)
curve = model.abatement_curve()
if not curve.empty:
    fig = px.bar(
        curve,
        x="Material swap",
        y="AED per tCO2e saved",
        color="AED per tCO2e saved",
        color_continuous_scale="RdYlGn_r",
        text=curve["AED per tCO2e saved"].map(lambda v: f"{v:,.0f}"),
    )
    fig.update_traces(marker_line_width=0, textposition="outside")
    fig.update_layout(
        height=420,
        showlegend=False,
        margin=dict(t=20, b=10),
        yaxis_title="AED per tCO₂e saved",
    )
    st.plotly_chart(fig, width="stretch")
    st.dataframe(curve, width="stretch", hide_index=True)
else:
    st.info("No abatement options available.")

st.divider()

# --------------------------------------------------------------------------- #
# Swap detail + detailed BOQ
# --------------------------------------------------------------------------- #
tabs = st.tabs(["🔁 Swap Analysis", "📄 Detailed BOQ", "📦 Materials DB"])

with tabs[0]:
    if scenario.swaps:
        sdf = scenario.swaps_frame()
        st.dataframe(sdf, width="stretch", hide_index=True)
        st.caption(
            "AED / tCO₂e saved: cost premium per tonne avoided. "
            "Negative = the swap *saves* money while cutting carbon."
        )
    else:
        st.info("No swaps applied.")

with tabs[1]:
    detail = model.detailed_boq({mid: "alt" for mid in selected})
    st.dataframe(
        detail.style.format(
            {
                "Baseline Cost (AED)": "{:,.0f}",
                "Scenario Cost (AED)": "{:,.0f}",
                "Baseline Carbon (tCO2e)": "{:,.2f}",
                "Scenario Carbon (tCO2e)": "{:,.2f}",
                "Delta Cost (AED)": "{:,.0f}",
                "Delta Carbon (tCO2e)": "{:,.2f}",
            }
        ),
        width="stretch",
        hide_index=True,
    )

with tabs[2]:
    show = model.materials[
        [
            "material_id",
            "material_name",
            "category",
            "unit",
            "unit_cost_aed",
            "carbon_factor_kgco2e_per_unit",
            "alt_material_name",
            "alt_unit_cost_aed",
            "alt_carbon_factor_kgco2e_per_unit",
            "carbon_factor_source",
        ]
    ].copy()
    st.dataframe(show, width="stretch", hide_index=True)
    st.caption(
        "Carbon factors: cradle-to-gate (A1–A3), kgCO₂e per functional unit. "
        "Sources: ICE Database v3, Worldsteel LCI, IAI LCI, manufacturer EPDs."
    )

# --------------------------------------------------------------------------- #
# Export
# --------------------------------------------------------------------------- #
st.divider()
st.subheader("⬇️ Export Report")
xlsx = model.to_excel(scenario, float(carbon_price))
st.download_button(
    label="Download full report (Excel)",
    data=xlsx,
    file_name="carbon_cost_report.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)
st.caption("Workbook includes Summary, Detailed BOQ, Swap Analysis and MACC sheets.")
