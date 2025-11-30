import pytest
from django.contrib.auth.models import User
from rest_framework import status

pytestmark = pytest.mark.django_db


class TestUserProfile:
    """Test user profile management."""

    def test_get_user_profile(self, authenticated_client):
        """Test retrieving user profile with financial summary."""
        response = authenticated_client.get('/api/auth/profile/')

        assert response.status_code == status.HTTP_200_OK
        assert 'username' in response.data
        assert 'email' in response.data
        assert 'financial_summary' in response.data
        assert 'net_worth' in response.data['financial_summary']

    def test_update_user_profile(self, authenticated_client):
        """Test updating user profile information."""
        response = authenticated_client.patch('/api/auth/profile/update/', {
            'first_name': 'Updated',
            'last_name': 'Name',
            'email': 'updated@example.com'
        })

        assert response.status_code == status.HTTP_200_OK
        assert response.data['user']['first_name'] == 'Updated'
        assert response.data['user']['email'] == 'updated@example.com'

        # Verify in database
        user = User.objects.get(username=authenticated_client.user.username)
        assert user.first_name == 'Updated'

    def test_update_password(self, authenticated_client):
        """Test changing user password via change-password endpoint."""
        # Set a known password first
        authenticated_client.user.set_password('oldpassword123')
        authenticated_client.user.save()

        response = authenticated_client.post('/api/auth/change-password/', {
            'current_password': 'oldpassword123',
            'new_password': 'newsecurepass456'
        })

        assert response.status_code == status.HTTP_200_OK

        # Verify password was changed
        user = User.objects.get(username=authenticated_client.user.username)
        assert user.check_password('newsecurepass456')

    def test_logout_deletes_token(self, authenticated_client):
        """Test that logout properly deletes auth token."""
        from rest_framework.authtoken.models import Token

        # Verify token exists
        assert Token.objects.filter(user=authenticated_client.user).exists()

        # Logout
        response = authenticated_client.post('/api/auth/logout/')
        assert response.status_code == status.HTTP_200_OK

        # Verify token was deleted
        assert not Token.objects.filter(
            user=authenticated_client.user).exists()

        # Verify subsequent requests fail
        response = authenticated_client.get('/api/transactions/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
