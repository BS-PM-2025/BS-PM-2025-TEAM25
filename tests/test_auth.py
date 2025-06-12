import pytest
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from bson import ObjectId
from conftest import login_user, register_user

def test_login_success(client, test_user):
    """Test successful login"""
    response = login_user(client, test_user["email"], test_user["password"])
    assert response.status_code == 302  # Redirect after login
    assert response.location.endswith("/home")  # Redirects to home page

def test_login_failure_wrong_password(client, test_user):
    """Test login with wrong password"""
    response = login_user(client, test_user["email"], "wrong_password")
    assert response.status_code == 302
    assert "auth" in response.location  # Redirects back to auth page

def test_login_failure_user_not_found(client):
    """Test login with non-existent user"""
    response = login_user(client, "nonexistent@example.com", "password")
    assert response.status_code == 302
    assert "auth" in response.location  # Redirects back to auth page

def test_register_success(client, mongodb):
    """Test successful user registration"""
    email = "new_user@example.com"
    password = "NewPass123!"
    
    # Ensure user doesn't exist
    mongodb.users.delete_many({"email": email})
    
    response = register_user(client, "New User", email, password)
    assert response.status_code == 302
    assert "auth" in response.location
    
    # Check user was created in database
    user = mongodb.users.find_one({"email": email})
    assert user is not None
    assert user["name"] == "New User"
    assert check_password_hash(user["password"], password)
    
    # Clean up
    mongodb.users.delete_many({"email": email})

def test_register_duplicate_email(client, test_user, mongodb):
    """Test registration with existing email"""
    response = register_user(client, "Duplicate User", test_user["email"], "NewPass123!")
    assert response.status_code == 302
    assert "auth" in response.location
    
    # Check that only one user with this email exists
    users = list(mongodb.users.find({"email": test_user["email"]}))
    assert len(users) == 1

def test_logout(client, authenticated_user):
    """Test user logout"""
    response = authenticated_user.get("/auth/logout")
    assert response.status_code == 302
    assert "auth" in response.location
    
    # Check session is cleared
    with authenticated_user.session_transaction() as sess:
        assert "user" not in sess

def test_forgot_password_page_loads(client):
    """Test that forgot password page loads correctly"""
    response = client.get("/auth/forgot-password")
    assert response.status_code == 200
    assert b"Forgot Password" in response.data or b"Reset Password" in response.data

def test_forgot_password_submit(client, mongodb, monkeypatch, test_user):
    """Test submitting forgot password form"""
    # Mock the email sending function
    emails_sent = []
    def mock_send_password_reset_email(to_email, reset_code, expires_minutes):
        emails_sent.append({
            "to": to_email,
            "code": reset_code,
            "expires": expires_minutes
        })
        return True
    
    monkeypatch.setattr("auth.main.send_password_reset_email", mock_send_password_reset_email)
    
    # Submit forgot password form
    response = client.post(
        "/auth/forgot-password",
        data={"email": test_user["email"]},
        follow_redirects=False
    )
    
    assert response.status_code == 302
    assert len(emails_sent) == 1
    assert emails_sent[0]["to"] == test_user["email"]
    
    # Check that reset request was created in database
    reset_request = mongodb.password_resets.find_one({"email": test_user["email"]})
    assert reset_request is not None
    assert reset_request["code"] == emails_sent[0]["code"]
    assert reset_request["used"] is False
    
    # Clean up
    mongodb.password_resets.delete_many({"email": test_user["email"]})

def test_verify_reset_code(client, mongodb, test_user):
    """Test reset code verification page"""
    # Create a reset token
    reset_code = "123456"
    reset_token = "test_token_12345"
    expires_at = datetime.utcnow() + timedelta(minutes=15)
    
    mongodb.password_resets.delete_many({"email": test_user["email"]})
    reset_id = mongodb.password_resets.insert_one({
        "email": test_user["email"],
        "code": reset_code,
        "token": reset_token,
        "expires_at": expires_at,
        "used": False,
        "created_at": datetime.utcnow()
    }).inserted_id
    
    # Test the verification page loads
    response = client.get(f"/auth/verify-reset-code/{reset_token}")
    assert response.status_code == 200
    assert b"code" in response.data.lower()
    
    # Clean up
    mongodb.password_resets.delete_many({"_id": reset_id})

def test_reset_password_success(client, mongodb, monkeypatch, test_user):
    """Test successful password reset"""
    # Create a reset token
    reset_code = "123456"
    reset_token = "test_token_12345"
    expires_at = datetime.utcnow() + timedelta(minutes=15)
    
    mongodb.password_resets.delete_many({"email": test_user["email"]})
    reset_id = mongodb.password_resets.insert_one({
        "email": test_user["email"],
        "code": reset_code,
        "token": reset_token,
        "expires_at": expires_at,
        "used": False,
        "created_at": datetime.utcnow()
    }).inserted_id
    
    # New password
    new_password = "NewPass456!"
    
    # Submit reset password form
    response = client.post(
        f"/auth/verify-reset-code/{reset_token}",
        data={
            "code": reset_code,
            "password": new_password,
            "confirm_password": new_password
        },
        follow_redirects=False
    )
    
    assert response.status_code == 302
    assert "auth" in response.location
    
    # Check user's password was updated
    user = mongodb.users.find_one({"email": test_user["email"]})
    assert check_password_hash(user["password"], new_password)
    
    # Check reset request was marked as used
    reset_request = mongodb.password_resets.find_one({"token": reset_token})
    assert reset_request["used"] is True
    
    # Clean up
    mongodb.password_resets.delete_many({"_id": reset_id})

def test_reset_password_invalid_code(client, mongodb, test_user):
    """Test reset password with invalid code"""
    # Create a reset token
    reset_code = "123456"
    reset_token = "test_token_12345"
    expires_at = datetime.utcnow() + timedelta(minutes=15)
    
    mongodb.password_resets.delete_many({"email": test_user["email"]})
    reset_id = mongodb.password_resets.insert_one({
        "email": test_user["email"],
        "code": reset_code,
        "token": reset_token,
        "expires_at": expires_at,
        "used": False,
        "created_at": datetime.utcnow()
    }).inserted_id
    
    # Submit with wrong code
    response = client.post(
        f"/auth/verify-reset-code/{reset_token}",
        data={
            "code": "654321",  # Wrong code
            "password": "NewPass456!",
            "confirm_password": "NewPass456!"
        },
        follow_redirects=False
    )
    
    assert response.status_code == 200  # Shows form again
    assert b"Invalid verification code" in response.data
    
    # Clean up
    mongodb.password_resets.delete_many({"_id": reset_id})

def test_resend_reset_code(client, mongodb, monkeypatch, test_user):
    """Test resending reset code"""
    # Mock the email sending function
    emails_sent = []
    def mock_send_password_reset_email(to_email, reset_code, expires_minutes):
        emails_sent.append({
            "to": to_email,
            "code": reset_code,
            "expires": expires_minutes
        })
        return True
    
    monkeypatch.setattr("auth.main.send_password_reset_email", mock_send_password_reset_email)
    
    # Create initial reset request
    reset_code = "123456"
    reset_token = "test_token_12345"
    expires_at = datetime.utcnow() + timedelta(minutes=15)
    
    mongodb.password_resets.delete_many({"email": test_user["email"]})
    reset_id = mongodb.password_resets.insert_one({
        "email": test_user["email"],
        "code": reset_code,
        "token": reset_token,
        "expires_at": expires_at,
        "used": False,
        "created_at": datetime.utcnow() - timedelta(minutes=2)  # Created 2 minutes ago
    }).inserted_id
    
    # Request resend
    response = client.post(
        "/auth/resend-code",
        json={"email": test_user["email"]},
        content_type="application/json"
    )
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    
    # Check new email was sent
    assert len(emails_sent) == 1
    assert emails_sent[0]["to"] == test_user["email"]
    assert emails_sent[0]["code"] != reset_code  # Should be a new code
    
    # Check old reset request was replaced
    old_request = mongodb.password_resets.find_one({"token": reset_token})
    assert old_request is None
    
    # Clean up
    mongodb.password_resets.delete_many({"email": test_user["email"]})