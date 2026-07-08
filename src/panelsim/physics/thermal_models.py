"""Algebraic cell-temperature models (Faiman, PVsyst, Sandia/SAPM, NOCT).

Each public function takes :class:`Conditions` and :class:`PanelParams` and
returns the cell temperature in degrees Celsius. Where an authoritative
implementation exists in :mod:`pvlib`, we delegate to it so the app stays
validated against the reference library; the closed-form expression is kept in
the docstring and mirrored in :mod:`panelsim.math_explain`.
"""

from __future__ import annotations

from pvlib import temperature as pvtemp

from panelsim.models import Conditions, Mounting, PanelParams

# Per-mounting coefficients. The SAPM (a, b, deltaT) and PVsyst (u_c, u_v) rows
# reproduce pvlib's standard presets; the Faiman rows and the full-balance back
# factors are illustrative values chosen so worse-cooled mountings run hotter.
MOUNTING_PRESETS: dict[Mounting, dict[str, dict[str, float]]] = {
    Mounting.OPEN_RACK: {
        "faiman": {"u0": 25.0, "u1": 6.84},
        "pvsyst": {"u_c": 29.0, "u_v": 0.0},
        "sapm": {"a": -3.47, "b": -0.0594, "deltaT": 3.0},
        "balance": {"f_back": 1.0, "u_cond": 0.5},
    },
    Mounting.ROOF_CLOSE: {
        "faiman": {"u0": 20.0, "u1": 4.5},
        "pvsyst": {"u_c": 20.0, "u_v": 0.0},
        "sapm": {"a": -2.98, "b": -0.0471, "deltaT": 1.0},
        "balance": {"f_back": 0.35, "u_cond": 2.0},
    },
    Mounting.INSULATED: {
        "faiman": {"u0": 15.0, "u1": 2.0},
        "pvsyst": {"u_c": 15.0, "u_v": 0.0},
        "sapm": {"a": -2.81, "b": -0.0455, "deltaT": 0.0},
        "balance": {"f_back": 0.0, "u_cond": 1.0},
    },
}


def mounting_coeffs(mounting: Mounting, model_key: str) -> dict[str, float]:
    """Return the coefficient dict for a mounting and model family key."""
    return MOUNTING_PRESETS[mounting][model_key]


def faiman_temperature(conditions: Conditions, panel: PanelParams) -> float:
    r"""Faiman (2008): :math:`T_{cell}=T_{air}+G/(u_0+u_1 v)`."""
    c = mounting_coeffs(panel.mounting, "faiman")
    return float(
        pvtemp.faiman(
            poa_global=conditions.g,
            temp_air=conditions.t_air,
            wind_speed=conditions.wind,
            u0=c["u0"],
            u1=c["u1"],
        )
    )


def pvsyst_temperature(conditions: Conditions, panel: PanelParams) -> float:
    r"""PVsyst: :math:`T_{cell}=T_{air}+\alpha G(1-\eta)/(U_c+U_v v)`."""
    c = mounting_coeffs(panel.mounting, "pvsyst")
    return float(
        pvtemp.pvsyst_cell(
            poa_global=conditions.g,
            temp_air=conditions.t_air,
            wind_speed=conditions.wind,
            u_c=c["u_c"],
            u_v=c["u_v"],
            module_efficiency=panel.eta_stc,
            alpha_absorption=panel.alpha,
        )
    )


def sandia_temperature(conditions: Conditions, panel: PanelParams) -> float:
    r"""Sandia/SAPM (King): module temp :math:`T_m=T_{air}+G e^{a+b v}`,
    then cell temp :math:`T_{cell}=T_m+(G/G_{ref})\,\Delta T`."""
    c = mounting_coeffs(panel.mounting, "sapm")
    return float(
        pvtemp.sapm_cell(
            poa_global=conditions.g,
            temp_air=conditions.t_air,
            wind_speed=conditions.wind,
            a=c["a"],
            b=c["b"],
            deltaT=c["deltaT"],
        )
    )


def noct_temperature(conditions: Conditions, panel: PanelParams) -> float:
    r"""Basic NOCT benchmark: :math:`T_{cell}=T_{air}+(G/800)(NOCT-20)`."""
    return conditions.t_air + (conditions.g / 800.0) * (panel.noct - 20.0)


__all__ = [
    "MOUNTING_PRESETS",
    "mounting_coeffs",
    "faiman_temperature",
    "pvsyst_temperature",
    "sandia_temperature",
    "noct_temperature",
]
