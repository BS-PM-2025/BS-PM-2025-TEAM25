import pytest
import json
from datetime import datetime
from bson import ObjectId
from io import BytesIO

def test_done_reports_public(client, mongodb):
    """Test public view of completed reports"""
    # Create test completed reports
    done_issues = [
        {
            'original_issue_id': str(ObjectId()),
            'completion_description': 'First completed task',
            'technician': 'tech1@example.com',
            'timestamp': datetime.utcnow().isoformat(),
            'category': 'Electric',
            'before_file_id': ObjectId(),
            'after_file_id': ObjectId()
        },
        {
            'original_issue_id': str(ObjectId()),
            'completion_description': 'Second completed task',
            'technician': 'tech2@example.com',
            'timestamp': datetime.utcnow().isoformat(),
            'category': 'Water',
            'before_file_id': ObjectId(),
            'after_file_id': ObjectId()
        }
    ]
    
    for issue in done_issues:
        mongodb.done_issues.insert_one(issue)
    
    # View public done reports page
    response = client.get('/done_reports_public')
    assert response.status_code == 200
    
    # Clean up
    for issue in done_issues:
        mongodb.done_issues.delete_one({'original_issue_id': issue['original_issue_id']})

def test_api_done_reports(client, mongodb):
    """Test API for done reports with ratings"""
    # Create test completed reports
    report_ids = []
    done_issues = [
        {
            'original_issue_id': str(ObjectId()),
            'completion_description': 'API test completed task',
            'technician': 'tech@example.com',
            'timestamp': datetime.utcnow().isoformat(),
            'category': 'Test Category'
        }
    ]
    
    for issue in done_issues:
        result = mongodb.done_issues.insert_one(issue)
        report_ids.append(str(result.inserted_id))
    
    # Get done reports API
    response = client.get('/api/done_reports')
    assert response.status_code == 200
    data = response.get_json()
    
    assert 'done_reports' in data
    assert len(data['done_reports']) >= 1
    
    # Find our test report
    test_report_found = False
    for report in data['done_reports']:
        if report['completion_description'] == 'API test completed task':
            test_report_found = True
            break
    
    assert test_report_found
    
    # Clean up
    for report_id in report_ids:
        mongodb.done_issues.delete_one({'_id': ObjectId(report_id)})

def test_rate_report(authenticated_user, mongodb):
    """Test rating a completed report"""
    # Create a test completed report
    report = {
        'original_issue_id': str(ObjectId()),
        'completion_description': 'Report to be rated',
        'technician': 'tech@example.com',
        'timestamp': datetime.utcnow().isoformat(),
        'category': 'Test Category'
    }
    
    report_id = str(mongodb.done_issues.insert_one(report).inserted_id)
    
    # Get user email
    with authenticated_user.session_transaction() as sess:
        user_email = sess['user']
    
    # Submit a rating
    response = authenticated_user.post(
        '/api/rate_report',
        json={
            'report_id': report_id,
            'rating': 4
        },
        content_type='application/json'
    )
    
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    
    # Check rating was saved
    rating = mongodb.report_ratings.find_one({
        'report_id': report_id,
        'user_email': user_email
    })
    
    assert rating is not None
    assert rating['rating'] == 4
    
    # Update the rating
    response = authenticated_user.post(
        '/api/rate_report',
        json={
            'report_id': report_id,
            'rating': 5
        },
        content_type='application/json'
    )
    
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    
    # Check rating was updated
    updated_rating = mongodb.report_ratings.find_one({
        'report_id': report_id,
        'user_email': user_email
    })
    
    assert updated_rating['rating'] == 5
    
    # Clean up
    mongodb.done_issues.delete_one({'_id': ObjectId(report_id)})
    mongodb.report_ratings.delete_one({'_id': rating['_id']})

def test_get_report_ratings(authenticated_user, mongodb):
    """Test getting ratings for a report"""
    # Create a test completed report
    report = {
        'original_issue_id': str(ObjectId()),
        'completion_description': 'Report with ratings',
        'technician': 'tech@example.com',
        'timestamp': datetime.utcnow().isoformat(),
        'category': 'Test Category'
    }
    
    report_id = str(mongodb.done_issues.insert_one(report).inserted_id)
    
    # Add some ratings
    ratings = [
        {
            'report_id': report_id,
            'user_email': 'user1@example.com',
            'rating': 5,
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat()
        },
        {
            'report_id': report_id,
            'user_email': 'user2@example.com',
            'rating': 4,
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat()
        },
        {
            'report_id': report_id,
            'user_email': 'user3@example.com',
            'rating': 3,
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat()
        }
    ]
    
    for rating in ratings:
        mongodb.report_ratings.insert_one(rating)
    
    # Get report ratings
    response = authenticated_user.get(f'/api/report_ratings/{report_id}')
    
    assert response.status_code == 200
    data = response.get_json()
    
    # Check average rating
    assert data['avg_rating'] == 4.0  # (5 + 4 + 3) / 3 = 4
    assert data['rating_count'] == 3
    
    # Check distribution
    assert data['distribution']['1'] == 0
    assert data['distribution']['2'] == 0
    assert data['distribution']['3'] == 1
    assert data['distribution']['4'] == 1
    assert data['distribution']['5'] == 1
    
    # Clean up
    mongodb.done_issues.delete_one({'_id': ObjectId(report_id)})
    mongodb.report_ratings.delete_many({'report_id': report_id})

def test_admin_done_reports(authenticated_admin, mongodb):
    """Test admin view of done reports"""
    # Create test completed reports
    done_issues = [
        {
            'original_issue_id': str(ObjectId()),
            'completion_description': 'Admin test completed task',
            'technician': 'tech@example.com',
            'timestamp': datetime.utcnow().isoformat(),
            'category': 'Test Category',
            'before_file_id': ObjectId(),
            'after_file_id': ObjectId()
        }
    ]
    
    for issue in done_issues:
        mongodb.done_issues.insert_one(issue)
    
    # View admin done reports page
    response = authenticated_admin.get('/admin/done_reports')
    assert response.status_code == 200
    assert b'Admin test completed task' in response.data
    
    # Clean up
    for issue in done_issues:
        mongodb.done_issues.delete_one({'original_issue_id': issue['original_issue_id']})

def test_review_done_report_accept(authenticated_admin, mongodb, monkeypatch):
    """Test admin accepting a completed report"""
    # Mock email sending
    emails_sent = []
    def mock_send_email(to_email, subject, body):
        emails_sent.append({
            'to': to_email,
            'subject': subject,
            'body': body
        })
    
    monkeypatch.setattr('reports.done_reports.send_email', mock_send_email)
    
    # Create a test issue
    reporter_email = 'reporter@example.com'
    issue_id = mongodb.issues.insert_one({
        'reporter_email': reporter_email,
        'description': 'Issue for accepting',
        'city_street': 'Test Street',
        'category': 'Test Category',
        'priority': 'medium',
        'severity': 'moderate',
        'location': {'lat': 10.0, 'lng': 20.0},
        'timestamp': datetime.utcnow().isoformat(),
        'status': 'in progress',
        'assigned_to': 'tech@example.com',
        'maintenance_email': 'tech@example.com'
    }).inserted_id
    
    # Create a done report for this issue
    done_report = {
        'original_issue_id': str(issue_id),
        'completion_description': 'Completed for acceptance',
        'technician': 'tech@example.com',
        'timestamp': datetime.utcnow().isoformat(),
        'category': 'Test Category'
    }
    
    done_report_id = mongodb.done_issues.insert_one(done_report).inserted_id
    
    # Accept the report
    response = authenticated_admin.post(
        f'/admin/review_done_report/{done_report_id}',
        data={'status': 'accepted'},
        follow_redirects=False
    )
    
    assert response.status_code == 302
    
    # Check issue status was updated
    updated_issue = mongodb.issues.find_one({'_id': issue_id})
    assert updated_issue['status'] == 'done'
    
    # Check notification email was sent
    assert len(emails_sent) == 1
    assert emails_sent[0]['to'] == reporter_email
    assert 'completed' in emails_sent[0]['subject'].lower() or 'done' in emails_sent[0]['subject'].lower()
    
    # Clean up
    mongodb.issues.delete_one({'_id': issue_id})
    mongodb.done_issues.delete_one({'_id': done_report_id})

def test_review_done_report_reject(authenticated_admin, mongodb):
    """Test admin rejecting a completed report"""
    # Create a test issue
    issue_id = mongodb.issues.insert_one({
        'reporter_email': 'reporter@example.com',
        'description': 'Issue for rejecting',
        'city_street': 'Test Street',
        'category': 'Test Category',
        'priority': 'medium',
        'severity': 'moderate',
        'location': {'lat': 10.0, 'lng': 20.0},
        'timestamp': datetime.utcnow().isoformat(),
        'status': 'in progress',
        'assigned_to': 'tech@example.com',
        'maintenance_email': 'tech@example.com'
    }).inserted_id
    
    # Create a done report for this issue
    done_report = {
        'original_issue_id': str(issue_id),
        'completion_description': 'Completed for rejection',
        'technician': 'tech@example.com',
        'timestamp': datetime.utcnow().isoformat(),
        'category': 'Test Category'
    }
    
    done_report_id = mongodb.done_issues.insert_one(done_report).inserted_id
    
    # Reject the report
    response = authenticated_admin.post(
        f'/admin/review_done_report/{done_report_id}',
        data={
            'status': 'rejected',
            'rejection_reason': 'Not completed properly'
        },
        follow_redirects=False
    )
    
    assert response.status_code == 302
    
    # Check issue status was updated back to in progress
    updated_issue = mongodb.issues.find_one({'_id': issue_id})
    assert updated_issue['status'] == 'in progress'
    
    # Check done report was deleted
    assert mongodb.done_issues.find_one({'_id': done_report_id}) is None
    
    # Check rejection record was created
    rejection = mongodb.rejected_reports.find_one({
        'original_issue_id': str(issue_id),
        'technician': 'tech@example.com'
    })
    
    assert rejection is not None
    assert rejection['rejection_reason'] == 'Not completed properly'
    
    # Clean up
    mongodb.issues.delete_one({'_id': issue_id})
    mongodb.rejected_reports.delete_one({'_id': rejection['_id']})

def test_rejected_reports_view(authenticated_maintenance, mongodb):
    """Test maintenance user viewing rejected reports"""
    # Get maintenance user email
    with authenticated_maintenance.session_transaction() as sess:
        maintenance_email = sess['user']
    
    # Create a test issue
    issue_id = mongodb.issues.insert_one({
        'reporter_email': 'reporter@example.com',
        'description': 'Issue with rejection',
        'city_street': 'Test Street',
        'category': 'Test Category',
        'priority': 'medium',
        'severity': 'moderate',
        'location': {'lat': 10.0, 'lng': 20.0},
        'timestamp': datetime.utcnow().isoformat(),
        'status': 'in progress',
        'assigned_to': maintenance_email,
        'maintenance_email': maintenance_email
    }).inserted_id
    
    # Create a rejection record
    rejection_id = mongodb.rejected_reports.insert_one({
        'original_issue_id': str(issue_id),
        'technician': maintenance_email,
        'rejection_reason': 'Test rejection reason',
        'admin': 'admin@example.com',
        'timestamp': datetime.utcnow().isoformat()
    }).inserted_id
    
    # View rejected reports
    response = authenticated_maintenance.get('/maintenance/rejected_reports')
    assert response.status_code == 200
    assert b'Test rejection reason' in response.data
    
    # Clean up
    mongodb.issues.delete_one({'_id': issue_id})
    mongodb.rejected_reports.delete_one({'_id': rejection_id})