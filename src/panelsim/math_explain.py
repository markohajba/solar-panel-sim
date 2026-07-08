"""Per-model math content for the "Show the math" feature.

Each :class:`ModelMath` bundles a language-neutral LaTeX equation, the list of
variables (symbol + i18n description key + typical value), assumption keys, a
literature reference, and a ``worked_example`` callable that renders the equation
with the user's numbers substituted. The worked example calls the very same
physics functions the engine uses, so the number shown in the UI is by
construction identical to the model's numerical result.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field

from panelsim.models import Conditions, ModelChoice, PanelParams
from panelsim.physics.energy_balance import (
    electrical_power,
    q_conduction,
    q_convection,
    q_radiation,
    solve_cell_temperature,
)
from panelsim.physics.thermal_models import (
    faiman_temperature,
    mounting_coeffs,
    noct_temperature,
    pvsyst_temperature,
    sandia_temperature,
)


@dataclass(frozen=True)
class Variable:
    """One symbol in an equation: LaTeX symbol, i18n key, typical value string."""

    symbol: str
    desc_key: str
    typical: str


@dataclass(frozen=True)
class ModelMath:
    """All math-explanation content for a single temperature model."""

    latex: str
    variables: list[Variable]
    assumption_keys: list[str]
    reference: str
    worked_example: Callable[[Conditions, PanelParams], str]
    extra_latex: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Worked examples (return LaTeX with the user's numbers already substituted).  #
# --------------------------------------------------------------------------- #
def _wex_faiman(c: Conditions, p: PanelParams) -> str:
    k = mounting_coeffs(p.mounting, "faiman")
    t = faiman_temperature(c, p)
    return (
        rf"T_{{cell}} = {c.t_air:.1f} + \frac{{{c.g:.0f}}}"
        rf"{{{k['u0']:.2f} + {k['u1']:.2f}\cdot {c.wind:.1f}}} "
        rf"= {t:.1f}\ ^\circ\mathrm{{C}}"
    )


def _wex_pvsyst(c: Conditions, p: PanelParams) -> str:
    k = mounting_coeffs(p.mounting, "pvsyst")
    t = pvsyst_temperature(c, p)
    numerator = rf"{p.alpha:.2f}\cdot {c.g:.0f}\cdot(1-{p.eta_stc:.2f})"
    denom = rf"{k['u_c']:.1f} + {k['u_v']:.1f}\cdot {c.wind:.1f}"
    return (
        rf"T_{{cell}} = {c.t_air:.1f} + \frac{{{numerator}}}{{{denom}}} "
        rf"= {t:.1f}\ ^\circ\mathrm{{C}}"
    )


def _wex_sandia(c: Conditions, p: PanelParams) -> str:
    k = mounting_coeffs(p.mounting, "sapm")
    t_m = c.t_air + c.g * math.exp(k["a"] + k["b"] * c.wind)
    t = sandia_temperature(c, p)
    return (
        rf"T_m = {c.t_air:.1f} + {c.g:.0f}\,e^{{{k['a']:.3f} + ({k['b']:.4f})\cdot {c.wind:.1f}}} "
        rf"= {t_m:.1f}\ ^\circ\mathrm{{C}}\\[4pt]"
        rf"T_{{cell}} = {t_m:.1f} + \frac{{{c.g:.0f}}}{{1000}}\cdot {k['deltaT']:.1f} "
        rf"= {t:.1f}\ ^\circ\mathrm{{C}}"
    )


def _wex_noct(c: Conditions, p: PanelParams) -> str:
    t = noct_temperature(c, p)
    return (
        rf"T_{{cell}} = {c.t_air:.1f} + \frac{{{c.g:.0f}}}{{800}}\cdot({p.noct:.0f}-20) "
        rf"= {t:.1f}\ ^\circ\mathrm{{C}}"
    )


def _wex_balance(c: Conditions, p: PanelParams) -> str:
    t = solve_cell_temperature(c, p)
    absorbed = p.alpha * c.g
    p_el = electrical_power(t, c, p)
    q_r = q_radiation(t, c, p)
    q_c = q_convection(t, c, p)
    q_k = q_conduction(t, c, p)
    return (
        rf"\alpha G = {absorbed:.0f}\ \mathrm{{W/m^2}} "
        rf"= P_{{el}} + Q_{{rad}} + Q_{{conv}} + Q_{{cond}}\\[4pt]"
        rf"\Rightarrow\ T_{{cell}} = {t:.1f}\ ^\circ\mathrm{{C}},\quad "
        rf"P_{{el}}={p_el:.0f},\ Q_{{rad}}={q_r:.0f},\ "
        rf"Q_{{conv}}={q_c:.0f},\ Q_{{cond}}={q_k:.0f}\ \mathrm{{W/m^2}}"
    )


# --------------------------------------------------------------------------- #
# Model registry.                                                             #
# --------------------------------------------------------------------------- #
_V_G = Variable("G", "var.g", "600-1000 W/m^2")
_V_TAIR = Variable("T_{air}", "var.t_air", "0-40 degC")
_V_WIND = Variable("v", "var.wind", "0-10 m/s")

MODEL_MATH: dict[ModelChoice, ModelMath] = {
    ModelChoice.FAIMAN: ModelMath(
        latex=r"T_{cell} = T_{air} + \dfrac{G}{u_0 + u_1\,v}",
        variables=[
            _V_G,
            _V_TAIR,
            _V_WIND,
            Variable("u_0", "var.u0", "25 W/(m^2 K)"),
            Variable("u_1", "var.u1", "6.84 W s/(m^3 K)"),
        ],
        assumption_keys=["assume.faiman.1", "assume.faiman.2", "assume.steady"],
        reference="Faiman, D. (2008). Prog. Photovolt. 16(4), 307-315.",
        worked_example=_wex_faiman,
    ),
    ModelChoice.PVSYST: ModelMath(
        latex=r"T_{cell} = T_{air} + \dfrac{\alpha\,G\,(1-\eta)}{U_c + U_v\,v}",
        variables=[
            _V_G,
            _V_TAIR,
            _V_WIND,
            Variable(r"\alpha", "var.alpha", "0.90"),
            Variable(r"\eta", "var.eta", "0.15-0.22"),
            Variable("U_c", "var.uc", "29 W/(m^2 K)"),
            Variable("U_v", "var.uv", "0 W s/(m^3 K)"),
        ],
        assumption_keys=["assume.pvsyst.1", "assume.pvsyst.2", "assume.steady"],
        reference="PVsyst thermal model documentation; Mermoud & Lejeune (2010).",
        worked_example=_wex_pvsyst,
    ),
    ModelChoice.SANDIA: ModelMath(
        latex=r"T_m = T_{air} + G\,e^{a+b\,v}, \qquad "
        r"T_{cell} = T_m + \dfrac{G}{G_{ref}}\,\Delta T",
        variables=[
            _V_G,
            _V_TAIR,
            _V_WIND,
            Variable("a", "var.a", "-3.47"),
            Variable("b", "var.b", "-0.0594 s/m"),
            Variable(r"\Delta T", "var.deltaT", "3 K"),
            Variable("G_{ref}", "var.gref", "1000 W/m^2"),
        ],
        assumption_keys=["assume.sandia.1", "assume.sandia.2", "assume.steady"],
        reference="King, D. et al. (2004). Sandia SAND2004-3535.",
        worked_example=_wex_sandia,
    ),
    ModelChoice.NOCT: ModelMath(
        latex=r"T_{cell} = T_{air} + \dfrac{G}{800}\,(NOCT - 20)",
        variables=[
            _V_G,
            _V_TAIR,
            Variable("NOCT", "var.noct", "44-48 degC"),
        ],
        assumption_keys=["assume.noct.1", "assume.noct.2", "assume.steady"],
        reference="IEC 61215; standard NOCT benchmark (800 W/m^2, 20 degC, 1 m/s).",
        worked_example=_wex_noct,
    ),
    ModelChoice.FULL_BALANCE: ModelMath(
        latex=r"\alpha G \;=\; P_{el} + Q_{rad} + Q_{conv} + Q_{cond} + C\,\dfrac{dT}{dt}",
        variables=[
            _V_G,
            _V_TAIR,
            _V_WIND,
            Variable(r"\alpha", "var.alpha", "0.90"),
            Variable(r"\varepsilon", "var.epsilon", "0.90"),
            Variable(r"\sigma", "var.sigma", "5.67e-8 W/(m^2 K^4)"),
            Variable("h_c", "var.hc", "5.7 + 3.8 v"),
            Variable("C", "var.capacitance", "m c_p / A"),
        ],
        assumption_keys=[
            "assume.balance.1",
            "assume.balance.2",
            "assume.balance.3",
            "assume.balance.4",
        ],
        reference=(
            "Surface energy balance; Duffie & Beckman, Solar Engineering of Thermal Processes."
        ),
        worked_example=_wex_balance,
        extra_latex=[
            r"Q_{rad} = \varepsilon\sigma\left[(T_{cell}^4 - T_{sky}^4) "
            r"+ f_{back}(T_{cell}^4 - T_{gnd}^4)\right]",
            r"Q_{conv} = h_c\,(T_{cell} - T_{air}), \qquad h_c = 5.7 + 3.8\,v",
            r"P_{el} = \eta_{STC}\left[1 + \gamma (T_{cell}-25)\right] G",
        ],
    ),
}


def model_reference(model: ModelChoice) -> str:
    """Literature reference string for a model (language-neutral)."""
    return MODEL_MATH[model].reference


__all__ = ["Variable", "ModelMath", "MODEL_MATH", "model_reference"]
