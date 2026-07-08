"""Validation of the full energy balance, flux split, transient and worked math."""

from __future__ import annotations

import pytest

from panelsim.math_explain import MODEL_MATH
from panelsim.models import Conditions, ModelChoice, Mounting, PanelParams, SimInput
from panelsim.physics.energy_balance import (
    balance_residual,
    eta_of_t,
    net_heat,
    simulate_transient,
    solve_cell_temperature,
)
from panelsim.simulate import run_simulation

COND = Conditions(g=800.0, t_air=25.0, wind=2.0)
PANEL = PanelParams()


@pytest.mark.parametrize("model", list(ModelChoice))
def test_energy_balance_closes(model: ModelChoice) -> None:
    """R + P_el + Q_rad + Q_conv + Q_cond ~= G for every model (PLAN section 11)."""
    result = run_simulation(SimInput(conditions=COND, panel=PANEL, model=model))
    assert result.fluxes.closure_residual() == pytest.approx(0.0, abs=1e-6)


def test_full_balance_solver_residual_zero() -> None:
    """The full-balance solve satisfies the surface energy balance itself."""
    t = solve_cell_temperature(COND, PANEL)
    assert balance_residual(t, COND, PANEL) == pytest.approx(0.0, abs=1e-5)


@pytest.mark.parametrize("model", list(ModelChoice))
def test_worked_example_matches_numeric_result(model: ModelChoice) -> None:
    """The number rendered in the UI equals the model's numerical result."""
    result = run_simulation(SimInput(conditions=COND, panel=PANEL, model=model))
    worked = MODEL_MATH[model].worked_example(COND, PANEL)
    assert f"{result.t_cell:.1f}" in worked


def test_efficiency_decreases_with_temperature() -> None:
    assert eta_of_t(25.0, PANEL) > eta_of_t(60.0, PANEL)
    assert eta_of_t(25.0, PANEL) == pytest.approx(PANEL.eta_stc)


def test_net_heat_is_absorbed_minus_electricity() -> None:
    t = solve_cell_temperature(COND, PANEL)
    absorbed = PANEL.alpha * COND.g
    p_el = eta_of_t(t, PANEL) * COND.g
    assert net_heat(t, COND, PANEL) == pytest.approx(absorbed - p_el, abs=1e-9)


def test_flux_channels_nonnegative_in_sun() -> None:
    f = run_simulation(
        SimInput(conditions=COND, panel=PANEL, model=ModelChoice.FULL_BALANCE)
    ).fluxes
    for name, value in f.channels_per_m2().items():
        assert value >= -1e-6, f"{name} unexpectedly negative: {value}"


def test_transient_warms_from_ambient_to_steady() -> None:
    tr = simulate_transient(COND, PANEL)
    steady = solve_cell_temperature(COND, PANEL)
    assert tr.t_cell[0] == pytest.approx(COND.t_air, abs=1e-6)
    # Monotonic heating and convergence to the steady solution.
    assert tr.t_cell[-1] > tr.t_cell[0]
    assert tr.t_cell[-1] == pytest.approx(steady, abs=0.5)
    diffs = [b - a for a, b in zip(tr.t_cell, tr.t_cell[1:], strict=False)]
    assert all(d >= -1e-6 for d in diffs)


def test_night_radiative_cooling_below_ambient() -> None:
    """With no sun the balance model cools below ambient toward the sky."""
    night = Conditions(g=0.0, t_air=15.0, wind=1.0, t_sky=-10.0)
    t = solve_cell_temperature(night, PANEL)
    assert t < night.t_air


def test_insulated_hotter_than_open_full_balance() -> None:
    open_t = run_simulation(
        SimInput(
            conditions=COND,
            panel=PanelParams(mounting=Mounting.OPEN_RACK),
            model=ModelChoice.FULL_BALANCE,
        )
    ).t_cell
    ins_t = run_simulation(
        SimInput(
            conditions=COND,
            panel=PanelParams(mounting=Mounting.INSULATED),
            model=ModelChoice.FULL_BALANCE,
        )
    ).t_cell
    assert ins_t > open_t


def test_zero_irradiance_flux_breakdown_is_safe() -> None:
    res = run_simulation(
        SimInput(
            conditions=Conditions(g=0.0, t_air=20.0, wind=2.0), panel=PANEL, model=ModelChoice.NOCT
        )
    )
    assert res.fluxes.closure_residual() == pytest.approx(0.0, abs=1e-6)
    assert res.fluxes.p_el == pytest.approx(0.0, abs=1e-9)
