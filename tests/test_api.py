import main
from src import MovieStorage


def upload(client, content, filename="movies.csv"):
    return client.post("/upload", files={"file": (filename, content, "text/csv")})


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_upload_sample(client, sample_csv):
    response = upload(client, sample_csv, "sample_movies.csv")
    assert response.status_code == 200
    assert response.json() == {
        "filename": "sample_movies.csv",
        "rows": 20,
        "columns": 4,
        "column_names": ["title", "release_year", "rating", "genre"],
    }


def test_upload_rejects_non_csv(client):
    response = upload(client, b"hello", "notes.txt")
    assert response.status_code == 400


def test_upload_rejects_wrong_columns(client):
    response = upload(client, b"name,year\nMovie X,2020\n")
    assert response.status_code == 400


def test_upload_rejects_no_data_rows(client):
    response = upload(client, b"title,release_year,rating,genre\n")
    assert response.status_code == 400


def test_reupload_replaces_collection(uploaded_client, sample_csv):
    upload(uploaded_client, sample_csv, "sample_movies.csv")
    body = uploaded_client.get("/movies", params={"limit": 1}).json()
    assert body["total_rows"] == 20
    assert body["data"][0]["id"] == 1


def test_get_movies_empty(client):
    response = client.get("/movies")
    assert response.status_code == 200
    assert response.json() == {"data": [], "total_rows": 0}


def test_get_movies_limit(uploaded_client):
    body = uploaded_client.get("/movies", params={"limit": 2}).json()
    assert body["total_rows"] == 20
    assert body["data"] == [
        {"id": 1, "title": "Movie A", "release_year": 2020,
            "rating": 8.0, "genre": "Drama"},
        {"id": 2, "title": "Movie B", "release_year": 2021,
            "rating": 8.5, "genre": "Comedy"},
    ]


def test_data_persists_in_database(uploaded_client):
    # A brand-new MovieStorage pointing at the same file still sees the rows
    new_storage = MovieStorage(main.storage.db_path)
    assert new_storage.count_movies() == 20


def test_search_default_columns(uploaded_client):
    response = uploaded_client.get(
        "/movies/search", params={"min_rating": 8.5, "limit": 2})
    assert response.status_code == 200
    assert response.json() == [
        {"id": 4, "title": "Movie C"},
        {"id": 2, "title": "Movie B"},
    ]


def test_search_title_and_rating(uploaded_client):
    response = uploaded_client.get(
        "/movies/search",
        params={"columns": ["title", "rating"], "min_rating": 8.5, "limit": 2},
    )
    assert response.json() == [
        {"id": 4, "title": "Movie C", "rating": 9.0},
        {"id": 2, "title": "Movie B", "rating": 8.5},
    ]


def test_search_invalid_column(uploaded_client):
    response = uploaded_client.get(
        "/movies/search", params={"columns": ["budget"]})
    assert response.status_code == 400


def test_search_high_min_rating(uploaded_client):
    response = uploaded_client.get(
        "/movies/search", params={"columns": ["rating"], "min_rating": 10}
    )
    assert response.status_code == 200
    assert all(movie["rating"] >= 10 for movie in response.json())


def test_process_and_retrieve(uploaded_client, processing_body):
    response = uploaded_client.post("/movies/process", json=processing_body)
    assert response.status_code == 200

    body = response.json()
    assert "id" not in body
    assert body["validation_rows_removed"] >= 0
    assert "cleaning_report" in body

    # The processed rows were saved back to SQLite
    response = uploaded_client.get("/movies")
    assert response.status_code == 200
    assert response.json()[
        "total_rows"] == body["cleaning_report"]["rows_after"]


def test_process_with_no_movies(client, processing_body):
    response = client.post("/movies/process", json=processing_body)
    assert response.status_code == 400
