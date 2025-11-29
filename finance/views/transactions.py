from datetime import datetime, timedelta
from decimal import Decimal
from django.core.cache import cache
from django.db import transaction as db_transaction
from django.db.models import Sum, Q, Count, Avg
from django.utils import timezone
from rest_framework import viewsets, status, filters, serializers
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiResponse, inline_serializer
from finance.models import Transaction, BankAccount, Category
from finance.serializers import (
    TransactionSerializer,
    TransactionListSerializer,
    BankAccountSerializer
)


# Request serializers for documentation
class BulkCategorizeRequestSerializer(serializers.Serializer):
    transaction_ids = serializers.ListField(
        child=serializers.UUIDField(),
        help_text="List of transaction IDs to categorize"
    )
    category_id = serializers.UUIDField(help_text="Target category ID")


class DuplicateRequestSerializer(serializers.Serializer):
    transaction_date = serializers.DateField(
        required=False,
        help_text="Date for the duplicated transaction (default: today)"
    )


@extend_schema_view(
    list=extend_schema(
        tags=['Transactions'],
        summary='List transactions',
        description='Retrieve all transactions for the authenticated user with optional filtering.',
        parameters=[
            OpenApiParameter(
                name='bank_account', description='Filter by bank account ID', required=False, type=str),
            OpenApiParameter(
                name='category', description='Filter by category ID', required=False, type=str),
            OpenApiParameter(
                name='type', description='Filter by transaction type (income, expense, transfer)', required=False, type=str),
            OpenApiParameter(
                name='date_from', description='Filter from date (YYYY-MM-DD)', required=False, type=str),
            OpenApiParameter(
                name='date_to', description='Filter to date (YYYY-MM-DD)', required=False, type=str),
            OpenApiParameter(
                name='min_amount', description='Filter by minimum absolute amount', required=False, type=float),
            OpenApiParameter(
                name='is_recurring', description='Filter by recurring status', required=False, type=bool),
        ]
    ),
    create=extend_schema(
        tags=['Transactions'],
        summary='Create transaction',
        description='Create a new transaction. Amount sign is auto-adjusted based on type.'
    ),
    retrieve=extend_schema(
        tags=['Transactions'],
        summary='Get transaction',
        description='Retrieve a specific transaction by ID.'
    ),
    update=extend_schema(
        tags=['Transactions'],
        summary='Update transaction',
        description='Update all fields of a transaction.'
    ),
    partial_update=extend_schema(
        tags=['Transactions'],
        summary='Partially update transaction',
        description='Update specific fields of a transaction.'
    ),
    destroy=extend_schema(
        tags=['Transactions'],
        summary='Delete transaction',
        description='Delete a transaction. Account balance will be reversed.'
    ),
)
class TransactionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing transactions.

    Provides CRUD operations plus custom actions for statistics,
    monthly summaries, bulk categorization, and duplication.
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter, filters.SearchFilter]
    ordering_fields = ['transaction_date', 'transaction_amount', 'created_at']
    ordering = ['-transaction_date', '-created_at']
    search_fields = ['transaction_description',
                     'reference_number', 'transaction_note']

    def get_queryset(self):
        queryset = Transaction.objects.filter(
            user=self.request.user
        ).select_related(
            'bank_account',
            'category',
            'user'
        ).prefetch_related(
            'bank_account__user',
            'category__user'
        )

        bank_account_id = self.request.query_params.get('bank_account', None)
        if bank_account_id:
            queryset = queryset.filter(
                bank_account__bank_account_id=bank_account_id)

        category_id = self.request.query_params.get('category', None)
        if category_id:
            queryset = queryset.filter(category__category_id=category_id)

        transaction_type = self.request.query_params.get('type', None)
        if transaction_type in ['income', 'expense', 'transfer']:
            queryset = queryset.filter(transaction_type=transaction_type)

        date_from = self.request.query_params.get('date_from', None)
        if date_from:
            try:
                date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
                queryset = queryset.filter(transaction_date__gte=date_from)
            except ValueError:
                pass

        date_to = self.request.query_params.get('date_to', None)
        if date_to:
            try:
                date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
                queryset = queryset.filter(transaction_date__lte=date_to)
            except ValueError:
                pass

        min_amount = self.request.query_params.get('min_amount', None)
        if min_amount:
            try:
                min_amount = Decimal(min_amount)
                queryset = queryset.filter(
                    Q(transaction_amount__gte=min_amount) |
                    Q(transaction_amount__lte=-min_amount)
                )
            except (ValueError, TypeError):
                pass

        is_recurring = self.request.query_params.get('is_recurring', None)
        if is_recurring is not None:
            queryset = queryset.filter(
                is_recurring=is_recurring.lower() == 'true')

        return queryset

    def get_serializer_class(self):
        if self.action == 'list':
            return TransactionListSerializer
        return TransactionSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        serializer.save(user=self.request.user)

    @db_transaction.atomic
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        bank_account = instance.bank_account
        amount_to_reverse = -instance.transaction_amount

        bank_account.current_balance += amount_to_reverse
        bank_account.save(update_fields=['current_balance', 'updated_at'])

        self._invalidate_user_cache()

        return super().destroy(request, *args, **kwargs)

    @extend_schema(
        tags=['Transactions'],
        summary='Get transaction statistics',
        description='Get detailed statistics including income/expense summaries, category breakdown, and top expenses. Results are cached for 5 minutes.',
        parameters=[
            OpenApiParameter(
                name='date_from', description='Start date (YYYY-MM-DD)', required=False, type=str),
            OpenApiParameter(
                name='date_to', description='End date (YYYY-MM-DD)', required=False, type=str),
        ]
    )
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        cache_key = f'user_statistics_{request.user.id}'
        cached_stats = cache.get(cache_key)

        if cached_stats:
            return Response(cached_stats)

        transactions = self.get_queryset()

        date_from = request.query_params.get('date_from', None)
        date_to = request.query_params.get('date_to', None)

        if date_from:
            try:
                date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
                transactions = transactions.filter(
                    transaction_date__gte=date_from)
            except ValueError:
                date_from = None

        if date_to:
            try:
                date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
                transactions = transactions.filter(
                    transaction_date__lte=date_to)
            except ValueError:
                date_to = None

        if not date_from:
            date_from = timezone.now().date() - timedelta(days=30)
            transactions = transactions.filter(transaction_date__gte=date_from)

        income = transactions.filter(
            transaction_type='income'
        ).aggregate(
            total=Sum('transaction_amount')
        )['total'] or Decimal('0')

        expenses = transactions.filter(
            transaction_type='expense'
        ).aggregate(
            total=Sum('transaction_amount')
        )['total'] or Decimal('0')

        category_breakdown = transactions.filter(
            transaction_type='expense'
        ).values(
            'category__category_name'
        ).annotate(
            total=Sum('transaction_amount'),
            count=Count('transaction_id'),
            average=Avg('transaction_amount')
        ).order_by('total')

        account_breakdown = transactions.values(
            'bank_account__account_name',
            'bank_account__bank_account_id'
        ).annotate(
            total_in=Sum('transaction_amount', filter=Q(
                transaction_type='income')),
            total_out=Sum('transaction_amount', filter=Q(
                transaction_type='expense')),
            transaction_count=Count('transaction_id')
        )

        top_expenses = transactions.filter(
            transaction_type='expense'
        ).order_by('transaction_amount')[:5].values(
            'transaction_description',
            'transaction_amount',
            'transaction_date',
            'category__category_name'
        )

        statistics = {
            'period': {
                'from': date_from.isoformat() if date_from else None,
                'to': date_to.isoformat() if date_to else timezone.now().date().isoformat()
            },
            'summary': {
                'total_income': float(income),
                'total_expenses': float(abs(expenses)),
                'net_savings': float(income + expenses),
                'transaction_count': transactions.count(),
                'average_transaction': float(
                    transactions.aggregate(avg=Avg('transaction_amount'))[
                        'avg'] or 0
                )
            },
            'category_breakdown': [
                {
                    'category': item['category__category_name'],
                    'total': float(abs(item['total'])),
                    'count': item['count'],
                    'average': float(abs(item['average'])) if item['average'] else 0
                }
                for item in category_breakdown
            ],
            'account_breakdown': [
                {
                    'account': item['bank_account__account_name'],
                    'account_id': str(item['bank_account__bank_account_id']),
                    'income': float(item['total_in'] or 0),
                    'expenses': float(abs(item['total_out'] or 0)),
                    'net': float((item['total_in'] or 0) + (item['total_out'] or 0)),
                    'transaction_count': item['transaction_count']
                }
                for item in account_breakdown
            ],
            'top_expenses': [
                {
                    'description': item['transaction_description'],
                    'amount': float(abs(item['transaction_amount'])),
                    'date': item['transaction_date'].isoformat(),
                    'category': item['category__category_name']
                }
                for item in top_expenses
            ]
        }

        cache.set(cache_key, statistics, 300)

        return Response(statistics)

    @extend_schema(
        tags=['Transactions'],
        summary='Get monthly summary',
        description='Get a detailed monthly summary with daily breakdown of income and expenses.',
        parameters=[
            OpenApiParameter(
                name='year', description='Year (default: current year)', required=False, type=int),
            OpenApiParameter(
                name='month', description='Month 1-12 (default: current month)', required=False, type=int),
        ]
    )
    @action(detail=False, methods=['get'])
    def monthly_summary(self, request):
        year = request.query_params.get('year', timezone.now().year)
        month = request.query_params.get('month', timezone.now().month)

        try:
            year = int(year)
            month = int(month)
        except (ValueError, TypeError):
            return Response(
                {'error': 'Invalid year or month parameter'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not (1 <= month <= 12):
            return Response(
                {'error': 'Month must be between 1 and 12'},
                status=status.HTTP_400_BAD_REQUEST
            )

        start_date = datetime(year, month, 1).date()
        if month == 12:
            end_date = datetime(year + 1, 1, 1).date() - timedelta(days=1)
        else:
            end_date = datetime(year, month + 1, 1).date() - timedelta(days=1)

        transactions = self.get_queryset().filter(
            transaction_date__gte=start_date,
            transaction_date__lte=end_date
        )

        daily_transactions = transactions.values('transaction_date').annotate(
            income=Sum('transaction_amount', filter=Q(
                transaction_type='income')),
            expenses=Sum('transaction_amount', filter=Q(
                transaction_type='expense')),
            count=Count('transaction_id')
        ).order_by('transaction_date')

        summary = {
            'month': f'{year}-{month:02d}',
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'total_income': float(
                transactions.filter(transaction_type='income').aggregate(
                    total=Sum('transaction_amount')
                )['total'] or 0
            ),
            'total_expenses': float(abs(
                transactions.filter(transaction_type='expense').aggregate(
                    total=Sum('transaction_amount')
                )['total'] or 0
            )),
            'daily_breakdown': [
                {
                    'date': item['transaction_date'].isoformat(),
                    'income': float(item['income'] or 0),
                    'expenses': float(abs(item['expenses'] or 0)),
                    'net': float((item['income'] or 0) + (item['expenses'] or 0)),
                    'transaction_count': item['count']
                }
                for item in daily_transactions
            ],
            'transaction_count': transactions.count(),
            'recurring_count': transactions.filter(is_recurring=True).count()
        }

        return Response(summary)

    @extend_schema(
        tags=['Transactions'],
        summary='Bulk categorize transactions',
        description='Assign a category to multiple transactions at once.',
        request=BulkCategorizeRequestSerializer,
        responses={
            200: OpenApiResponse(description='Transactions categorized successfully'),
            400: OpenApiResponse(description='Validation error or incompatible transaction types'),
            404: OpenApiResponse(description='Category not found'),
        }
    )
    @action(detail=False, methods=['post'])
    @db_transaction.atomic
    def bulk_categorize(self, request):
        transaction_ids = request.data.get('transaction_ids', [])
        category_id = request.data.get('category_id')

        if not transaction_ids or not category_id:
            return Response(
                {'error': 'transaction_ids and category_id are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            category = Category.objects.get(
                category_id=category_id,
                user=request.user,
                is_active=True
            )
        except Category.DoesNotExist:
            return Response(
                {'error': 'Category not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        transactions = Transaction.objects.filter(
            transaction_id__in=transaction_ids,
            user=request.user
        )

        if transactions.count() != len(transaction_ids):
            return Response(
                {'error': 'Some transactions were not found or do not belong to you'},
                status=status.HTTP_400_BAD_REQUEST
            )

        invalid_transactions = transactions.exclude(
            transaction_type__in=['transfer', category.category_type]
        )

        if invalid_transactions.exists():
            return Response(
                {'error': f'Some transactions have incompatible types for {category.category_type} category'},
                status=status.HTTP_400_BAD_REQUEST
            )

        updated_count = transactions.update(
            category=category,
            updated_at=timezone.now()
        )

        self._invalidate_user_cache()

        return Response({
            'message': f'Successfully categorized {updated_count} transactions',
            'updated_count': updated_count,
            'category': {
                'id': str(category.category_id),
                'name': category.category_name
            }
        })

    @extend_schema(
        tags=['Transactions'],
        summary='Duplicate transaction',
        description='Create a copy of an existing transaction with a new date.',
        request=DuplicateRequestSerializer,
        responses={
            201: TransactionSerializer,
            400: OpenApiResponse(description='Invalid date format'),
        }
    )
    @action(detail=True, methods=['post'])
    @db_transaction.atomic
    def duplicate(self, request, pk=None):
        original = self.get_object()

        new_date = request.data.get('transaction_date', timezone.now().date())
        if isinstance(new_date, str):
            try:
                new_date = datetime.strptime(new_date, '%Y-%m-%d').date()
            except ValueError:
                return Response(
                    {'error': 'Invalid date format. Use YYYY-MM-DD'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        duplicated = Transaction.objects.create(
            user=request.user,
            bank_account=original.bank_account,
            category=original.category,
            transaction_description=f"Copy of {original.transaction_description}",
            transaction_type=original.transaction_type,
            transaction_amount=original.transaction_amount,
            transaction_date=new_date,
            transaction_note=original.transaction_note,
            reference_number=None,
            is_recurring=original.is_recurring
        )

        original.bank_account.current_balance += original.transaction_amount
        original.bank_account.save(
            update_fields=['current_balance', 'updated_at'])

        self._invalidate_user_cache()

        serializer = TransactionSerializer(
            duplicated, context={'request': request})

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED
        )

    def _invalidate_user_cache(self):
        cache_keys = [
            f'user_statistics_{self.request.user.id}',
            f'user_transactions_{self.request.user.id}',
            f'user_balance_{self.request.user.id}'
        ]
        cache.delete_many(cache_keys)
