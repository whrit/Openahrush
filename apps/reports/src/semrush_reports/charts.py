"""
Chart generation module for PDF reports.

Provides chart generation using matplotlib:
- Pie charts for distribution data
- Line charts for trend data
- Bar charts for comparison data

Charts are generated as PNG bytes for embedding in HTML/PDF.
"""

from __future__ import annotations

import base64
import io
from typing import Any

import matplotlib
import matplotlib.pyplot as plt

# Use non-interactive backend for server-side rendering
matplotlib.use("Agg")


# Default color palette for charts
DEFAULT_COLORS = [
    "#2563eb",  # Blue
    "#16a34a",  # Green
    "#ea580c",  # Orange
    "#dc2626",  # Red
    "#9333ea",  # Purple
    "#0891b2",  # Cyan
    "#ca8a04",  # Yellow
    "#be185d",  # Pink
]

# Severity-specific colors
SEVERITY_COLORS = {
    "critical": "#dc2626",
    "high": "#ea580c",
    "medium": "#ca8a04",
    "low": "#16a34a",
    "info": "#0284c7",
}


def generate_pie_chart(
    data: dict[str, int | float],
    title: str,
    colors: list[str] | None = None,
    figsize: tuple[float, float] = (6, 6),
) -> bytes:
    """
    Generate a pie chart as PNG bytes.

    Args:
        data: Dictionary of labels to values.
        title: Chart title.
        colors: Optional list of colors for slices.
        figsize: Figure size in inches (width, height).

    Returns:
        PNG image as bytes, or empty bytes if data is empty.
    """
    if not data:
        return b""

    # Use default colors if not provided
    if colors is None:
        colors = DEFAULT_COLORS[: len(data)]

    fig, ax = plt.subplots(figsize=figsize)

    labels = list(data.keys())
    values = list(data.values())

    # Create pie chart
    wedges, texts, autotexts = ax.pie(
        values,
        labels=labels,
        colors=colors,
        autopct="%1.1f%%",
        startangle=90,
        pctdistance=0.75,
    )

    # Style text
    for text in texts:
        text.set_fontsize(10)
    for autotext in autotexts:
        autotext.set_fontsize(9)
        autotext.set_color("white")
        autotext.set_weight("bold")

    ax.set_title(title, fontsize=12, fontweight="bold", pad=20)
    ax.axis("equal")  # Equal aspect ratio for circular pie

    # Save to bytes
    buffer = io.BytesIO()
    plt.tight_layout()
    fig.savefig(buffer, format="png", dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    buffer.seek(0)
    return buffer.read()


def generate_line_chart(
    data: dict[str, Any],
    title: str,
    x_label: str = "",
    y_label: str = "",
    color: str = "#2563eb",
    figsize: tuple[float, float] = (8, 4),
) -> bytes:
    """
    Generate a line chart as PNG bytes.

    Args:
        data: Dictionary with 'labels' and 'values' keys, or 'labels' and 'series'.
              For single series: {"labels": ["A", "B"], "values": [10, 20]}
              For multiple series: {"labels": ["A", "B"], "series": [
                  {"name": "Series 1", "values": [10, 20]},
                  {"name": "Series 2", "values": [15, 25]}
              ]}
        title: Chart title.
        x_label: X-axis label.
        y_label: Y-axis label.
        color: Line color for single series.
        figsize: Figure size in inches.

    Returns:
        PNG image as bytes, or empty bytes if data is empty.
    """
    labels = data.get("labels", [])
    values = data.get("values", [])
    series = data.get("series", [])

    # Check for empty data
    if not labels:
        return b""
    if not values and not series:
        return b""

    fig, ax = plt.subplots(figsize=figsize)

    if series:
        # Multiple series
        for i, s in enumerate(series):
            series_color = DEFAULT_COLORS[i % len(DEFAULT_COLORS)]
            ax.plot(
                labels,
                s["values"],
                marker="o",
                markersize=6,
                linewidth=2,
                color=series_color,
                label=s.get("name", f"Series {i + 1}"),
            )
        ax.legend(loc="upper left", fontsize=9)
    else:
        # Single series
        ax.plot(
            labels,
            values,
            marker="o",
            markersize=6,
            linewidth=2,
            color=color,
        )

    ax.set_title(title, fontsize=12, fontweight="bold", pad=15)
    if x_label:
        ax.set_xlabel(x_label, fontsize=10)
    if y_label:
        ax.set_ylabel(y_label, fontsize=10)

    # Style
    ax.grid(True, linestyle="--", alpha=0.3)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # Rotate x-axis labels if many
    if len(labels) > 5:
        plt.xticks(rotation=45, ha="right")

    # Save to bytes
    buffer = io.BytesIO()
    plt.tight_layout()
    fig.savefig(buffer, format="png", dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    buffer.seek(0)
    return buffer.read()


def generate_bar_chart(
    data: dict[str, Any],
    title: str,
    x_label: str = "",
    y_label: str = "",
    colors: list[str] | None = None,
    horizontal: bool = False,
    figsize: tuple[float, float] = (8, 4),
) -> bytes:
    """
    Generate a bar chart as PNG bytes.

    Args:
        data: Dictionary with 'labels' and 'values' keys.
        title: Chart title.
        x_label: X-axis label.
        y_label: Y-axis label.
        colors: Optional list of colors for bars.
        horizontal: Whether to create horizontal bars.
        figsize: Figure size in inches.

    Returns:
        PNG image as bytes, or empty bytes if data is empty.
    """
    labels = data.get("labels", [])
    values = data.get("values", [])

    if not labels or not values:
        return b""

    # Use default colors if not provided
    if colors is None:
        colors = [DEFAULT_COLORS[i % len(DEFAULT_COLORS)] for i in range(len(labels))]

    fig, ax = plt.subplots(figsize=figsize)

    if horizontal:
        ax.barh(labels, values, color=colors)
        if x_label:
            ax.set_xlabel(x_label, fontsize=10)
        if y_label:
            ax.set_ylabel(y_label, fontsize=10)
    else:
        ax.bar(labels, values, color=colors)
        if x_label:
            ax.set_xlabel(x_label, fontsize=10)
        if y_label:
            ax.set_ylabel(y_label, fontsize=10)
        # Rotate x-axis labels if many
        if len(labels) > 5:
            plt.xticks(rotation=45, ha="right")

    ax.set_title(title, fontsize=12, fontweight="bold", pad=15)

    # Style
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # Save to bytes
    buffer = io.BytesIO()
    plt.tight_layout()
    fig.savefig(buffer, format="png", dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    buffer.seek(0)
    return buffer.read()


class ChartGenerator:
    """
    Chart generator with configurable styling.

    Provides methods for generating charts as bytes or base64 strings
    for embedding in HTML templates.
    """

    def __init__(self, style: str | None = None) -> None:
        """
        Initialize chart generator.

        Args:
            style: Matplotlib style name (e.g., 'seaborn', 'dark_background').
        """
        self._style = style

    def _apply_style(self) -> None:
        """Apply configured matplotlib style."""
        if self._style:
            plt.style.use(self._style)

    def generate_pie_chart(
        self,
        data: dict[str, int | float],
        title: str,
        colors: list[str] | None = None,
        figsize: tuple[float, float] = (6, 6),
    ) -> bytes:
        """Generate pie chart as PNG bytes."""
        self._apply_style()
        return generate_pie_chart(data, title, colors, figsize)

    def generate_pie_chart_base64(
        self,
        data: dict[str, int | float],
        title: str,
        colors: list[str] | None = None,
        figsize: tuple[float, float] = (6, 6),
    ) -> str:
        """Generate pie chart as base64-encoded string."""
        png_bytes = self.generate_pie_chart(data, title, colors, figsize)
        if not png_bytes:
            return ""
        return base64.b64encode(png_bytes).decode("utf-8")

    def generate_line_chart(
        self,
        data: dict[str, Any],
        title: str,
        x_label: str = "",
        y_label: str = "",
        color: str = "#2563eb",
        figsize: tuple[float, float] = (8, 4),
    ) -> bytes:
        """Generate line chart as PNG bytes."""
        self._apply_style()
        return generate_line_chart(data, title, x_label, y_label, color, figsize)

    def generate_line_chart_base64(
        self,
        data: dict[str, Any],
        title: str,
        x_label: str = "",
        y_label: str = "",
        color: str = "#2563eb",
        figsize: tuple[float, float] = (8, 4),
    ) -> str:
        """Generate line chart as base64-encoded string."""
        png_bytes = self.generate_line_chart(data, title, x_label, y_label, color, figsize)
        if not png_bytes:
            return ""
        return base64.b64encode(png_bytes).decode("utf-8")

    def generate_bar_chart(
        self,
        data: dict[str, Any],
        title: str,
        x_label: str = "",
        y_label: str = "",
        colors: list[str] | None = None,
        horizontal: bool = False,
        figsize: tuple[float, float] = (8, 4),
    ) -> bytes:
        """Generate bar chart as PNG bytes."""
        self._apply_style()
        return generate_bar_chart(data, title, x_label, y_label, colors, horizontal, figsize)

    def generate_bar_chart_base64(
        self,
        data: dict[str, Any],
        title: str,
        x_label: str = "",
        y_label: str = "",
        colors: list[str] | None = None,
        horizontal: bool = False,
        figsize: tuple[float, float] = (8, 4),
    ) -> str:
        """Generate bar chart as base64-encoded string."""
        png_bytes = self.generate_bar_chart(
            data, title, x_label, y_label, colors, horizontal, figsize
        )
        if not png_bytes:
            return ""
        return base64.b64encode(png_bytes).decode("utf-8")

    @staticmethod
    def get_default_colors() -> list[str]:
        """Get default color palette."""
        return DEFAULT_COLORS.copy()

    @staticmethod
    def get_severity_colors() -> dict[str, str]:
        """Get severity-based color mapping."""
        return SEVERITY_COLORS.copy()
