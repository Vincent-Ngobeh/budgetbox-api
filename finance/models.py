import uuid
from django.db import models
from django.contrib.auth.models import User


class BankAccount(models.Model):
    ACCOUNT_TYPES = [
        ('current', 'Current'),
        ('savings', 'Savings'),
        ('isa', 'ISA'),
        ('credit', 'Credit'),
    ]

    CURRENCY_CHOICES = [
        ('GBP', 'British Pound'),
        ('USD', 'US Dollar'),
        ('EUR', 'Euro'),
    ]

    bank_account_id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False)  
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='user_bank_accounts')
    account_name = models.CharField(max_length=100)
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPES)
    bank_name = models.CharField(max_length=100)
    account_number_masked = models.CharField(max_length=20)
    currency = models.CharField(
        max_length=3, choices=CURRENCY_CHOICES, default='GBP')
    current_balance = models.DecimalField(max_digits=15, decimal_places=2)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "bank_account"

    def __str__(self):
        return f"{self.account_name} - {self.bank_name}"


class Category(models.Model):
    CATEGORY_TYPES = [
        ('income', 'Income'),
        ('expense', 'Expense'),
    ]

    category_id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='user_categories')
    category_name = models.CharField(max_length=50)
    category_type = models.CharField(max_length=20, choices=CATEGORY_TYPES)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "category"

    def __str__(self):
        return f"{self.category_name} ({self.category_type})"


class Transaction(models.Model):
    TRANSACTION_TYPES = [
        ('income', 'Income'),
        ('expense', 'Expense'),
        ('transfer', 'Transfer'),
    ]

    transaction_id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='user_transactions')
    bank_account = models.ForeignKey(
        BankAccount, on_delete=models.CASCADE, related_name='bank_account_transactions')
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name='category_transactions')
    transaction_description = models.CharField(max_length=255)
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    transaction_amount = models.DecimalField(max_digits=15, decimal_places=2)
    transaction_date = models.DateField()
    transaction_note = models.TextField(blank=True, null=True)
    reference_number = models.CharField(max_length=100, blank=True, null=True)
    is_recurring = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "transaction"

    def __str__(self):
        return f"{self.transaction_description} - £{self.transaction_amount}"


class Budget(models.Model):
    BUDGET_TYPES = [
        ('monthly', 'Monthly'),
        ('weekly', 'Weekly'),
        ('yearly', 'Yearly'),
    ]

    PERIOD_TYPES = [
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly'),
    ]

    budget_id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='user_budgets')
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name='category_budgets')
    budget_name = models.CharField(max_length=100)
    budget_amount = models.DecimalField(max_digits=15, decimal_places=2)
    budget_type = models.CharField(max_length=20, choices=BUDGET_TYPES)
    period_type = models.CharField(max_length=20, choices=PERIOD_TYPES)
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "budget"

    def __str__(self):
        return f"{self.budget_name} - £{self.budget_amount}"