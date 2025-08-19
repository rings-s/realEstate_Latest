from django.urls import path
from . import views

urlpatterns = [
    path('', views.property_list, name='property_list'),
    path('create/', views.property_create, name='property_create'),
    path('my-properties/', views.my_properties, name='my_properties'),
    path('statistics/', views.property_statistics, name='property_statistics'),
    path('<uuid:pk>/', views.property_detail, name='property_detail'),
    path('<uuid:pk>/update/', views.property_update, name='property_update'),
    path('<uuid:pk>/delete/', views.property_delete, name='property_delete'),
    path('<uuid:pk>/favorite/', views.toggle_favorite, name='toggle_favorite'),
]