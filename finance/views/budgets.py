from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, Q, F, DecimalField, Case, When, Value
from django.db.models.functions import Coalesce
from django.db import transaction as db_transaction
from django.utils import timezone
from datetime import datetime, timedelta, date
from decimal import Decimal
from collections import defaultdict

from finance.models import Budget, Transaction, Category
from finance.serializers import BudgetSerializer


class BudgetViewSet(viewsets.ModelViewSet):
    serializer_class = BudgetSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['start_date', 'end_date', 'budget_amount', 'created_at']
    ordering = ['-start_date', 'budget_name']

    def get_queryset(self):
        queryset = Budget.objects.filter(
            user=self.request.user
        ).select_related(
            'category',
            'user'
        ).annotate(
            spent=Coalesce(
                Sum(
                    'category__category_transactions__transaction_amount',
                    filter=Q(
                        category__category_transactions__user=self.request.user,
                        category__category_transactions__transaction_date__gte=F(
                            'start_date'),
                        category__category_transactions__transaction_date__lte=F(
                            'end_date'),
                        category__category_transactions__transaction_type='expense'
                    )
                ),
                Value(Decimal('0')),
                output_field=DecimalField()
            )
        ).annotate(
            remaining=F('budget_amount') + F('spent'),
            utilization_percentage=Case(
                When(budget_amount=0, then=Value(Decimal('0'))),
                default=(-F('spent') / F('budget_amount')) * 100,
                output_field=DecimalField()
            )
        )

        is_active = self.request.query_params.get('is_active', None)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')

        period_type = self.request.query_params.get('period_type', None)
        if period_type in ['weekly', 'monthly', 'quarterly', 'yearly']:
            queryset = queryset.filter(period_type=period_type)

        category_id = self.request.query_params.get('category', None)
        if category_id:
            queryset = queryset.filter(category__category_id=category_id)

        current = self.request.query_params.get('current', None)
        if current and current.lower() == 'true':
            today = timezone.now().date()
            queryset = queryset.filter(
                start_date__lte=today,
                end_date__gte=today
            )

        exceeded = self.request.query_params.get('exceeded', None)
        if exceeded and exceeded.lower() == 'true':
            queryset = queryset.filter(utilization_percentage__gt=100)

        return queryset

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['get'])
    def progress(self, request, pk=None):
        budget = self.get_object()
        today = timezone.now().date()

        transactions = Transaction.objects.filter(
            user=request.user,
            category=budget.category,
            transaction_type='expense',
            transaction_date__gte=budget.start_date,
            transaction_date__lte=budget.end_date
        ).order_by('transaction_date')

        total_spent = abs(
            transactions.aggregate(
                total=Sum('transaction_amount')
            )['total'] or Decimal('0')
        )

        total_days = (budget.end_date - budget.start_date).days + 1
        days_elapsed = min((today - budget.start_date).days + 1, total_days)
        days_remaining = max(0, (budget.end_date - today).days + 1)

        if days_elapsed > 0:
            expected_spend = (budget.budget_amount / total_days) * days_elapsed
            pace_percentage = (total_spent / expected_spend *
                               100) if expected_spend > 0 else 0
        else:
            expected_spend = Decimal('0')
            pace_percentage = 0

        daily_spending = transactions.values('transaction_date').annotate(
            amount=Sum('transaction_amount')
        ).order_by('transaction_date')

        cumulative_spending = []
        running_total = Decimal('0')
        for day in daily_spending:
            running_total += abs(day['amount'])
            cumulative_spending.append({
                'date': day['transaction_date'].isoformat(),
                'daily_amount': float(abs(day['amount'])),
                'cumulative': float(running_total)
            })

        if days_remaining > 0 and budget.budget_amount > total_spent:
            daily_allowance = (budget.budget_amount -
                               total_spent) / days_remaining
        else:
            daily_allowance = Decimal('0')

        recent_transactions = transactions[:10].values(
            'transaction_id',
            'transaction_description',
            'transaction_amount',
            'transaction_date'
        )

        response_data = {
            'budget': {
                'id': str(budget.budget_id),
                'name': budget.budget_name,
                'amount': float(budget.budget_amount),
                'period': {
                    'start': budget.start_date.isoformat(),
                    'end': budget.end_date.isoformat(),
                    'total_days': total_days,
                    'days_elapsed': days_elapsed,
                    'days_remaining': days_remaining
                }
            },
            'spending': {
                'total_spent': float(total_spent),
                'remaining': float(budget.budget_amount - total_spent),
                'percentage_used': float((total_spent / budget.budget_amount * 100) if budget.budget_amount > 0 else 0),
                'expected_spend': float(expected_spend),
                'pace_percentage': float(pace_percentage),
                'daily_allowance': float(daily_allowance)
            },
            'status': self._determine_budget_status(
                total_spent,
                budget.budget_amount,
                pace_percentage
            ),
            'daily_breakdown': cumulative_spending,
            'recent_transactions': [
                {
                    'id': str(t['transaction_id']),
                    'description': t['transaction_description'],
                    'amount': float(abs(t['transaction_amount'])),
                    'date': t['transaction_date'].isoformat()
                }
                for t in recent_transactions
            ]
        }

        return Response(response_data)

    @action(detail=False, methods=['get'])
    def overview(self, request):
        today = timezone.now().date()

        budgets = self.get_queryset().filter(
            is_active=True,
            start_date__lte=today,
            end_date__gte=today
        )

        total_budgeted = budgets.aggregate(
            total=Sum('budget_amount')
        )['total'] or Decimal('0')

        total_spent = Decimal('0')
        budget_details = []

        for budget in budgets:
            spent = abs(budget.spent)
            total_spent += spent

            budget_details.append({
                'id': str(budget.budget_id),
                'name': budget.budget_name,
                'category': budget.category.category_name,
                'amount': float(budget.budget_amount),
                'spent': float(spent),
                'remaining': float(budget.remaining),
                'percentage': float(budget.utilization_percentage),
                'status': self._determine_budget_status(
                    spent,
                    budget.budget_amount,
                    budget.utilization_percentage
                ),
                'end_date': budget.end_date.isoformat()
            })

        upcoming_budgets = Budget.objects.filter(
            user=request.user,
            is_active=True,
            start_date__gt=today,
            start_date__lte=today + timedelta(days=30)
        ).order_by('start_date')[:5]

        expiring_budgets = Budget.objects.filter(
            user=request.user,
            is_active=True,
            end_date__gte=today,
            end_date__lte=today + timedelta(days=7)
        ).order_by('end_date')[:5]

        return Response({
            'summary': {
                'total_budgeted': float(total_budgeted),
                'total_spent': float(total_spent),
                'total_remaining': float(total_budgeted - total_spent),
                'overall_percentage': float(
                    (total_spent / total_budgeted *
                     100) if total_budgeted > 0 else 0
                ),
                'active_budget_count': budgets.count()
            },
            'active_budgets': budget_details,
            'upcoming_budgets': [
                {
                    'id': str(b.budget_id),
                    'name': b.budget_name,
                    'starts_in_days': (b.start_date - today).days,
                    'start_date': b.start_date.isoformat(),
                    'amount': float(b.budget_amount)
                }
                for b in upcoming_budgets
            ],
            'expiring_soon': [
                {
                    'id': str(b.budget_id),
                    'name': b.budget_name,
                    'expires_in_days': (b.end_date - today).days,
                    'end_date': b.end_date.isoformat(),
                    'amount': float(b.budget_amount)
                }
                for b in expiring_budgets
            ]
        })

    @action(detail=False, methods=['get'])
    def recommendations(self, request):
        lookback_months = int(request.query_params.get('months', 3))
        start_date = timezone.now().date() - timedelta(days=lookback_months * 30)

        categories_without_budgets = Category.objects.filter(
            user=request.user,
            category_type='expense',
            is_active=True
        ).exclude(
            category_budgets__is_active=True,
            category_budgets__start_date__lte=timezone.now().date(),
            category_budgets__end_date__gte=timezone.now().date()
        ).annotate(
            recent_spending=Coalesce(
                Sum(
                    'category_transactions__transaction_amount',
                    filter=Q(
                        category_transactions__user=request.user,
                        category_transactions__transaction_date__gte=start_date,
                        category_transactions__transaction_type='expense'
                    )
                ),
                Value(Decimal('0')),
                output_field=DecimalField()
            )
        ).filter(recent_spending__lt=0).order_by('recent_spending')

        overbudget_categories = []
        for budget in self.get_queryset().filter(is_active=True):
            if budget.utilization_percentage > 120:
                avg_monthly = abs(budget.spent) / max(
                    ((budget.end_date - budget.start_date).days / 30), 1
                )
                overbudget_categories.append({
                    'category': budget.category.category_name,
                    'current_budget': float(budget.budget_amount),
                    'actual_spending': float(abs(budget.spent)),
                    'recommended_budget': float(avg_monthly * Decimal('1.1')),
                    'overspend_percentage': float(budget.utilization_percentage - 100)
                })

        historical_patterns = defaultdict(lambda: {'amounts': [], 'dates': []})

        historical_transactions = Transaction.objects.filter(
            user=request.user,
            transaction_type='expense',
            transaction_date__gte=start_date
        ).values('category__category_name', 'transaction_date').annotate(
            monthly_total=Sum('transaction_amount')
        )

        for trans in historical_transactions:
            month_key = trans['transaction_date'].strftime('%Y-%m')
            historical_patterns[trans['category__category_name']]['amounts'].append(
                abs(trans['monthly_total'])
            )
            historical_patterns[trans['category__category_name']]['dates'].append(
                month_key)

        recommendations = {
            'unbudgeted_categories': [
                {
                    'category': cat.category_name,
                    'recent_spending': float(abs(cat.recent_spending)),
                    'suggested_budget': float(
                        abs(cat.recent_spending) /
                        lookback_months * Decimal('1.1')
                    ),
                    'priority': 'high' if abs(cat.recent_spending) > 500 else 'medium'
                }
                for cat in categories_without_budgets[:10]
            ],
            'adjustment_needed': overbudget_categories[:5],
            'savings_opportunities': self._identify_savings_opportunities(request.user),
            'period_recommendation': self._recommend_budget_periods(historical_patterns)
        }

        return Response(recommendations)

    @action(detail=True, methods=['post'])
    @db_transaction.atomic
    def clone(self, request, pk=None):
        original = self.get_object()

        period_shift = request.data.get('period_shift', 'next')
        new_amount = request.data.get('budget_amount', None)

        if period_shift == 'next':
            if original.period_type == 'monthly':
                start_date = original.end_date + timedelta(days=1)
                end_date = (start_date + timedelta(days=32)
                            ).replace(day=1) - timedelta(days=1)
            elif original.period_type == 'weekly':
                start_date = original.end_date + timedelta(days=1)
                end_date = start_date + timedelta(days=6)
            elif original.period_type == 'quarterly':
                start_date = original.end_date + timedelta(days=1)
                end_date = start_date + timedelta(days=90)
            else:
                start_date = original.end_date + timedelta(days=1)
                end_date = start_date + timedelta(days=364)
        else:
            start_date = request.data.get('start_date')
            end_date = request.data.get('end_date')

            if not start_date or not end_date:
                return Response(
                    {'error': 'start_date and end_date required for custom period'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            except ValueError:
                return Response(
                    {'error': 'Invalid date format. Use YYYY-MM-DD'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        overlapping = Budget.objects.filter(
            user=request.user,
            category=original.category,
            is_active=True,
            start_date__lte=end_date,
            end_date__gte=start_date
        ).exists()

        if overlapping:
            return Response(
                {'error': 'A budget already exists for this category in the specified period'},
                status=status.HTTP_400_BAD_REQUEST
            )

        cloned = Budget.objects.create(
            user=request.user,
            category=original.category,
            budget_name=f"{original.budget_name} (Cloned)",
            budget_amount=Decimal(
                str(new_amount)) if new_amount else original.budget_amount,
            period_type=original.period_type,
            start_date=start_date,
            end_date=end_date,
            is_active=True
        )

        serializer = BudgetSerializer(cloned, context={'request': request})

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        budget = self.get_object()

        if not budget.is_active:
            return Response(
                {'error': 'Budget is already inactive'},
                status=status.HTTP_400_BAD_REQUEST
            )

        budget.is_active = False
        budget.save(update_fields=['is_active', 'updated_at'])

        return Response({
            'message': 'Budget deactivated successfully',
            'budget': {
                'id': str(budget.budget_id),
                'name': budget.budget_name,
                'is_active': budget.is_active
            }
        })

    @action(detail=True, methods=['post'])
    def reactivate(self, request, pk=None):
        budget = self.get_object()

        if budget.is_active:
            return Response(
                {'error': 'Budget is already active'},
                status=status.HTTP_400_BAD_REQUEST
            )

        overlapping = Budget.objects.filter(
            user=request.user,
            category=budget.category,
            is_active=True,
            start_date__lte=budget.end_date,
            end_date__gte=budget.start_date
        ).exists()

        if overlapping:
            return Response(
                {'error': 'Cannot reactivate: another budget overlaps this period'},
                status=status.HTTP_400_BAD_REQUEST
            )

        budget.is_active = True
        budget.save(update_fields=['is_active', 'updated_at'])

        return Response({
            'message': 'Budget reactivated successfully',
            'budget': {
                'id': str(budget.budget_id),
                'name': budget.budget_name,
                'is_active': budget.is_active
            }
        })

    @action(detail=False, methods=['post'])
    @db_transaction.atomic
    def bulk_create(self, request):
        template = request.data.get('template', None)
        start_date = request.data.get('start_date', None)

        if not start_date:
            start_date = timezone.now().date().replace(day=1)
        else:
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            except ValueError:
                return Response(
                    {'error': 'Invalid date format'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        if template == 'essential':
            budget_templates = [
                ('Housing', 'Rent/Mortgage', 1500),
                ('Food', 'Groceries', 400),
                ('Transport', 'Transport', 200),
                ('Utilities', 'Utilities', 150),
                ('Council Tax', 'Council Tax', 150),
            ]
        elif template == 'comprehensive':
            budget_templates = [
                ('Housing', 'Rent/Mortgage', 1500),
                ('Food', 'Groceries', 400),
                ('Transport', 'Transport', 200),
                ('Utilities', 'Utilities', 150),
                ('Council Tax', 'Council Tax', 150),
                ('Entertainment', 'Entertainment', 200),
                ('Eating Out', 'Eating Out', 300),
                ('Shopping', 'Shopping', 250),
                ('Health', 'Health & Fitness', 100),
            ]
        else:
            return Response(
                {'error': 'Invalid template. Use "essential" or "comprehensive"'},
                status=status.HTTP_400_BAD_REQUEST
            )

        created_budgets = []
        skipped = []

        end_date = (start_date + timedelta(days=32)
                    ).replace(day=1) - timedelta(days=1)

        for budget_name, category_name, amount in budget_templates:
            try:
                category = Category.objects.get(
                    user=request.user,
                    category_name=category_name,
                    category_type='expense'
                )

                if Budget.objects.filter(
                    user=request.user,
                    category=category,
                    start_date__lte=end_date,
                    end_date__gte=start_date,
                    is_active=True
                ).exists():
                    skipped.append(category_name)
                    continue

                budget = Budget.objects.create(
                    user=request.user,
                    category=category,
                    budget_name=f"Monthly {budget_name} Budget",
                    budget_amount=Decimal(str(amount)),
                    period_type='monthly',
                    start_date=start_date,
                    end_date=end_date,
                    is_active=True
                )
                created_budgets.append(budget)

            except Category.DoesNotExist:
                skipped.append(category_name)

        return Response({
            'created_count': len(created_budgets),
            'created_budgets': BudgetSerializer(
                created_budgets,
                many=True,
                context={'request': request}
            ).data,
            'skipped_categories': skipped
        })

    def _determine_budget_status(self, spent, budget_amount, percentage):
        if percentage <= 50:
            return 'on_track'
        elif percentage <= 80:
            return 'attention'
        elif percentage <= 100:
            return 'warning'
        else:
            return 'exceeded'

    def _identify_savings_opportunities(self, user):
        last_month = timezone.now().date() - timedelta(days=30)

        variable_expenses = Transaction.objects.filter(
            user=user,
            transaction_type='expense',
            transaction_date__gte=last_month,
            category__category_name__in=[
                'Eating Out', 'Entertainment', 'Shopping', 'Subscriptions']
        ).values('category__category_name').annotate(
            total=Sum('transaction_amount')
        ).order_by('total')[:3]

        return [
            {
                'category': exp['category__category_name'],
                'current_spending': float(abs(exp['total'])),
                'potential_savings': float(abs(exp['total']) * Decimal('0.2')),
                'suggestion': f"Reducing by 20% could save £{abs(exp['total']) * Decimal('0.2'):.2f}"
            }
            for exp in variable_expenses
        ]

    def _recommend_budget_periods(self, historical_patterns):
        recommendations = {}

        for category, data in historical_patterns.items():
            if len(data['amounts']) >= 2:
                amounts = data['amounts']
                avg = sum(amounts) / len(amounts)
                variance = sum((x - avg) ** 2 for x in amounts) / len(amounts)
                std_dev = variance ** 0.5
                cv = (std_dev / avg) if avg > 0 else 0

                if cv < 0.15:
                    recommendations[category] = 'monthly'
                elif cv < 0.30:
                    recommendations[category] = 'quarterly'
                else:
                    recommendations[category] = 'weekly'

        return recommendations
