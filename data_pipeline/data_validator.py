import logging
import pandas as pd

logger = logging.getLogger(__name__)


def validate_dataframe(df, required_columns, numeric_columns):
    """Validate the DataFrame and return valid data.
    required_columns: a list of column names that must exist.
    numeric_columns: a list of column names whose values should be numeric.
    """
    before = len(df)

    for col in required_columns:
        if col not in df.columns:
            logger.error(f"Required column not found: {col}")
            raise ValueError(f"Missing required column: {col}")

    for col in required_columns:
        if col not in df.columns:
            logger.error(f"Required column not found: {col}")
            raise ValueError(f"Missing required column: {col}")

    for col in numeric_columns:
        invalid_rows = []
        for i, value in df[col].items():
            if pd.notna(value):
                try:
                    float(value)
                except ValueError:
                    logger.warning(
                        f"Invalid numeric value in column {col}: {value}")
                    invalid_rows.append(i)

        if invalid_rows:
            logger.warning(
                f"Removed {len(invalid_rows)} rows with invalid numeric values in {col}")
            df = df.drop(index=invalid_rows)

        df[col] = pd.to_numeric(df[col])

    after = len(df)
    logger.debug(f"Validation: {before} -> {after} rows")

    return df
