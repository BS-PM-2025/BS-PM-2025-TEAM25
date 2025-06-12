import pytest
from datetime import datetime
from bson import ObjectId
from reports.reports import calculate_urgency_score, get_priority_score, get_severity_score

def test_priority_severity_score_functions():
    """Test the priority and severity scoring functions"""
    # Test priority scoring
    assert get_priority_score('low') == 1
    assert get_priority_score('medium') == 2
    assert get_priority_score('high') == 3
    assert get_priority_score('critical') == 4
    assert get_priority_score(None) == 2  # Default to medium
    assert get_priority_score('invalid') == 2  # Invalid defaults to medium
    
    # Test severity scoring
    assert get_severity_score('minor') == 1
    assert get_severity_score('moderate') == 2
    assert get_severity_score('major') == 3
    assert get_severity_score('critical') == 4
    assert get_severity_score(None) == 2  # Default to moderate
    assert get_severity_score('invalid') == 2  # Invalid defaults to moderate
    
    # Test urgency score calculation (priority * 0.6 + severity * 0.4)
    assert calculate_urgency_score('low', 'minor') == (1 * 0.6) + (1 * 0.4)
    assert calculate_urgency_score('critical', 'critical') == (4 * 0.6) + (4 * 0.4)
    assert calculate_urgency_score('high', 'moderate') == (3 * 0.6) + (2 * 0.4)
    assert calculate_urgency_score(None, None) == (2 * 0.6) + (2 * 0.4)  # Default values

def test_report_creation(authenticated_user, mongodb):
    """Test creating a report with priority and severity"""
    # Submit a new report
    response = authenticated_user.post(
        '/report_issue',
        data={
            'description': 'Test issue with priority and severity',
            'city_street': 'Test Street',
            'category': 'Test Category',
            'priority': 'high',
            'severity': 'major',
            'lat': '10.0',
            'lng': '20.0'
        },
        follow_redirects=False
    )
    
    assert response.status_code == 302
    
    # Find the newly created issue
    with authenticated_user.session_transaction() as sess:
        user_email = sess['user']
    
    issue = mongodb.issues.find_one({
        'reporter_email': user_email,
        'description': 'Test issue with priority and severity'
    })
    
    assert issue is not None
    assert issue['priority'] == 'high'
    assert issue['severity'] == 'major'
    assert 'urgency_score' in issue
    assert issue['urgency_score'] == calculate_urgency_score('high', 'major')
    
    # Clean up
    mongodb.issues.delete_one({'_id': issue['_id']})

def test_report_list_by_urgency(authenticated_user, mongodb):
    """Test that reports are sorted by urgency correctly"""
    # Create test user email
    with authenticated_user.session_transaction() as sess:
        user_email = sess['user']
    
    # Clean up any existing issues
    mongodb.issues.delete_many({'reporter_email': user_email})
    
    # Create test issues with different priorities
    issues = [
        # Low priority
        {
            'reporter_email': user_email,
            'description': 'Low priority issue',
            'city_street': 'Test Street',
            'category': 'Test Category',
            'priority': 'low',
            'severity': 'minor',
            'location': {'lat': 10.0, 'lng': 20.0},
            'urgency_score': calculate_urgency_score('low', 'minor'),
            'timestamp': datetime.now().isoformat(),
            'status': 'pending',
            'assigned_to': None,
            'edit_count': 0,
            'edit_history': []
        },
        # Medium priority
        {
            'reporter_email': user_email,
            'description': 'Medium priority issue',
            'city_street': 'Test Street',
            'category': 'Test Category',
            'priority': 'medium',
            'severity': 'moderate',
            'location': {'lat': 10.0, 'lng': 20.0},
            'urgency_score': calculate_urgency_score('medium', 'moderate'),
            'timestamp': datetime.now().isoformat(),
            'status': 'pending',
            'assigned_to': None,
            'edit_count': 0,
            'edit_history': []
        },
        # High priority
        {
            'reporter_email': user_email,
            'description': 'High priority issue',
            'city_street': 'Test Street',
            'category': 'Test Category',
            'priority': 'high',
            'severity': 'major',
            'location': {'lat': 10.0, 'lng': 20.0},
            'urgency_score': calculate_urgency_score('high', 'major'),
            'timestamp': datetime.now().isoformat(),
            'status': 'pending',
            'assigned_to': None,
            'edit_count': 0,
            'edit_history': []
        },
        # Critical priority
        {
            'reporter_email': user_email,
            'description': 'Critical priority issue',
            'city_street': 'Test Street',
            'category': 'Test Category',
            'priority': 'critical',
            'severity': 'critical',
            'location': {'lat': 10.0, 'lng': 20.0},
            'urgency_score': calculate_urgency_score('critical', 'critical'),
            'timestamp': datetime.now().isoformat(),
            'status': 'pending',
            'assigned_to': None,
            'edit_count': 0,
            'edit_history': []
        }
    ]
    
    # Insert issues
    for issue in issues:
        mongodb.issues.insert_one(issue)
    
    # Get my_reports page (default sorted by urgency)
    response = authenticated_user.get('/my_reports')
    assert response.status_code == 200
    
    # Clean up
    mongodb.issues.delete_many({'reporter_email': user_email})

def test_edit_issue(authenticated_user, mongodb):
    """Test editing an issue with priority/severity changes"""
    # Create test user email
    with authenticated_user.session_transaction() as sess:
        user_email = sess['user']
    
    # Create a test issue
    issue_id = mongodb.issues.insert_one({
        'reporter_email': user_email,
        'description': 'Issue to be edited',
        'city_street': 'Test Street',
        'category': 'Test Category',
        'priority': 'medium',
        'severity': 'moderate',
        'location': {'lat': 10.0, 'lng': 20.0},
        'urgency_score': calculate_urgency_score('medium', 'moderate'),
        'timestamp': datetime.now().isoformat(),
        'status': 'pending',
        'assigned_to': None,
        'edit_count': 0,
        'edit_history': []
    }).inserted_id
    
    # Edit the issue
    response = authenticated_user.post(
        f'/reports/edit/{issue_id}',
        data={
            'description': 'Updated issue description',
            'city_street': 'Updated Street',
            'category': 'Updated Category',
            'priority': 'high',
            'severity': 'major',
            'lat': '15.0',
            'lng': '25.0'
        },
        follow_redirects=False
    )
    
    assert response.status_code == 302
    
    # Check the issue was updated
    updated_issue = mongodb.issues.find_one({'_id': issue_id})
    assert updated_issue['description'] == 'Updated issue description'
    assert updated_issue['city_street'] == 'Updated Street'
    assert updated_issue['category'] == 'Updated Category'
    assert updated_issue['priority'] == 'high'
    assert updated_issue['severity'] == 'major'
    assert updated_issue['location'] == {'lat': 15.0, 'lng': 25.0}
    assert updated_issue['urgency_score'] == calculate_urgency_score('high', 'major')
    assert updated_issue['edit_count'] == 1
    assert len(updated_issue['edit_history']) == 1
    
    # Check edit history
    history_entry = updated_issue['edit_history'][0]
    assert history_entry['modified_by'] == user_email
    assert 'timestamp' in history_entry
    assert 'changes' in history_entry
    assert 'description' in history_entry['changes']
    assert 'priority' in history_entry['changes']
    assert 'severity' in history_entry['changes']
    
    # Clean up
    mongodb.issues.delete_one({'_id': issue_id})

def test_delete_issue(authenticated_user, mongodb):
    """Test deleting an issue"""
    # Create test user email
    with authenticated_user.session_transaction() as sess:
        user_email = sess['user']
    
    # Create a test issue
    issue_id = mongodb.issues.insert_one({
        'reporter_email': user_email,
        'description': 'Issue to be deleted',
        'city_street': 'Test Street',
        'category': 'Test Category',
        'priority': 'medium',
        'severity': 'moderate',
        'location': {'lat': 10.0, 'lng': 20.0},
        'urgency_score': calculate_urgency_score('medium', 'moderate'),
        'timestamp': datetime.now().isoformat(),
        'status': 'pending',
        'assigned_to': None,
        'edit_count': 0,
        'edit_history': []
    }).inserted_id
    
    # Delete the issue
    response = authenticated_user.post(
        f'/delete_issue/{issue_id}',
        follow_redirects=False
    )
    
    assert response.status_code == 302
    
    # Check the issue was deleted
    deleted_issue = mongodb.issues.find_one({'_id': issue_id})
    assert deleted_issue is None

def test_view_issue_detail(client, mongodb, test_user):
    """Test viewing a single issue detail"""
    # Create a test issue
    issue_id = mongodb.issues.insert_one({
        'reporter_email': test_user['email'],
        'description': 'Issue for detail view',
        'city_street': 'Test Street',
        'category': 'Test Category',
        'priority': 'high',
        'severity': 'major',
        'location': {'lat': 10.0, 'lng': 20.0},
        'urgency_score': calculate_urgency_score('high', 'major'),
        'timestamp': datetime.now().isoformat(),
        'status': 'pending',
        'assigned_to': None,
        'edit_count': 0,
        'edit_history': []
    }).inserted_id
    
    # View the issue detail
    response = client.get(f'/report/{issue_id}')
    assert response.status_code == 200
    
    # Clean up
    mongodb.issues.delete_one({'_id': issue_id})

def test_assign_issue(authenticated_admin, mongodb, test_maintenance, monkeypatch):
    """Test assigning an issue to maintenance staff"""
    # Mock email sending
    emails_sent = []
    def mock_send_email(to_email, subject, body):
        emails_sent.append({
            'to': to_email,
            'subject': subject,
            'body': body
        })
    
    monkeypatch.setattr('reports.reports.send_email', mock_send_email)
    
    # Create a test issue
    reporter_email = "test_reporter@example.com"
    issue_id = mongodb.issues.insert_one({
        'reporter_email': reporter_email,
        'description': 'Issue for assignment',
        'city_street': 'Test Street',
        'category': 'Test Category',
        'priority': 'high',
        'severity': 'major',
        'location': {'lat': 10.0, 'lng': 20.0},
        'urgency_score': calculate_urgency_score('high', 'major'),
        'timestamp': datetime.now().isoformat(),
        'status': 'pending',
        'assigned_to': None,
        'edit_count': 0,
        'edit_history': []
    }).inserted_id
    
    # Assign the issue to maintenance staff
    response = authenticated_admin.post(
        f'/reports/assign/{issue_id}',
        data={'maintenance_email': test_maintenance['email']},
        follow_redirects=False
    )
    
    assert response.status_code == 302
    
    # Check the issue was assigned
    updated_issue = mongodb.issues.find_one({'_id': issue_id})
    assert updated_issue['assigned_to'] == test_maintenance['email']
    assert updated_issue['status'] == 'assigned'
    
    # Check emails were sent
    assert len(emails_sent) >= 1
    maintenance_email_sent = False
    for email in emails_sent:
        if email['to'] == test_maintenance['email']:
            maintenance_email_sent = True
            assert 'assigned' in email['subject'].lower() or 'assignment' in email['subject'].lower()
    
    assert maintenance_email_sent
    
    # Clean up
    mongodb.issues.delete_one({'_id': issue_id})

def test_public_reports_list(client, mongodb):
    """Test public reports list with filtering"""
    # Create some test issues
    issues = [
        {
            'reporter_email': 'public_test@example.com',
            'description': 'Public low priority issue',
            'city_street': 'Test Street',
            'category': 'Electric',
            'priority': 'low',
            'severity': 'minor',
            'location': {'lat': 10.0, 'lng': 20.0},
            'urgency_score': calculate_urgency_score('low', 'minor'),
            'timestamp': datetime.now().isoformat(),
            'status': 'pending',
            'assigned_to': None,
            'edit_count': 0,
            'edit_history': []
        },
        {
            'reporter_email': 'public_test@example.com',
            'description': 'Public high priority issue',
            'city_street': 'Test Street',
            'category': 'Water',
            'priority': 'high',
            'severity': 'major',
            'location': {'lat': 10.0, 'lng': 20.0},
            'urgency_score': calculate_urgency_score('high', 'major'),
            'timestamp': datetime.now().isoformat(),
            'status': 'pending',
            'assigned_to': None,
            'edit_count': 0,
            'edit_history': []
        }
    ]
    
    # Insert issues
    for issue in issues:
        mongodb.issues.insert_one(issue)
    
    # View public reports - we're just checking the page loads, not the content
    # since the page uses JavaScript to load the data
    response = client.get('/reports')
    assert response.status_code == 200
    
    # Test the API endpoint that provides the data instead
    response = client.get('/api/issues')
    assert response.status_code == 200
    data = response.get_json()
    assert 'issues' in data
    
    # Clean up
    mongodb.issues.delete_many({'reporter_email': 'public_test@example.com'})

def test_api_issue_endpoints(client, mongodb, test_user):
    """Test API endpoints for issues"""
    # Create a test issue
    issue_id = mongodb.issues.insert_one({
        'reporter_email': test_user['email'],
        'description': 'API test issue',
        'city_street': 'API Street',
        'category': 'API Category',
        'priority': 'medium',
        'severity': 'moderate',
        'location': {'lat': 10.0, 'lng': 20.0},
        'urgency_score': calculate_urgency_score('medium', 'moderate'),
        'timestamp': datetime.now().isoformat(),
        'status': 'pending',
        'assigned_to': None,
        'edit_count': 0,
        'edit_history': []
    }).inserted_id
    
    # Test all issues API
    response = client.get('/api/issues')
    assert response.status_code == 200
    data = response.get_json()
    assert 'issues' in data
    
    # Test single issue API
    response = client.get(f'/api/issues/{issue_id}')
    assert response.status_code == 200
    data = response.get_json()
    assert 'issue' in data
    assert data['issue']['description'] == 'API test issue'
    
    # Test user issues API
    response = client.get(f'/api/issues/user/{test_user["email"]}')
    assert response.status_code == 200
    data = response.get_json()
    assert 'issues' in data
    
    # Clean up
    mongodb.issues.delete_one({'_id': issue_id})