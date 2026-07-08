"""Plotly figures for the results and transient tabs.

Styling follows the project graph conventions: large fonts, mathematical axis
labels, tick marks extended beyond the data extremes, and no overlapping labels.
Math is typeset with Plotly's native rich-text tags (``<i>``/``<sub>``) rather
than LaTeX ``$...$``, because Plotly's LaTeX path collides with the MathJax v3
that Streamlit ships and silently blanks the figure.
"""

from __future__ import annotations

import plotly.graph_objects as go

from panelsim.models import FluxBreakdown, Transient

# Channel colours, matched to the animation legend.
CHANNEL_COLORS: dict[str, str] = {
    "reflected": "#78aaff",
    "p_el": "#ffce00",
    "q_rad": "#ff6e3c",
    "q_conv": "#2f8fff",
    "q_cond": "#96593c",
}

_AXIS_FONT = 17
_TICK_FONT = 14


def energy_split_bar(
    fluxes: FluxBreakdown,
    labels: dict[str, str],
    title: str,
    x_title: str = "% of <i>G</i>",
) -> go.Figure:
    """Horizontal 100%-of-G stacked bar of the energy split."""
    order = ["reflected", "p_el", "q_rad", "q_conv", "q_cond"]
    label_keys = {
        "reflected": labels["reflected"],
        "p_el": labels["electricity"],
        "q_rad": labels["radiated"],
        "q_conv": labels["convected"],
        "q_cond": labels["conducted"],
    }
    pct = fluxes.channels_percent()
    values = fluxes.channels_per_m2()

    fig = go.Figure()
    for ch in order:
        fig.add_bar(
            x=[pct[ch]],
            y=[title],
            name=label_keys[ch],
            orientation="h",
            marker_color=CHANNEL_COLORS[ch],
            customdata=[[values[ch]]],
            hovertemplate=(
                f"<b>{label_keys[ch]}</b><br>"
                "%{x:.1f} % of G<br>%{customdata[0]:.0f} W/m²<extra></extra>"
            ),
        )

    fig.update_layout(
        barmode="stack",
        height=210,
        margin=dict(l=10, r=10, t=10, b=55),
        legend=dict(orientation="h", yanchor="bottom", y=-0.9, x=0, font=dict(size=13)),
        font=dict(size=_TICK_FONT),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_xaxes(
        title_text=x_title,
        title_font=dict(size=_AXIS_FONT),
        tickfont=dict(size=_TICK_FONT),
        range=[-2, 105],
        tickvals=[0, 20, 40, 60, 80, 100],
        showgrid=True,
        gridcolor="rgba(0,0,0,0.08)",
    )
    fig.update_yaxes(showticklabels=False)
    return fig


def transient_chart(
    transient: Transient,
    steady_t: float,
    t_air: float,
    labels: dict[str, str],
) -> go.Figure:
    """Cell temperature versus time during warm-up, with the steady-state line."""
    times = transient.time_s
    temps = transient.t_cell
    t_max = max(temps + [steady_t])
    t_min = min(temps + [t_air])
    pad = max(1.0, 0.08 * (t_max - t_min))

    fig = go.Figure()
    fig.add_scatter(
        x=times,
        y=temps,
        mode="lines",
        line=dict(color="#ff6e3c", width=3),
        name="<i>T</i><sub>cell</sub>(<i>t</i>)",
    )
    fig.add_hline(
        y=steady_t,
        line=dict(color="#2f8fff", width=2, dash="dash"),
        annotation_text=labels["steady"] + f" = {steady_t:.1f} °C",
        annotation_position="top left",
        annotation_font_size=14,
    )

    fig.update_layout(
        height=340,
        margin=dict(l=70, r=25, t=30, b=60),
        showlegend=False,
        font=dict(size=_TICK_FONT),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_xaxes(
        title_text="<i>t</i>  (s)",
        title_font=dict(size=_AXIS_FONT),
        tickfont=dict(size=_TICK_FONT),
        range=[-0.02 * times[-1], 1.02 * times[-1]] if times else None,
        showgrid=True,
        gridcolor="rgba(0,0,0,0.08)",
    )
    fig.update_yaxes(
        title_text="<i>T</i><sub>cell</sub>  (°C)",
        title_font=dict(size=_AXIS_FONT),
        tickfont=dict(size=_TICK_FONT),
        range=[t_min - pad, t_max + pad],
        showgrid=True,
        gridcolor="rgba(0,0,0,0.08)",
    )
    return fig


__all__ = ["energy_split_bar", "transient_chart", "CHANNEL_COLORS"]
