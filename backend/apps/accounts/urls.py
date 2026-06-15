from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from . import views

urlpatterns = [
    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('me/', views.DriverDetailView.as_view(), name='driver_detail'),
    path('drivers/<int:driver_id>/history/', views.DriverHistoryView.as_view(), name='driver_history'),
    path('drivers/<int:driver_id>/data/', views.DriverDataErasureView.as_view(), name='driver_data_erasure'),
]
