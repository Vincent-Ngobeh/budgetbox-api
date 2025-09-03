import pytest
from decimal import Decimal
from datetime import date
from finance.models import Transaction, BankAccount
from rest_framework import status

pytestmark = pytest.mark.django_db


class TestTransactionCreation:
    """Test transaction creation and balance updates."""

    def test_create_expense_transaction(self, authenticated_client, sample_account, sample_category):
        """Test creating an expense reduces account balance."""
        initial_balance = sample_account.current_balance

        response = authenticated_client.post('/api/transactions/', {
            'bank_account': str(sample_account.bank_account_id),
            'category': str(sample_category.category_id),
            'transaction_description': 'Test expense',
            'transaction_type': 'expense',
            'transaction_amount': '50.00',
            'transaction_date': date.today().isoformat()
        })

        assert response.status_code == status.HTTP_201_CREATED

        # Verify balance was updated
        sample_account.refresh_from_db()
        assert sample_account.current_balance == initial_balance - \
            Decimal('50.00')

        # Verify transaction amount is negative
        transaction = Transaction.objects.get(
            transaction_id=response.data['transaction_id']
        )
        assert transaction.transaction_amount == Decimal('-50.00')

    def test_create_income_transaction(self, authenticated_client, sample_account):
        """Test creating income increases account balance."""
        from finance.models import Category
        income_category = Category.objects.create(
            user=authenticated_client.user,
            category_name='Salary',
            category_type='income'
        )

        initial_balance = sample_account.current_balance

        response = authenticated_client.post('/api/transactions/', {
            'bank_account': str(sample_account.bank_account_id),
            'category': str(income_category.category_id),
            'transaction_description': 'Monthly salary',
            'transaction_type': 'income',
            'transaction_amount': '2500.00',
            'transaction_date': date.today().isoformat()
        })

        assert response.status_code == status.HTTP_201_CREATED

        # Verify balance was updated
        sample_account.refresh_from_db()
        assert sample_account.current_balance == initial_balance + \
            Decimal('2500.00')

    def test_insufficient_funds_rejected(self, authenticated_client, sample_account, sample_category):
        """Test that transactions causing negative balance are rejected."""
        sample_account.current_balance = Decimal('100.00')
        sample_account.save()

        response = authenticated_client.post('/api/transactions/', {
            'bank_account': str(sample_account.bank_account_id),
            'category': str(sample_category.category_id),
            'transaction_description': 'Large expense',
            'transaction_type': 'expense',
            'transaction_amount': '200.00',
            'transaction_date': date.today().isoformat()
        })

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'Insufficient funds' in str(response.data)


class TestTransactionFiltering:
    """Test transaction list filtering."""

    def test_user_sees_only_own_transactions(self, authenticated_client, sample_account, sample_category):
        """Test users only see their own transactions."""
        # Create a transaction
        Transaction.objects.create(
            user=authenticated_client.user,
            bank_account=sample_account,
            category=sample_category,
            transaction_description='My transaction',
            transaction_type='expense',
            transaction_amount=Decimal('-25.00'),
            transaction_date=date.today()
        )

        # Create another user with a transaction
        from django.contrib.auth.models import User
        other_user = User.objects.create_user(
            'otheruser', 'other@example.com', 'pass123')
        other_account = BankAccount.objects.create(
            user=other_user,
            account_name='Other Account',
            account_type='current',
            bank_name='Other Bank',
            account_number_masked='****5678',
            current_balance=Decimal('500.00')
        )
        from finance.models import Category
        other_category = Category.objects.create(
            user=other_user,
            category_name='Other Category',
            category_type='expense'
        )
        Transaction.objects.create(
            user=other_user,
            bank_account=other_account,
            category=other_category,
            transaction_description='Other transaction',
            transaction_type='expense',
            transaction_amount=Decimal('-50.00'),
            transaction_date=date.today()
        )

        # Request transactions
        response = authenticated_client.get('/api/transactions/')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 1
        assert response.data['results'][0]['transaction_description'] == 'My transaction'
