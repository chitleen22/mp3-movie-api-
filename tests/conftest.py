from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import main
from src import MovieStorage

SAMPLE_CSV = Path(__file__).parent.parent / "fixtures" / "sample_movies.csv"


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Test client that uses a temporary database, so tests never touch data/movies.db."""
    monkeypatch.setattr(main, "storage", MovieStorage(tmp_path / "test.db"))
    return TestClient(main.app)


@pytest.fixture
def sample_csv():
    return SAMPLE_CSV.read_bytes()


@pytest.fixture
def uploaded_client(client, sample_csv):
    """Client that already has the sample movies uploaded."""
    response = client.post(
        "/upload", files={"file": ("sample_movies.csv", sample_csv, "text/csv")}
    )
    assert response.status_code == 200
    return client


@pytest.fixture
def processing_body():
    return {
        "validation": {
            "required_columns": ["title", "rating"],
            "numeric_columns": ["rating"],
        },
        "processing": {
            "remove_duplicates": True,
            "missing": {
                "enabled": True,
                "axis": "rows",
            },
            "outliers": {
                "enabled": False,
                "columns": [],
                "method": "iqr",
                "threshold": 1.5,
            },
        },
    }
