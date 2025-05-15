# tests/test_import_app.py

import pytest
import json
from werkzeug.security import generate_password_hash
from bson import ObjectId
import run
from datetime import datetime, timezone
datetime.now(timezone.utc)

# Use the Flask app from your entrypoint
app = run.app

@pytest.fixture
def client():
    # Activate testing mode
    flask_app = app
    flask_app.config['TESTING'] = True
    flask_app.config['WTF_CSRF_ENABLED'] = False
    return flask_app.test_client()

@pytest.fixture
def mongodb():
    # Shortcut to the test database
    return app.mongo.db

# Helper functions for auth

def login(client, email, password):
    return client.post(
        "/auth/login",
        data={"email": email, "password": password},
        follow_redirects=False
    )


def register_user(client, name, email, password, role="user"):
    return client.post(
        "/auth/register",
        data={"name": name, "email": email, "password": password, "role": role},
        follow_redirects=False
    )

# 1. Smoke-test app import

def test_import_app():
    assert hasattr(run, 'app'), "run.py must expose a Flask `app`"

# 2. Index page

def test_index_page(client):
    rv = client.get('/')
    assert rv.status_code == 200
    assert b'<html' in rv.data or b'welcome' in rv.data.lower()

# 3. Registration & duplicate handling

def test_register_and_duplicate(client, mongodb):
    db = mongodb
    db.users.delete_many({"email": "alice@example.com"})

    rv1 = register_user(client, "Alice", "alice@example.com", "Secret123!")
    assert rv1.status_code == 302

    rv2 = register_user(client, "Alice", "alice@example.com", "Secret123!")
    # duplicate should still redirect/flash
    assert rv2.status_code == 302

# 4. Login with valid & invalid credentials

def test_login_and_invalid(client):
    rv = login(client, "alice@example.com", "Secret123!")
    assert rv.status_code == 302

    rv2 = login(client, "alice@example.com", "WrongPass")
    assert rv2.status_code in (204, 302)

# 5. Profile view, update, and delete

def test_profile_and_update_and_delete(client, mongodb):
    db = mongodb
    pw = "Secret123!"
    db.users.delete_many({"email": "bob@example.com"})
    db.users.insert_one({
        "name": "Bob",
        "email": "bob@example.com",
        "password": generate_password_hash(pw),
        "role": "user"
    })

    # Log in
    login(client, "bob@example.com", pw)

    # View profile
    rv = client.get('/profile')
    assert rv.status_code == 200
    assert b'bob@example.com' in rv.data.lower()

    # Update profile (only name)
    rv2 = client.post(
        '/update_profile',
        data={"name": "Bobby", "password": ""},
        follow_redirects=False
    )
    assert rv2.status_code == 302

    # Confirm update in DB
    user = db.users.find_one({"email": "bob@example.com"})
    assert user['name'] == 'Bobby'

    # Delete account
    rv3 = client.post('/delete_account', follow_redirects=False)
    assert rv3.status_code == 302
    assert db.users.find_one({"email": "bob@example.com"}) is None

# 6. Reports listing & detail

def test_list_reports_access(client):
    rv = client.get('/reports')
    assert rv.status_code == 200


def test_report_detail_not_found(client):
    rv = client.get('/report/000000000000000000000000')
    assert rv.status_code == 404

# 7. Create, list, and delete own reports

def test_create_and_list_my_reports(client, mongodb):
    db = mongodb
    pw = "CarolPass1"
    db.users.delete_many({"email": "carol@example.com"})
    db.users.insert_one({
        "name": "Carol",
        "email": "carol@example.com",
        "password": generate_password_hash(pw),
        "role": "user"
    })

    # Log in and set session
    login(client, "carol@example.com", pw)
    with client.session_transaction() as sess:
        sess['user'] = 'carol@example.com'
        sess['role'] = 'user'

    # Create a report
    rv = client.post(
        '/report_issue',
        data={
            'description': 'Broken lamp',
            'city_street': 'Main St',
            'category': 'Electrical',
            'lat': '10.0',
            'lng': '20.0'
        },
        follow_redirects=False
    )
    assert rv.status_code == 302

    # List my_reports
    rv2 = client.get('/my_reports')
    assert rv2.status_code == 200
    assert b'broken lamp' in rv2.data.lower()


def test_delete_issue(client, mongodb):
    db = mongodb
    # Attempt deleting nonexistent issue
    with client.session_transaction() as sess:
        sess['user'] = 'carol@example.com'
        sess['role'] = 'user'
    fake_id = '000000000000000000000000'
    rv = client.post(f'/delete_issue/{fake_id}', follow_redirects=False)
    assert rv.status_code == 302

    # Insert and delete a real issue
    res = db.issues.insert_one({
        'reporter_email': 'carol@example.com',
        'description': 'To delete',
        'city_street': 'X',
        'category': 'Test',
        'location': {'lat': 0, 'lng': 0},
        'image_path': None,
        'status': 'pending',
        'assigned_to': None,
        'timestamp': datetime.utcnow().isoformat()
    })
    issue_id = str(res.inserted_id)
    rv2 = client.post(f'/delete_issue/{issue_id}', follow_redirects=False)
    assert rv2.status_code == 302
    assert db.issues.find_one({'_id': ObjectId(issue_id)}) is None
