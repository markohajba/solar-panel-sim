"""panelsim: educational thermal simulator for a single solar panel.

Public entry points::

    from panelsim import run_simulation, SimInput, Conditions, PanelParams, ModelChoice
"""

from __future__ import annotations

from panelsim.models import (
    Conditions,
    FluxBreakdown,
    ModelChoice,
    Mounting,
    PanelParams,
    SimInput,
    SimResult,
    Transient,
)
from panelsim.simulate import cell_temperature, run_simulation

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "Conditions",
    "PanelParams",
    "SimInput",
    "SimResult",
    "FluxBreakdown",
    "Transient",
    "ModelChoice",
    "Mounting",
    "run_simulation",
    "cell_temperature",
]
