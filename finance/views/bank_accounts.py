from datetime import timedelta
from decimal import Decimal
from django.db.models import Sum, Q, Count, F
from django.db import transaction as db_transaction
from django.utils import timezone
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from finance.models import BankAccount, Transaction
from finance.serializers import (
    BankAccountSerializer,
    BankAccountListSerializer,
    TransactionListSerializer
)


class BankAccountViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter, filters.SearchFilter]
    ordering_fields = ['account_name', 'bank_name',
                       'current_balance', 'created_at']
    ordering = ['account_name']
    search_fields = ['account_name', 'bank_name']

    def get_queryset(self):
        queryset = BankAccount.objects.filter(
            user=self.request.user
        ).annotate(
            transaction_count=Count('bank_account_transactions'),
            monthly_income=Sum(
                'bank_account_transactions__transaction_amount',
                filter=Q(
                    bank_account_transactions__transaction_type='income',
                    bank_account_transactions__transaction_date__gte=timezone.now().date() -
                    timedelta(days=30)
                )
            ),
            monthly_expenses=Sum(
                'bank_account_transactions__transaction_amount',
                filter=Q(
                    bank_account_transactions__transaction_type='expense',
                    bank_account_transactions__transaction_date__gte=timezone.now().date() -
                    timedelta(days=30)
                )
            )
        )

        account_type = self.request.query_params.get('type', None)
        if account_type in ['current', 'savings', 'isa', 'credit']:
            queryset = queryset.filter(account_type=account_type)

        is_active = self.request.query_params.get('is_active', None)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')

        currency = self.request.query_params.get('currency', None)
        if currency in ['GBP', 'USD', 'EUR']:
            queryset = queryset.filter(currency=currency)

        min_balance = self.request.query_params.get('min_balance', None)
        if min_balance:
            try:
                min_balance = Decimal(min_balance)
                queryset = queryset.filter(current_balance__gte=min_balance)
            except (ValueError, TypeError):
                pass

        return queryset

    def get_serializer_class(self):
        if self.action == 'list':
            return BankAccountListSerializer
        return BankAccountSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def destroy(self, request, *args, **kwargs):
        account = self.get_object()

        if account.bank_account_transactions.exists():
            return Response(
                {
                    'error': 'Cannot delete account with existing transactions',
                    'suggestion': 'Transfer funds and transactions to another account first, or deactivate this account'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        return super().destroy(request, *args, **kwargs)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        accounts = self.get_queryset().filter(is_active=True)

        account_details = []
        total_by_currency = {}

        for account in accounts:
            currency = account.currency
            balance = account.current_balance

            if currency not in total_by_currency:
                total_by_currency[currency] = {
                    'total': Decimal('0'),
                    'by_type': {}
                }

            total_by_currency[currency]['total'] += balance

            if account.account_type not in total_by_currency[currency]['by_type']:
                total_by_currency[currency]['by_type'][account.account_type] = Decimal(
                    '0')

            total_by_currency[currency]['by_type'][account.account_type] += balance

            account_details.append({
                'id': str(account.bank_account_id),
                'name': account.account_name,
                'bank': account.bank_name,
                'type': account.account_type,
                'balance': float(balance),
                'currency': currency,
                'transaction_count': account.transaction_count,
                'monthly_income': float(account.monthly_income or 0),
                'monthly_expenses': float(abs(account.monthly_expenses or 0)),
                'monthly_net': float((account.monthly_income or 0) + (account.monthly_expenses or 0))
            })

        formatted_totals = {}
        for currency, data in total_by_currency.items():
            formatted_totals[currency] = {
                'total': float(data['total']),
                'by_type': {k: float(v) for k, v in data['by_type'].items()}
            }

        recent_activity = Transaction.objects.filter(
            user=request.user,
            bank_account__in=accounts
        ).order_by('-transaction_date', '-created_at')[:10].values(
            'transaction_description',
            'transaction_amount',
            'transaction_date',
            'bank_account__account_name'
        )

        return Response({
            'summary': {
                'total_accounts': accounts.count(),
                'active_accounts': accounts.filter(is_active=True).count(),
                'totals_by_currency': formatted_totals,
                'primary_currency': 'GBP'
            },
            'accounts': account_details,
            'recent_activity': [
                {
                    'description': t['transaction_description'],
                    'amount': float(t['transaction_amount']),
                    'date': t['transaction_date'].isoformat(),
                    'account': t['bank_account__account_name']
                }
                for t in recent_activity
            ]
        })

    @action(detail=True, methods=['get'])
    def statement(self, request, pk=None):
        account = self.get_object()

        days = int(request.query_params.get('days', 30))
        start_date = timezone.now().date() - timedelta(days=days)

        transactions = Transaction.objects.filter(
            user=request.user,
            bank_account=account,
            transaction_date__gte=start_date
        ).order_by('-transaction_date')

        opening_balance = account.current_balance - transactions.aggregate(
            total=Sum('transaction_amount')
        )['total'] or Decimal('0')

        transaction_list = []
        running_balance = opening_balance

        for trans in transactions.reverse():
            running_balance += trans.transaction_amount
            transaction_list.append({
                'date': trans.transaction_date.isoformat(),
                'description': trans.transaction_description,
                'category': trans.category.category_name,
                'amount': float(trans.transaction_amount),
                'balance': float(running_balance),
                'type': trans.transaction_type,
                'reference': trans.reference_number
            })

        transaction_list.reverse()

        total_credits = transactions.filter(
            transaction_type='income'
        ).aggregate(total=Sum('transaction_amount'))['total'] or Decimal('0')

        total_debits = transactions.filter(
            transaction_type='expense'
        ).aggregate(total=Sum('transaction_amount'))['total'] or Decimal('0')

        return Response({
            'account': {
                'id': str(account.bank_account_id),
                'name': account.account_name,
                'bank': account.bank_name,
                'type': account.account_type,
                'account_number': account.account_number_masked
            },
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': timezone.now().date().isoformat(),
                'days': days
            },
            'balances': {
                'opening': float(opening_balance),
                'closing': float(account.current_balance),
                'current': float(account.current_balance)
            },
            'summary': {
                'total_credits': float(total_credits),
                'total_debits': float(abs(total_debits)),
                'net_change': float(total_credits + total_debits),
                'transaction_count': transactions.count()
            },
            'transactions': transaction_list
        })

    @action(detail=True, methods=['post'])
    @db_transaction.atomic
    def transfer(self, request, pk=None):
        source_account = self.get_object()
        target_account_id = request.data.get('target_account_id')
        amount = request.data.get('amount')
        description = request.data.get(
            'description', 'Transfer between accounts')

        if not target_account_id or not amount:
            return Response(
                {'error': 'target_account_id and amount are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            amount = Decimal(str(amount))
            if amount <= 0:
                raise ValueError()
        except (ValueError, TypeError):
            return Response(
                {'error': 'Amount must be a positive number'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            target_account = BankAccount.objects.get(
                bank_account_id=target_account_id,
                user=request.user,
                is_active=True
            )
        except BankAccount.DoesNotExist:
            return Response(
                {'error': 'Target account not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        if source_account.bank_account_id == target_account.bank_account_id:
            return Response(
                {'error': 'Cannot transfer to the same account'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if source_account.currency != target_account.currency:
            return Response(
                {'error': 'Currency conversion not supported'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if source_account.account_type != 'credit' and source_account.current_balance < amount:
            return Response(
                {'error': 'Insufficient funds'},
                status=status.HTTP_400_BAD_REQUEST
            )

        transfer_category, _ = request.user.user_categories.get_or_create(
            category_name='Transfer',
            category_type='expense',
            defaults={'is_default': True}
        )

        outgoing = Transaction.objects.create(
            user=request.user,
            bank_account=source_account,
            category=transfer_category,
            transaction_description=f"Transfer to {target_account.account_name}: {description}",
            transaction_type='transfer',
            transaction_amount=-amount,
            transaction_date=timezone.now().date(),
            reference_number=f"TRF-{timezone.now().timestamp()}"
        )

        incoming = Transaction.objects.create(
            user=request.user,
            bank_account=target_account,
            category=transfer_category,
            transaction_description=f"Transfer from {source_account.account_name}: {description}",
            transaction_type='transfer',
            transaction_amount=amount,
            transaction_date=timezone.now().date(),
            reference_number=outgoing.reference_number
        )

        source_account.current_balance -= amount
        source_account.save(update_fields=['current_balance', 'updated_at'])

        target_account.current_balance += amount
        target_account.save(update_fields=['current_balance', 'updated_at'])

        return Response({
            'message': 'Transfer completed successfully',
            'transfer': {
                'reference': outgoing.reference_number,
                'amount': float(amount),
                'from_account': {
                    'id': str(source_account.bank_account_id),
                    'name': source_account.account_name,
                    'new_balance': float(source_account.current_balance)
                },
                'to_account': {
                    'id': str(target_account.bank_account_id),
                    'name': target_account.account_name,
                    'new_balance': float(target_account.current_balance)
                }
            }
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        account = self.get_object()

        if account.current_balance != 0:
            return Response(
                {
                    'error': 'Cannot deactivate account with non-zero balance',
                    'current_balance': float(account.current_balance)
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        account.is_active = False
        account.save(update_fields=['is_active', 'updated_at'])

        return Response({
            'message': 'Account deactivated successfully',
            'account': {
                'id': str(account.bank_account_id),
                'name': account.account_name,
                'is_active': account.is_active
            }
        })
