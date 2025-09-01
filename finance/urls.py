from django.urls import path, include
from rest_framework.routers import DefaultRouter
from finance.views import (
    TransactionViewSet,
    BudgetViewSet,
    CategoryViewSet,
    BankAccountViewSet
)

router = DefaultRouter()

router.register(r'accounts', BankAccountViewSet, basename='bankaccount')
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'transactions', TransactionViewSet, basename='transaction')
router.register(r'budgets', BudgetViewSet, basename='budget')

app_name = 'finance'

urlpatterns = [
    path('', include(router.urls)),
]
