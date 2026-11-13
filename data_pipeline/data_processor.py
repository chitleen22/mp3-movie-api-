# data_processor.py
import logging
import pandas as pd

logger = logging.getLogger(__name__)


def remove_duplicates(df):
    """Remove duplicate rows."""
    before = len(df)
    df = df.drop_duplicates()
    removed = before - len(df)
    logger.debug(f"remove_duplicates: {before} -> {len(df)} rows")
    return df


def handle_missing(df, axis="rows"):
    """Drop rows or columns containing missing values."""
    if axis == "rows":
        before = len(df)
        df = df.dropna(axis=0)
        logger.debug(f"handle_missing: {before} -> {len(df)} rows")
    elif axis == "columns":
        before = df.shape[1]
        df = df.dropna(axis=1)
        logger.debug(f"handle_missing: {before} -> {df.shape[1]} columns")
    else:
        logger.error(f"Unsupported axis: {axis}")
        raise ValueError(f"Unsupported axis: {axis}")
    return df


def remove_outliers(df, columns, method, threshold):
    """Remove outliers from the specified numeric columns."""
    if method not in ("iqr", "zscore"):
        logger.error(f"unsupported outlier method: {method}")
        raise ValueError(f"Unsupported outlier method: {method}")

    for col in columns:
        if col not in df.columns:
            logger.warning(f"Column not found: {col}")
            continue

        if not pd.api.types.is_numeric_dtype(df[col]):
            logger.warning(f"column not numeric: {col}")
            continue
        before = len(df)
        if method == "iqr":
            q1 = df[col].quantile(0.25)
            q3 = df[col].quantile(0.75)
            iqr = q3 - q1
            lower = q1 - threshold * iqr
            upper = q3 + threshold * iqr
            df = df[(df[col] >= lower) & (df[col] <= upper)]
            logger.debug(
                f"[{col}: lower={lower}, upper={upper}, removed={before - len(df)}]")

        elif method == "zscore":
            mean = df[col].mean()
            std = df[col].std()
            z_scores = (df[col] - mean) / std
            df = df[z_scores.abs() <= threshold]
            logger.debug(
                f"{col}: mean={mean}, std={std}, removed={before - len(df)}")
    return df


def process_data(df, config):
    """Apply the processing steps enabled in the configuration."""
    processing = config.get("processing", {})

    if processing.get("remove_duplicates"):
        df = remove_duplicates(df)

    missing = processing.get("missing", {})
    if missing.get("enabled"):
        df = handle_missing(df, axis=missing.get("axis", "rows"))

    outliers = processing.get("outliers", {})
    if outliers.get("enabled"):
        df = remove_outliers(
            df,
            columns=outliers.get("columns", []),
            method=outliers.get("method"),
            threshold=outliers.get("threshold")
        )

    return df


def create_cleaning_report(df_before, df_after):
    """Return a dictionary summarizing the cleaning results."""
    return {
        "rows_before": len(df_before),
        "rows_after": len(df_after),
        "rows_removed": len(df_before) - len(df_after),
        "columns_before": df_before.shape[1],
        "columns_after": df_after.shape[1],
        "columns_removed": df_before.shape[1] - df_after.shape[1]
    }
