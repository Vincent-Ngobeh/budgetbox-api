import pytest
from rest_framework.test import APIClient
from django.contrib.auth.models import User
from decimal import Decimal
from datetime import date, timedelta


@pytest.fixture
def api_client():
    """Provide an API client for testing."""
    return APIClient()


@pytest.fixture
def create_user():
    """Factory for creating test users."""
    def _create_user(username='testuser', email='test@example.com', password='testpass123'):
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name='Test',
            last_name='User'
        )
        return user
    return _create_user


@pytest.fixture
def authenticated_client(api_client, create_user):
    """Provide an authenticated API client."""
    user = create_user()
    from rest_framework.authtoken.models import Token
    token = Token.objects.create(user=user)
    api_client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
    api_client.user = user
    return api_client


@pytest.fixture
def sample_category(authenticated_client):
    """Create a sample expense category."""
    from finance.models import Category
    return Category.objects.create(
        user=authenticated_client.user,
        category_name='Groceries',
        category_type='expense'
    )


@pytest.fixture
def sample_account(authenticated_client):
    """Create a sample bank account."""
    from finance.models import BankAccount
    return BankAccount.objects.create(
        user=authenticated_client.user,
        account_name='Test Current Account',
        account_type='current',
        bank_name='Test Bank',
        account_number_masked='****1234',
        current_balance=Decimal('1000.00')
    )
