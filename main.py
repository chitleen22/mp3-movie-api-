import io
import logging
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, File, HTTPException, Query, UploadFile

from data_pipeline import create_cleaning_report, process_data, validate_dataframe
from src import (
    HealthResponse,
    MovieDataResponse,
    MovieProcessingReport,
    MovieStorage,
    MovieUploadInfo,
    ProcessConfig,
    log_requests,
    setup_logging,
)
from src.storage import MOVIE_COLUMNS


setup_logging(verbose=True)
logger = logging.getLogger(__name__)

app = FastAPI(title="Data Processing API", version="1.0.0")
app.middleware("http")(log_requests)
storage = MovieStorage()


@app.get("/health", response_model=HealthResponse)
def health_check():
    """Return the application status and version."""
    return HealthResponse(status="ok", version=app.version)


@app.post("/upload", response_model=MovieUploadInfo)
async def upload_movies(file: UploadFile = File(...)):
    """Read a CSV upload and replace the stored movie collection."""
    suffix = Path(file.filename or "").suffix.lower()
    if suffix != ".csv":
        logger.warning("Unsupported file format: %s", suffix or "(none)")
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format '{suffix}'. Please upload a .csv file.",
        )

    contents = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(contents))
    except pd.errors.EmptyDataError:
        logger.warning("Empty CSV upload: %s", file.filename)
        raise HTTPException(status_code=400, detail="The CSV file is empty.")
    except (pd.errors.ParserError, UnicodeDecodeError) as e:
        logger.warning("Could not parse CSV %s: %s", file.filename, e)
        raise HTTPException(
            status_code=400,
            detail="Could not read the CSV file. Check that it is valid, UTF-8 encoded CSV.",
        )

    if set(df.columns) != set(MOVIE_COLUMNS) or len(df.columns) != len(MOVIE_COLUMNS):
        logger.warning("Wrong columns in %s: %s",
                       file.filename, list(df.columns))
        raise HTTPException(
            status_code=400,
            detail=f"CSV must have exactly these columns: {MOVIE_COLUMNS}",
        )
    if df.empty:
        logger.warning("CSV has no data rows: %s", file.filename)
        raise HTTPException(
            status_code=400, detail="The CSV file has no data rows.")

    df = df[MOVIE_COLUMNS]
    storage.save(df)
    logger.info("Uploaded movies: filename=%s, rows=%d",
                file.filename, len(df))

    return MovieUploadInfo(
        filename=file.filename,
        rows=len(df),
        columns=len(df.columns),
        column_names=list(df.columns),
    )


@app.get("/movies", response_model=MovieDataResponse)
def get_movies(limit: int = Query(default=100, ge=1)):
    """Return up to limit stored movies and the total count."""
    data = storage.select_columns(list(MOVIE_COLUMNS), limit)
    total = storage.count_movies()
    logger.info("Retrieved movies: returned_rows=%d, total_rows=%d",
                len(data), total)
    return {"data": data, "total_rows": total}


@app.get("/movies/search", response_model=list[dict])
def query_movies(
    columns: list[str] = Query(default=["title"]),
    min_rating: float = Query(default=0, ge=0, le=10),
    limit: int = Query(default=100, ge=1),
):
    """Return selected fields from movies with rating >= min_rating."""
    try:
        results = storage.query_movies(columns, min_rating, limit)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    logger.info(
        "Queried movies: columns=%s, min_rating=%s, returned_rows=%d",
        columns, min_rating, len(results),
    )
    return results


@app.post("/movies/process", response_model=MovieProcessingReport)
def process_movies(config: ProcessConfig):
    """Validate and process the stored movies using MP1 functions."""
    # 1. Retrieve the stored movies; 400 if there are none
    df = storage.get()
    if df.empty:
        logger.warning("No movies stored to process")
        raise HTTPException(
            status_code=400, detail="No movies stored. Upload a CSV first.")

    # 2. Convert request model to the dict structure MP1 expects
    config_dict = config.model_dump()
    validation = config_dict["validation"]

    # 3. Every numeric column must exist
    missing_cols = [c for c in validation["numeric_columns"]
                    if c not in df.columns]
    if missing_cols:
        logger.warning("Numeric columns not found: %s", missing_cols)
        raise HTTPException(
            status_code=400,
            detail=f"Numeric columns not found: {missing_cols}",
        )

    try:
        # 4. Validate
        validated = validate_dataframe(
            df,
            validation["required_columns"],
            validation["numeric_columns"],
        )
        validation_removed = len(df) - len(validated)

        # 5. Copy before processing so the report can compare before/after
        before = validated.copy()
        processed = process_data(validated, config_dict)

        # 6. Cleaning report
        report = create_cleaning_report(before, processed)
    except ValueError as error:
        logger.warning("Processing failed: %s", error)
        raise HTTPException(status_code=400, detail=str(error))

    # 7. Only replace storage once everything succeeded
    storage.save(processed)
    logger.info(
        "Processed movies: validation_removed=%d, rows_before=%d, rows_after=%d",
        validation_removed, len(before), len(processed),
    )

    return {
        "validation_rows_removed": validation_removed,
        "cleaning_report": report,
    }
