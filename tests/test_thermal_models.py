"""Validation of the algebraic temperature models against pvlib."""

from __future__ import annotations

import pvlib.temperature as pvtemp
import pytest

from panelsim.models import Conditions, ModelChoice, Mounting, PanelParams, SimInput
from panelsim.physics.thermal_models import (
    faiman_temperature,
    noct_temperature,
    pvsyst_temperature,
    sandia_temperature,
)
from panelsim.simulate import cell_temperature

COND = Conditions(g=800.0, t_air=25.0, wind=2.0)
PANEL = PanelParams()  # open rack, eta 0.20, alpha 0.90


def test_pvlib_pvsyst_smoke_37_9() -> None:
    """pvlib smoke test from PLAN section 11: ~37.9 degC at 1000 W/m^2, 10 degC."""
    t = float(
        pvtemp.pvsyst_cell(
            1000.0,
            10.0,
            wind_speed=1.0,
            u_c=29.0,
            u_v=0.0,
            module_efficiency=0.1,
            alpha_absorption=0.9,
        )
    )
    assert t == pytest.approx(37.9, abs=0.15)


def test_faiman_matches_pvlib() -> None:
    expected = float(pvtemp.faiman(COND.g, COND.t_air, COND.wind, u0=25.0, u1=6.84))
    assert faiman_temperature(COND, PANEL) == pytest.approx(expected, abs=1e-9)


def test_pvsyst_matches_pvlib() -> None:
    expected = float(
        pvtemp.pvsyst_cell(
            COND.g,
            COND.t_air,
            wind_speed=COND.wind,
            u_c=29.0,
            u_v=0.0,
            module_efficiency=PANEL.eta_stc,
            alpha_absorption=PANEL.alpha,
        )
    )
    assert pvsyst_temperature(COND, PANEL) == pytest.approx(expected, abs=1e-9)


def test_sandia_matches_pvlib() -> None:
    expected = float(
        pvtemp.sapm_cell(COND.g, COND.t_air, COND.wind, a=-3.47, b=-0.0594, deltaT=3.0)
    )
    assert sandia_temperature(COND, PANEL) == pytest.approx(expected, abs=1e-9)


def test_noct_closed_form() -> None:
    # 25 + 800/800 * (45 - 20) = 50
    assert noct_temperature(COND, PanelParams(noct=45.0)) == pytest.approx(50.0, abs=1e-9)


def test_hotter_than_ambient_in_sun() -> None:
    for model in ModelChoice:
        t = cell_temperature(model, COND, PANEL)
        assert t > COND.t_air, f"{model} should be above ambient in full sun"


@pytest.mark.parametrize("model", [ModelChoice.FAIMAN, ModelChoice.FULL_BALANCE])
def test_mounting_monotonic(model: ModelChoice) -> None:
    """Worse-cooled mountings must run hotter: open rack < roof < insulated."""
    temps = [
        cell_temperature(model, COND, PanelParams(mounting=m))
        for m in (Mounting.OPEN_RACK, Mounting.ROOF_CLOSE, Mounting.INSULATED)
    ]
    assert temps[0] < temps[1] < temps[2]


def test_more_wind_cools() -> None:
    calm = cell_temperature(ModelChoice.FAIMAN, Conditions(g=800, t_air=25, wind=0.5), PANEL)
    windy = cell_temperature(ModelChoice.FAIMAN, Conditions(g=800, t_air=25, wind=8.0), PANEL)
    assert windy < calm


def test_siminput_defaults_are_valid() -> None:
    si = SimInput()
    assert si.model == ModelChoice.FAIMAN
    assert si.conditions.g == pytest.approx(800.0)
