"""Streamlit UI for the single-panel thermal simulator.

Layout (see PLAN section 6): a sidebar with the language switch, a conditions
form, panel parameters, the model and mounting selectors and a Compute button;
and a main area with four tabs -- result & balance, animation, the math, and
assumptions.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make the src-layout ``panelsim`` package importable when the app is launched
# without an editable install -- e.g. on Streamlit Community Cloud, which installs
# requirements.txt but does not pip-install the project itself. Harmless locally
# (the path is already present via the editable install / pytest config).
_SRC = Path(__file__).resolve().parent.parent / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import pandas as pd
import streamlit as st

from panelsim.i18n import SUPPORTED_LANGS, get_language, set_language, t
from panelsim.math_explain import MODEL_MATH
from panelsim.models import (
    Conditions,
    ModelChoice,
    Mounting,
    PanelParams,
    SimInput,
)
from panelsim.physics.energy_balance import simulate_transient
from panelsim.simulate import run_simulation
from panelsim.viz.charts import energy_split_bar, transient_chart
from panelsim.viz.heatflow_component import render_heatflow

LANG_NAMES = {"en": "English", "hr": "Hrvatski"}

# Default values for the keyed condition widgets, seeded into session state so
# the scenario presets can overwrite them cleanly.
_INPUT_DEFAULTS: dict[str, object] = {
    "g": 800.0,
    "t_air": 25.0,
    "wind": 2.0,
    "sky_auto": True,
    "gnd_auto": True,
    "t_sky_val": 5.0,
    "t_gnd_val": 25.0,
}

# One-click weather presets. Each sets the ambient conditions; a clear sky is
# left on auto (T_air - 20 degC), while overcast pins a warmer radiative sky.
SCENARIOS: dict[str, dict[str, object]] = {
    "clear_day": {"g": 1000.0, "t_air": 32.0, "wind": 1.5, "sky_auto": True},
    "cloudy": {"g": 250.0, "t_air": 19.0, "wind": 5.0, "sky_auto": False, "t_sky_val": 14.0},
    "sunset": {"g": 180.0, "t_air": 16.0, "wind": 2.5, "sky_auto": True},
}


def apply_scenario(name: str) -> None:
    """Write a preset's values into session state (runs before widgets render)."""
    for key, value in SCENARIOS[name].items():
        st.session_state[key] = value


st.set_page_config(
    page_title="Solar Panel Thermal Simulator",
    page_icon="☀️",
    layout="wide",
    initial_sidebar_state="expanded",
)

_CSS = """
<style>
.block-container {padding-top: 2.2rem; max-width: 1200px;}
div[data-testid="stMetric"] {
    background: rgba(130,160,200,0.10);
    border: 1px solid rgba(130,160,200,0.25);
    border-radius: 12px; padding: 12px 16px;
}
div[data-testid="stMetricValue"] {font-size: 1.7rem;}
h1 {font-weight: 750; letter-spacing: -0.5px;}
.small-note {color: rgba(120,120,130,0.95); font-size: 0.86rem;}
</style>
"""
st.markdown(_CSS, unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Sidebar: language, then a form with conditions, parameters, model, mounting. #
# --------------------------------------------------------------------------- #
def build_sidebar() -> tuple[SimInput, bool]:
    for key, value in _INPUT_DEFAULTS.items():
        st.session_state.setdefault(key, value)

    lang = st.sidebar.selectbox(
        t("sidebar.language"),
        options=SUPPORTED_LANGS,
        index=SUPPORTED_LANGS.index(get_language()),
        format_func=lambda code: LANG_NAMES.get(code, code),
        key="lang_select",
    )
    set_language(lang)

    st.sidebar.subheader(t("scenario.title"))
    st.sidebar.caption(t("scenario.hint"))
    sc = st.sidebar.columns(3)
    sc[0].button(
        "☀️ " + t("scenario.clear_day"),
        key="sc_clear",
        on_click=apply_scenario,
        args=("clear_day",),
        width="stretch",
    )
    sc[1].button(
        "☁️ " + t("scenario.cloudy"),
        key="sc_cloud",
        on_click=apply_scenario,
        args=("cloudy",),
        width="stretch",
    )
    sc[2].button(
        "🌇 " + t("scenario.sunset"),
        key="sc_sunset",
        on_click=apply_scenario,
        args=("sunset",),
        width="stretch",
    )

    show_transient = st.sidebar.toggle(t("sidebar.transient"), value=False, key="transient_toggle")

    with st.sidebar.form("conditions_form"):
        st.subheader(t("sidebar.conditions"))
        g = st.slider(
            t("input.irradiance"),
            min_value=0.0,
            max_value=1400.0,
            step=10.0,
            key="g",
            help=t("help.irradiance"),
        )
        t_air = st.slider(
            t("input.ambient_temp"),
            min_value=-20.0,
            max_value=55.0,
            step=0.5,
            key="t_air",
            help=t("help.ambient_temp"),
        )
        wind = st.slider(
            t("input.wind_speed"),
            min_value=0.0,
            max_value=20.0,
            step=0.1,
            key="wind",
            help=t("help.wind_speed"),
        )

        col_a, col_b = st.columns(2)
        with col_a:
            st.caption(t("input.sky_temp"))
            sky_auto = st.checkbox(t("input.auto"), key="sky_auto")
            t_sky = (
                None
                if sky_auto
                else st.number_input(
                    t("input.sky_temp"),
                    key="t_sky_val",
                    help=t("help.sky_temp"),
                    label_visibility="collapsed",
                )
            )
        with col_b:
            st.caption(t("input.gnd_temp"))
            gnd_auto = st.checkbox(t("input.auto"), key="gnd_auto")
            t_gnd = (
                None
                if gnd_auto
                else st.number_input(
                    t("input.gnd_temp"),
                    key="t_gnd_val",
                    help=t("help.gnd_temp"),
                    label_visibility="collapsed",
                )
            )

        st.subheader(t("sidebar.model"))
        model = st.selectbox(
            t("sidebar.model"),
            options=list(ModelChoice),
            index=0,
            format_func=lambda m: t(f"model.{m.value}"),
            label_visibility="collapsed",
            help=t("help.model"),
        )
        mounting = st.selectbox(
            t("sidebar.mounting"),
            options=list(Mounting),
            index=0,
            format_func=lambda m: t(f"mounting.{m.value}"),
            help=t("help.mounting"),
        )

        with st.expander(t("sidebar.advanced")):
            eta_stc = st.number_input(
                t("input.eta_stc"), 0.05, 0.35, 0.20, 0.005, help=t("help.eta_stc")
            )
            gamma = st.number_input(
                t("input.gamma"), -0.010, 0.0, -0.004, 0.0005, format="%.4f", help=t("help.gamma")
            )
            alpha = st.number_input(t("input.alpha"), 0.50, 1.0, 0.90, 0.01, help=t("help.alpha"))
            epsilon = st.number_input(
                t("input.epsilon"), 0.50, 1.0, 0.90, 0.01, help=t("help.epsilon")
            )
            noct = st.number_input(t("input.noct"), 30.0, 58.0, 45.0, 0.5, help=t("help.noct"))
            area = st.number_input(t("input.area"), 0.5, 5.0, 1.7, 0.1, help=t("help.area"))
            mass_cp = st.number_input(
                t("input.mass_cp"), 2000.0, 40000.0, 11000.0, 500.0, help=t("help.mass_cp")
            )

        # Inside a form, widget values only commit on submit; we then read them
        # below to build the SimInput, so the return value itself is unused.
        st.form_submit_button(t("sidebar.compute"), type="primary", width="stretch")

    sim_input = SimInput(
        conditions=Conditions(g=g, t_air=t_air, wind=wind, t_sky=t_sky, t_gnd=t_gnd),
        panel=PanelParams(
            eta_stc=eta_stc,
            gamma=gamma,
            alpha=alpha,
            epsilon=epsilon,
            noct=noct,
            area_m2=area,
            mass_cp=mass_cp,
            mounting=mounting,
        ),
        model=model,
    )
    return sim_input, show_transient


# --------------------------------------------------------------------------- #
# Tab renderers.                                                              #
# --------------------------------------------------------------------------- #
def _anim_labels() -> dict[str, str]:
    return {
        "sun": t("anim.sun"),
        "reflection": t("anim.reflection"),
        "radiation": t("anim.radiation"),
        "convection": t("anim.convection"),
        "conduction": t("anim.conduction"),
        "electricity": t("anim.electricity"),
        "panel_temp": t("anim.panel_temp"),
        "wm2": t("result.wm2"),
        "transient_note": t("anim.transient_note"),
    }


def render_result_tab(sim_input: SimInput) -> None:
    result = run_simulation(sim_input)
    f = result.fluxes
    area = sim_input.panel.area_m2
    eta_here = f.p_el / sim_input.conditions.g if sim_input.conditions.g > 0 else 0.0

    st.subheader(t("result.header"))
    c1, c2, c3 = st.columns(3)
    c1.metric(
        t("result.cell_temp"),
        f"{result.t_cell:.1f} °C",
        delta=f"{result.t_cell - result.t_air:+.1f} °C {t('result.delta_t')}",
        delta_color="off",
    )
    c2.metric(t("result.efficiency"), f"{eta_here * 100:.1f} %")
    c3.metric(
        t("result.electricity"),
        f"{f.p_el * area:.0f} W",
        delta=f"{f.p_el:.0f} {t('result.wm2')}",
        delta_color="off",
    )

    st.markdown(f"#### {t('result.balance_header')}")
    labels = {
        "reflected": t("result.reflected"),
        "electricity": t("result.electricity_ch"),
        "radiated": t("result.radiated"),
        "convected": t("result.convected"),
        "conducted": t("result.conducted"),
    }
    st.plotly_chart(
        energy_split_bar(
            f,
            labels,
            t("result.balance_header"),
            x_title=t("result.percent").replace("G", "<i>G</i>"),
        ),
        use_container_width=True,
        config={"displayModeBar": False},
    )

    pct = f.channels_percent()
    watts = f.channels_watts(area)
    per_m2 = f.channels_per_m2()
    rows = [
        ("reflected", "result.reflected", "desc.reflected"),
        ("p_el", "result.electricity_ch", "desc.electricity"),
        ("q_rad", "result.radiated", "desc.radiated"),
        ("q_conv", "result.convected", "desc.convected"),
        ("q_cond", "result.conducted", "desc.conducted"),
    ]
    table = pd.DataFrame(
        {
            t("result.wm2"): [f"{per_m2[k]:.1f}" for k, _, _ in rows],
            t("result.percent"): [f"{pct[k]:.1f}" for k, _, _ in rows],
            t("result.watts"): [f"{watts[k]:.0f}" for k, _, _ in rows],
        },
        index=[t(lbl) for _, lbl, _ in rows],
    )
    table.index.name = t("result.channel")
    # st.table renders a static HTML table (no lazy canvas grid), so it is always
    # visible and prints/screenshots reliably regardless of scroll position.
    st.table(table)

    heat_total = f.q_thermal_out
    st.markdown(
        f"**{t('result.heat_out_total')}: {heat_total:.0f} {t('result.wm2')} "
        f"({heat_total * area:.0f} W)** — {t('note.radiated_vs_total')}"
    )

    with st.expander(t("general.summary"), expanded=False):
        for _, _, dkey in rows:
            st.markdown(f"- {t(dkey)}")

    st.info(t("note.stored_steady"))
    st.caption(t("note.single_panel"))
    st.caption("✓ " + t("note.closure") + f"  (residual = {f.closure_residual():+.2e} W/m²)")
    if sim_input.model != ModelChoice.FULL_BALANCE:
        st.caption(t("note.model_split"))


def render_animation_tab(sim_input: SimInput, show_transient: bool) -> None:
    result = run_simulation(sim_input)
    st.subheader(t("anim.header"))
    warmup = show_transient and sim_input.model == ModelChoice.FULL_BALANCE
    render_heatflow(
        result,
        _anim_labels(),
        wind=sim_input.conditions.wind,
        height=460,
        warmup=warmup,
    )
    st.caption(t("anim.hint"))

    if sim_input.model == ModelChoice.FULL_BALANCE and show_transient:
        transient = simulate_transient(sim_input.conditions, sim_input.panel)
        st.markdown(f"#### {t('chart.header')}")
        st.plotly_chart(
            transient_chart(
                transient,
                steady_t=result.t_cell,
                t_air=result.t_air,
                labels={"steady": t("chart.steady")},
            ),
            use_container_width=True,
        )
    elif show_transient:
        st.caption(t("note.model_split"))


def render_math_tab(sim_input: SimInput) -> None:
    spec = MODEL_MATH[sim_input.model]
    st.subheader(f"{t('math.header')} — {t(f'model.{sim_input.model.value}')}")
    st.caption(t("math.intro"))

    st.markdown(f"**{t('math.equation')}**")
    st.latex(spec.latex)
    for extra in spec.extra_latex:
        st.latex(extra)

    st.markdown(f"**{t('math.variables')}**")
    header = f"| {t('math.var_symbol')} | {t('math.var_meaning')} | {t('math.var_typical')} |\n"
    header += "|---|---|---|\n"
    body = "".join(f"| ${v.symbol}$ | {t(v.desc_key)} | {v.typical} |\n" for v in spec.variables)
    st.markdown(header + body)

    st.markdown(f"**{t('math.worked')}**")
    worked = spec.worked_example(sim_input.conditions, sim_input.panel)
    st.latex(r"\begin{aligned}" + worked + r"\end{aligned}")

    st.markdown(f"**{t('math.assumptions')}**")
    for key in spec.assumption_keys:
        st.markdown(f"- {t(key)}")

    st.markdown(f"**{t('math.reference')}**")
    st.caption(spec.reference)


def render_assumptions_tab(sim_input: SimInput) -> None:
    spec = MODEL_MATH[sim_input.model]
    st.subheader(t("assume_tab.header"))
    st.markdown(
        f"**{t('assume_tab.model')}:** {t(f'model.{sim_input.model.value}')}  \n"
        f"**{t('assume_tab.mounting')}:** {t(f'mounting.{sim_input.panel.mounting.value}')}"
    )

    st.markdown(f"#### {t('assume_tab.limitations')}")
    for key in spec.assumption_keys:
        st.markdown(f"- {t(key)}")

    st.markdown(f"#### {t('assume_tab.general')}")
    st.markdown(f"- {t('note.stored_steady')}")
    st.markdown(f"- {t('note.radiated_vs_total')}")
    st.markdown(f"- {t('note.single_panel')}")

    st.markdown(f"#### {t('assume_tab.reference')}")
    st.caption(spec.reference)


# --------------------------------------------------------------------------- #
# Main.                                                                       #
# --------------------------------------------------------------------------- #
def main() -> None:
    sim_input, show_transient = build_sidebar()

    st.title("☀️ " + t("app.title"))
    st.caption(t("app.subtitle") + " · " + t("app.tagline"))

    tab_result, tab_anim, tab_math, tab_assume = st.tabs(
        [t("tab.result"), t("tab.animation"), t("tab.math"), t("tab.assumptions")]
    )
    with tab_result:
        render_result_tab(sim_input)
    with tab_anim:
        render_animation_tab(sim_input, show_transient)
    with tab_math:
        render_math_tab(sim_input)
    with tab_assume:
        render_assumptions_tab(sim_input)


if __name__ == "__main__":
    main()
