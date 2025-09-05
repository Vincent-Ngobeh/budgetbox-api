import pytest
from rest_framework import status

pytestmark = pytest.mark.django_db


class TestAPIEndpoints:
    """Test API endpoint accessibility and authentication."""

    def test_unauthenticated_requests_rejected(self, api_client):
        """Test that protected endpoints require authentication."""
        endpoints = [
            '/api/accounts/',
            '/api/categories/',
            '/api/transactions/',
            '/api/budgets/',
        ]

        for endpoint in endpoints:
            response = api_client.get(endpoint)
            assert response.status_code == status.HTTP_401_UNAUTHORIZED
            assert 'Authentication credentials were not provided' in str(
                response.data)

    def test_public_endpoints_accessible(self, api_client):
        """Test that public endpoints work without authentication."""
        # Registration should be public
        # Invalid data but endpoint is accessible
        response = api_client.post('/api/auth/register/', {})
        # Bad request, not unauthorized
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        # Login should be public
        response = api_client.post('/api/auth/login/', {})
        # Bad request, not unauthorized
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_invalid_token_rejected(self, api_client):
        """Test that invalid tokens are rejected."""
        api_client.credentials(HTTP_AUTHORIZATION='Token invalid123token')

        response = api_client.get('/api/transactions/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
