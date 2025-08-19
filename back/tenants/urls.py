from django.urls import path
from . import views

urlpatterns = [
    path('', views.tenant_list, name='tenant_list'),
    path('create/', views.tenant_create, name='tenant_create'),
    path('dashboard/', views.tenant_dashboard, name='tenant_dashboard'),
    path('<uuid:pk>/', views.tenant_detail, name='tenant_detail'),
    
    path('leases/', views.lease_list, name='lease_list'),
    path('leases/create/', views.lease_create, name='lease_create'),
    
    path('payments/', views.rent_payments, name='rent_payments'),
    path('payments/<uuid:pk>/record/', views.record_payment, name='record_payment'),
    
    path('maintenance/', views.maintenance_requests, name='maintenance_requests'),
    path('maintenance/<uuid:pk>/update/', views.update_maintenance_request, name='update_maintenance_request'),
]