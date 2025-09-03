import pytest
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.authtoken.models import Token

pytestmark = pytest.mark.django_db


class TestUserRegistration:
    """Test user registration functionality."""

    def test_successful_registration(self, api_client):
        """Test that users can register with valid data."""
        response = api_client.post('/api/auth/register/', {
            'username': 'newuser',
            'email': 'new@example.com',
            'password': 'securepass123',
            'first_name': 'New',
            'last_name': 'User'
        })

        assert response.status_code == status.HTTP_201_CREATED
        assert 'token' in response.data
        assert response.data['user']['username'] == 'newuser'

        # Verify user was created
        assert User.objects.filter(username='newuser').exists()

        # Verify token was created
        user = User.objects.get(username='newuser')
        assert Token.objects.filter(user=user).exists()

    def test_registration_creates_default_categories(self, api_client):
        """Test that registration creates default categories."""
        response = api_client.post('/api/auth/register/', {
            'username': 'catuser',
            'email': 'cat@example.com',
            'password': 'securepass123',
            'first_name': 'Cat',
            'last_name': 'User'
        })

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['categories_created'] > 0

        # Verify categories exist
        from finance.models import Category
        user = User.objects.get(username='catuser')
        categories = Category.objects.filter(user=user)
        assert categories.exists()
        assert categories.filter(category_type='income').exists()
        assert categories.filter(category_type='expense').exists()

    def test_duplicate_username_rejected(self, api_client, create_user):
        """Test that duplicate usernames are rejected."""
        create_user(username='existing')

        response = api_client.post('/api/auth/register/', {
            'username': 'existing',
            'email': 'different@example.com',
            'password': 'securepass123',
            'first_name': 'New',
            'last_name': 'User'
        })

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'username' in response.data


class TestUserLogin:
    """Test user login functionality."""

    def test_successful_login(self, api_client, create_user):
        """Test login with valid credentials."""
        create_user(username='loginuser', password='testpass123')

        response = api_client.post('/api/auth/login/', {
            'username': 'loginuser',
            'password': 'testpass123'
        })

        assert response.status_code == status.HTTP_200_OK
        assert 'token' in response.data
        assert response.data['user']['username'] == 'loginuser'

    def test_invalid_credentials_rejected(self, api_client, create_user):
        """Test login with invalid credentials."""
        create_user(username='testuser', password='correctpass')

        response = api_client.post('/api/auth/login/', {
            'username': 'testuser',
            'password': 'wrongpass'
        })

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert 'error' in response.data
