import pytest
from finance.models import Category, Transaction
from rest_framework import status
from decimal import Decimal
from datetime import date

pytestmark = pytest.mark.django_db


class TestCategoryManagement:
    """Test category creation and management."""

    def test_create_category(self, authenticated_client):
        """Test creating a new expense category."""
        response = authenticated_client.post('/api/categories/', {
            'category_name': 'Entertainment',
            'category_type': 'expense'
        })

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['category_name'] == 'Entertainment'
        assert response.data['category_type'] == 'expense'

    def test_duplicate_category_rejected(self, authenticated_client):
        """Test that duplicate categories are rejected."""
        # Create first category
        Category.objects.create(
            user=authenticated_client.user,
            category_name='Food',
            category_type='expense'
        )

        # Try to create duplicate
        response = authenticated_client.post('/api/categories/', {
            'category_name': 'Food',
            'category_type': 'expense'
        })

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'already have' in str(response.data)

    def test_list_categories_by_type(self, authenticated_client):
        """Test filtering categories by type."""
        # Create mixed categories
        Category.objects.create(
            user=authenticated_client.user,
            category_name='Salary',
            category_type='income'
        )
        Category.objects.create(
            user=authenticated_client.user,
            category_name='Rent',
            category_type='expense'
        )
        Category.objects.create(
            user=authenticated_client.user,
            category_name='Freelance',
            category_type='income'
        )

        # Get only income categories
        response = authenticated_client.get('/api/categories/?type=income')

        assert response.status_code == status.HTTP_200_OK
        assert all(cat['category_type'] ==
                   'income' for cat in response.data['results'])
        assert len(response.data['results']) == 2

    def test_category_usage_statistics(self, authenticated_client, sample_account):
        """Test getting category usage statistics."""
        category = Category.objects.create(
            user=authenticated_client.user,
            category_name='Shopping',
            category_type='expense'
        )

        # Create some transactions
        for i in range(3):
            Transaction.objects.create(
                user=authenticated_client.user,
                bank_account=sample_account,
                category=category,
                transaction_description=f'Purchase {i+1}',
                transaction_type='expense',
                transaction_amount=Decimal(f'-{(i+1)*50}.00'),
                transaction_date=date.today()
            )

        response = authenticated_client.get(
            f'/api/categories/{category.category_id}/usage/')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['summary']['transaction_count'] == 3
        # 50 + 100 + 150
        assert response.data['summary']['total_amount'] == 300.00

    def test_cannot_delete_category_with_transactions(self, authenticated_client, sample_account):
        """Test that categories with transactions cannot be deleted."""
        category = Category.objects.create(
            user=authenticated_client.user,
            category_name='Transport',
            category_type='expense'
        )

        # Create a transaction using this category
        Transaction.objects.create(
            user=authenticated_client.user,
            bank_account=sample_account,
            category=category,
            transaction_description='Bus fare',
            transaction_type='expense',
            transaction_amount=Decimal('-5.00'),
            transaction_date=date.today()
        )

        # Try to delete category
        response = authenticated_client.delete(
            f'/api/categories/{category.category_id}/')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'Cannot delete category with' in str(response.data)

    def test_set_default_categories(self, authenticated_client):
        """Test creating default categories for new user."""
        response = authenticated_client.post('/api/categories/set_defaults/')

        assert response.status_code in [
            status.HTTP_200_OK, status.HTTP_201_CREATED]

        # Verify categories were created
        categories = Category.objects.filter(user=authenticated_client.user)
        assert categories.filter(category_type='income').exists()
        assert categories.filter(category_type='expense').exists()
        assert categories.filter(is_default=True).exists()
