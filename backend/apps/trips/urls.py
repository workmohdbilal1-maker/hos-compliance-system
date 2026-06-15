from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'trips', views.TripViewSet, basename='trip')

urlpatterns = [
    path('', include(router.urls)),
    path('maps/route/', views.RouteView.as_view(), name='route'),
    path('maps/geocode/', views.GeocodeView.as_view(), name='geocode'),
]
