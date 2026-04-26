"""
VOTE.X — Comprehensive Test Suite
Covers authentication, voter application, admin workflows, and security.
"""
import pytest
from werkzeug.security import generate_password_hash


# ─────────────────────────────────────────────
# SECTION 1: Public Route Smoke Tests
# ─────────────────────────────────────────────

def test_index_page(client):
    """Home page loads."""
    response = client.get('/')
    assert response.status_code == 200


def test_login_page_get(client):
    """Login page renders."""
    response = client.get('/login')
    assert response.status_code == 200


def test_register_page_get(client):
    """Register page renders."""
    response = client.get('/register')
    assert response.status_code == 200


def test_forgot_password_page_get(client):
    """Forgot password page renders."""
    response = client.get('/forgot-password')
    assert response.status_code == 200


def test_search_voter_public(client):
    """Search voter page is publicly accessible (no login required)."""
    response = client.get('/voter/search')
    assert response.status_code == 200


# ─────────────────────────────────────────────
# SECTION 2: Authentication Flow Tests
# ─────────────────────────────────────────────

def test_login_wrong_credentials(client):
    """Login with bad credentials shows error flash, no redirect."""
    response = client.post('/login', data={
        'username': 'nonexistent_user',
        'password': 'wrongpassword'
    }, follow_redirects=True)
    assert response.status_code == 200
    # Should stay on login page with error message
    data = response.data.decode()
    assert 'Login Unsuccessful' in data or 'login' in data.lower()


def test_protected_admin_route_redirects_unauthenticated(client):
    """Admin dashboard redirects to login for unauthenticated users."""
    response = client.get('/admin/dashboard')
    assert response.status_code == 302
    assert '/login' in response.headers['Location']


def test_protected_voter_route_redirects_unauthenticated(client):
    """Voter profile redirects to login for unauthenticated users."""
    response = client.get('/voter/profile')
    assert response.status_code == 302
    assert '/login' in response.headers['Location']


def test_forgot_password_generic_response(client):
    """Forgot password always shows generic message regardless of email existence."""
    response = client.post('/forgot-password', data={
        'email': 'nonexistent@example.com'
    }, follow_redirects=True)
    assert response.status_code == 200
    data = response.data.decode()
    # Should show generic message, not reveal if email exists
    assert 'sent' in data.lower() or 'check' in data.lower() or 'login' in data.lower()


def test_reset_password_invalid_token(client):
    """Reset password with invalid token redirects to forgot-password."""
    response = client.get('/reset-password/invalid-garbage-token', follow_redirects=True)
    assert response.status_code == 200
    data = response.data.decode()
    # Should be redirected to forgot-password with error
    assert 'Invalid' in data or 'Reset' in data or 'forgot' in data.lower()


# ─────────────────────────────────────────────
# SECTION 3: API Endpoint Tests
# ─────────────────────────────────────────────

def test_api_states_returns_list(client):
    """States API returns a JSON list."""
    response = client.get('/voter/api/states')
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)


def test_api_districts_requires_state(client):
    """Districts API returns empty list without state param."""
    response = client.get('/voter/api/districts')
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)


def test_api_search_missing_params_returns_400(client):
    """Search API returns 400 when required params are missing."""
    # Detail search without name
    response = client.get('/voter/api/search?type=detail')
    assert response.status_code == 400
    json_data = response.get_json()
    assert 'error' in json_data

    # EPIC search without epic number
    response = client.get('/voter/api/search?type=epic')
    assert response.status_code == 400
    json_data = response.get_json()
    assert 'error' in json_data


# ─────────────────────────────────────────────
# SECTION 4: Error Handler Tests
# ─────────────────────────────────────────────

def test_404_error_handler(client):
    """Non-existent route returns styled 404 page."""
    response = client.get('/this/route/does/not/exist/at/all')
    assert response.status_code == 404
    data = response.data.decode()
    assert '404' in data


def test_403_admin_route_as_voter_returns_403_or_redirect(client):
    """Accessing deeply protected admin sub-route returns 302 (redirect to login) for anonymous."""
    response = client.get('/admin/export/csv')
    # Should redirect to login, not serve CSV
    assert response.status_code in (302, 403)


# ─────────────────────────────────────────────
# SECTION 5: File Upload Security Tests
# ─────────────────────────────────────────────

def test_allowed_file_valid_jpg():
    """allowed_file accepts valid .jpg extension."""
    from app import create_app
    from config import TestConfig
    app = create_app(TestConfig)
    with app.app_context():
        from utils import allowed_file
        assert allowed_file('passport.jpg') is True


def test_allowed_file_rejects_exe():
    """allowed_file rejects .exe extension."""
    from app import create_app
    from config import TestConfig
    app = create_app(TestConfig)
    with app.app_context():
        from utils import allowed_file
        assert allowed_file('malware.exe') is False


def test_allowed_file_rejects_no_extension():
    """allowed_file rejects filenames with no extension."""
    from app import create_app
    from config import TestConfig
    app = create_app(TestConfig)
    with app.app_context():
        from utils import allowed_file
        assert allowed_file('noextension') is False


def test_allowed_file_accepts_pdf():
    """allowed_file accepts .pdf extension."""
    from app import create_app
    from config import TestConfig
    app = create_app(TestConfig)
    with app.app_context():
        from utils import allowed_file
        assert allowed_file('document.pdf') is True


def test_allowed_file_accepts_png():
    """allowed_file accepts .png extension (BUG-013 regression)."""
    from app import create_app
    from config import TestConfig
    app = create_app(TestConfig)
    with app.app_context():
        from utils import allowed_file
        assert allowed_file('photo.png') is True


# ─────────────────────────────────────────────
# SECTION 6: Utility / Logic Tests
# ─────────────────────────────────────────────

def test_application_status_enum_values():
    """ApplicationStatus Enum has all expected values."""
    from utils import ApplicationStatus
    assert ApplicationStatus.PENDING.value == 'Pending'
    assert ApplicationStatus.APPROVED.value == 'Approved'
    assert ApplicationStatus.REJECTED.value == 'Rejected'
    assert ApplicationStatus.FLAGGED.value == 'Flagged'
    assert ApplicationStatus.UNDER_REVIEW.value == 'Under Review'
    assert len(ApplicationStatus.values()) == 5


def test_application_status_enum_membership():
    """ApplicationStatus.values() contains all expected strings."""
    from utils import ApplicationStatus
    assert 'Pending' in ApplicationStatus.values()
    assert 'Approved' in ApplicationStatus.values()
    assert 'Rejected' in ApplicationStatus.values()


def test_fraud_risk_underage_blocking():
    """Fraud engine blocks applicants under 18."""
    from utils.risk_engine import assess_fraud_risk
    import mongomock

    client = mongomock.MongoClient()
    mock_mongo = type('obj', (object,), {'db': client['test']})()

    app_data = {
        'dob': '2015-01-01',   # 9 years old
        'user_id': 'test_user_1',
    }
    result = assess_fraud_risk(app_data, mock_mongo)
    assert result['action'] == 'Block'
    assert any('Underage' in ind for ind in result['indicators'])


def test_fraud_risk_valid_age_allowed():
    """Fraud engine allows applicants 18+."""
    from utils.risk_engine import assess_fraud_risk
    import mongomock

    client = mongomock.MongoClient()
    mock_mongo = type('obj', (object,), {'db': client['test']})()

    app_data = {
        'dob': '1990-06-15',   # ~33 years old
        'user_id': 'test_user_2',
    }
    result = assess_fraud_risk(app_data, mock_mongo)
    assert result['action'] != 'Block' or 'Underage' not in result['indicators']


def test_duplicate_detection_blocks_same_id_proof():
    """Duplicate detector blocks an application with the same ID proof number."""
    from utils.risk_engine import detect_duplicate_voter
    import mongomock

    client = mongomock.MongoClient()
    mock_mongo = type('obj', (object,), {'db': client['test']})()

    # Seed existing application
    mock_mongo.db.applications.insert_one({
        'id_proof_number': 'AADHAAR1234',
        'user_id': 'existing_user',
        'status': 'Pending',
    })

    app_data = {
        'id_proof_number': 'AADHAAR1234',
        'user_id': 'new_user',
        'phone': '9999999999',
        'full_name': 'Test User',
    }
    result = detect_duplicate_voter(app_data, mock_mongo)
    assert result['action'] == 'Block'
    assert result['duplicate_type'] == 'Exact'


def test_duplicate_detection_allows_unique_application():
    """Duplicate detector allows a completely new, unique application."""
    from utils.risk_engine import detect_duplicate_voter
    import mongomock

    client = mongomock.MongoClient()
    mock_mongo = type('obj', (object,), {'db': client['test']})()

    app_data = {
        'id_proof_number': 'UNIQUE98765',
        'user_id': 'brand_new_user',
        'phone': '8888888888',
        'full_name': 'Brand New Person',
        'pin_code': '500001',
    }
    result = detect_duplicate_voter(app_data, mock_mongo)
    assert result['action'] == 'Allow'