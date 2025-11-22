import uuid
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal


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
    category_type = models.CharField(max_length=10, choices=CATEGORY_TYPES)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "category"
        unique_together = [['user', 'category_name', 'category_type']]
        ordering = ['category_type', 'category_name']

    def __str__(self):
        return f"{self.category_name} ({self.category_type})"


class BankAccount(models.Model):
    ACCOUNT_TYPES = [
        ('current', 'Current Account'),
        ('savings', 'Savings Account'),
        ('credit', 'Credit Card'),
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
    account_number_masked = models.CharField(max_length=8)
    currency = models.CharField(
        max_length=3, choices=CURRENCY_CHOICES, default='GBP')
    current_balance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal('-10000.00')),
            MaxValueValidator(Decimal('9999999.99'))
        ]
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "bank_account"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.account_name} - {self.bank_name}"


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
        Category, on_delete=models.SET_NULL, null=True, related_name='category_transactions')
    transaction_description = models.CharField(max_length=255)
    transaction_type = models.CharField(
        max_length=10, choices=TRANSACTION_TYPES)
    transaction_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal('-999999.99')),
            MaxValueValidator(Decimal('999999.99'))
        ]
    )
    transaction_date = models.DateField()
    transaction_note = models.TextField(blank=True, null=True)
    reference_number = models.CharField(max_length=100, blank=True, null=True)
    is_recurring = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "transaction"
        ordering = ['-transaction_date', '-created_at']
        indexes = [
            models.Index(fields=['user', 'transaction_date']),
            models.Index(fields=['user', 'transaction_type']),
            models.Index(fields=['bank_account', 'transaction_date']),
        ]

    def __str__(self):
        return f"{self.transaction_description} - £{self.transaction_amount}"


class Budget(models.Model):
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
    period_type = models.CharField(max_length=20, choices=PERIOD_TYPES)
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "budget"
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.budget_name} - £{self.budget_amount}"
