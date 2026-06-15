from __future__ import annotations

import json as _json
from pathlib import Path

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from pipeline import run_pipeline

app     = typer.Typer(help="InsightDrop – sales analytics pipeline")
console = Console()

# ── display ───────────────────────────────────────────────────────

def _print_analytics(analytics: dict):
    kpis   = analytics["kpis"]
    charts = analytics["charts"]
    meta   = analytics["meta"]

    console.print(Panel(
        f"[dim]Period : {meta['date_range']['start']} → {meta['date_range']['end']}\n"
        f"Rows   : {meta['rows_processed']:,} orders processed[/]",
        title="[bold magenta]InsightDrop Report[/]",
        border_style="magenta",
    ))

    # KPIs
    kpi = Table(box=box.ROUNDED, border_style="magenta", show_header=False, padding=(0, 2))
    kpi.add_column(style="dim",       min_width=20)
    kpi.add_column(style="bold cyan", min_width=18)
    kpi.add_row("Total Revenue",   f"${kpis['total_revenue']:,.2f}")
    kpi.add_row("Total Profit",    f"${kpis['total_profit']:,.2f}")
    kpi.add_row("Total Orders",    f"{kpis['total_orders']:,}")
    kpi.add_row("Avg Order Value", f"${kpis['avg_order_value']:,.2f}")
    kpi.add_row("Profit Margin",   f"{kpis['profit_margin_pct']:.2f}%")
    console.print("\n[bold]Key Performance Indicators[/]")
    console.print(kpi)

    # Monthly Sales
    t = Table("Month", "Revenue", "Orders", box=box.SIMPLE_HEAD, border_style="dim")
    for r in charts["monthly_sales"][-6:]:
        t.add_row(r["month"], f"${r['revenue']:,.2f}", str(r["orders"]))
    console.print("\n[bold]Monthly Sales (last 6)[/]")
    console.print(t)

    # Top Products
    t = Table("Product", "Revenue", "Qty", box=box.SIMPLE_HEAD, border_style="dim")
    for r in charts["top_products"][:5]:
        t.add_row(r["product"], f"${r['revenue']:,.2f}", f"{int(r['quantity']):,}")
    console.print("\n[bold]Top 5 Products[/]")
    console.print(t)

    # Region Sales
    t = Table("Region", "Revenue", "Orders", box=box.SIMPLE_HEAD, border_style="dim")
    for r in charts["region_sales"]:
        t.add_row(r["region"], f"${r['revenue']:,.2f}", str(r["orders"]))
    console.print("\n[bold]Sales by Region[/]")
    console.print(t)

    # Category Sales
    t = Table("Category", "Revenue", "Profit", "Orders", box=box.SIMPLE_HEAD, border_style="dim")
    for r in charts["category_sales"]:
        t.add_row(r["category"], f"${r['revenue']:,.2f}", f"${r['profit']:,.2f}", str(r["orders"]))
    console.print("\n[bold]Sales by Category[/]")
    console.print(t)


# ── command ───────────────────────────────────────────────────────

@app.command()
def analyze(
    file: str  = typer.Argument(...,   help="Path to CSV or Excel file"),
    json: bool = typer.Option(False, "--json", help="Output raw JSON"),
):
    """Analyze a CSV/XLSX file and print results to terminal."""
    path = Path(file)
    if not path.exists():
        console.print(f"[bold red]✗  File not found: {path}[/]")
        raise typer.Exit(1)

    with console.status(f"[dim]Loading {path.name}…[/]"):
        try:
            analytics = run_pipeline(path, path.name)
        except ValueError as e:
            console.print(f"[bold red]✗  {e}[/]")
            raise typer.Exit(1)

    if json:
        console.print_json(_json.dumps(analytics))
    else:
        _print_analytics(analytics)


if __name__ == "__main__":
    app()