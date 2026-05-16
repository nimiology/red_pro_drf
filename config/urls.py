from django.contrib import admin
from django.urls import path, include
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

schema_view = get_schema_view(
    openapi.Info(
        title="Red DRF API",
        default_version='v1',
        description="API documentation for Red app",
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path('admin/', admin.admin_site.urls if hasattr(admin, 'admin_site') else admin.site.urls),
    
    # API Documentation
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    
    # Auth
    path('auth/', include('djoser.urls')),
    path('auth/', include('djoser.urls.jwt')),
    
    # App URLs
    path('accounts/', include('apps.accounts.urls')),
    path('activities/', include('apps.activities.urls')),
    path('squads/', include('apps.squads.urls')),
    path('missions/', include('apps.missions.urls')),
]
