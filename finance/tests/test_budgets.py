import pytest
from decimal import Decimal
from datetime import date, timedelta
from finance.models import Budget, Category, Transaction
from rest_framework import status

pytestmark = pytest.mark.django_db


class TestBudgetTracking:
    """Test budget creation and tracking."""

    def test_budget_spending_calculation(self, authenticated_client, sample_account):
        """Test that budget correctly calculates spending."""
        # Create category and budget
        category = Category.objects.create(
            user=authenticated_client.user,
            category_name='Food',
            category_type='expense'
        )

        budget = Budget.objects.create(
            user=authenticated_client.user,
            category=category,
            budget_name='Monthly Food Budget',
            budget_amount=Decimal('500.00'),
            budget_type='monthly',
            period_type='monthly',
            start_date=date.today().replace(day=1),
            end_date=date.today().replace(day=28)
        )

        # Create transactions
        Transaction.objects.create(
            user=authenticated_client.user,
            bank_account=sample_account,
            category=category,
            transaction_description='Groceries',
            transaction_type='expense',
            transaction_amount=Decimal('-150.00'),
            transaction_date=date.today()
        )

        Transaction.objects.create(
            user=authenticated_client.user,
            bank_account=sample_account,
            category=category,
            transaction_description='Restaurant',
            transaction_type='expense',
            transaction_amount=Decimal('-75.00'),
            transaction_date=date.today()
        )

        # Get budget progress
        response = authenticated_client.get(
            f'/api/budgets/{budget.budget_id}/progress/')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['spending']['total_spent'] == 225.00
        assert response.data['spending']['remaining'] == 275.00
