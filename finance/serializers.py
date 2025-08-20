from rest_framework import serializers
from django.db import transaction
from django.core.cache import cache
from decimal import Decimal
from datetime import date, timedelta

from .models import Transaction, Category, BankAccount


class TransactionSerializer(serializers.ModelSerializer):
    """Transaction serializer with comprehensive validation and security."""

    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    category_name = serializers.CharField(
        source='category.category_name', read_only=True)
    account_name = serializers.CharField(
        source='bank_account.account_name', read_only=True)
    formatted_amount = serializers.SerializerMethodField(read_only=True)

    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.none(),
        required=True
    )
    bank_account = serializers.PrimaryKeyRelatedField(
        queryset=BankAccount.objects.none(),
        required=True
    )

    class Meta:
        model = Transaction
        fields = [
            'transaction_id', 'user', 'bank_account', 'account_name',
            'category', 'category_name', 'transaction_description',
            'transaction_type', 'transaction_amount', 'formatted_amount',
            'transaction_date', 'transaction_note', 'reference_number',
            'is_recurring', 'created_at', 'updated_at'
        ]
        read_only_fields = ['transaction_id', 'created_at', 'updated_at']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            self.fields['category'].queryset = Category.objects.filter(
                user=request.user,
                is_active=True
            ).select_related('user')
            self.fields['bank_account'].queryset = BankAccount.objects.filter(
                user=request.user,
                is_active=True
            ).select_related('user')

    def get_formatted_amount(self, obj):
        amount = obj.transaction_amount
        currency_symbol = '£' if obj.bank_account.currency == 'GBP' else obj.bank_account.currency

        if amount >= 0:
            return f"+{currency_symbol}{amount:,.2f}"
        return f"-{currency_symbol}{abs(amount):,.2f}"

    def validate_transaction_amount(self, value):
        if value == 0:
            raise serializers.ValidationError(
                "Transaction amount cannot be zero.")

        if abs(value) > Decimal('999999.99'):
            raise serializers.ValidationError(
                "Transaction amount exceeds maximum allowed value."
            )

        return value

    def validate_transaction_date(self, value):
        if value > date.today() + timedelta(days=1):
            raise serializers.ValidationError(
                "Transaction date cannot be more than one day in the future."
            )

        if value < date.today() - timedelta(days=365 * 2):
            raise serializers.ValidationError(
                "Transaction date cannot be more than 2 years in the past."
            )

        return value

    def validate_transaction_description(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError(
                "Transaction description is required.")

        cleaned = value.strip()
        if len(cleaned) < 2:
            raise serializers.ValidationError(
                "Transaction description must be at least 2 characters."
            )

        if len(cleaned) > 255:
            raise serializers.ValidationError(
                "Transaction description cannot exceed 255 characters."
            )

        return cleaned

    def validate_reference_number(self, value):
        if value:
            cleaned = value.strip().upper()
            if len(cleaned) > 100:
                raise serializers.ValidationError(
                    "Reference number cannot exceed 100 characters."
                )
            return cleaned
        return value

    def validate(self, attrs):
        category = attrs.get('category')
        transaction_type = attrs.get('transaction_type')
        bank_account = attrs.get('bank_account')
        transaction_amount = attrs.get('transaction_amount')

        if category and transaction_type:
            if transaction_type != 'transfer' and category.category_type != transaction_type:
                raise serializers.ValidationError({
                    'transaction_type': f'Transaction type must match category type ({category.category_type}).'
                })

        if bank_account and transaction_amount:
            if bank_account.account_type != 'credit' and transaction_type == 'expense':
                expected_balance = bank_account.current_balance + transaction_amount
                if expected_balance < Decimal('0'):
                    raise serializers.ValidationError({
                        'transaction_amount': 'Insufficient funds. This transaction would result in a negative balance.'
                    })

        if transaction_type == 'expense' and transaction_amount > 0:
            attrs['transaction_amount'] = -abs(transaction_amount)
        elif transaction_type == 'income' and transaction_amount < 0:
            attrs['transaction_amount'] = abs(transaction_amount)

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        transaction_obj = super().create(validated_data)

        self._update_account_balance(
            transaction_obj.bank_account,
            transaction_obj.transaction_amount
        )

        self._invalidate_cache(transaction_obj.user.id)

        return transaction_obj

    @transaction.atomic
    def update(self, instance, validated_data):
        old_amount = instance.transaction_amount
        old_account = instance.bank_account

        updated_transaction = super().update(instance, validated_data)

        if old_account == updated_transaction.bank_account:
            amount_difference = updated_transaction.transaction_amount - old_amount
            if amount_difference != 0:
                self._update_account_balance(
                    updated_transaction.bank_account,
                    amount_difference
                )
        else:
            self._update_account_balance(old_account, -old_amount)
            self._update_account_balance(
                updated_transaction.bank_account,
                updated_transaction.transaction_amount
            )

        self._invalidate_cache(updated_transaction.user.id)

        return updated_transaction

    def _update_account_balance(self, account, amount):
        account.current_balance += amount
        account.save(update_fields=['current_balance', 'updated_at'])

    def _invalidate_cache(self, user_id):
        cache_keys = [
            f'user_transactions_{user_id}',
            f'user_balance_{user_id}',
            f'user_statistics_{user_id}'
        ]
        cache.delete_many(cache_keys)
