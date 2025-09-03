import pytest
from decimal import Decimal
from finance.models import BankAccount
from rest_framework import status

pytestmark = pytest.mark.django_db


class TestAccountTransfers:
    """Test money transfers between accounts."""

    def test_successful_transfer(self, authenticated_client):
        """Test transferring money between accounts."""
        # Create two accounts
        source = BankAccount.objects.create(
            user=authenticated_client.user,
            account_name='Source Account',
            account_type='current',
            bank_name='Test Bank',
            account_number_masked='****1111',
            current_balance=Decimal('1000.00')
        )

        target = BankAccount.objects.create(
            user=authenticated_client.user,
            account_name='Target Account',
            account_type='savings',
            bank_name='Test Bank',
            account_number_masked='****2222',
            current_balance=Decimal('500.00')
        )

        # Perform transfer
        response = authenticated_client.post(
            f'/api/accounts/{source.bank_account_id}/transfer/',
            {
                'target_account_id': str(target.bank_account_id),
                'amount': '200.00',
                'description': 'Test transfer'
            }
        )

        assert response.status_code == status.HTTP_201_CREATED

        # Verify balances
        source.refresh_from_db()
        target.refresh_from_db()
        assert source.current_balance == Decimal('800.00')
        assert target.current_balance == Decimal('700.00')

    def test_transfer_insufficient_funds(self, authenticated_client):
        """Test transfer with insufficient funds is rejected."""
        source = BankAccount.objects.create(
            user=authenticated_client.user,
            account_name='Poor Account',
            account_type='current',
            bank_name='Test Bank',
            account_number_masked='****3333',
            current_balance=Decimal('50.00')
        )

        target = BankAccount.objects.create(
            user=authenticated_client.user,
            account_name='Target Account',
            account_type='savings',
            bank_name='Test Bank',
            account_number_masked='****4444',
            current_balance=Decimal('100.00')
        )

        response = authenticated_client.post(
            f'/api/accounts/{source.bank_account_id}/transfer/',
            {
                'target_account_id': str(target.bank_account_id),
                'amount': '100.00',
                'description': 'Too much'
            }
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'Insufficient funds' in str(response.data)
