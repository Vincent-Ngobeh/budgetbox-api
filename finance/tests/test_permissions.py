import pytest
from django.contrib.auth.models import User
from finance.models import BankAccount, Category, Transaction, Budget
from rest_framework import status
from decimal import Decimal
from datetime import date

pytestmark = pytest.mark.django_db


class TestDataIsolation:
    """Test that users can only access their own data."""

    def test_cannot_see_other_users_accounts(self, authenticated_client):
        """Test users cannot see other users' bank accounts."""
        # Create another user with an account
        other_user = User.objects.create_user(
            'otheruser', 'other@test.com', 'pass123')
        other_account = BankAccount.objects.create(
            user=other_user,
            account_name='Private Account',
            account_type='current',
            bank_name='Other Bank',
            account_number_masked='****9999',
            current_balance=Decimal('10000.00')
        )

        # Try to access it
        response = authenticated_client.get(
            f'/api/accounts/{other_account.bank_account_id}/')
        assert response.status_code == status.HTTP_404_NOT_FOUND

        # Verify it doesn't appear in list
        response = authenticated_client.get('/api/accounts/')
        assert response.status_code == status.HTTP_200_OK
        account_ids = [acc['bank_account_id']
                       for acc in response.data['results']]
        assert str(other_account.bank_account_id) not in account_ids

    def test_cannot_transfer_to_other_users_account(self, authenticated_client, sample_account):
        """Test users cannot transfer money to other users' accounts."""
        # Create another user's account
        other_user = User.objects.create_user(
            'richuser', 'rich@test.com', 'pass123')
        other_account = BankAccount.objects.create(
            user=other_user,
            account_name='Rich Account',
            account_type='savings',
            bank_name='Rich Bank',
            account_number_masked='****8888',
            current_balance=Decimal('50000.00')
        )

        # Try to transfer to it
        response = authenticated_client.post(
            f'/api/accounts/{sample_account.bank_account_id}/transfer/',
            {
                'target_account_id': str(other_account.bank_account_id),
                'amount': '100.00',
                'description': 'Sneaky transfer'
            }
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_cannot_use_other_users_category(self, authenticated_client, sample_account):
        """Test users cannot create transactions with other users' categories."""
        # Create another user's category
        other_user = User.objects.create_user(
            'catowner', 'cat@test.com', 'pass123')
        other_category = Category.objects.create(
            user=other_user,
            category_name='Private Category',
            category_type='expense'
        )

        # Try to use it in a transaction
        response = authenticated_client.post('/api/transactions/', {
            'bank_account': str(sample_account.bank_account_id),
            'category': str(other_category.category_id),
            'transaction_description': 'Using wrong category',
            'transaction_type': 'expense',
            'transaction_amount': '25.00',
            'transaction_date': date.today().isoformat()
        })

        assert response.status_code == status.HTTP_400_BAD_REQUEST
