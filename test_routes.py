import unittest
from app import create_app
from flask_login import current_user

class TestRoutes(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

    def tearDown(self):
        self.app_context.pop()

    def test_landing_page(self):
        print("Testing Landing Page...")
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Voter Registration', response.data)
        print("Landing Page OK")

    def test_dashboard_redirect(self):
        print("Testing Dashboard Access (Unauth)...")
        response = self.client.get('/dashboard')
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn(b'/login', response.data)
        print("Dashboard Redirect OK")

    def test_login_page(self):
        print("Testing Login Page...")
        response = self.client.get('/login')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Login', response.data)
        print("Login Page OK")

    def test_register_page(self):
        print("Testing Register Page...")
        response = self.client.get('/register')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Register', response.data)
        print("Register Page OK")
    
    def test_services_section_content(self):
        print("Testing Services Section Content...")
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        # Check for key services text
        self.assertIn(b'New Registration', response.data)
        self.assertIn(b'Track Status', response.data)
        self.assertIn(b'Download e-EPIC', response.data)
        print("Services Content OK")

    def test_responsive_elements(self):
        print("Testing Responsive Elements...")
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        # Check for mobile menu button
        self.assertIn(b'mobile-menu-btn', response.data)
        self.assertIn(b'mobile-menu', response.data)
        print("Responsive Elements OK")

if __name__ == '__main__':
    unittest.main()
