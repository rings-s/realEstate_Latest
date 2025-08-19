from django.urls import path
from . import views

urlpatterns = [
    path('', views.notification_list, name='notification_list'),
    path('unread-count/', views.unread_count, name='unread_count'),
    path('preferences/', views.notification_preferences, name='notification_preferences'),
    path('mark-all-read/', views.mark_all_as_read, name='mark_all_as_read'),
    path('clear/', views.clear_notifications, name='clear_notifications'),
    path('test/', views.test_notification, name='test_notification'),
    path('<uuid:pk>/', views.notification_detail, name='notification_detail'),
    path('<uuid:pk>/read/', views.mark_as_read, name='mark_as_read'),
    path('<uuid:pk>/delete/', views.delete_notification, name='delete_notification'),
]