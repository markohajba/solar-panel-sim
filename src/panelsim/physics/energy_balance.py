"""Full steady-state energy balance, flux split, and transient ODE.

The steady state satisfies (per m^2)::

    alpha*G = P_el(T) + Q_rad(T) + Q_conv(T) + Q_cond(T)

with

    P_el   = eta_STC * [1 + gamma*(T - 25)] * G
    Q_rad  = eps*sigma * [ (T^4 - T_sky^4) + f_back*(T^4 - T_gnd^4) ]     (kelvin)
    Q_conv = (0.5 + 0.5*f_back) * (5.7 + 3.8*v) * (T - T_air)             (McAdams)
    Q_cond = U_cond * (T - T_air)

The mounting sets ``f_back`` (how much the back exchanges with the environment)
and ``U_cond`` (conduction into the structure), so an open rack runs cooler than
an insulated back-sheet mount.
"""

from __future__ import annotations

import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import brentq

from panelsim.models import Conditions, FluxBreakdown, PanelParams, Transient
from panelsim.physics.thermal_models import mounting_coeffs
from panelsim.units import c_to_k

# Stefan-Boltzmann constant [W/(m^2 K^4)].
SIGMA = 5.670374419e-8


def eta_of_t(t_cell: float, panel: PanelParams) -> float:
    """Temperature-dependent efficiency eta(T), floored at zero."""
    return max(0.0, panel.eta_stc * (1.0 + panel.gamma * (t_cell - 25.0)))


def electrical_power(t_cell: float, conditions: Conditions, panel: PanelParams) -> float:
    """Electrical power extracted, P_el = eta(T) * G [W/m^2]."""
    return eta_of_t(t_cell, panel) * conditions.g


def reflected_flux(conditions: Conditions, panel: PanelParams) -> float:
    """Reflected / non-absorbed optical flux, (1 - alpha) * G [W/m^2]."""
    return (1.0 - panel.alpha) * conditions.g


def q_radiation(t_cell: float, conditions: Conditions, panel: PanelParams) -> float:
    """Net long-wave radiation to sky (front) and ground (back) [W/m^2]."""
    f_back = mounting_coeffs(panel.mounting, "balance")["f_back"]
    tc4 = c_to_k(t_cell) ** 4
    tsky4 = c_to_k(conditions.sky_temperature()) ** 4
    tgnd4 = c_to_k(conditions.ground_temperature()) ** 4
    front = tc4 - tsky4
    back = f_back * (tc4 - tgnd4)
    return panel.epsilon * SIGMA * (front + back)


def q_convection(t_cell: float, conditions: Conditions, panel: PanelParams) -> float:
    """Convective loss to the air (McAdams), scaled by mounting exposure [W/m^2]."""
    f_back = mounting_coeffs(panel.mounting, "balance")["f_back"]
    h_c = 5.7 + 3.8 * conditions.wind
    m_conv = 0.5 + 0.5 * f_back
    return m_conv * h_c * (t_cell - conditions.t_air)


def q_conduction(t_cell: float, conditions: Conditions, panel: PanelParams) -> float:
    """Conductive loss into the mount/structure [W/m^2]."""
    u_cond = mounting_coeffs(panel.mounting, "balance")["u_cond"]
    return u_cond * (t_cell - conditions.t_air)


def net_heat(t_cell: float, conditions: Conditions, panel: PanelParams) -> float:
    """Heat that must be dissipated, Q_gen = alpha*G - P_el [W/m^2]."""
    return panel.alpha * conditions.g - electrical_power(t_cell, conditions, panel)


def balance_residual(t_cell: float, conditions: Conditions, panel: PanelParams) -> float:
    """Steady-state residual: absorbed - electricity - all thermal losses [W/m^2]."""
    losses = (
        q_radiation(t_cell, conditions, panel)
        + q_convection(t_cell, conditions, panel)
        + q_conduction(t_cell, conditions, panel)
    )
    return net_heat(t_cell, conditions, panel) - losses


def solve_cell_temperature(conditions: Conditions, panel: PanelParams) -> float:
    """Solve the steady-state balance for the cell temperature [degC]."""
    lo = min(conditions.t_air, conditions.sky_temperature()) - 60.0
    hi = conditions.t_air + 200.0
    f_lo = balance_residual(lo, conditions, panel)
    f_hi = balance_residual(hi, conditions, panel)
    if f_lo == 0.0:
        return lo
    if f_hi == 0.0:
        return hi
    if f_lo * f_hi < 0.0:
        return float(brentq(balance_residual, lo, hi, args=(conditions, panel), xtol=1e-8))
    # Degenerate bracket (e.g. G = 0 with unusual sky/ground): fall back to a
    # damped fixed-point sweep and return the temperature of least residual.
    grid = np.linspace(lo, hi, 4001)
    residuals = np.array([abs(balance_residual(float(t), conditions, panel)) for t in grid])
    return float(grid[int(np.argmin(residuals))])


def split_heat(
    t_cell: float, conditions: Conditions, panel: PanelParams
) -> tuple[float, float, float]:
    """Apportion Q_gen across (radiation, convection, conduction) [W/m^2].

    The raw fluxes at ``t_cell`` are rescaled so they sum exactly to Q_gen,
    which enforces energy conservation for every model. For the full balance the
    rescale factor is ~1 (the raw fluxes already close), so no distortion occurs;
    for the algebraic models it distributes the required heat by each pathway's
    instantaneous magnitude.
    """
    q_gen = net_heat(t_cell, conditions, panel)
    raw = (
        q_radiation(t_cell, conditions, panel),
        q_convection(t_cell, conditions, panel),
        q_conduction(t_cell, conditions, panel),
    )
    total = sum(raw)
    if abs(total) < 1e-9:
        # No temperature difference to drive the split; use nominal weights.
        return (0.55 * q_gen, 0.40 * q_gen, 0.05 * q_gen)
    scale = q_gen / total
    return (raw[0] * scale, raw[1] * scale, raw[2] * scale)


def build_flux_breakdown(
    t_cell: float, conditions: Conditions, panel: PanelParams
) -> FluxBreakdown:
    """Assemble the full steady-state energy split at ``t_cell``."""
    q_rad, q_conv, q_cond = split_heat(t_cell, conditions, panel)
    return FluxBreakdown(
        g=conditions.g,
        reflected=reflected_flux(conditions, panel),
        p_el=electrical_power(t_cell, conditions, panel),
        q_rad=q_rad,
        q_conv=q_conv,
        q_cond=q_cond,
        storage=0.0,
    )


def thermal_time_constant(conditions: Conditions, panel: PanelParams) -> float:
    """Rough thermal time constant tau = C / h_c [s] for transient scaling."""
    h_c = 5.7 + 3.8 * conditions.wind
    return panel.mass_cp / max(h_c, 1.0)


def simulate_transient(
    conditions: Conditions,
    panel: PanelParams,
    t_end: float | None = None,
    n_points: int = 200,
    t_start: float | None = None,
) -> Transient:
    """Integrate C dT/dt = alpha*G - P_el - Q_rad - Q_conv - Q_cond from T_air."""
    capacitance = panel.mass_cp
    if t_end is None:
        t_end = 6.0 * thermal_time_constant(conditions, panel)
    t0 = conditions.t_air if t_start is None else t_start

    def rhs(_t: float, y: np.ndarray) -> list[float]:
        temp = float(y[0])
        return [balance_residual(temp, conditions, panel) / capacitance]

    times = np.linspace(0.0, t_end, n_points)
    sol = solve_ivp(rhs, (0.0, t_end), [t0], t_eval=times, rtol=1e-6, atol=1e-6)
    return Transient(time_s=sol.t.tolist(), t_cell=sol.y[0].tolist())


__all__ = [
    "SIGMA",
    "eta_of_t",
    "electrical_power",
    "reflected_flux",
    "q_radiation",
    "q_convection",
    "q_conduction",
    "net_heat",
    "balance_residual",
    "solve_cell_temperature",
    "split_heat",
    "build_flux_breakdown",
    "thermal_time_constant",
    "simulate_transient",
]
