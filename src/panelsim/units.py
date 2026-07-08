"""Shared unit registry (pint) and small conversion helpers.

Heavy numerical work in this package is done in plain SI floats for speed and
clarity; :data:`ureg` is provided for typed I/O, display, and unit-aware
conversions at the boundaries.
"""

from __future__ import annotations

from pint import UnitRegistry

# A single shared registry for the whole application.
ureg: UnitRegistry = UnitRegistry()
Q_ = ureg.Quantity

# Absolute zero, used for the °C <-> K conversions that the radiation term needs.
KELVIN_OFFSET = 273.15


def c_to_k(celsius: float) -> float:
    """Convert a temperature from degrees Celsius to kelvin."""
    return celsius + KELVIN_OFFSET


def k_to_c(kelvin: float) -> float:
    """Convert a temperature from kelvin to degrees Celsius."""
    return kelvin - KELVIN_OFFSET


__all__ = ["ureg", "Q_", "KELVIN_OFFSET", "c_to_k", "k_to_c"]
