from rest_framework import serializers
from django.contrib.auth.models import User
from django.db import transaction as db_transaction
from django.db.models import Sum, Q
from django.core.cache import cache
from decimal import Decimal
from datetime import date, timedelta
from .models import BankAccount, Category, Transaction, Budget


class UserSerializer(serializers.ModelSerializer):
    """User serializer for authentication and profile management."""

    password = serializers.CharField(
        write_only=True, min_length=8, required=False)
    total_accounts = serializers.IntegerField(
        read_only=True, source='user_bank_accounts.count')
    total_categories = serializers.IntegerField(
        read_only=True, source='user_categories.count')

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'password', 'date_joined', 'last_login',
            'total_accounts', 'total_categories'
        ]
        read_only_fields = ['id', 'date_joined', 'last_login']
        extra_kwargs = {
            'email': {'required': True},
            'first_name': {'required': True},
            'last_name': {'required': True}
        }

    def validate_email(self, value):
        if not value:
            raise serializers.ValidationError("Email is required.")

        email_lower = value.lower()
        user = self.context.get(
            'request').user if self.context.get('request') else None

        existing = User.objects.filter(email__iexact=email_lower)
        if self.instance:
            existing = existing.exclude(pk=self.instance.pk)
        elif user and user.is_authenticated:
            existing = existing.exclude(pk=user.pk)

        if existing.exists():
            raise serializers.ValidationError(
                "A user with this email already exists.")

        return email_lower

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        user = User.objects.create_user(**validated_data)
        if password:
            user.set_password(password)
            user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class CategorySerializer(serializers.ModelSerializer):
    """Category serializer for income/expense categorisation."""

    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    transaction_count = serializers.IntegerField(
        read_only=True, source='category_transactions.count')

    class Meta:
        model = Category
        fields = [
            'category_id', 'user', 'category_name', 'category_type',
            'is_default', 'is_active', 'transaction_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['category_id', 'created_at', 'updated_at']

    def validate_category_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Category name is required.")

        cleaned = value.strip().title()
        if len(cleaned) < 2:
            raise serializers.ValidationError(
                "Category name must be at least 2 characters.")
        if len(cleaned) > 50:
            raise serializers.ValidationError(
                "Category name cannot exceed 50 characters.")

        return cleaned

    def validate(self, attrs):
        user = self.context['request'].user
        category_name = attrs.get('category_name')
        category_type = attrs.get('category_type')

        if category_name and category_type:
            existing = Category.objects.filter(
                user=user,
                category_name__iexact=category_name,
                category_type=category_type
            )
            if self.instance:
                existing = existing.exclude(
                    category_id=self.instance.category_id)

            if existing.exists():
                raise serializers.ValidationError({
                    'category_name': f'You already have a {category_type} category named "{category_name}".'
                })

        return attrs


class BankAccountSerializer(serializers.ModelSerializer):
    """Bank account serializer with balance management."""

    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    bank_display = serializers.CharField(
        read_only=True, source='get_account_type_display')
    formatted_balance = serializers.SerializerMethodField(read_only=True)
    transaction_count = serializers.IntegerField(
        read_only=True, source='bank_account_transactions.count')

    class Meta:
        model = BankAccount
        fields = [
            'bank_account_id', 'user', 'account_name', 'account_type',
            'bank_display', 'bank_name', 'account_number_masked',
            'currency', 'current_balance', 'formatted_balance',
            'transaction_count', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['bank_account_id', 'created_at', 'updated_at']

    def get_formatted_balance(self, obj):
        symbols = {'GBP': '£', 'USD': '$', 'EUR': '€'}
        symbol = symbols.get(obj.currency, obj.currency)
        return f"{symbol}{obj.current_balance:,.2f}"

    def validate_account_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Account name is required.")

        cleaned = value.strip()
        if len(cleaned) < 2:
            raise serializers.ValidationError(
                "Account name must be at least 2 characters.")
        if len(cleaned) > 100:
            raise serializers.ValidationError(
                "Account name cannot exceed 100 characters.")

        return cleaned

    def validate_bank_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Bank name is required.")

        cleaned = value.strip()
        if len(cleaned) < 2:
            raise serializers.ValidationError(
                "Bank name must be at least 2 characters.")

        return cleaned

    def validate_account_number_masked(self, value):
        if not value:
            raise serializers.ValidationError(
                "Masked account number is required.")

        if not value.startswith('****') or len(value) != 8:
            raise serializers.ValidationError(
                "Account number must be in format ****1234.")

        try:
            int(value[4:])
        except ValueError:
            raise serializers.ValidationError("Last 4 digits must be numbers.")

        return value

    def validate_current_balance(self, value):
        if value is None:
            raise serializers.ValidationError("Current balance is required.")

        if value < Decimal('-10000'):
            raise serializers.ValidationError(
                "Overdraft limit cannot exceed £10,000.")

        if value > Decimal('9999999.99'):
            raise serializers.ValidationError(
                "Balance exceeds maximum allowed value.")

        return value

    def validate(self, attrs):
        account_type = attrs.get(
            'account_type', self.instance.account_type if self.instance else None)
        current_balance = attrs.get(
            'current_balance', self.instance.current_balance if self.instance else None)

        if account_type and current_balance is not None:
            if account_type != 'credit' and current_balance < 0:
                raise serializers.ValidationError({
                    'current_balance': 'Only credit accounts can have negative balance.'
                })

            if account_type == 'credit' and current_balance > 0:
                raise serializers.ValidationError({
                    'current_balance': 'Credit accounts should have zero or negative balance.'
                })

        return attrs


class TransactionSerializer(serializers.ModelSerializer):
    """Transaction serializer with comprehensive validation and balance updates."""

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
                "Transaction amount exceeds maximum allowed value.")

        return value

    def validate_transaction_date(self, value):
        if value > date.today() + timedelta(days=1):
            raise serializers.ValidationError(
                "Transaction date cannot be more than one day in the future.")

        if value < date.today() - timedelta(days=365 * 2):
            raise serializers.ValidationError(
                "Transaction date cannot be more than 2 years in the past.")

        return value

    def validate_transaction_description(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError(
                "Transaction description is required.")

        cleaned = value.strip()
        if len(cleaned) < 2:
            raise serializers.ValidationError(
                "Transaction description must be at least 2 characters.")

        if len(cleaned) > 255:
            raise serializers.ValidationError(
                "Transaction description cannot exceed 255 characters.")

        return cleaned

    def validate_reference_number(self, value):
        if value:
            cleaned = value.strip().upper()
            if len(cleaned) > 100:
                raise serializers.ValidationError(
                    "Reference number cannot exceed 100 characters.")
            return cleaned
        return value

    def validate(self, attrs):
        category = attrs.get('category')
        transaction_type = attrs.get('transaction_type')
        bank_account = attrs.get('bank_account')
        transaction_amount = attrs.get('transaction_amount')

        # Validate category type matches transaction type
        if category and transaction_type:
            if transaction_type != 'transfer' and category.category_type != transaction_type:
                raise serializers.ValidationError({
                    'transaction_type': f'Transaction type must match category type ({category.category_type}).'
                })

        # Convert transaction amounts to correct sign
        if transaction_type == 'expense' and transaction_amount > 0:
            attrs['transaction_amount'] = -abs(transaction_amount)
            # Update local variable
            transaction_amount = attrs['transaction_amount']
        elif transaction_type == 'income' and transaction_amount < 0:
            attrs['transaction_amount'] = abs(transaction_amount)
            # Update local variable
            transaction_amount = attrs['transaction_amount']

        # Validate insufficient funds with correctly signed amount
        if bank_account and transaction_type == 'expense':
            if bank_account.account_type != 'credit':
                expected_balance = bank_account.current_balance + transaction_amount
                if expected_balance < Decimal('0'):
                    raise serializers.ValidationError({
                        'transaction_amount': 'Insufficient funds. This transaction would result in a negative balance.'
                    })

        return attrs

    @db_transaction.atomic
    def create(self, validated_data):
        transaction_obj = super().create(validated_data)

        self._update_account_balance(
            transaction_obj.bank_account,
            transaction_obj.transaction_amount
        )

        self._invalidate_cache(transaction_obj.user.id)

        return transaction_obj

    @db_transaction.atomic
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


class BudgetSerializer(serializers.ModelSerializer):
    """Budget serializer with period validation and overlap detection."""

    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    category_name = serializers.CharField(
        source='category.category_name', read_only=True)
    days_remaining = serializers.SerializerMethodField(read_only=True)
    spent_amount = serializers.SerializerMethodField(read_only=True)
    remaining_amount = serializers.SerializerMethodField(read_only=True)
    percentage_used = serializers.SerializerMethodField(read_only=True)

    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.none(),
        required=True
    )

    class Meta:
        model = Budget
        fields = [
            'budget_id', 'user', 'category', 'category_name',
            'budget_name', 'budget_amount', 'budget_type',
            'period_type', 'start_date', 'end_date',
            'spent_amount', 'remaining_amount', 'percentage_used',
            'days_remaining', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['budget_id',
                            'created_at', 'updated_at', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            self.fields['category'].queryset = Category.objects.filter(
                user=request.user,
                category_type='expense',
                is_active=True
            ).select_related('user')

    def get_days_remaining(self, obj):
        today = date.today()
        if today > obj.end_date:
            return 0
        return (obj.end_date - today).days

    def get_spent_amount(self, obj):
        transactions = Transaction.objects.filter(
            user=obj.user,
            category=obj.category,
            transaction_date__gte=obj.start_date,
            transaction_date__lte=obj.end_date
        ).aggregate(
            total=Sum('transaction_amount')
        )
        return abs(transactions['total'] or Decimal('0'))

    def get_remaining_amount(self, obj):
        spent = self.get_spent_amount(obj)
        return max(obj.budget_amount - spent, Decimal('0'))

    def get_percentage_used(self, obj):
        if obj.budget_amount == 0:
            return "0.00"
        spent = self.get_spent_amount(obj)
        percentage = (spent / obj.budget_amount) * 100
        return f"{min(percentage, 100):.2f}"

    def validate_budget_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Budget name is required.")

        cleaned = value.strip()
        if len(cleaned) < 2:
            raise serializers.ValidationError(
                "Budget name must be at least 2 characters.")
        if len(cleaned) > 100:
            raise serializers.ValidationError(
                "Budget name cannot exceed 100 characters.")

        return cleaned

    def validate_budget_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Budget amount must be positive.")

        if value > Decimal('999999.99'):
            raise serializers.ValidationError(
                "Budget amount exceeds maximum allowed value.")

        return value

    def validate_start_date(self, value):
        if value < date.today() - timedelta(days=365):
            raise serializers.ValidationError(
                "Start date cannot be more than 1 year in the past.")

        if value > date.today() + timedelta(days=365):
            raise serializers.ValidationError(
                "Start date cannot be more than 1 year in the future.")

        return value

    def validate(self, attrs):
        start_date = attrs.get(
            'start_date', self.instance.start_date if self.instance else None)
        end_date = attrs.get(
            'end_date', self.instance.end_date if self.instance else None)
        category = attrs.get(
            'category', self.instance.category if self.instance else None)

        if start_date and end_date:
            if start_date >= end_date:
                raise serializers.ValidationError({
                    'end_date': 'End date must be after start date.'
                })

            if (end_date - start_date).days > 366:
                raise serializers.ValidationError({
                    'end_date': 'Budget period cannot exceed 1 year.'
                })

        if category and start_date and end_date:
            overlapping = Budget.objects.filter(
                user=self.context['request'].user,
                category=category,
                is_active=True,
                start_date__lte=end_date,
                end_date__gte=start_date
            )

            if self.instance:
                overlapping = overlapping.exclude(
                    budget_id=self.instance.budget_id)

            if overlapping.exists():
                raise serializers.ValidationError({
                    'category': 'An active budget already exists for this category in this period.'
                })

        return attrs


class TransactionListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for transaction list views."""

    category_name = serializers.CharField(
        source='category.category_name', read_only=True)
    account_name = serializers.CharField(
        source='bank_account.account_name', read_only=True)
    formatted_amount = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Transaction
        fields = [
            'transaction_id', 'transaction_description',
            'transaction_amount', 'formatted_amount',
            'transaction_date', 'transaction_type',
            'category_name', 'account_name', 'is_recurring'
        ]
        read_only_fields = ['transaction_id']

    def get_formatted_amount(self, obj):
        amount = obj.transaction_amount
        if amount >= 0:
            return f"+£{amount:,.2f}"
        return f"-£{abs(amount):,.2f}"


class BankAccountListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for bank account list views."""

    formatted_balance = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = BankAccount
        fields = [
            'bank_account_id', 'account_name', 'bank_name',
            'account_type', 'current_balance', 'formatted_balance',
            'is_active'
        ]
        read_only_fields = ['bank_account_id']

    def get_formatted_balance(self, obj):
        symbols = {'GBP': '£', 'USD': '$', 'EUR': '€'}
        symbol = symbols.get(obj.currency, obj.currency)
        return f"{symbol}{obj.current_balance:,.2f}"
