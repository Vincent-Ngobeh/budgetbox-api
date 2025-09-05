import pytest
from decimal import Decimal
from datetime import date, timedelta
from finance.models import BankAccount, Category, Transaction, Budget
from rest_framework import status

pytestmark = pytest.mark.django_db


class TestBusinessRules:
    """Test critical business logic and rules."""

    def test_expense_always_negative_income_always_positive(self, authenticated_client, sample_account):
        """Test that amounts are automatically adjusted based on transaction type."""
        expense_cat = Category.objects.create(
            user=authenticated_client.user,
            category_name='Bills',
            category_type='expense'
        )
        income_cat = Category.objects.create(
            user=authenticated_client.user,
            category_name='Bonus',
            category_type='income'
        )

        response = authenticated_client.post('/api/transactions/', {
            'bank_account': str(sample_account.bank_account_id),
            'category': str(expense_cat.category_id),
            'transaction_description': 'Electric bill',
            'transaction_type': 'expense',
            'transaction_amount': '100.00',
            'transaction_date': date.today().isoformat()
        })

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['transaction_amount'] == '-100.00'

        response = authenticated_client.post('/api/transactions/', {
            'bank_account': str(sample_account.bank_account_id),
            'category': str(income_cat.category_id),
            'transaction_description': 'Performance bonus',
            'transaction_type': 'income',
            'transaction_amount': '-500.00',
            'transaction_date': date.today().isoformat()
        })

        assert response.status_code == status.HTTP_201_CREATED
        assert float(response.data['transaction_amount']) == 500.00

    def test_credit_account_allows_negative_balance(self, authenticated_client):
        """Test that credit accounts can have negative balance."""
        credit_account = BankAccount.objects.create(
            user=authenticated_client.user,
            account_name='Credit Card',
            account_type='credit',
            bank_name='Credit Bank',
            account_number_masked='****1234',
            current_balance=Decimal('-500.00')
        )

        expense_cat = Category.objects.create(
            user=authenticated_client.user,
            category_name='Shopping',
            category_type='expense'
        )

        response = authenticated_client.post('/api/transactions/', {
            'bank_account': str(credit_account.bank_account_id),
            'category': str(expense_cat.category_id),
            'transaction_description': 'Online shopping',
            'transaction_type': 'expense',
            'transaction_amount': '200.00',
            'transaction_date': date.today().isoformat()
        })

        assert response.status_code == status.HTTP_201_CREATED

        credit_account.refresh_from_db()
        assert credit_account.current_balance == Decimal('-700.00')

    def test_budget_overlap_prevention(self, authenticated_client):
        """Test that overlapping budgets for same category are prevented."""
        category = Category.objects.create(
            user=authenticated_client.user,
            category_name='Food',
            category_type='expense'
        )

        today = date.today()
        first_start = today
        first_end = today + timedelta(days=30)

        response = authenticated_client.post('/api/budgets/', {
            'category': str(category.category_id),
            'budget_name': 'Food Budget 1',
            'budget_amount': '500.00',
            'budget_type': 'monthly',
            'period_type': 'monthly',
            'start_date': first_start.isoformat(),
            'end_date': first_end.isoformat()
        })

        assert response.status_code == status.HTTP_201_CREATED

        second_start = today + timedelta(days=15)
        second_end = today + timedelta(days=45)

        response = authenticated_client.post('/api/budgets/', {
            'category': str(category.category_id),
            'budget_name': 'Food Budget 2',
            'budget_amount': '600.00',
            'budget_type': 'monthly',
            'period_type': 'monthly',
            'start_date': second_start.isoformat(),
            'end_date': second_end.isoformat()
        })

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'budget already exists' in str(response.data).lower()

    def test_transaction_date_validation(self, authenticated_client, sample_account, sample_category):
        """Test transaction date cannot be too far in past or future."""
        response = authenticated_client.post('/api/transactions/', {
            'bank_account': str(sample_account.bank_account_id),
            'category': str(sample_category.category_id),
            'transaction_description': 'Future transaction',
            'transaction_type': 'expense',
            'transaction_amount': '50.00',
            'transaction_date': (date.today() + timedelta(days=7)).isoformat()
        })

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'cannot be more than one day in the future' in str(
            response.data)

        response = authenticated_client.post('/api/transactions/', {
            'bank_account': str(sample_account.bank_account_id),
            'category': str(sample_category.category_id),
            'transaction_description': 'Ancient transaction',
            'transaction_type': 'expense',
            'transaction_amount': '50.00',
            'transaction_date': (date.today() - timedelta(days=800)).isoformat()
        })

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'cannot be more than 2 years in the past' in str(response.data)
