from django.urls import path
from . import views

urlpatterns = [
    # Payment Methods
    path('methods/', views.payment_methods, name='payment_methods'),
    path('methods/add/', views.add_payment_method, name='add_payment_method'),
    path('methods/<uuid:pk>/delete/', views.delete_payment_method, name='delete_payment_method'),
    path('methods/<uuid:pk>/set-default/', views.set_default_payment_method, name='set_default_payment_method'),
    
    # Transactions
    path('transactions/', views.transaction_list, name='transaction_list'),
    path('transactions/<str:transaction_id>/', views.transaction_detail, name='transaction_detail'),
    path('process/', views.process_payment, name='process_payment'),
    
    # Wallet
    path('wallet/', views.wallet_balance, name='wallet_balance'),
    path('wallet/withdraw/', views.withdraw_from_wallet, name='withdraw_from_wallet'),
]