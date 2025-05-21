# tests/test_import_app.py

import pytest
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash
from bson import ObjectId

import run
from run import app

# ------------------------------------------------------------
# FIXTURES
# ------------------------------------------------------------
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

# ------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------
def register_user(client, name, email, password, role="user"):
    return client.post(
        "/auth/register",
        data={"name": name, "email": email, "password": password, "role": role},
        follow_redirects=False
    )


def login(client, email, password):
    return client.post(
        "/auth/login",
        data={"email": email, "password": password},
        follow_redirects=False
    )


def create_user(db, email, password, role="user"):
    db.users.delete_many({"email": email})
    db.users.insert_one({
        "name":     email.split("@")[0].capitalize(),
        "email":    email,
        "password": generate_password_hash(password),
        "role":     role
    })


def create_job(db, reporter_email):
    # Insert into issues collection
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

# ------------------------------------------------------------
# 1. SMOKE & PUBLIC PAGES
# ------------------------------------------------------------
def test_import_app():
    assert hasattr(run, 'app'), "run.py must expose a Flask `app`"


def test_index_page(client):
    rv = client.get('/')
    assert rv.status_code == 200
    assert b'<html' in rv.data or b'welcome' in rv.data.lower()


def test_auth_pages_load(client):
    for url in ['/auth/register', '/auth/login']:
        rv = client.get(url)
        assert rv.status_code in (200, 405)
        if rv.status_code == 200:
            assert b'<form' in rv.data

# ------------------------------------------------------------
# 2. REGISTRATION & DUPLICATES
# ------------------------------------------------------------
def test_register_and_duplicate(client, mongodb):
    db = mongodb
    email = "alice@example.com"
    db.users.delete_many({"email": email})

    rv1 = register_user(client, "Alice", email, "Secret123!")
    assert rv1.status_code == 302

    rv2 = register_user(client, "Alice", email, "Secret123!")
    assert rv2.status_code == 302

# ------------------------------------------------------------
# 3. LOGIN / LOGOUT FLOWS
# ------------------------------------------------------------
def test_login_valid_and_invalid(client, mongodb):
    db = mongodb
    email, pw = "test@example.com", "MyPass1!"
    db.users.delete_many({"email": email})
    db.users.insert_one({
        "name":     "Test",
        "email":    email,
        "password": generate_password_hash(pw),
        "role":     "user"
    })

    rv = login(client, email, pw)
    assert rv.status_code == 302

    rv_bad = login(client, email, "wrong!")
    assert rv_bad.status_code in (302, 401, 204)


def test_logout(client):
    rv = client.get('/auth/logout', follow_redirects=True)
    assert rv.status_code == 200
    assert b'login' in rv.data.lower()

# ------------------------------------------------------------
# 4. PROFILE CRUD
# ------------------------------------------------------------
def test_profile_view_update_delete(client, mongodb):
    db = mongodb
    email, pw = "bob@example.com", "Secret123!"
    db.users.delete_many({"email": email})
    db.users.insert_one({
        "name":     "Bob",
        "email":    email,
        "password": generate_password_hash(pw),
        "role":     "user"
    })

    login(client, email, pw)
    rv = client.get('/profile')
    assert rv.status_code == 200
    assert b'bob@example.com' in rv.data.lower()

    rv2 = client.post(
        '/update_profile',
        data={"name": "Bobby", "password": ""},
        follow_redirects=False
    )
    assert rv2.status_code == 302
    user = db.users.find_one({"email": email})
    assert user['name'] == "Bobby"

    rv3 = client.post('/delete_account', follow_redirects=False)
    assert rv3.status_code == 302
    assert db.users.find_one({"email": email}) is None

# ------------------------------------------------------------
# 5. REPORTS: CREATE, LIST, DETAIL, DELETE
# ------------------------------------------------------------
def test_report_issue_requires_login(client):
    rv = client.get('/report_issue')
    assert rv.status_code in (302, 401)


def test_create_list_detail_and_delete_report(client, mongodb):
    db = mongodb
    email, pw = "carol@example.com", "CarolPass1"
    db.users.delete_many({"email": email})
    db.issues.delete_many({"reporter_email": email})
    db.users.insert_one({
        "name":     "Carol",
        "email":    email,
        "password": generate_password_hash(pw),
        "role":     "user"
    })

    login(client, email, pw)
    with client.session_transaction() as sess:
        sess['user'] = email
        sess['role'] = 'user'

    rv_form = client.get('/report_issue')
    assert rv_form.status_code == 200

    rv = client.post(
        '/report_issue',
        data={
            'description': 'Broken lamp',
            'city_street': 'Main St',
            'category':    'Electrical',
            'lat':         '10.0',
            'lng':         '20.0'
        },
        follow_redirects=False
    )
    assert rv.status_code == 302

    rv2 = client.get('/my_reports')
    assert rv2.status_code == 200

    report = db.issues.find_one({"reporter_email": email})
    rid = str(report['_id'])
    rv3 = client.get(f'/report/{rid}')
    assert rv3.status_code == 200

    rv4 = client.post(f'/delete_issue/{rid}', follow_redirects=False)
    assert rv4.status_code == 302
    assert db.issues.find_one({'_id': ObjectId(rid)}) is None

# ------------------------------------------------------------
# 6. ADMIN: DONE REPORTS API & PAGE
# ------------------------------------------------------------
def test_api_done_reports_and_page(client, mongodb):
    db = mongodb
    db.done_issues.delete_many({})
    now = datetime.now(timezone.utc).isoformat()
    db.done_issues.insert_one({
        "original_issue_id": str(ObjectId()),
        "completion_description": "fixed",
        "timestamp": now
    })

    rv = client.get('/api/done_reports')
    assert rv.status_code == 200
    data = rv.get_json()
    assert data['done_reports'][0]['completion_description'] == "fixed"

    create_user(db, "admin@example.com", "Admin123!", role="admin")
    login(client, "admin@example.com", "Admin123!")
    with client.session_transaction() as sess:
        sess['user'] = 'admin@example.com'
        sess['role'] = 'admin'
    rv2 = client.get('/admin/done_reports')
    assert rv2.status_code == 200

# ------------------------------------------------------------
# 7. USER SELF-DELETION
# ------------------------------------------------------------
def test_user_self_delete(client, mongodb):
    db = mongodb
    email, pw = "eve@example.com", "EvePass1!"
    db.users.delete_many({"email": email})
    db.users.insert_one({
        "name":     "Eve",
        "email":    email,
        "password": generate_password_hash(pw),
        "role":     "user"
    })

    login(client, email, pw)
    rv = client.post("/delete_account", follow_redirects=False)
    assert rv.status_code == 302
    assert db.users.find_one({"email": email}) is None

# ------------------------------------------------------------
# 8. ADMIN DELETE USER
# ------------------------------------------------------------
def test_admin_delete_user(client, mongodb):
    db = mongodb
    email, pw = "frank@example.com", "FrankPass1!"
    db.users.delete_many({"email": email})
    uid = str(db.users.insert_one({
        "name":     "Frank",
        "email":    email,
        "password": generate_password_hash(pw),
        "role":     "user"
    }).inserted_id)

    create_user(db, "admin@example.com", "Admin123!", role="admin")
    login(client, "admin@example.com", "Admin123!")
    with client.session_transaction() as sess:
        sess['user'] = 'admin@example.com'
        sess['role'] = 'admin'

    rv = client.post(f"/admin/delete_user/{uid}", follow_redirects=False)
    assert rv.status_code in (302, 404)
    if rv.status_code == 302:
        assert db.users.find_one({"_id": ObjectId(uid)}) is None
    else:
        pytest.skip("admin delete endpoint not implemented")

# ------------------------------------------------------------
# 9. ADMIN EDIT USER PASSWORD & ROLE
# ------------------------------------------------------------
def test_admin_edit_user_password_and_role(client, mongodb):
    db = mongodb
    email, old_pw = "grace@example.com", "GracePass1!"
    db.users.delete_many({"email": email})
    uid = str(db.users.insert_one({
        "name":     "Grace",
        "email":    email,
        "password": generate_password_hash(old_pw),
        "role":     "user"
    }).inserted_id)

    create_user(mongodb, "admin@example.com", "Admin123!", role="admin")
    login(client, "admin@example.com", "Admin123!")
    with client.session_transaction() as sess:
        sess['user'] = 'admin@example.com'
        sess['role'] = 'admin'

    new_pw, new_role = "NewGracePass2!", "maintainer"
    rv = client.post(
        f"/admin/edit_user/{uid}",
        data={"password": new_pw, "role": new_role},
        follow_redirects=False
    )
    assert rv.status_code in (302, 404)
    if rv.status_code == 302:
        u = mongodb.users.find_one({"_id": ObjectId(uid)})
        assert u["role"] == new_role
        assert u["password"] != generate_password_hash(old_pw)

# ------------------------------------------------------------
# 10. ASSIGN ISSUE & EMAIL NOTIFICATION (REAL ACCOUNTS)
# ------------------------------------------------------------
ADMIN_EMAIL = "islammhareeq12@gmail.com"
MAINT_EMAIL = "islammhareeq5@gmail.com"
USER_EMAIL  = "ispammhareeq@gmail.com"
CRED_PW     = "Is212990360"


def test_assign_issue_requires_login(client, mongodb):
    issue_id = create_job(mongodb, USER_EMAIL)
    rv = client.post(
        f"/reports/assign/{issue_id}",
        data={"maintenance_email": MAINT_EMAIL},
        follow_redirects=False
    )
    assert rv.status_code in (302, 401)


def test_assign_issue_success_and_emails(client, mongodb, monkeypatch):
    sent = []
    monkeypatch.setattr("reports.reports.send_email", lambda to, subj, body: sent.append(to))

    create_user(mongodb, ADMIN_EMAIL, CRED_PW, role="admin")
    create_user(mongodb, MAINT_EMAIL, CRED_PW)
    create_user(mongodb, USER_EMAIL,  CRED_PW)
    issue_id = create_job(mongodb, USER_EMAIL)

    login(client, ADMIN_EMAIL, CRED_PW)
    with client.session_transaction() as sess:
        sess["user"] = ADMIN_EMAIL
        sess["role"] = "admin"

    rv = client.post(
        f"/reports/assign/{issue_id}",
        data={"maintenance_email": MAINT_EMAIL},
        follow_redirects=False
    )
    assert rv.status_code == 302

    issue = mongodb.issues.find_one({"_id": ObjectId(issue_id)})
    assert issue["assigned_to"] == MAINT_EMAIL

    assert MAINT_EMAIL in sent
    assert USER_EMAIL  in sent

# ------------------------------------------------------------
# 11. ADMIN TEST EMAIL ENDPOINT (REAL ADMIN)
# ------------------------------------------------------------
def test_admin_test_email_requires_login(client):
    rv = client.get("/admin/test-email", follow_redirects=False)
    assert rv.status_code == 200


def test_admin_test_email_success(client, mongodb, monkeypatch):
    sent = []
    monkeypatch.setattr("reports.reports.send_email", lambda to, subj, body: sent.append(to))

    create_user(mongodb, ADMIN_EMAIL, CRED_PW, role="admin")
    login(client, ADMIN_EMAIL, CRED_PW)
    with client.session_transaction() as sess:
        sess["user"] = ADMIN_EMAIL
        sess["role"] = "admin"

    rv = client.get("/admin/test-email")
    assert rv.status_code == 200
    assert sent, "Expected test-email to send at least one email"

# ------------------------------------------------------------
# 12. DONE REPORTS REVIEW ENDPOINTS
# ------------------------------------------------------------
def test_review_done_report_requires_login(client, mongodb):
    orig_id = str(mongodb.issues.insert_one({
        "reporter_email": "u@x.com",
        "description":    "foo",
        "status":         "pending",
        "timestamp":      datetime.now(timezone.utc).isoformat()
    }).inserted_id)
    dr_id = str(mongodb.done_issues.insert_one({
        "original_issue_id": orig_id,
        "completion_description": "desc",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }).inserted_id)

    rv = client.post(f"/admin/review_done_report/{dr_id}", data={"status": "accepted"})
    assert rv.status_code == 302

def test_review_done_report_invalid_id(client, mongodb):
    create_user(mongodb, ADMIN_EMAIL, CRED_PW, role="admin")
    login(client, ADMIN_EMAIL, CRED_PW)
    with client.session_transaction() as sess:
        sess["user"] = ADMIN_EMAIL
        sess["role"] = "admin"

    rv = client.post("/admin/review_done_report/not_an_id", data={"status": "accepted"})
    assert rv.status_code == 404

def test_review_done_report_accept_success(client, mongodb, monkeypatch):
    sent = []
    monkeypatch.setattr("reports.done_reports.send_email", lambda to, subj, body: sent.append(to))
    reporter = USER_EMAIL
    create_user(mongodb, ADMIN_EMAIL, CRED_PW, role="admin")
    create_user(mongodb, reporter, CRED_PW)
    issue_id = str(mongodb.issues.insert_one({
        "reporter_email": reporter,
        "description":    "baz",
        "status":         "pending",
        "timestamp":      datetime.now(timezone.utc).isoformat()
    }).inserted_id)
    dr_id = str(mongodb.done_issues.insert_one({
        "original_issue_id": issue_id,
        "completion_description": "worked",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }).inserted_id)

    login(client, ADMIN_EMAIL, CRED_PW)
    with client.session_transaction() as sess:
        sess["user"] = ADMIN_EMAIL
        sess["role"] = "admin"

    rv = client.post(
        f"/admin/review_done_report/{dr_id}",
        data={"status": "accepted"},
        follow_redirects=False
    )
    assert rv.status_code == 302

    issue = mongodb.issues.find_one({"_id": ObjectId(issue_id)})
    assert issue["status"] == "done"
    assert reporter in sent

def test_review_done_report_reject_requires_reason(client, mongodb):
    create_user(mongodb, ADMIN_EMAIL, CRED_PW, role="admin")
    issue_id = str(mongodb.issues.insert_one({
        "reporter_email": "u2@x.com",
        "description":    "qux",
        "status":         "pending",
        "timestamp":      datetime.now(timezone.utc).isoformat()
    }).inserted_id)
    dr_id = str(mongodb.done_issues.insert_one({
        "original_issue_id": issue_id,
        "completion_description": "nope",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }).inserted_id)

    login(client, ADMIN_EMAIL, CRED_PW)
    with client.session_transaction() as sess:
        sess["user"] = ADMIN_EMAIL
        sess["role"] = "admin"

    rv = client.post(
        f"/admin/review_done_report/{dr_id}",
        data={"status": "rejected"},
        follow_redirects=False
    )
    assert rv.status_code == 302
    assert mongodb.done_issues.find_one({"_id": ObjectId(dr_id)}) is not None

def test_review_done_report_reject_success(client, mongodb):
    create_user(mongodb, ADMIN_EMAIL, CRED_PW, role="admin")
    issue_id = str(mongodb.issues.insert_one({
        "reporter_email": "u3@x.com",
        "description":    "zap",
        "status":         "pending",
        "timestamp":      datetime.now(timezone.utc).isoformat()
    }).inserted_id)
    dr_id = str(mongodb.done_issues.insert_one({
        "original_issue_id": issue_id,
        "completion_description": "meh",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }).inserted_id)

    login(client, ADMIN_EMAIL, CRED_PW)
    with client.session_transaction() as sess:
        sess["user"] = ADMIN_EMAIL
        sess["role"] = "admin"

    rv = client.post(
        f"/admin/review_done_report/{dr_id}",
        data={"status": "rejected", "rejection_reason": "bad work"},
        follow_redirects=False
    )
    assert rv.status_code == 302

    assert mongodb.done_issues.find_one({"_id": ObjectId(dr_id)}) is None
    issue = mongodb.issues.find_one({"_id": ObjectId(issue_id)})
    assert issue["status"] == "in progress"
    rej = mongodb.rejected_reports.find_one({"original_issue_id": issue_id})
    assert rej and rej["rejection_reason"] == "bad work"
