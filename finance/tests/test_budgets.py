import pytest
from decimal import Decimal
from django.contrib.auth.models import User
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


class TestBudgetActions:
    """Test budget deactivate and reactivate actions."""

    def test_deactivate_active_budget(self, authenticated_client):
        """Test deactivating an active budget."""
        category = Category.objects.create(
            user=authenticated_client.user,
            category_name='Food',
            category_type='expense'
        )

        budget = Budget.objects.create(
            user=authenticated_client.user,
            category=category,
            budget_name='Monthly Food',
            budget_amount=Decimal('500.00'),
            period_type='monthly',
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30),
            is_active=True
        )

        response = authenticated_client.post(
            f'/api/budgets/{budget.budget_id}/deactivate/'
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data['message'] == 'Budget deactivated successfully'
        assert response.data['budget']['is_active'] == False

        budget.refresh_from_db()
        assert budget.is_active == False

    def test_deactivate_already_inactive_budget(self, authenticated_client):
        """Test deactivating already inactive budget fails."""
        category = Category.objects.create(
            user=authenticated_client.user,
            category_name='Food',
            category_type='expense'
        )

        budget = Budget.objects.create(
            user=authenticated_client.user,
            category=category,
            budget_name='Monthly Food',
            budget_amount=Decimal('500.00'),
            period_type='monthly',
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30),
            is_active=False
        )

        response = authenticated_client.post(
            f'/api/budgets/{budget.budget_id}/deactivate/'
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'already inactive' in response.data['error']

    def test_reactivate_inactive_budget(self, authenticated_client):
        """Test reactivating inactive budget with no overlaps."""
        category = Category.objects.create(
            user=authenticated_client.user,
            category_name='Food',
            category_type='expense'
        )

        budget = Budget.objects.create(
            user=authenticated_client.user,
            category=category,
            budget_name='Monthly Food',
            budget_amount=Decimal('500.00'),
            period_type='monthly',
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30),
            is_active=False
        )

        response = authenticated_client.post(
            f'/api/budgets/{budget.budget_id}/reactivate/'
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data['message'] == 'Budget reactivated successfully'
        assert response.data['budget']['is_active'] == True

        budget.refresh_from_db()
        assert budget.is_active == True

    def test_reactivate_with_overlapping_active_budget(self, authenticated_client):
        """Test reactivate fails when overlapping active budget exists."""
        category = Category.objects.create(
            user=authenticated_client.user,
            category_name='Food',
            category_type='expense'
        )

        Budget.objects.create(
            user=authenticated_client.user,
            category=category,
            budget_name='Active Food Budget',
            budget_amount=Decimal('400.00'),
            period_type='monthly',
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30),
            is_active=True
        )

        inactive_budget = Budget.objects.create(
            user=authenticated_client.user,
            category=category,
            budget_name='Inactive Food Budget',
            budget_amount=Decimal('500.00'),
            period_type='monthly',
            start_date=date.today() + timedelta(days=15),
            end_date=date.today() + timedelta(days=45),
            is_active=False
        )

        response = authenticated_client.post(
            f'/api/budgets/{inactive_budget.budget_id}/reactivate/'
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'another budget overlaps this period' in response.data['error']

        inactive_budget.refresh_from_db()
        assert inactive_budget.is_active == False

    def test_deactivate_reactivate_workflow(self, authenticated_client):
        """Test complete deactivate then reactivate workflow."""
        category = Category.objects.create(
            user=authenticated_client.user,
            category_name='Food',
            category_type='expense'
        )

        budget = Budget.objects.create(
            user=authenticated_client.user,
            category=category,
            budget_name='Monthly Food',
            budget_amount=Decimal('500.00'),
            period_type='monthly',
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30),
            is_active=True
        )

        response = authenticated_client.post(
            f'/api/budgets/{budget.budget_id}/deactivate/'
        )
        assert response.status_code == status.HTTP_200_OK

        response = authenticated_client.post(
            f'/api/budgets/{budget.budget_id}/reactivate/'
        )
        assert response.status_code == status.HTTP_200_OK

        budget.refresh_from_db()
        assert budget.is_active == True
