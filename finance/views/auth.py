from django.contrib.auth.models import User
from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from finance.serializers import UserSerializer


@api_view(['POST'])
@permission_classes([AllowAny])
def register_view(request):
    """
    Register a new user

    Request body:
    {
        "username": "john_doe",
        "email": "john@example.com",
        "password": "securepass123",
        "first_name": "John",
        "last_name": "Doe"
    }
    """
    serializer = UserSerializer(data=request.data)

    if serializer.is_valid():
        # Create user
        user = serializer.save()

        # Create token for the user
        token, created = Token.objects.get_or_create(user=user)

        # Create default categories for new user
        from finance.models import Category
        default_categories = [
            ('Salary', 'income'),
            ('Freelance', 'income'),
            ('Other Income', 'income'),
            ('Rent/Mortgage', 'expense'),
            ('Groceries', 'expense'),
            ('Transport', 'expense'),
            ('Utilities', 'expense'),
            ('Entertainment', 'expense'),
            ('Other Expense', 'expense'),
        ]

        for name, cat_type in default_categories:
            Category.objects.get_or_create(
                user=user,
                category_name=name,
                category_type=cat_type,
                defaults={'is_default': True}
            )

        return Response({
            'message': 'User created successfully',
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name
            },
            'token': token.key,
            'categories_created': len(default_categories)
        }, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    """
    Login user and return token

    Request body:
    {
        "username": "john_doe",
        "password": "securepass123"
    }
    """
    username = request.data.get('username')
    password = request.data.get('password')

    if not username or not password:
        return Response({
            'error': 'Username and password are required'
        }, status=status.HTTP_400_BAD_REQUEST)

    # Try to authenticate
    from django.contrib.auth import authenticate
    user = authenticate(username=username, password=password)

    if user:
        if not user.is_active:
            return Response({
                'error': 'User account is disabled'
            }, status=status.HTTP_403_FORBIDDEN)

        # Get or create token
        token, created = Token.objects.get_or_create(user=user)

        # Update last login
        from django.utils import timezone
        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])

        # Get user's account summary
        from finance.models import BankAccount, Category, Transaction, Budget

        accounts_count = BankAccount.objects.filter(
            user=user, is_active=True).count()
        categories_count = Category.objects.filter(
            user=user, is_active=True).count()
        recent_transactions = Transaction.objects.filter(user=user).count()
        active_budgets = Budget.objects.filter(
            user=user,
            is_active=True,
            start_date__lte=timezone.now().date(),
            end_date__gte=timezone.now().date()
        ).count()

        return Response({
            'message': 'Login successful',
            'token': token.key,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'last_login': user.last_login.isoformat() if user.last_login else None
            },
            'summary': {
                'accounts': accounts_count,
                'categories': categories_count,
                'transactions': recent_transactions,
                'active_budgets': active_budgets
            }
        })

    return Response({
        'error': 'Invalid username or password'
    }, status=status.HTTP_401_UNAUTHORIZED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """
    Logout user by deleting their token
    """
    try:
        # Delete the user's token
        request.user.auth_token.delete()

        return Response({
            'message': 'Logout successful'
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({
            'error': 'An error occurred during logout'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def profile_view(request):
    """
    Get current user's profile
    """
    serializer = UserSerializer(request.user, context={'request': request})

    # Get additional stats
    from finance.models import BankAccount, Transaction
    from django.db.models import Sum
    from decimal import Decimal

    # Calculate net worth
    net_worth = BankAccount.objects.filter(
        user=request.user,
        is_active=True
    ).aggregate(
        total=Sum('current_balance')
    )['total'] or Decimal('0')

    # Get this month's income/expenses
    from django.utils import timezone
    from datetime import timedelta

    current_month_start = timezone.now().date().replace(day=1)

    monthly_stats = Transaction.objects.filter(
        user=request.user,
        transaction_date__gte=current_month_start
    ).aggregate(
        income=Sum('transaction_amount', filter=Q(transaction_type='income')),
        expenses=Sum('transaction_amount', filter=Q(
            transaction_type='expense'))
    )

    response_data = serializer.data
    response_data['financial_summary'] = {
        'net_worth': float(net_worth),
        'monthly_income': float(monthly_stats['income'] or 0),
        'monthly_expenses': float(abs(monthly_stats['expenses'] or 0)),
        'monthly_savings': float((monthly_stats['income'] or 0) + (monthly_stats['expenses'] or 0))
    }

    return Response(response_data)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_profile_view(request):
    """
    Update current user's profile

    Request body (all fields optional):
    {
        "email": "newemail@example.com",
        "first_name": "John",
        "last_name": "Smith",
        "password": "newpassword123"
    }
    """
    serializer = UserSerializer(
        request.user,
        data=request.data,
        partial=True,
        context={'request': request}
    )

    if serializer.is_valid():
        serializer.save()
        return Response({
            'message': 'Profile updated successfully',
            'user': serializer.data
        })

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
