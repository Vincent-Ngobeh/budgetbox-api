"""
Main URL Configuration for BudgetBox Project
"""
from django.contrib import admin
from django.urls import path, include
from rest_framework.authtoken.views import obtain_auth_token
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.db.models import Q
from finance.views.auth import (
    register_view,
    login_view,
    logout_view,
    profile_view,
    update_profile_view
)


@api_view(['GET'])
def api_root(request):
    """
    API root endpoint - provides overview of available endpoints
    """
    return Response({
        'message': 'Welcome to BudgetBox API',
        'version': '1.0.0',
        'endpoints': {
            'auth': {
                'login': '/api/auth/login/',
                'logout': '/api/auth/logout/',
                'register': '/api/auth/register/',
            },
            'finance': {
                'accounts': '/api/accounts/',
                'categories': '/api/categories/',
                'transactions': '/api/transactions/',
                'budgets': '/api/budgets/',
            },
            'admin': '/admin/',
        },
        'documentation': {
            'api_browser': '/api/',
            'schema': '/api/schema/',
        }
    })


urlpatterns = [
    # Admin site
    path('admin/', admin.site.urls),

    # API root
    path('', api_root, name='api-root'),
    path('api/', api_root, name='api-root-alt'),

    # Authentication endpoints
    path('api/auth/login/', login_view, name='api-login'),
    path('api/auth/logout/', logout_view, name='api-logout'),
    path('api/auth/register/', register_view, name='api-register'),
    path('api/auth/profile/', profile_view, name='api-profile'),
    path('api/auth/profile/update/',
         update_profile_view, name='api-profile-update'),

    # Alternative token auth endpoint (DRF built-in)
    path('api/auth/token/', obtain_auth_token, name='api-token-auth'),

    # Finance app URLs
    path('api/', include('finance.urls')),

    # DRF browsable API auth
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),
]
