from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
import uuid
from decimal import Decimal


class PaymentMethod(models.Model):
    """User payment methods."""
    
    METHOD_TYPES = (
        ('card', 'Credit/Debit Card'),
        ('bank', 'Bank Transfer'),
        ('wallet', 'Digital Wallet'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='payment_methods')
    
    # Method details
    method_type = models.CharField(_('method type'), max_length=20, choices=METHOD_TYPES)
    stripe_payment_method_id = models.CharField(_('stripe payment method ID'), max_length=255, unique=True, blank=True)
    
    # Card details (masked)
    last_four = models.CharField(_('last four digits'), max_length=4, blank=True)
    brand = models.CharField(_('brand'), max_length=50, blank=True)
    exp_month = models.IntegerField(_('expiry month'), null=True, blank=True)
    exp_year = models.IntegerField(_('expiry year'), null=True, blank=True)
    
    # Bank details
    bank_name = models.CharField(_('bank name'), max_length=100, blank=True)
    account_number_masked = models.CharField(_('account number (masked)'), max_length=50, blank=True)
    
    # Status
    is_default = models.BooleanField(_('is default'), default=False)
    is_verified = models.BooleanField(_('is verified'), default=False)
    
    # Timestamps
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    
    class Meta:
        db_table = 'payment_methods'
        verbose_name = _('Payment Method')
        verbose_name_plural = _('Payment Methods')
        ordering = ['-is_default', '-created_at']
    
    def __str__(self):
        if self.method_type == 'card':
            return f"{self.brand} ending in {self.last_four}"
        elif self.method_type == 'bank':
            return f"{self.bank_name} - {self.account_number_masked}"
        return f"{self.get_method_type_display()}"


class Transaction(models.Model):
    """Payment transactions."""
    
    TRANSACTION_TYPES = (
        ('payment', 'Payment'),
        ('refund', 'Refund'),
        ('payout', 'Payout'),
        ('transfer', 'Transfer'),
        ('subscription', 'Subscription'),
        ('deposit', 'Deposit'),
    )
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('succeeded', 'Succeeded'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction_id = models.CharField(_('transaction ID'), max_length=100, unique=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='transactions')
    
    # Type and status
    transaction_type = models.CharField(_('type'), max_length=20, choices=TRANSACTION_TYPES)
    status = models.CharField(_('status'), max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Amounts
    amount = models.DecimalField(_('amount'), max_digits=12, decimal_places=2)
    currency = models.CharField(_('currency'), max_length=3, default='SAR')
    fee = models.DecimalField(_('fee'), max_digits=10, decimal_places=2, default=Decimal('0.00'))
    net_amount = models.DecimalField(_('net amount'), max_digits=12, decimal_places=2)
    
    # Payment details
    payment_method = models.ForeignKey(PaymentMethod, on_delete=models.SET_NULL, null=True, blank=True)
    stripe_payment_intent_id = models.CharField(_('stripe payment intent ID'), max_length=255, blank=True)
    stripe_charge_id = models.CharField(_('stripe charge ID'), max_length=255, blank=True)
    
    # Reference
    reference_type = models.CharField(_('reference type'), max_length=50, blank=True)
    reference_id = models.CharField(_('reference ID'), max_length=100, blank=True)
    description = models.TextField(_('description'), blank=True)
    
    # Metadata
    metadata = models.JSONField(_('metadata'), default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    completed_at = models.DateTimeField(_('completed at'), null=True, blank=True)
    
    class Meta:
        db_table = 'transactions'
        verbose_name = _('Transaction')
        verbose_name_plural = _('Transactions')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['transaction_id']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['reference_type', 'reference_id']),
        ]
    
    def save(self, *args, **kwargs):
        self.net_amount = self.amount - self.fee
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.transaction_id} - {self.amount} {self.currency}"


class Wallet(models.Model):
    """User wallet for balance management."""
    
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='wallet')
    
    # Balances
    balance = models.DecimalField(_('balance'), max_digits=12, decimal_places=2, default=Decimal('0.00'))
    pending_balance = models.DecimalField(_('pending balance'), max_digits=12, decimal_places=2, default=Decimal('0.00'))
    currency = models.CharField(_('currency'), max_length=3, default='SAR')
    
    # Limits
    withdrawal_limit = models.DecimalField(_('withdrawal limit'), max_digits=10, decimal_places=2, default=Decimal('10000.00'))
    
    # Status
    is_active = models.BooleanField(_('is active'), default=True)
    is_verified = models.BooleanField(_('is verified'), default=False)
    
    # Timestamps
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    last_activity = models.DateTimeField(_('last activity'), null=True, blank=True)
    
    class Meta:
        db_table = 'wallets'
        verbose_name = _('Wallet')
        verbose_name_plural = _('Wallets')
    
    def __str__(self):
        return f"{self.user.email} - {self.balance} {self.currency}"