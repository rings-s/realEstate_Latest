from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('google-auth/', views.google_auth, name='google_auth'),
    path('refresh/', views.refresh_token, name='refresh_token'),
    path('profile/', views.profile, name='profile'),
    path('profile/update/', views.update_profile, name='update_profile'),
    path('password/reset-request/', views.password_reset_request, name='password_reset_request'),
    path('password/reset/', views.password_reset, name='password_reset'),
    path('password/change/', views.change_password, name='change_password'),
    path('verify-email/', views.verify_email, name='verify_email'),
]