"""Typed input/output schemas for the panel simulator (pydantic v2).

These models are the contract between the physics engine, the UI, and the
animation component. Everything is expressed per square metre of panel unless a
field name says otherwise; absolute watts are derived with :attr:`PanelParams.area_m2`.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ModelChoice(StrEnum):
    """Cell-temperature model selected by the user."""

    FAIMAN = "faiman"
    PVSYST = "pvsyst"
    SANDIA = "sandia"
    NOCT = "noct"
    FULL_BALANCE = "full_balance"


class Mounting(StrEnum):
    """Mounting configuration; controls how well the panel back is cooled."""

    OPEN_RACK = "open_rack"
    ROOF_CLOSE = "roof_close"
    INSULATED = "insulated"


class Conditions(BaseModel):
    """Ambient conditions in the plane of the panel."""

    model_config = ConfigDict(frozen=True)

    g: float = Field(800.0, ge=0.0, le=1500.0, description="Plane-of-array irradiance [W/m^2]")
    t_air: float = Field(25.0, ge=-40.0, le=60.0, description="Ambient air temperature [degC]")
    wind: float = Field(2.0, ge=0.0, le=30.0, description="Wind speed [m/s]")
    t_sky: float | None = Field(
        None, description="Effective sky temperature [degC]; auto-estimated when None"
    )
    t_gnd: float | None = Field(
        None, description="Ground/surface temperature [degC]; defaults to t_air when None"
    )

    def sky_temperature(self) -> float:
        """Sky temperature, using a clear-sky offset of -20 degC when unset."""
        return self.t_sky if self.t_sky is not None else self.t_air - 20.0

    def ground_temperature(self) -> float:
        """Ground temperature, defaulting to the air temperature when unset."""
        return self.t_gnd if self.t_gnd is not None else self.t_air


class PanelParams(BaseModel):
    """Physical and optical parameters of the module."""

    model_config = ConfigDict(frozen=True)

    eta_stc: float = Field(0.20, gt=0.0, le=0.35, description="Efficiency at STC [-]")
    gamma: float = Field(-0.004, le=0.0, ge=-0.02, description="Power temp. coefficient [1/degC]")
    alpha: float = Field(0.90, gt=0.0, le=1.0, description="Solar absorptance [-]")
    epsilon: float = Field(0.90, gt=0.0, le=1.0, description="Thermal emissivity [-]")
    noct: float = Field(45.0, ge=30.0, le=58.0, description="Nominal operating cell temp. [degC]")
    area_m2: float = Field(1.7, gt=0.0, le=10.0, description="Module area [m^2]")
    mass_cp: float = Field(
        11000.0, gt=0.0, description="Areal thermal mass m*cp [J/(m^2*K)] (transient only)"
    )
    mounting: Mounting = Field(Mounting.OPEN_RACK, description="Mounting configuration")


class SimInput(BaseModel):
    """A complete simulation request."""

    conditions: Conditions = Field(default_factory=Conditions)
    panel: PanelParams = Field(default_factory=PanelParams)
    model: ModelChoice = ModelChoice.FAIMAN


class FluxBreakdown(BaseModel):
    """Steady-state (or instantaneous) energy split, all in W/m^2.

    Bookkeeping identity (per m^2)::

        g = reflected + p_el + q_rad + q_conv + q_cond + storage

    because absorbed = g - reflected = p_el + q_rad + q_conv + q_cond + storage.
    """

    g: float
    reflected: float
    p_el: float
    q_rad: float
    q_conv: float
    q_cond: float
    storage: float = 0.0

    @property
    def absorbed(self) -> float:
        """Absorbed solar flux alpha*G [W/m^2]."""
        return self.g - self.reflected

    @property
    def q_gen(self) -> float:
        """Net heat that must leave the panel = absorbed - electricity [W/m^2]."""
        return self.q_rad + self.q_conv + self.q_cond + self.storage

    @property
    def q_thermal_out(self) -> float:
        """Total heat handed to the surroundings, Q_rad + Q_conv + Q_cond [W/m^2]."""
        return self.q_rad + self.q_conv + self.q_cond

    def closure_residual(self) -> float:
        """g minus the sum of all outgoing channels; ~0 when the balance closes."""
        return self.g - (
            self.reflected + self.p_el + self.q_rad + self.q_conv + self.q_cond + self.storage
        )

    def channels_per_m2(self) -> dict[str, float]:
        """The six accounting channels keyed by name, in W/m^2."""
        return {
            "reflected": self.reflected,
            "p_el": self.p_el,
            "q_rad": self.q_rad,
            "q_conv": self.q_conv,
            "q_cond": self.q_cond,
            "storage": self.storage,
        }

    def channels_percent(self) -> dict[str, float]:
        """Each channel as a percentage of the incident irradiance G."""
        if self.g <= 0.0:
            return dict.fromkeys(self.channels_per_m2(), 0.0)
        return {k: 100.0 * v / self.g for k, v in self.channels_per_m2().items()}

    def channels_watts(self, area_m2: float) -> dict[str, float]:
        """Each channel in absolute watts for a panel of the given area."""
        return {k: v * area_m2 for k, v in self.channels_per_m2().items()}


class Transient(BaseModel):
    """Optional transient warm-up trajectory from the full-balance ODE."""

    time_s: list[float]
    t_cell: list[float]


class SimResult(BaseModel):
    """Everything the UI and animation need after a run."""

    model: ModelChoice
    mounting: Mounting
    t_cell: float
    t_air: float
    fluxes: FluxBreakdown
    area_m2: float
    reference: str = ""
    transient: Transient | None = None

    def flux_json(self) -> dict[str, float]:
        """Flat dict of the quantities the canvas animation consumes."""
        return {
            "g": self.fluxes.g,
            "reflected": self.fluxes.reflected,
            "p_el": self.fluxes.p_el,
            "q_rad": self.fluxes.q_rad,
            "q_conv": self.fluxes.q_conv,
            "q_cond": self.fluxes.q_cond,
            "storage": self.fluxes.storage,
            "t_cell": self.t_cell,
            "t_air": self.t_air,
        }


__all__ = [
    "ModelChoice",
    "Mounting",
    "Conditions",
    "PanelParams",
    "SimInput",
    "FluxBreakdown",
    "Transient",
    "SimResult",
]
