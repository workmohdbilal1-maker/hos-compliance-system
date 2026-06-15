from django.urls import path
from . import views

urlpatterns = [
    path('trips/<int:trip_id>/pdf/', views.TripPDFView.as_view(), name='trip_pdf'),
    path('templates/mapping/', views.TemplateMappingView.as_view(), name='template_mapping'),
]
