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
        primary_key=True, default=uuid.uuid4, editable=True)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='bank_accounts')
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
