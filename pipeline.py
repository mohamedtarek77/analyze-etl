"""
InsightDrop – ETL Pipeline (standalone, no FastAPI)
Reusable core: load → clean → aggregate → return analytics dict + cleaned DataFrame.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Union

import pandas as pd

# ── Column alias map ──────────────────────────────────────────────────────────
COLUMN_ALIASES: dict[str, list[str]] = {
    "order_id":     ["orderid", "order id", "id"],
    "product_name": ["productname", "product name", "product"],
    "category":     ["cat"],
    "quantity":     ["qty", "units"],
    "price":        ["unit_price", "unit price", "selling_price", "sale_price"],
    "cost":         ["unit_cost", "unit cost"],
    "order_date":   ["date", "sale_date", "sale date", "orderdate"],
    "region":       ["area", "zone"],
}

REQUIRED_COLUMNS = list(COLUMN_ALIASES.keys())


# ── helpers ───────────────────────────────────────────────────────────────────

def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename aliased columns to canonical names."""
    rename_map: dict[str, str] = {}
    lower_cols = {c.lower().strip(): c for c in df.columns}
    for canonical, aliases in COLUMN_ALIASES.items():
        if canonical in lower_cols:
            rename_map[lower_cols[canonical]] = canonical
        else:
            for alias in aliases:
                if alias in lower_cols:
                    rename_map[lower_cols[alias]] = canonical
                    break
    return df.rename(columns=rename_map)


def _load_file(source: Union[str, Path, BytesIO], filename: str) -> pd.DataFrame:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext == "csv":
        return pd.read_csv(source)
    elif ext in ("xlsx", "xls"):
        return pd.read_excel(source)
    else:
        raise ValueError(f"Unsupported file type '.{ext}'. Allowed: csv, xlsx, xls")


def _validate_columns(df: pd.DataFrame) -> None:
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            f"Missing required columns: {missing}\n"
            f"Available columns: {list(df.columns)}\n"
            f"Check the README for column aliases."
        )


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = df.columns.str.lower().str.strip()
    df = _normalise_columns(df)
    _validate_columns(df)

    # drop fully empty rows
    df.dropna(how="all", inplace=True)
    if df.empty:
        raise ValueError("File is empty after removing blank rows.")

    # numeric coercion
    for col in ("quantity", "price", "cost"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # drop rows with invalid numerics
    df.dropna(subset=["quantity", "price", "cost"], inplace=True)
    df = df[df["quantity"] > 0]
    df = df[df["price"] > 0]
    df = df[df["cost"] >= 0]

    # date parsing
    df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce", dayfirst=False)
    df.dropna(subset=["order_date"], inplace=True)

    # derived columns
    df["revenue"] = df["quantity"] * df["price"]
    df["profit"]  = df["quantity"] * (df["price"] - df["cost"])
    df["order_month"] = df["order_date"].dt.to_period("M").astype(str)
    df["order_year"]  = df["order_date"].dt.year

    # tidy text columns
    for col in ("product_name", "category", "region"):
        df[col] = df[col].astype(str).str.strip().str.title()

    return df.reset_index(drop=True)


# ── public API ────────────────────────────────────────────────────────────────

def run_pipeline(source: Union[str, Path, BytesIO], filename: str) -> dict:
    """Return analytics dict only."""
    df = _load_file(source, filename)
    df = _clean(df)
    return _build_analytics(df)


def run_pipeline_full(source: Union[str, Path, BytesIO], filename: str) -> tuple[dict, pd.DataFrame]:
    """Return (analytics dict, cleaned DataFrame)."""
    df = _load_file(source, filename)
    df = _clean(df)
    return _build_analytics(df), df


def _build_analytics(df: pd.DataFrame) -> dict:
    total_revenue = round(df["revenue"].sum(), 2)
    total_profit  = round(df["profit"].sum(), 2)
    total_orders  = int(df["order_id"].nunique()) if "order_id" in df.columns else len(df)
    avg_order_val = round(total_revenue / max(total_orders, 1), 2)
    profit_margin = round(total_profit / total_revenue * 100, 2) if total_revenue else 0.0

    # Monthly sales
    monthly = (
        df.groupby("order_month")
          .agg(revenue=("revenue", "sum"), orders=("order_id", "nunique"))
          .reset_index()
          .rename(columns={"order_month": "month"})
          .sort_values("month")
    )
    monthly["revenue"] = monthly["revenue"].round(2)

    # Top 10 products
    top_products = (
        df.groupby("product_name")
          .agg(revenue=("revenue", "sum"), quantity=("quantity", "sum"))
          .reset_index()
          .rename(columns={"product_name": "product"})
          .sort_values("revenue", ascending=False)
          .head(10)
    )
    top_products["revenue"] = top_products["revenue"].round(2)

    # Region sales
    region_sales = (
        df.groupby("region")
          .agg(revenue=("revenue", "sum"), orders=("order_id", "nunique"))
          .reset_index()
          .sort_values("revenue", ascending=False)
    )
    region_sales["revenue"] = region_sales["revenue"].round(2)

    # Category sales
    category_sales = (
        df.groupby("category")
          .agg(revenue=("revenue", "sum"), profit=("profit", "sum"), orders=("order_id", "nunique"))
          .reset_index()
          .sort_values("revenue", ascending=False)
    )
    category_sales["revenue"] = category_sales["revenue"].round(2)
    category_sales["profit"]  = category_sales["profit"].round(2)

    return {
        "kpis": {
            "total_revenue":      total_revenue,
            "total_profit":       total_profit,
            "total_orders":       total_orders,
            "avg_order_value":    avg_order_val,
            "profit_margin_pct":  profit_margin,
        },
        "charts": {
            "monthly_sales":  monthly.to_dict(orient="records"),
            "top_products":   top_products.to_dict(orient="records"),
            "region_sales":   region_sales.to_dict(orient="records"),
            "category_sales": category_sales.to_dict(orient="records"),
        },
        "meta": {
            "rows_processed": len(df),
            "date_range": {
                "start": str(df["order_date"].min().date()),
                "end":   str(df["order_date"].max().date()),
            },
        },
    }