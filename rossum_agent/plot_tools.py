"""Advanced Plotting Tools for Rossum Agent

State-of-the-art data visualization tools supporting both interactive (Plotly)
and static (Matplotlib/Seaborn) plots. Designed for integration with smolagents.

Features:
- Interactive plots with Plotly (hover, zoom, pan)
- Beautiful static plots with Matplotlib and Seaborn
- Automatic color schemes and styling
- Support for various chart types: bar, line, pie, scatter, heatmap
- Smart defaults with extensive customization options
- HTML output for interactive plots, PNG for static plots

Example usage:
    # Interactive bar chart
    data = {'Category A': 100, 'Category B': 150, 'Category C': 120}
    plot_data(json.dumps(data), chart_type='bar', title='Sales by Category',
              interactive=True, output_path='sales.html')

    # Static pie chart with custom colors
    plot_data(json.dumps(data), chart_type='pie', title='Distribution',
              interactive=False, output_path='distribution.png')
"""

import json
from pathlib import Path
from typing import Any, Literal

import matplotlib.pyplot as plt
import plotly.graph_objects as go
import seaborn as sns
from smolagents import tool

# Chart type definitions
ChartType = Literal["bar", "line", "pie", "scatter", "heatmap", "horizontal_bar"]
ColorScheme = Literal["default", "viridis", "plasma", "inferno", "magma", "cividis", "pastel", "bold"]


@tool
def plot_data(
    data_json: str,
    chart_type: str = "bar",
    title: str = "Data Visualization",
    x_label: str | None = None,
    y_label: str | None = None,
    output_path: str = "plot.html",
    interactive: bool = True,
    color_scheme: str = "default",
    sort_values: bool = True,
    sort_descending: bool = True,
    show_values: bool = True,
    width: int = 1000,
    height: int = 600,
) -> str:
    """Create beautiful data visualizations from dictionary data.

    This tool creates professional-quality charts using Plotly (interactive) or
    Matplotlib/Seaborn (static). Supports various chart types with smart defaults.

    Args:
        data_json: JSON string containing data to plot. Must be json.dumps() of:
            - Dict[str, float]: For bar, line, pie charts (e.g., {'A': 100, 'B': 150})
            - Dict[str, List[float]]: For multi-series line charts
            - List[Dict]: For scatter plots with 'x', 'y' keys
            - Dict[str, Dict[str, float]]: For heatmaps (nested dict)
        chart_type: Type of chart to create. Options:
            - 'bar': Vertical bar chart (default)
            - 'horizontal_bar': Horizontal bar chart
            - 'line': Line chart (single or multi-series)
            - 'pie': Pie chart with percentages
            - 'scatter': Scatter plot (requires list of dicts with x, y)
            - 'heatmap': Heatmap (requires nested dict or 2D structure)
        title: Chart title
        x_label: Label for X axis (auto-generated if None)
        y_label: Label for Y axis (auto-generated if None)
        output_path: Path to save plot (*.html for interactive, *.png for static)
        interactive: If True, create interactive Plotly plot; if False, static Matplotlib plot
        color_scheme: Color scheme to use. Options:
            - 'default': Beautiful default colors
            - 'viridis', 'plasma', 'inferno', 'magma': Scientific colormaps
            - 'pastel': Soft, pastel colors
            - 'bold': Bold, vibrant colors
        sort_values: If True, sort data by values before plotting (for bar/pie charts)
        sort_descending: If True, sort in descending order
        show_values: If True, display values on bars/slices
        width: Plot width in pixels
        height: Plot height in pixels

    Returns:
        JSON string with result status and file path. Use json.loads() to parse.
        Success: {"status": "success", "output_path": "/path/to/plot.html", "chart_type": "bar"}
        Error: {"status": "error", "error": "error message"}

    Examples:
        # Bar chart from invoice line items
        data = {'API Dev': 26992.25, 'System Design': 59209.98, 'DevOps': 21064.31}
        result = plot_data(
            json.dumps(data),
            chart_type='bar',
            title='Revenue by Service Category',
            y_label='Total Revenue ($)',
            interactive=True,
            output_path='revenue.html',
            color_scheme='viridis'
        )

        # Horizontal bar chart (better for long labels)
        result = plot_data(
            json.dumps(data),
            chart_type='horizontal_bar',
            title='Top Services by Revenue',
            sort_descending=True
        )

        # Static plot (PNG output)
        result = plot_data(
            json.dumps(data),
            chart_type='bar',
            interactive=False,
            output_path='revenue.png'
        )
    """
    try:
        # Parse input data
        data = json.loads(data_json)

        # Validate chart type
        valid_types = ["bar", "horizontal_bar", "line", "pie", "scatter", "heatmap"]
        if chart_type not in valid_types:
            return json.dumps(
                {
                    "status": "error",
                    "error": f"Invalid chart_type '{chart_type}'. Must be one of: {', '.join(valid_types)}",
                }
            )

        # Create plot based on interactivity preference
        if interactive:
            result = _create_plotly_chart(
                data=data,
                chart_type=chart_type,
                title=title,
                x_label=x_label,
                y_label=y_label,
                output_path=output_path,
                color_scheme=color_scheme,
                sort_values=sort_values,
                sort_descending=sort_descending,
                show_values=show_values,
                width=width,
                height=height,
            )
        else:
            result = _create_matplotlib_chart(
                data=data,
                chart_type=chart_type,
                title=title,
                x_label=x_label,
                y_label=y_label,
                output_path=output_path,
                color_scheme=color_scheme,
                sort_values=sort_values,
                sort_descending=sort_descending,
                show_values=show_values,
                width=width,
                height=height,
            )

        return json.dumps(result, indent=2)

    except json.JSONDecodeError as e:
        return json.dumps({"status": "error", "error": f"Invalid JSON in data_json: {e!s}"})
    except Exception as e:
        return json.dumps({"status": "error", "error": f"Plot creation error: {e!s}"})


def _create_plotly_chart(
    data: Any,
    chart_type: str,
    title: str,
    x_label: str | None,
    y_label: str | None,
    output_path: str,
    color_scheme: str,
    sort_values: bool,
    sort_descending: bool,
    show_values: bool,
    width: int,
    height: int,
) -> dict[str, Any]:
    """Create interactive Plotly chart."""
    # Ensure output path has .html extension for interactive plots
    if not output_path.endswith(".html"):
        output_path = output_path.rsplit(".", 1)[0] + ".html"

    # Get color palette
    colors = _get_plotly_colors(color_scheme)

    try:
        # Create chart based on type
        match chart_type:
            case "bar" | "horizontal_bar":
                result = _create_plotly_bar_chart(
                    data, chart_type, colors, x_label, y_label, sort_values, sort_descending, show_values
                )
            case "line":
                result = _create_plotly_line_chart(data, colors, x_label, y_label)
            case "pie":
                result = _create_plotly_pie_chart(data, colors, sort_values, sort_descending, show_values)
            case "scatter":
                result = _create_plotly_scatter_chart(data, colors, x_label, y_label)
            case "heatmap":
                result = _create_plotly_heatmap_chart(data, color_scheme, x_label, y_label, show_values)
            case _:
                return {"status": "error", "error": f"Failed to create chart of type '{chart_type}'"}

        # Check if error was returned
        if isinstance(result, dict):
            return result

        # At this point, result must be a go.Figure
        # Update layout with common settings
        result.update_layout(
            title=dict(text=title, x=0.5, xanchor="center", font=dict(size=20, family="Arial, sans-serif")),
            width=width,
            height=height,
            template="plotly_white",
            hovermode="closest",
            showlegend=chart_type == "line",
        )

        # Save to file
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        result.write_html(str(output_file))

        return {
            "status": "success",
            "output_path": str(output_file.absolute()),
            "chart_type": chart_type,
            "interactive": True,
        }

    except Exception as e:
        return {"status": "error", "error": f"Plotly chart creation failed: {e!s}"}


def _create_plotly_bar_chart(
    data: Any,
    chart_type: str,
    colors: list[str],
    x_label: str | None,
    y_label: str | None,
    sort_values: bool,
    sort_descending: bool,
    show_values: bool,
) -> go.Figure | dict[str, Any]:
    """Create Plotly bar chart (vertical or horizontal)."""
    if not isinstance(data, dict):
        return {"status": "error", "error": "Bar chart requires dict data {label: value}"}

    # Sort if requested
    if sort_values:
        data = dict(sorted(data.items(), key=lambda x: x[1], reverse=sort_descending))

    labels = list(data.keys())
    values = list(data.values())

    if chart_type == "horizontal_bar":
        fig = go.Figure(
            data=[
                go.Bar(
                    y=labels,
                    x=values,
                    orientation="h",
                    marker=dict(color=colors),
                    text=values if show_values else None,
                    texttemplate="%{x:,.2f}" if show_values else None,
                    textposition="auto",
                )
            ]
        )
        fig.update_layout(
            xaxis_title=y_label or "Value",
            yaxis_title=x_label or "Category",
        )
    else:
        fig = go.Figure(
            data=[
                go.Bar(
                    x=labels,
                    y=values,
                    marker=dict(color=colors),
                    text=values if show_values else None,
                    texttemplate="%{y:,.2f}" if show_values else None,
                    textposition="auto",
                )
            ]
        )
        fig.update_layout(
            xaxis_title=x_label or "Category",
            yaxis_title=y_label or "Value",
        )

    return fig


def _create_plotly_line_chart(
    data: Any, colors: list[str], x_label: str | None, y_label: str | None
) -> go.Figure | dict[str, Any]:
    """Create Plotly line chart (single or multi-series)."""
    if not isinstance(data, dict):
        return {"status": "error", "error": "Line chart requires dict data"}

    # Check if multi-series (values are lists)
    if data and isinstance(next(iter(data.values())), list):
        # Multi-series line chart
        fig = go.Figure()
        for i, (series_name, values) in enumerate(data.items()):
            fig.add_trace(
                go.Scatter(
                    x=list(range(len(values))),
                    y=values,
                    mode="lines+markers",
                    name=series_name,
                    line=dict(color=colors[i % len(colors)]),
                )
            )
    else:
        # Single series
        labels = list(data.keys())
        values = list(data.values())
        fig = go.Figure(data=[go.Scatter(x=labels, y=values, mode="lines+markers", line=dict(color=colors[0]))])

    fig.update_layout(
        xaxis_title=x_label or "X",
        yaxis_title=y_label or "Y",
    )

    return fig


def _create_plotly_pie_chart(
    data: Any, colors: list[str], sort_values: bool, sort_descending: bool, show_values: bool
) -> go.Figure | dict[str, Any]:
    """Create Plotly pie chart."""
    if not isinstance(data, dict):
        return {"status": "error", "error": "Pie chart requires dict data"}

    # Sort if requested
    if sort_values:
        data = dict(sorted(data.items(), key=lambda x: x[1], reverse=sort_descending))

    labels = list(data.keys())
    values = list(data.values())

    return go.Figure(
        data=[
            go.Pie(
                labels=labels,
                values=values,
                marker=dict(colors=colors),
                textinfo="label+percent" if show_values else "label",
                hovertemplate="<b>%{label}</b><br>Value: %{value:,.2f}<br>Percent: %{percent}<extra></extra>",
            )
        ]
    )


def _create_plotly_scatter_chart(
    data: Any, colors: list[str], x_label: str | None, y_label: str | None
) -> go.Figure | dict[str, Any]:
    """Create Plotly scatter plot."""
    if not isinstance(data, list):
        return {"status": "error", "error": "Scatter plot requires list of dicts with 'x' and 'y' keys"}

    x_vals = [item.get("x", 0) for item in data]
    y_vals = [item.get("y", 0) for item in data]

    fig = go.Figure(data=[go.Scatter(x=x_vals, y=y_vals, mode="markers", marker=dict(color=colors[0], size=10))])
    fig.update_layout(
        xaxis_title=x_label or "X",
        yaxis_title=y_label or "Y",
    )

    return fig


def _create_plotly_heatmap_chart(
    data: Any, color_scheme: str, x_label: str | None, y_label: str | None, show_values: bool
) -> go.Figure | dict[str, Any]:
    """Create Plotly heatmap."""
    if isinstance(data, dict) and all(isinstance(v, dict) for v in data.values()):
        # Nested dict format
        row_labels = list(data.keys())
        col_labels = list(next(iter(data.values())).keys())
        z_values = [[data[row][col] for col in col_labels] for row in row_labels]
    else:
        return {
            "status": "error",
            "error": "Heatmap requires nested dict format {row: {col: value}}",
        }

    fig = go.Figure(
        data=[
            go.Heatmap(
                z=z_values,
                x=col_labels,
                y=row_labels,
                colorscale=_get_plotly_colorscale(color_scheme),
                text=z_values if show_values else None,
                texttemplate="%{text:.2f}" if show_values else None,
            )
        ]
    )
    fig.update_layout(
        xaxis_title=x_label or "Column",
        yaxis_title=y_label or "Row",
    )

    return fig


def _create_matplotlib_chart(
    data: Any,
    chart_type: str,
    title: str,
    x_label: str | None,
    y_label: str | None,
    output_path: str,
    color_scheme: str,
    sort_values: bool,
    sort_descending: bool,
    show_values: bool,
    width: int,
    height: int,
) -> dict[str, Any]:
    """Create static Matplotlib/Seaborn chart."""
    # Ensure output path has image extension
    if not any(output_path.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".pdf", ".svg"]):
        output_path = output_path.rsplit(".", 1)[0] + ".png"

    # Set style
    sns.set_theme(style="whitegrid" if chart_type in ["bar", "horizontal_bar", "line"] else "white")

    # Get color palette
    colors = _get_matplotlib_colors(color_scheme)

    try:
        # Create figure
        _fig, ax = plt.subplots(figsize=(width / 100, height / 100), dpi=100)

        # Create chart based on type
        match chart_type:
            case "bar" | "horizontal_bar":
                result = _create_matplotlib_bar_chart(
                    ax, data, chart_type, colors, x_label, y_label, sort_values, sort_descending, show_values
                )
            case "line":
                result = _create_matplotlib_line_chart(ax, data, colors, x_label, y_label)
            case "pie":
                result = _create_matplotlib_pie_chart(ax, data, colors, sort_values, sort_descending, show_values)
            case "scatter":
                result = _create_matplotlib_scatter_chart(ax, data, colors, x_label, y_label)
            case "heatmap":
                result = _create_matplotlib_heatmap_chart(ax, data, color_scheme, x_label, y_label, show_values)
            case _:
                plt.close()
                return {"status": "error", "error": f"Unknown chart type '{chart_type}'"}

        # Check if error was returned
        if isinstance(result, dict) and result.get("status") == "error":
            plt.close()
            return result

        # Set title
        ax.set_title(title, fontsize=16, fontweight="bold", pad=20)

        # Tight layout
        plt.tight_layout()

        # Save figure
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(str(output_file), dpi=100, bbox_inches="tight")
        plt.close()

        return {
            "status": "success",
            "output_path": str(output_file.absolute()),
            "chart_type": chart_type,
            "interactive": False,
        }

    except Exception as e:
        plt.close()
        return {"status": "error", "error": f"Matplotlib chart creation failed: {e!s}"}


def _create_matplotlib_bar_chart(
    ax: plt.Axes,
    data: Any,
    chart_type: str,
    colors: list[str],
    x_label: str | None,
    y_label: str | None,
    sort_values: bool,
    sort_descending: bool,
    show_values: bool,
) -> None | dict[str, Any]:
    """Create Matplotlib bar chart (vertical or horizontal)."""
    if not isinstance(data, dict):
        return {"status": "error", "error": "Bar chart requires dict data"}

    # Sort if requested
    if sort_values:
        data = dict(sorted(data.items(), key=lambda x: x[1], reverse=sort_descending))

    labels = list(data.keys())
    values = list(data.values())

    if chart_type == "horizontal_bar":
        bars = ax.barh(labels, values, color=colors[: len(labels)])
        ax.set_xlabel(y_label or "Value")
        ax.set_ylabel(x_label or "Category")

        if show_values:
            for i, value in enumerate(values):
                ax.text(value, i, f" {value:,.2f}", va="center", ha="left", fontsize=9)
    else:
        bars = ax.bar(labels, values, color=colors[: len(labels)])
        ax.set_xlabel(x_label or "Category")
        ax.set_ylabel(y_label or "Value")

        if show_values:
            for bar in bars:
                height = bar.get_height()
                ax.text(
                    bar.get_x() + bar.get_width() / 2.0,
                    height,
                    f"{height:,.2f}",
                    ha="center",
                    va="bottom",
                    fontsize=9,
                )

        # Rotate labels if they're long
        if any(len(str(label)) > 10 for label in labels):
            plt.xticks(rotation=45, ha="right")

    return None


def _create_matplotlib_line_chart(
    ax: plt.Axes, data: Any, colors: list[str], x_label: str | None, y_label: str | None
) -> None | dict[str, Any]:
    """Create Matplotlib line chart (single or multi-series)."""
    if not isinstance(data, dict):
        return {"status": "error", "error": "Line chart requires dict data"}

    # Check if multi-series
    if data and isinstance(next(iter(data.values())), list):
        # Multi-series
        for i, (series_name, values) in enumerate(data.items()):
            ax.plot(range(len(values)), values, marker="o", label=series_name, color=colors[i % len(colors)])
        ax.legend()
    else:
        # Single series
        labels = list(data.keys())
        values = list(data.values())
        ax.plot(labels, values, marker="o", color=colors[0], linewidth=2, markersize=8)

    ax.set_xlabel(x_label or "X")
    ax.set_ylabel(y_label or "Y")
    ax.grid(True, alpha=0.3)

    return None


def _create_matplotlib_pie_chart(
    ax: plt.Axes, data: Any, colors: list[str], sort_values: bool, sort_descending: bool, show_values: bool
) -> None | dict[str, Any]:
    """Create Matplotlib pie chart."""
    if not isinstance(data, dict):
        return {"status": "error", "error": "Pie chart requires dict data"}

    # Sort if requested
    if sort_values:
        data = dict(sorted(data.items(), key=lambda x: x[1], reverse=sort_descending))

    labels = list(data.keys())
    values = list(data.values())

    _wedges, texts, autotexts = ax.pie(
        values,
        labels=labels,
        colors=colors[: len(labels)],
        autopct="%1.1f%%" if show_values else None,
        startangle=90,
    )

    # Improve text visibility
    for text in texts:
        text.set_fontsize(10)
    if show_values:
        for autotext in autotexts:
            autotext.set_color("white")
            autotext.set_fontsize(9)
            autotext.set_weight("bold")

    ax.axis("equal")

    return None


def _create_matplotlib_scatter_chart(
    ax: plt.Axes, data: Any, colors: list[str], x_label: str | None, y_label: str | None
) -> None | dict[str, Any]:
    """Create Matplotlib scatter plot."""
    if not isinstance(data, list):
        return {"status": "error", "error": "Scatter plot requires list of dicts"}

    x_vals = [item.get("x", 0) for item in data]
    y_vals = [item.get("y", 0) for item in data]

    ax.scatter(x_vals, y_vals, color=colors[0], s=100, alpha=0.6, edgecolors="black", linewidth=1)
    ax.set_xlabel(x_label or "X")
    ax.set_ylabel(y_label or "Y")
    ax.grid(True, alpha=0.3)

    return None


def _create_matplotlib_heatmap_chart(
    ax: plt.Axes, data: Any, color_scheme: str, x_label: str | None, y_label: str | None, show_values: bool
) -> None | dict[str, Any]:
    """Create Matplotlib heatmap."""
    if isinstance(data, dict) and all(isinstance(v, dict) for v in data.values()):
        row_labels = list(data.keys())
        col_labels = list(next(iter(data.values())).keys())
        z_values = [[data[row][col] for col in col_labels] for row in row_labels]
    else:
        return {"status": "error", "error": "Heatmap requires nested dict"}

    sns.heatmap(
        z_values,
        xticklabels=col_labels,
        yticklabels=row_labels,
        annot=show_values,
        fmt=".2f" if show_values else "",
        cmap=_get_matplotlib_colormap(color_scheme),
        ax=ax,
        cbar_kws={"label": y_label or "Value"},
    )
    ax.set_xlabel(x_label or "Column")
    ax.set_ylabel(y_label or "Row")

    return None


def _get_plotly_colors(scheme: str) -> list[str]:
    """Get Plotly color palette based on scheme."""
    color_schemes = {
        "default": [
            "#636EFA",
            "#EF553B",
            "#00CC96",
            "#AB63FA",
            "#FFA15A",
            "#19D3F3",
            "#FF6692",
            "#B6E880",
            "#FF97FF",
            "#FECB52",
        ],
        "pastel": [
            "#FFB3BA",
            "#BAFFC9",
            "#BAE1FF",
            "#FFFFBA",
            "#FFD9BA",
            "#E0BBE4",
            "#957DAD",
            "#D291BC",
            "#FEC8D8",
            "#FFDFD3",
        ],
        "bold": [
            "#E63946",
            "#F1FAEE",
            "#A8DADC",
            "#457B9D",
            "#1D3557",
            "#2A9D8F",
            "#E9C46A",
            "#F4A261",
            "#E76F51",
            "#264653",
        ],
    }
    return color_schemes.get(scheme, color_schemes["default"])


def _get_plotly_colorscale(scheme: str) -> str:
    """Get Plotly colorscale for heatmaps."""
    colorscales = {
        "default": "Viridis",
        "viridis": "Viridis",
        "plasma": "Plasma",
        "inferno": "Inferno",
        "magma": "Magma",
        "cividis": "Cividis",
        "pastel": "Pastel",
        "bold": "RdBu",
    }
    return colorscales.get(scheme, "Viridis")


def _get_matplotlib_colors(scheme: str) -> list[str]:
    """Get Matplotlib color palette based on scheme."""
    palettes = {
        "default": sns.color_palette("husl", 10),
        "viridis": sns.color_palette("viridis", 10),
        "plasma": sns.color_palette("plasma", 10),
        "inferno": sns.color_palette("inferno", 10),
        "magma": sns.color_palette("magma", 10),
        "cividis": sns.color_palette("cividis", 10),
        "pastel": sns.color_palette("pastel", 10),
        "bold": sns.color_palette("bright", 10),
    }
    palette = palettes.get(scheme, palettes["default"])
    return [f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}" for r, g, b in palette]


def _get_matplotlib_colormap(scheme: str) -> str:
    """Get Matplotlib colormap for heatmaps."""
    colormaps = {
        "default": "viridis",
        "viridis": "viridis",
        "plasma": "plasma",
        "inferno": "inferno",
        "magma": "magma",
        "cividis": "cividis",
        "pastel": "Pastel1",
        "bold": "RdYlBu",
    }
    return colormaps.get(scheme, "viridis")
