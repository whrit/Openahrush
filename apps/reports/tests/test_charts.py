"""
Tests for chart generation module.
"""

import base64
from io import BytesIO

import pytest

from semrush_reports.charts import (
    ChartGenerator,
    generate_bar_chart,
    generate_line_chart,
    generate_pie_chart,
)


class TestPieChart:
    """Tests for pie chart generation."""

    def test_generate_pie_chart_returns_bytes(self) -> None:
        """Test that pie chart returns PNG bytes."""
        data = {"Critical": 5, "High": 10, "Medium": 20, "Low": 30}
        result = generate_pie_chart(data, "Issues by Severity")

        assert isinstance(result, bytes)
        assert len(result) > 0
        # Check PNG magic number
        assert result[:8] == b"\x89PNG\r\n\x1a\n"

    def test_generate_pie_chart_empty_data(self) -> None:
        """Test pie chart with empty data returns empty bytes."""
        data: dict[str, int] = {}
        result = generate_pie_chart(data, "Empty Chart")

        assert isinstance(result, bytes)
        assert len(result) == 0

    def test_generate_pie_chart_single_item(self) -> None:
        """Test pie chart with single item."""
        data = {"Critical": 5}
        result = generate_pie_chart(data, "Single Item")

        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_generate_pie_chart_custom_colors(self) -> None:
        """Test pie chart with custom colors."""
        data = {"A": 10, "B": 20, "C": 30}
        colors = ["#ff0000", "#00ff00", "#0000ff"]
        result = generate_pie_chart(data, "Custom Colors", colors=colors)

        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_generate_pie_chart_figsize(self) -> None:
        """Test pie chart with custom figure size."""
        data = {"A": 10, "B": 20}
        result = generate_pie_chart(data, "Custom Size", figsize=(8, 8))

        assert isinstance(result, bytes)
        assert len(result) > 0


class TestLineChart:
    """Tests for line chart generation."""

    def test_generate_line_chart_returns_bytes(self) -> None:
        """Test that line chart returns PNG bytes."""
        data = {
            "labels": ["Jan", "Feb", "Mar", "Apr"],
            "values": [100, 150, 120, 180],
        }
        result = generate_line_chart(data, "Traffic Over Time")

        assert isinstance(result, bytes)
        assert len(result) > 0
        assert result[:8] == b"\x89PNG\r\n\x1a\n"

    def test_generate_line_chart_empty_data(self) -> None:
        """Test line chart with empty data."""
        data = {"labels": [], "values": []}
        result = generate_line_chart(data, "Empty Chart")

        assert isinstance(result, bytes)
        assert len(result) == 0

    def test_generate_line_chart_single_point(self) -> None:
        """Test line chart with single data point."""
        data = {"labels": ["Jan"], "values": [100]}
        result = generate_line_chart(data, "Single Point")

        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_generate_line_chart_with_axis_labels(self) -> None:
        """Test line chart with custom axis labels."""
        data = {
            "labels": ["Week 1", "Week 2", "Week 3"],
            "values": [50, 75, 100],
        }
        result = generate_line_chart(
            data,
            "Performance",
            x_label="Week",
            y_label="Score",
        )

        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_generate_line_chart_custom_color(self) -> None:
        """Test line chart with custom line color."""
        data = {
            "labels": ["A", "B", "C"],
            "values": [10, 20, 30],
        }
        result = generate_line_chart(data, "Custom Color", color="#ff5500")

        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_generate_line_chart_multiple_series(self) -> None:
        """Test line chart with multiple data series."""
        data = {
            "labels": ["Jan", "Feb", "Mar"],
            "series": [
                {"name": "Organic", "values": [100, 120, 150]},
                {"name": "Paid", "values": [50, 60, 70]},
            ],
        }
        result = generate_line_chart(data, "Traffic by Source")

        assert isinstance(result, bytes)
        assert len(result) > 0


class TestBarChart:
    """Tests for bar chart generation."""

    def test_generate_bar_chart_returns_bytes(self) -> None:
        """Test that bar chart returns PNG bytes."""
        data = {
            "labels": ["Critical", "High", "Medium", "Low"],
            "values": [5, 15, 30, 50],
        }
        result = generate_bar_chart(data, "Issues Count")

        assert isinstance(result, bytes)
        assert len(result) > 0
        assert result[:8] == b"\x89PNG\r\n\x1a\n"

    def test_generate_bar_chart_empty_data(self) -> None:
        """Test bar chart with empty data."""
        data = {"labels": [], "values": []}
        result = generate_bar_chart(data, "Empty Chart")

        assert isinstance(result, bytes)
        assert len(result) == 0

    def test_generate_bar_chart_horizontal(self) -> None:
        """Test horizontal bar chart."""
        data = {
            "labels": ["Page A", "Page B", "Page C"],
            "values": [10, 20, 30],
        }
        result = generate_bar_chart(data, "Pages", horizontal=True)

        assert isinstance(result, bytes)
        assert len(result) > 0


class TestChartGenerator:
    """Tests for ChartGenerator class."""

    def test_chart_generator_init(self) -> None:
        """Test ChartGenerator initialization."""
        generator = ChartGenerator()
        assert generator is not None

    def test_chart_generator_custom_style(self) -> None:
        """Test ChartGenerator with custom style."""
        generator = ChartGenerator(style="dark_background")
        assert generator._style == "dark_background"

    def test_generate_pie_chart_base64(self) -> None:
        """Test generating pie chart as base64 string."""
        generator = ChartGenerator()
        data = {"A": 10, "B": 20, "C": 30}
        result = generator.generate_pie_chart_base64(data, "Test")

        assert isinstance(result, str)
        # Verify it's valid base64
        decoded = base64.b64decode(result)
        assert decoded[:8] == b"\x89PNG\r\n\x1a\n"

    def test_generate_line_chart_base64(self) -> None:
        """Test generating line chart as base64 string."""
        generator = ChartGenerator()
        data = {
            "labels": ["A", "B", "C"],
            "values": [10, 20, 30],
        }
        result = generator.generate_line_chart_base64(data, "Test")

        assert isinstance(result, str)
        decoded = base64.b64decode(result)
        assert decoded[:8] == b"\x89PNG\r\n\x1a\n"

    def test_generate_bar_chart_base64(self) -> None:
        """Test generating bar chart as base64 string."""
        generator = ChartGenerator()
        data = {
            "labels": ["A", "B", "C"],
            "values": [10, 20, 30],
        }
        result = generator.generate_bar_chart_base64(data, "Test")

        assert isinstance(result, str)
        decoded = base64.b64decode(result)
        assert decoded[:8] == b"\x89PNG\r\n\x1a\n"

    def test_default_colors(self) -> None:
        """Test that default colors are available."""
        generator = ChartGenerator()
        colors = generator.get_default_colors()

        assert isinstance(colors, list)
        assert len(colors) >= 4

    def test_severity_colors(self) -> None:
        """Test severity color mapping."""
        generator = ChartGenerator()
        colors = generator.get_severity_colors()

        assert "critical" in colors
        assert "high" in colors
        assert "medium" in colors
        assert "low" in colors
