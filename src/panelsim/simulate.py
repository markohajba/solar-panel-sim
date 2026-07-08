"""High-level orchestration: turn a :class:`SimInput` into a :class:`SimResult`.

The chosen model yields the cell temperature; the energy balance then produces
the flux split (which closes to G for every model), and an optional transient
trajectory is attached for the animation's warm-up mode.
"""

from __future__ import annotations

from panelsim.math_explain import model_reference
from panelsim.models import (
    Conditions,
    ModelChoice,
    PanelParams,
    SimInput,
    SimResult,
    Transient,
)
from panelsim.physics.energy_balance import (
    build_flux_breakdown,
    simulate_transient,
    solve_cell_temperature,
)
from panelsim.physics.thermal_models import (
    faiman_temperature,
    noct_temperature,
    pvsyst_temperature,
    sandia_temperature,
)

# Algebraic models keyed by choice; the full balance is handled separately
# because it solves an implicit equation rather than a closed form.
_TEMPERATURE_MODELS = {
    ModelChoice.FAIMAN: faiman_temperature,
    ModelChoice.PVSYST: pvsyst_temperature,
    ModelChoice.SANDIA: sandia_temperature,
    ModelChoice.NOCT: noct_temperature,
}


def cell_temperature(model: ModelChoice, conditions: Conditions, panel: PanelParams) -> float:
    """Dispatch to the selected model and return the cell temperature [degC]."""
    if model == ModelChoice.FULL_BALANCE:
        return solve_cell_temperature(conditions, panel)
    return _TEMPERATURE_MODELS[model](conditions, panel)


def run_simulation(sim_input: SimInput, with_transient: bool = False) -> SimResult:
    """Run a full simulation and return everything the UI/animation need.

    ``with_transient`` attaches the warm-up ODE trajectory; it is only
    physically meaningful for the full-balance model (the algebraic models have
    no thermal mass), so it is ignored for the others.
    """
    conditions = sim_input.conditions
    panel = sim_input.panel
    model = sim_input.model

    t_cell = cell_temperature(model, conditions, panel)
    fluxes = build_flux_breakdown(t_cell, conditions, panel)

    transient: Transient | None = None
    if with_transient and model == ModelChoice.FULL_BALANCE:
        transient = simulate_transient(conditions, panel)

    return SimResult(
        model=model,
        mounting=panel.mounting,
        t_cell=t_cell,
        t_air=conditions.t_air,
        fluxes=fluxes,
        area_m2=panel.area_m2,
        reference=model_reference(model),
        transient=transient,
    )


__all__ = ["cell_temperature", "run_simulation"]
