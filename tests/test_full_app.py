import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from bson import ObjectId

import run
from run import app

# ------------------------------------------------------------------
# FIXTURES
# ------------------------------------------------------------------
@pytest.fixture
def client():
    app.config.update({
        'TESTING': True,
        'WTF_CSRF_ENABLED': False,
    })
    return app.test_client()

@pytest.fixture
def mongodb():
    return app.mongo.db

# ------------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------------
def register_user(client, name, email, password, role="user"):
    return client.post("/auth/register", data={"name": name, "email": email, "password": password, "role": role}, follow_redirects=False)

def login(client, email, password):
    return client.post("/auth/login", data={"email": email, "password": password}, follow_redirects=False)

def create_user(db, email, password, role="user"):
    db.users.delete_many({"email": email})
    db.users.insert_one({
        "name":     email.split("@")[0].capitalize(),
        "email":    email,
        "password": generate_password_hash(password),
        "role":     role
    })

def create_job(db, reporter_email):
    db.issues.delete_many({"reporter_email": reporter_email})
    res = db.issues.insert_one({
        "reporter_email": reporter_email,
        "description":    f"Test task for {reporter_email}",
        "status":         "pending",
        "assigned_to":    None,
        "published":      False,
        "timestamp":      datetime.now(timezone.utc).isoformat()
    })
    return str(res.inserted_id)

# ------------------------------------------------------------------
# ADMIN EDIT USER TESTS
# ------------------------------------------------------------------
ADMIN_EMAIL = "admin@cityfix.com"
CRED_PW = "Admin123!"

def test_admin_edit_user_role(client, mongodb):
    db = mongodb
    email = "editme@example.com"
    pw = "EditMe123!"
    db.users.delete_many({"email": email})
    uid = db.users.insert_one({
        "name": "Edit Me",
        "email": email,
        "password": generate_password_hash(pw),
        "role": "user"
    }).inserted_id

    create_user(db, ADMIN_EMAIL, CRED_PW, role="admin")
    login(client, ADMIN_EMAIL, CRED_PW)
    with client.session_transaction() as sess:
        sess["user"] = ADMIN_EMAIL
        sess["role"] = "admin"

    rv = client.post("/admin/users/", data={"user_id": str(uid), "role": "maintenance"}, follow_redirects=False)
    assert rv.status_code == 302
    u = db.users.find_one({"_id": uid})
    assert u["role"] == "maintenance"

def test_admin_edit_user_password(client, mongodb):
    db = mongodb
    email = "passchange@example.com"
    old_pw = "OldPass123!"
    new_pw = "NewPass321!"
    db.users.delete_many({"email": email})
    uid = db.users.insert_one({
        "name": "Pass Change",
        "email": email,
        "password": generate_password_hash(old_pw),
        "role": "user"
    }).inserted_id

    create_user(db, ADMIN_EMAIL, CRED_PW, role="admin")
    login(client, ADMIN_EMAIL, CRED_PW)
    with client.session_transaction() as sess:
        sess["user"] = ADMIN_EMAIL
        sess["role"] = "admin"

    rv = client.post("/admin/users/", data={"user_id": str(uid), "password": new_pw}, follow_redirects=False)
    assert rv.status_code == 302
    u = db.users.find_one({"_id": uid})
    assert check_password_hash(u["password"], new_pw)

# ------------------------------------------------------------------
# MAINTENANCE TESTS
# ------------------------------------------------------------------
def test_maintenance_dashboard_access(client, mongodb):
    db = mongodb
    email, pw = "maint@example.com", "Maint123!"
    create_user(db, email, pw, role="maintenance")
    login(client, email, pw)
    with client.session_transaction() as sess:
        sess['user'] = email
        sess['role'] = 'maintenance'
    rv = client.get("/maintenance/dashboard")
    assert rv.status_code == 200
    assert b"Assigned Issues" in rv.data or b"See what happens" in rv.data

def test_maintenance_update_status(client, mongodb):
    db = mongodb
    email, pw = "maint2@example.com", "Maint123!"
    create_user(db, email, pw, role="maintenance")
    issue_id = create_job(db, "u@x.com")
    db.issues.update_one({"_id": ObjectId(issue_id)}, {"$set": {"assigned_to": email}})
    login(client, email, pw)
    with client.session_transaction() as sess:
        sess['user'] = email
        sess['role'] = 'maintenance'
    rv = client.post(f"/maintenance/update_status/{issue_id}", data={"status": "in progress"}, follow_redirects=False)
    assert rv.status_code == 302
    updated = db.issues.find_one({"_id": ObjectId(issue_id)})
    assert updated['status'] == "in progress"

# ------------------------------------------------------------------
# REPORT DETAIL PAGE
# ------------------------------------------------------------------
def test_report_detail_view(client, mongodb):
    db = mongodb
    issue_id = create_job(db, "u@x.com")
    rv = client.get(f"/report/{issue_id}")
    assert rv.status_code == 200
    assert b"Description of the Issue" in rv.data or b"Report" in rv.data
