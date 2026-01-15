from django.contrib.auth.models import User
from django.db.models import Q
from rest_framework import status, serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from drf_spectacular.utils import extend_schema, OpenApiResponse, inline_serializer
from finance.serializers import UserSerializer


# Request/Response serializers for documentation
class RegisterRequestSerializer(serializers.Serializer):
    username = serializers.CharField(
        help_text="Unique username for the account")
    email = serializers.EmailField(help_text="User's email address")
    password = serializers.CharField(help_text="Password (min 8 characters)")
    first_name = serializers.CharField(help_text="User's first name")
    last_name = serializers.CharField(help_text="User's last name")


class LoginRequestSerializer(serializers.Serializer):
    username = serializers.CharField(help_text="Username")
    password = serializers.CharField(help_text="Password")


class ChangePasswordRequestSerializer(serializers.Serializer):
    current_password = serializers.CharField(help_text="Current password")
    new_password = serializers.CharField(
        help_text="New password (min 8 characters)")


class UpdateProfileRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(
        required=False, help_text="New email address")
    first_name = serializers.CharField(
        required=False, help_text="New first name")
    last_name = serializers.CharField(
        required=False, help_text="New last name")


@extend_schema(
    tags=['Authentication'],
    summary='Register a new user',
    description='Create a new user account. Default categories will be created automatically.',
    request=RegisterRequestSerializer,
    responses={
        201: OpenApiResponse(
            description='User created successfully',
            response=inline_serializer(
                name='RegisterResponse',
                fields={
                    'message': serializers.CharField(),
                    'user': inline_serializer(
                        name='RegisterUserData',
                        fields={
                            'id': serializers.IntegerField(),
                            'username': serializers.CharField(),
                            'email': serializers.EmailField(),
                            'first_name': serializers.CharField(),
                            'last_name': serializers.CharField(),
                        }
                    ),
                    'token': serializers.CharField(),
                    'categories_created': serializers.IntegerField(),
                }
            )
        ),
        400: OpenApiResponse(description='Validation error'),
    }
)
@api_view(['POST'])
@permission_classes([AllowAny])
def register_view(request):
    """Register a new user and create default categories."""
    try:
        serializer = UserSerializer(data=request.data)

        if serializer.is_valid():
            user = serializer.save()

            token, created = Token.objects.get_or_create(user=user)

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

    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'Registration error: {str(e)}')
        return Response({
            'error': 'An error occurred during registration. Please try again.',
            'detail': str(e) if request.query_params.get('debug') else None
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    tags=['Authentication'],
    summary='Login user',
    description='Authenticate user and return an access token along with account summary.',
    request=LoginRequestSerializer,
    responses={
        200: OpenApiResponse(
            description='Login successful',
            response=inline_serializer(
                name='LoginResponse',
                fields={
                    'message': serializers.CharField(),
                    'token': serializers.CharField(),
                    'user': inline_serializer(
                        name='LoginUserData',
                        fields={
                            'id': serializers.IntegerField(),
                            'username': serializers.CharField(),
                            'email': serializers.EmailField(),
                            'first_name': serializers.CharField(),
                            'last_name': serializers.CharField(),
                            'last_login': serializers.DateTimeField(),
                        }
                    ),
                    'summary': inline_serializer(
                        name='LoginSummary',
                        fields={
                            'accounts': serializers.IntegerField(),
                            'categories': serializers.IntegerField(),
                            'transactions': serializers.IntegerField(),
                            'active_budgets': serializers.IntegerField(),
                        }
                    ),
                }
            )
        ),
        400: OpenApiResponse(description='Username and password are required'),
        401: OpenApiResponse(description='Invalid credentials'),
        403: OpenApiResponse(description='User account is disabled'),
    }
)
@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    """Authenticate user and return access token."""
    username = request.data.get('username')
    password = request.data.get('password')

    if not username or not password:
        return Response({
            'error': 'Username and password are required'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        from django.contrib.auth import authenticate
        user = authenticate(username=username, password=password)

        if user:
            if not user.is_active:
                return Response({
                    'error': 'User account is disabled'
                }, status=status.HTTP_403_FORBIDDEN)

            token, created = Token.objects.get_or_create(user=user)

            from django.utils import timezone
            user.last_login = timezone.now()
            user.save(update_fields=['last_login'])

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

    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'Login error for user {username}: {str(e)}')
        return Response({
            'error': 'An error occurred during login. Please try again.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    tags=['Authentication'],
    summary='Logout user',
    description='Logout the current user by deleting their authentication token.',
    request=None,
    responses={
        200: OpenApiResponse(
            description='Logout successful',
            response=inline_serializer(
                name='LogoutResponse',
                fields={'message': serializers.CharField()}
            )
        ),
        500: OpenApiResponse(description='Server error during logout'),
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """Logout user by deleting their token."""
    try:
        request.user.auth_token.delete()

        return Response({
            'message': 'Logout successful'
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({
            'error': 'An error occurred during logout'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    tags=['Authentication'],
    summary='Get user profile',
    description='Retrieve the current user profile with financial summary including net worth and monthly statistics.',
    responses={
        200: OpenApiResponse(
            description='Profile retrieved successfully',
            response=inline_serializer(
                name='ProfileResponse',
                fields={
                    'id': serializers.IntegerField(),
                    'username': serializers.CharField(),
                    'email': serializers.EmailField(),
                    'first_name': serializers.CharField(),
                    'last_name': serializers.CharField(),
                    'date_joined': serializers.DateTimeField(),
                    'last_login': serializers.DateTimeField(),
                    'total_accounts': serializers.IntegerField(),
                    'total_categories': serializers.IntegerField(),
                    'financial_summary': inline_serializer(
                        name='FinancialSummary',
                        fields={
                            'net_worth': serializers.FloatField(),
                            'monthly_income': serializers.FloatField(),
                            'monthly_expenses': serializers.FloatField(),
                            'monthly_savings': serializers.FloatField(),
                        }
                    ),
                }
            )
        ),
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def profile_view(request):
    """Get current user's profile with financial summary."""
    serializer = UserSerializer(request.user, context={'request': request})

    from finance.models import BankAccount, Transaction
    from django.db.models import Sum
    from decimal import Decimal

    net_worth = BankAccount.objects.filter(
        user=request.user,
        is_active=True
    ).aggregate(
        total=Sum('current_balance')
    )['total'] or Decimal('0')

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


@extend_schema(
    tags=['Authentication'],
    summary='Update user profile',
    description='Update the current user profile. For password changes, use the change-password endpoint.',
    request=UpdateProfileRequestSerializer,
    responses={
        200: OpenApiResponse(
            description='Profile updated successfully',
            response=inline_serializer(
                name='UpdateProfileResponse',
                fields={
                    'message': serializers.CharField(),
                    'user': UserSerializer(),
                }
            )
        ),
        400: OpenApiResponse(description='Validation error or password change attempted'),
    }
)
@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_profile_view(request):
    """Update current user's profile."""
    data = request.data.copy()
    if 'password' in data:
        return Response({
            'error': 'Password changes must be done through /api/auth/change-password/ endpoint'
        }, status=status.HTTP_400_BAD_REQUEST)

    serializer = UserSerializer(
        request.user,
        data=data,
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


@extend_schema(
    tags=['Authentication'],
    summary='Change password',
    description='Change the current user password. The old token will be invalidated and a new one returned.',
    request=ChangePasswordRequestSerializer,
    responses={
        200: OpenApiResponse(
            description='Password changed successfully',
            response=inline_serializer(
                name='ChangePasswordResponse',
                fields={
                    'message': serializers.CharField(),
                    'token': serializers.CharField(help_text='New authentication token'),
                }
            )
        ),
        400: OpenApiResponse(description='Validation error or incorrect current password'),
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password_view(request):
    """Change user password and return new token."""
    current_password = request.data.get('current_password')
    new_password = request.data.get('new_password')

    if not current_password:
        return Response({
            'error': 'Current password is required'
        }, status=status.HTTP_400_BAD_REQUEST)

    if not new_password:
        return Response({
            'error': 'New password is required'
        }, status=status.HTTP_400_BAD_REQUEST)

    if not request.user.check_password(current_password):
        return Response({
            'error': 'Current password is incorrect'
        }, status=status.HTTP_400_BAD_REQUEST)

    if len(new_password) < 8:
        return Response({
            'error': 'New password must be at least 8 characters long'
        }, status=status.HTTP_400_BAD_REQUEST)

    if current_password == new_password:
        return Response({
            'error': 'New password must be different from current password'
        }, status=status.HTTP_400_BAD_REQUEST)

    from django.contrib.auth.password_validation import validate_password
    from django.core.exceptions import ValidationError

    try:
        validate_password(new_password, user=request.user)
    except ValidationError as e:
        return Response({
            'error': 'Password validation failed',
            'details': list(e.messages)
        }, status=status.HTTP_400_BAD_REQUEST)

    request.user.set_password(new_password)
    request.user.save()

    try:
        request.user.auth_token.delete()
    except:
        pass

    new_token, created = Token.objects.get_or_create(user=request.user)

    return Response({
        'message': 'Password changed successfully',
        'token': new_token.key
    }, status=status.HTTP_200_OK)
