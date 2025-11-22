from django.contrib import admin
from .models import BankAccount, Category, Transaction, Budget


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = ['account_name', 'bank_name',
                    'account_type', 'current_balance', 'user']
    list_filter = ['account_type', 'is_active']


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['category_name', 'category_type', 'user', 'is_active']
    list_filter = ['category_type', 'is_active']


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['transaction_description',
                    'transaction_amount', 'transaction_type', 'user']
    list_filter = ['transaction_type', 'transaction_date']


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ['budget_name', 'budget_amount', 'period_type', 'user']
    list_filter = ['period_type', 'is_active']
