# tests/test_import_app.py

import pytest
import json

# 1. Smoke-test that your app imports and exposes the Flask app
def test_import_app():
    import run
    assert hasattr(run, "app")

@pytest.fixture
def client():
    # Put Flask into testing mode
    from run import app as flask_app
    flask_app.config['TESTING'] = True
    flask_app.config['WTF_CSRF_ENABLED'] = False
    # (Optional) point at a test DB:
    # flask_app.config['MONGO_URI'] = "mongodb://localhost:27017/test_db"
    return flask_app.test_client()

# 2. Homepage / index
def test_index_page(client):
    rv = client.get("/")
    assert rv.status_code == 200
    assert b"<html" in rv.data or b"welcome" in rv.data.lower() or b"login" in rv.data.lower()

# 3. Registration endpoint
def test_register_user(client):
    payload = {
        "username": "testuser1",
        "password": "Password123!",
        "role": "user",
        "first_name": "Test",
        "last_name": "User",
        "id_number": "987654321",
        "credit_card_number": "4111111111111111",
        "valid_date": "12/25",
        "cvc": "123"
    }
    rv = client.post(
        "/api/register",
        data=json.dumps(payload),
        content_type="application/json"
    )
    assert rv.status_code in (200, 201)
    data = rv.get_json()
    assert any(k in data for k in ("success", "message"))

# 4. Login with valid credentials
def test_login_user(client):
    creds = {"username": "testuser1", "password": "Password123!"}
    rv = client.post(
        "/api/login",
        data=json.dumps(creds),
        content_type="application/json"
    )
    assert rv.status_code == 200
    data = rv.get_json()
    assert any(k in data for k in ("token", "success"))

# 5. Login with invalid credentials
def test_login_invalid(client):
    rv = client.post(
        "/api/login",
        data=json.dumps({"username": "nope", "password": "wrong"}),
        content_type="application/json"
    )
    assert rv.status_code in (400, 401)
    data = rv.get_json()
    assert "error" in data

# 6. List reports (public or protected based on your app)
def test_list_reports_access(client):
    rv = client.get("/reports")
    assert rv.status_code == 200

# 7. Detail for a non-existent report should 404 (or render "Not Found")
def test_report_detail_not_found(client):
    rv = client.get("/report/000000000000000000000000")
    assert rv.status_code in (404, 200)
    if rv.status_code == 200:
        assert b"not found" in rv.data.lower() or b"404" in rv.data

# --- STUBS: uncomment & fill in once you know the exact URLs & payloads ---

# def test_create_report(client):
#     # log in, then POST to /report/new
#     pass

# def test_update_report(client):
#     # log in, then PUT/PATCH to /report/<id>
#     pass

# def test_delete_report(client):
#     # log in, then DELETE /report/<id>
#     pass
