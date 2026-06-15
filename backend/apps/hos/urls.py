from django.urls import path
from . import views

urlpatterns = [
    path('hos/status/', views.HOSStatusView.as_view(), name='hos_status'),
    path('validate/hos/', views.ValidateHOSView.as_view(), name='validate_hos'),
    path('hos/logs/', views.DutyStatusLogListView.as_view(), name='duty_log_list'),
]
