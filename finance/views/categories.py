from datetime import timedelta
from decimal import Decimal
from django.db.models import Sum, Count, Q, Avg
from django.utils import timezone
from rest_framework import viewsets, status, filters, serializers
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiResponse
from finance.models import Category, Transaction
from finance.serializers import CategorySerializer


# Request serializers for documentation
class ReassignTransactionsRequestSerializer(serializers.Serializer):
    target_category_id = serializers.UUIDField(
        help_text="ID of the category to reassign transactions to")


@extend_schema_view(
    list=extend_schema(
        tags=['Categories'],
        summary='List categories',
        description='Retrieve all categories for the authenticated user.',
        parameters=[
            OpenApiParameter(
                name='type', description='Filter by category type (income, expense)', required=False, type=str),
            OpenApiParameter(
                name='is_active', description='Filter by active status', required=False, type=bool),
            OpenApiParameter(
                name='has_transactions', description='Filter by whether category has transactions', required=False, type=bool),
        ]
    ),
    create=extend_schema(
        tags=['Categories'],
        summary='Create category',
        description='Create a new income or expense category.'
    ),
    retrieve=extend_schema(
        tags=['Categories'],
        summary='Get category',
        description='Retrieve a specific category by ID.'
    ),
    update=extend_schema(
        tags=['Categories'],
        summary='Update category',
        description='Update all fields of a category.'
    ),
    partial_update=extend_schema(
        tags=['Categories'],
        summary='Partially update category',
        description='Update specific fields of a category.'
    ),
    destroy=extend_schema(
        tags=['Categories'],
        summary='Delete category',
        description='Delete a category. Cannot delete default categories or those with transactions.'
    ),
)
class CategoryViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing income and expense categories.

    Provides CRUD operations plus custom actions for usage statistics,
    setting defaults, and reassigning transactions.
    """
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter, filters.SearchFilter]
    ordering_fields = ['category_name', 'category_type', 'created_at']
    ordering = ['category_type', 'category_name']
    search_fields = ['category_name']

    def get_queryset(self):
        queryset = Category.objects.filter(
            user=self.request.user
        ).annotate(
            transaction_count=Count('category_transactions'),
            total_amount=Sum('category_transactions__transaction_amount')
        )

        category_type = self.request.query_params.get('type', None)
        if category_type in ['income', 'expense']:
            queryset = queryset.filter(category_type=category_type)

        is_active = self.request.query_params.get('is_active', None)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')

        has_transactions = self.request.query_params.get(
            'has_transactions', None)
        if has_transactions is not None:
            if has_transactions.lower() == 'true':
                queryset = queryset.filter(transaction_count__gt=0)
            else:
                queryset = queryset.filter(transaction_count=0)

        return queryset

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def destroy(self, request, *args, **kwargs):
        category = self.get_object()

        if category.is_default:
            return Response(
                {'error': 'Cannot delete default categories'},
                status=status.HTTP_400_BAD_REQUEST
            )

        transaction_count = category.category_transactions.count()
        if transaction_count > 0:
            return Response(
                {
                    'error': f'Cannot delete category with {transaction_count} transactions',
                    'suggestion': 'Reassign transactions to another category first or deactivate this category'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        return super().destroy(request, *args, **kwargs)

    @extend_schema(
        tags=['Categories'],
        summary='Get category usage',
        description='Get usage statistics for a category including monthly breakdown and recent transactions.',
        parameters=[
            OpenApiParameter(
                name='days', description='Number of days to analyze (default: 30)', required=False, type=int),
        ]
    )
    @action(detail=True, methods=['get'])
    def usage(self, request, pk=None):
        category = self.get_object()

        days = int(request.query_params.get('days', 30))
        start_date = timezone.now().date() - timedelta(days=days)

        transactions = Transaction.objects.filter(
            user=request.user,
            category=category,
            transaction_date__gte=start_date
        )

        monthly_stats = transactions.values(
            'transaction_date__year',
            'transaction_date__month'
        ).annotate(
            total=Sum('transaction_amount'),
            count=Count('transaction_id'),
            average=Avg('transaction_amount')
        ).order_by('-transaction_date__year', '-transaction_date__month')

        recent_transactions = transactions.order_by('-transaction_date')[:5].values(
            'transaction_id',
            'transaction_description',
            'transaction_amount',
            'transaction_date'
        )

        total_amount = transactions.aggregate(
            total=Sum('transaction_amount')
        )['total'] or Decimal('0')

        return Response({
            'category': {
                'id': str(category.category_id),
                'name': category.category_name,
                'type': category.category_type
            },
            'period': {
                'days': days,
                'start_date': start_date.isoformat(),
                'end_date': timezone.now().date().isoformat()
            },
            'summary': {
                'total_amount': float(abs(total_amount)),
                'transaction_count': transactions.count(),
                'average_amount': float(
                    abs(total_amount / transactions.count())
                ) if transactions.count() > 0 else 0,
                'is_active': category.is_active,
                'is_default': category.is_default
            },
            'monthly_breakdown': [
                {
                    'month': f"{stat['transaction_date__year']}-{stat['transaction_date__month']:02d}",
                    'total': float(abs(stat['total'])),
                    'count': stat['count'],
                    'average': float(abs(stat['average'])) if stat['average'] else 0
                }
                for stat in monthly_stats
            ],
            'recent_transactions': [
                {
                    'id': str(t['transaction_id']),
                    'description': t['transaction_description'],
                    'amount': float(abs(t['transaction_amount'])),
                    'date': t['transaction_date'].isoformat()
                }
                for t in recent_transactions
            ]
        })

    @extend_schema(
        tags=['Categories'],
        summary='Create default categories',
        description='Create a set of default income and expense categories for the user.',
        request=None,
        responses={
            200: OpenApiResponse(description='Default categories created or already exist'),
        }
    )
    @action(detail=False, methods=['post'])
    def set_defaults(self, request):
        if Category.objects.filter(user=request.user, is_default=True).exists():
            return Response(
                {'message': 'Default categories already exist'},
                status=status.HTTP_200_OK
            )

        default_categories = [
            ('Salary', 'income'),
            ('Freelance', 'income'),
            ('Investment', 'income'),
            ('Other Income', 'income'),
            ('Housing', 'expense'),
            ('Food', 'expense'),
            ('Transport', 'expense'),
            ('Utilities', 'expense'),
            ('Healthcare', 'expense'),
            ('Entertainment', 'expense'),
            ('Shopping', 'expense'),
            ('Other Expense', 'expense'),
        ]

        created_categories = []
        for name, cat_type in default_categories:
            category, created = Category.objects.get_or_create(
                user=request.user,
                category_name=name,
                category_type=cat_type,
                defaults={'is_default': True}
            )
            if created:
                created_categories.append(category)

        return Response({
            'message': f'Created {len(created_categories)} default categories',
            'categories': CategorySerializer(
                created_categories,
                many=True,
                context={'request': request}
            ).data
        })

    @extend_schema(
        tags=['Categories'],
        summary='Reassign transactions',
        description='Move all transactions from this category to another category of the same type. The source category will be deactivated.',
        request=ReassignTransactionsRequestSerializer,
        responses={
            200: OpenApiResponse(description='Transactions reassigned successfully'),
            400: OpenApiResponse(description='Validation error or type mismatch'),
            404: OpenApiResponse(description='Target category not found'),
        }
    )
    @action(detail=True, methods=['post'])
    def reassign_transactions(self, request, pk=None):
        source_category = self.get_object()
        target_category_id = request.data.get('target_category_id')

        if not target_category_id:
            return Response(
                {'error': 'target_category_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            target_category = Category.objects.get(
                category_id=target_category_id,
                user=request.user
            )
        except Category.DoesNotExist:
            return Response(
                {'error': 'Target category not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        if source_category.category_type != target_category.category_type:
            return Response(
                {'error': 'Categories must be of the same type (income/expense)'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if source_category.category_id == target_category.category_id:
            return Response(
                {'error': 'Source and target categories cannot be the same'},
                status=status.HTTP_400_BAD_REQUEST
            )

        transaction_count = Transaction.objects.filter(
            user=request.user,
            category=source_category
        ).update(
            category=target_category,
            updated_at=timezone.now()
        )

        source_category.is_active = False
        source_category.save(update_fields=['is_active', 'updated_at'])

        return Response({
            'message': f'Reassigned {transaction_count} transactions',
            'source_category': {
                'id': str(source_category.category_id),
                'name': source_category.category_name,
                'is_active': False
            },
            'target_category': {
                'id': str(target_category.category_id),
                'name': target_category.category_name,
                'new_transaction_count': target_category.category_transactions.count()
            }
        })
