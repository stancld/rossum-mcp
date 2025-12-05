"""Tests for the plotting tool.

This module tests the plot_data tool with various chart types and configurations.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from rossum_agent.plot_tools import plot_data


@pytest.fixture
def sample_data() -> dict[str, float]:
    """Sample data for testing plots."""
    return {
        "API Integration Development": 26992.25,
        "System Architecture Design": 59209.98,
        "DevOps Automation Setup": 21064.31,
        "Code Review and Optimization": 28266.45,
        "Database Design and Migration": 47037.86,
        "Software Development Services": 26441.66,
        "Security Audit Services": 16695.22,
        "Cloud Infrastructure Consulting": 23659.55,
        "Performance Testing": 9997.68,
        "Technical Documentation": 10884.77,
    }


@pytest.fixture
def temp_output_dir(tmp_path: Path) -> Path:
    """Create a temporary directory for plot outputs."""
    output_dir = tmp_path / "plots"
    output_dir.mkdir()
    return output_dir


class TestPlotData:
    """Test cases for plot_data tool."""

    def test_bar_chart_interactive(self, sample_data: dict[str, float], temp_output_dir: Path) -> None:
        """Test creating an interactive bar chart."""
        output_path = temp_output_dir / "bar_interactive.html"
        result_json = plot_data(
            data_json=json.dumps(sample_data),
            chart_type="bar",
            title="Revenue by Service Category",
            y_label="Revenue ($)",
            output_path=str(output_path),
            interactive=True,
            color_scheme="viridis",
        )

        result = json.loads(result_json)
        assert result["status"] == "success"
        assert Path(result["output_path"]).exists()
        assert result["chart_type"] == "bar"
        assert result["interactive"] is True

    def test_bar_chart_static(self, sample_data: dict[str, float], temp_output_dir: Path) -> None:
        """Test creating a static bar chart."""
        output_path = temp_output_dir / "bar_static.png"
        result_json = plot_data(
            data_json=json.dumps(sample_data),
            chart_type="bar",
            title="Revenue by Service Category",
            y_label="Revenue ($)",
            output_path=str(output_path),
            interactive=False,
            color_scheme="default",
        )

        result = json.loads(result_json)
        assert result["status"] == "success"
        assert Path(result["output_path"]).exists()
        assert result["chart_type"] == "bar"
        assert result["interactive"] is False

    def test_horizontal_bar_chart(self, sample_data: dict[str, float], temp_output_dir: Path) -> None:
        """Test creating a horizontal bar chart."""
        output_path = temp_output_dir / "horizontal_bar.html"
        result_json = plot_data(
            data_json=json.dumps(sample_data),
            chart_type="horizontal_bar",
            title="Top Services by Revenue",
            x_label="Revenue ($)",
            output_path=str(output_path),
            interactive=True,
            sort_descending=True,
        )

        result = json.loads(result_json)
        assert result["status"] == "success"
        assert Path(result["output_path"]).exists()
        assert result["chart_type"] == "horizontal_bar"

    def test_pie_chart_interactive(self, sample_data: dict[str, float], temp_output_dir: Path) -> None:
        """Test creating an interactive pie chart."""
        output_path = temp_output_dir / "pie_interactive.html"
        result_json = plot_data(
            data_json=json.dumps(sample_data),
            chart_type="pie",
            title="Revenue Distribution by Service",
            output_path=str(output_path),
            interactive=True,
            color_scheme="pastel",
        )

        result = json.loads(result_json)
        assert result["status"] == "success"
        assert Path(result["output_path"]).exists()
        assert result["chart_type"] == "pie"

    def test_pie_chart_static(self, sample_data: dict[str, float], temp_output_dir: Path) -> None:
        """Test creating a static pie chart."""
        output_path = temp_output_dir / "pie_static.png"
        result_json = plot_data(
            data_json=json.dumps(sample_data),
            chart_type="pie",
            title="Revenue Distribution",
            output_path=str(output_path),
            interactive=False,
        )

        result = json.loads(result_json)
        assert result["status"] == "success"
        assert Path(result["output_path"]).exists()

    def test_line_chart_single_series(self, temp_output_dir: Path) -> None:
        """Test creating a line chart with single series."""
        time_data = {"Jan": 1000, "Feb": 1200, "Mar": 1100, "Apr": 1400, "May": 1600, "Jun": 1550}
        output_path = temp_output_dir / "line_single.html"

        result_json = plot_data(
            data_json=json.dumps(time_data),
            chart_type="line",
            title="Monthly Revenue Trend",
            x_label="Month",
            y_label="Revenue ($)",
            output_path=str(output_path),
            interactive=True,
        )

        result = json.loads(result_json)
        assert result["status"] == "success"
        assert Path(result["output_path"]).exists()
        assert result["chart_type"] == "line"

    def test_line_chart_multi_series(self, temp_output_dir: Path) -> None:
        """Test creating a line chart with multiple series."""
        multi_data = {"Product A": [100, 120, 115, 140, 160], "Product B": [80, 85, 90, 95, 100]}
        output_path = temp_output_dir / "line_multi.html"

        result_json = plot_data(
            data_json=json.dumps(multi_data),
            chart_type="line",
            title="Product Performance Comparison",
            y_label="Sales",
            output_path=str(output_path),
            interactive=True,
        )

        result = json.loads(result_json)
        assert result["status"] == "success"
        assert Path(result["output_path"]).exists()

    def test_scatter_plot(self, temp_output_dir: Path) -> None:
        """Test creating a scatter plot."""
        scatter_data = [{"x": i, "y": i**2 + i * 10} for i in range(20)]
        output_path = temp_output_dir / "scatter.html"

        result_json = plot_data(
            data_json=json.dumps(scatter_data),
            chart_type="scatter",
            title="Scatter Plot Example",
            x_label="X Value",
            y_label="Y Value",
            output_path=str(output_path),
            interactive=True,
        )

        result = json.loads(result_json)
        assert result["status"] == "success"
        assert Path(result["output_path"]).exists()
        assert result["chart_type"] == "scatter"

    def test_heatmap(self, temp_output_dir: Path) -> None:
        """Test creating a heatmap."""
        heatmap_data = {
            "Row 1": {"Col A": 10, "Col B": 20, "Col C": 30},
            "Row 2": {"Col A": 15, "Col B": 25, "Col C": 35},
            "Row 3": {"Col A": 12, "Col B": 22, "Col C": 32},
        }
        output_path = temp_output_dir / "heatmap.html"

        result_json = plot_data(
            data_json=json.dumps(heatmap_data),
            chart_type="heatmap",
            title="Heatmap Example",
            output_path=str(output_path),
            interactive=True,
            color_scheme="plasma",
        )

        result = json.loads(result_json)
        assert result["status"] == "success"
        assert Path(result["output_path"]).exists()
        assert result["chart_type"] == "heatmap"

    def test_sorting_descending(self, sample_data: dict[str, float], temp_output_dir: Path) -> None:
        """Test sorting data in descending order."""
        output_path = temp_output_dir / "sorted_desc.html"
        result_json = plot_data(
            data_json=json.dumps(sample_data),
            chart_type="bar",
            title="Sorted Descending",
            output_path=str(output_path),
            sort_values=True,
            sort_descending=True,
        )

        result = json.loads(result_json)
        assert result["status"] == "success"

    def test_sorting_ascending(self, sample_data: dict[str, float], temp_output_dir: Path) -> None:
        """Test sorting data in ascending order."""
        output_path = temp_output_dir / "sorted_asc.html"
        result_json = plot_data(
            data_json=json.dumps(sample_data),
            chart_type="bar",
            title="Sorted Ascending",
            output_path=str(output_path),
            sort_values=True,
            sort_descending=False,
        )

        result = json.loads(result_json)
        assert result["status"] == "success"

    def test_no_value_labels(self, sample_data: dict[str, float], temp_output_dir: Path) -> None:
        """Test creating charts without value labels."""
        output_path = temp_output_dir / "no_labels.html"
        result_json = plot_data(
            data_json=json.dumps(sample_data),
            chart_type="bar",
            title="No Value Labels",
            output_path=str(output_path),
            show_values=False,
        )

        result = json.loads(result_json)
        assert result["status"] == "success"

    def test_custom_dimensions(self, sample_data: dict[str, float], temp_output_dir: Path) -> None:
        """Test custom plot dimensions."""
        output_path = temp_output_dir / "custom_size.html"
        result_json = plot_data(
            data_json=json.dumps(sample_data),
            chart_type="bar",
            title="Custom Size",
            output_path=str(output_path),
            width=1200,
            height=800,
        )

        result = json.loads(result_json)
        assert result["status"] == "success"

    def test_color_schemes(self, sample_data: dict[str, float], temp_output_dir: Path) -> None:
        """Test different color schemes."""
        color_schemes = ["default", "viridis", "plasma", "pastel", "bold"]

        for scheme in color_schemes:
            output_path = temp_output_dir / f"color_{scheme}.html"
            result_json = plot_data(
                data_json=json.dumps(sample_data),
                chart_type="bar",
                title=f"Color Scheme: {scheme}",
                output_path=str(output_path),
                color_scheme=scheme,
            )

            result = json.loads(result_json)
            assert result["status"] == "success"

    def test_invalid_json(self, temp_output_dir: Path) -> None:
        """Test handling of invalid JSON input."""
        result_json = plot_data(
            data_json="invalid json",
            chart_type="bar",
            output_path=str(temp_output_dir / "test.html"),
        )

        result = json.loads(result_json)
        assert result["status"] == "error"
        assert "Invalid JSON" in result["error"]

    def test_invalid_chart_type(self, sample_data: dict[str, float], temp_output_dir: Path) -> None:
        """Test handling of invalid chart type."""
        result_json = plot_data(
            data_json=json.dumps(sample_data),
            chart_type="invalid_type",
            output_path=str(temp_output_dir / "test.html"),
        )

        result = json.loads(result_json)
        assert result["status"] == "error"
        assert "Invalid chart_type" in result["error"]

    def test_auto_extension_html(self, sample_data: dict[str, float], temp_output_dir: Path) -> None:
        """Test automatic .html extension for interactive plots."""
        output_path = temp_output_dir / "test_no_ext"
        result_json = plot_data(
            data_json=json.dumps(sample_data),
            chart_type="bar",
            output_path=str(output_path),
            interactive=True,
        )

        result = json.loads(result_json)
        assert result["status"] == "success"
        assert result["output_path"].endswith(".html")

    def test_auto_extension_png(self, sample_data: dict[str, float], temp_output_dir: Path) -> None:
        """Test automatic .png extension for static plots."""
        output_path = temp_output_dir / "test_no_ext"
        result_json = plot_data(
            data_json=json.dumps(sample_data),
            chart_type="bar",
            output_path=str(output_path),
            interactive=False,
        )

        result = json.loads(result_json)
        assert result["status"] == "success"
        assert result["output_path"].endswith(".png")

    def test_directory_creation(self, sample_data: dict[str, float], tmp_path: Path) -> None:
        """Test that nested directories are created automatically."""
        output_path = tmp_path / "nested" / "dirs" / "plot.html"
        result_json = plot_data(
            data_json=json.dumps(sample_data),
            chart_type="bar",
            output_path=str(output_path),
        )

        result = json.loads(result_json)
        assert result["status"] == "success"
        assert Path(result["output_path"]).exists()
