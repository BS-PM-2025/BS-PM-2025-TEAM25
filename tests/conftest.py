import sys
import os
import pytest
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash
from bson import ObjectId

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import run
from run import app

@pytest.fixture
def client():
    """Create a test client for the Flask app with testing configuration"""
    app.config.update({
        'TESTING': True,
        'WTF_CSRF_ENABLED': False,
        'MONGO_URI': os.getenv("MONGO_URI", "mongodb://localhost:27017/cityfix_test")
    })
    with app.test_client() as client:
        yield client

@pytest.fixture
def mongodb():
    """Provide access to the MongoDB database"""
    return app.mongo.db

@pytest.fixture
def test_user(mongodb):
    """Create a test user and clean up afterward"""
    email = "test_user@example.com"
    password = "TestPass123!"
    
    # Delete any existing user with this email
    mongodb.users.delete_many({"email": email})
    
    # Create a new user
    user_id = mongodb.users.insert_one({
        "name": "Test User",
        "email": email,
        "password": generate_password_hash(password),
        "role": "user"
    }).inserted_id
    
    # Return user details
    yield {
        "id": user_id,
        "email": email,
        "password": password,
        "role": "user"
    }
    
    # Clean up
    mongodb.users.delete_many({"email": email})

@pytest.fixture
def test_admin(mongodb):
    """Create a test admin user and clean up afterward"""
    email = "test_admin@example.com"
    password = "AdminPass123!"
    
    # Delete any existing admin with this email
    mongodb.users.delete_many({"email": email})
    
    # Create a new admin
    user_id = mongodb.users.insert_one({
        "name": "Test Admin",
        "email": email,
        "password": generate_password_hash(password),
        "role": "admin"
    }).inserted_id
    
    # Return admin details
    yield {
        "id": user_id,
        "email": email,
        "password": password,
        "role": "admin"
    }
    
    # Clean up
    mongodb.users.delete_many({"email": email})

@pytest.fixture
def test_maintenance(mongodb):
    """Create a test maintenance user and clean up afterward"""
    email = "test_maintenance@example.com"
    password = "MaintPass123!"
    
    # Delete any existing maintenance user with this email
    mongodb.users.delete_many({"email": email})
    
    # Create a new maintenance user
    user_id = mongodb.users.insert_one({
        "name": "Test Maintenance",
        "email": email,
        "password": generate_password_hash(password),
        "role": "maintenance"
    }).inserted_id
    
    # Return maintenance details
    yield {
        "id": user_id,
        "email": email,
        "password": password,
        "role": "maintenance"
    }
    
    # Clean up
    mongodb.users.delete_many({"email": email})

@pytest.fixture
def test_issue(mongodb, test_user):
    """Create a test issue and clean up afterward"""
    # Delete any existing issues from this user
    mongodb.issues.delete_many({"reporter_email": test_user["email"]})
    
    # Create a new issue
    issue_id = mongodb.issues.insert_one({
        "reporter_email": test_user["email"],
        "description": "Test issue for automated testing",
        "city_street": "Test Street",
        "category": "Test Category",
        "priority": "medium",
        "severity": "moderate",
        "location": {"lat": 10.0, "lng": 20.0},
        "status": "pending",
        "assigned_to": None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "edit_count": 0,
        "edit_history": []
    }).inserted_id
    
    # Return issue details
    yield {
        "id": str(issue_id),
        "reporter_email": test_user["email"],
        "description": "Test issue for automated testing"
    }
    
    # Clean up
    mongodb.issues.delete_many({"_id": issue_id})

@pytest.fixture
def authenticated_user(client, test_user):
    """Log in a test user and set up session"""
    client.post(
        "/auth/login",
        data={"email": test_user["email"], "password": test_user["password"]}
    )
    
    with client.session_transaction() as sess:
        sess["user"] = test_user["email"]
        sess["role"] = "user"
    
    return client

@pytest.fixture
def authenticated_admin(client, test_admin):
    """Log in a test admin and set up session"""
    client.post(
        "/auth/login",
        data={"email": test_admin["email"], "password": test_admin["password"]}
    )
    
    with client.session_transaction() as sess:
        sess["user"] = test_admin["email"]
        sess["role"] = "admin"
    
    return client

@pytest.fixture
def authenticated_maintenance(client, test_maintenance):
    """Log in a test maintenance user and set up session"""
    client.post(
        "/auth/login",
        data={"email": test_maintenance["email"], "password": test_maintenance["password"]}
    )
    
    with client.session_transaction() as sess:
        sess["user"] = test_maintenance["email"]
        sess["role"] = "maintenance"
    
    return client

# Helper functions that can be imported in test files
def login_user(client, email, password):
    """Helper function to log in a user"""
    return client.post(
        "/auth/login",
        data={"email": email, "password": password},
        follow_redirects=False
    )

def register_user(client, name, email, password, role="user"):
    """Helper function to register a new user"""
    return client.post(
        "/auth/register",
        data={"name": name, "email": email, "password": password, "role": role},
        follow_redirects=False
    )

def create_test_issue(mongodb, reporter_email, priority="medium", severity="moderate"):
    """Helper function to create a test issue"""
    issue_id = mongodb.issues.insert_one({
        "reporter_email": reporter_email,
        "description": f"Test issue for {reporter_email}",
        "city_street": "Test Street",
        "category": "Test Category",
        "priority": priority,
        "severity": severity,
        "location": {"lat": 10.0, "lng": 20.0},
        "status": "pending",
        "assigned_to": None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "edit_count": 0,
        "edit_history": []
    }).inserted_id
    
    return str(issue_id)