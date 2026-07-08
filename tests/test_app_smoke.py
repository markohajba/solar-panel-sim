"""Headless smoke tests for the Streamlit app via streamlit.testing AppTest.

These run the whole app script in-process (no browser), so they exercise the
i18n lookups, the physics calls, the plotly figure construction and the
heat-flow component HTML generation, and assert the app renders without raising.
"""

from __future__ import annotations

import pytest

from panelsim.models import ModelChoice

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest

APP = "app/streamlit_app.py"
TIMEOUT = 60


def _fresh() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=TIMEOUT)
    at.run()
    return at


def test_app_boots_without_exception() -> None:
    at = _fresh()
    assert not at.exception
    assert len(at.tabs) == 4
    assert any("Solar Panel" in tl.value for tl in at.title)


def test_language_switch_to_croatian() -> None:
    at = _fresh()
    at.selectbox(key="lang_select").set_value("hr").run()
    assert not at.exception
    assert any("Simulator" in tl.value for tl in at.title)


def test_full_balance_with_transient_renders() -> None:
    at = _fresh()
    # Model + mounting are the two selectboxes inside the form (index 1 and 2);
    # index 0 is the language switch outside the form.
    at.selectbox[1].set_value(ModelChoice.FULL_BALANCE)
    at.toggle(key="transient_toggle").set_value(True)
    if len(at.button) > 0:
        at.button[0].click()
    at.run()
    assert not at.exception


@pytest.mark.parametrize("model", list(ModelChoice))
def test_each_model_renders(model: ModelChoice) -> None:
    at = _fresh()
    at.selectbox[1].set_value(model)
    if len(at.button) > 0:
        at.button[0].click()
    at.run()
    assert not at.exception


@pytest.mark.parametrize(
    ("scenario_key", "expected_g", "expected_t_air"),
    [("sc_clear", 1000.0, 32.0), ("sc_cloud", 250.0, 19.0), ("sc_sunset", 180.0, 16.0)],
)
def test_scenario_presets_apply(
    scenario_key: str, expected_g: float, expected_t_air: float
) -> None:
    at = _fresh()
    at.button(key=scenario_key).click().run()
    assert not at.exception
    assert at.session_state["g"] == expected_g
    assert at.session_state["t_air"] == expected_t_air


def test_clear_day_hotter_than_sunset() -> None:
    hot = _fresh()
    hot.button(key="sc_clear").click().run()
    cool = _fresh()
    cool.button(key="sc_sunset").click().run()
    # The cell-temperature metric is the first metric on the result tab.
    hot_temp = float(hot.metric[0].value.split()[0])
    cool_temp = float(cool.metric[0].value.split()[0])
    assert hot_temp > cool_temp
