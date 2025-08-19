from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
import uuid


class SubscriptionPlan(models.Model):
    """Subscription plans for the SaaS platform."""
    
    PLAN_TYPES = (
        ('free', 'Free'),
        ('basic', 'Basic'),
        ('premium', 'Premium'),
        ('enterprise', 'Enterprise'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_('name'), max_length=100)
    slug = models.SlugField(_('slug'), unique=True)
    plan_type = models.CharField(_('plan type'), max_length=20, choices=PLAN_TYPES, unique=True)
    stripe_price_id = models.CharField(_('stripe price ID'), max_length=255, blank=True)
    
    # Pricing
    price_monthly = models.DecimalField(_('monthly price'), max_digits=10, decimal_places=2)
    price_yearly = models.DecimalField(_('yearly price'), max_digits=10, decimal_places=2)
    currency = models.CharField(_('currency'), max_length=3, default='SAR')
    
    # Features
    max_properties = models.IntegerField(_('max properties'), default=10)
    max_users = models.IntegerField(_('max users'), default=2)
    max_auctions = models.IntegerField(_('max auctions per month'), default=5)
    max_tenants = models.IntegerField(_('max tenants'), default=10)
    
    # Feature flags
    has_analytics = models.BooleanField(_('has analytics'), default=False)
    has_api_access = models.BooleanField(_('has API access'), default=False)
    has_custom_branding = models.BooleanField(_('has custom branding'), default=False)
    has_priority_support = models.BooleanField(_('has priority support'), default=False)
    has_tenant_portal = models.BooleanField(_('has tenant portal'), default=False)
    has_maintenance_module = models.BooleanField(_('has maintenance module'), default=False)
    has_document_storage = models.BooleanField(_('has document storage'), default=False)
    has_advanced_reporting = models.BooleanField(_('has advanced reporting'), default=False)
    has_sms_notifications = models.BooleanField(_('has SMS notifications'), default=False)
    
    # Storage limits (in GB)
    storage_limit = models.IntegerField(_('storage limit (GB)'), default=5)
    
    # Meta
    is_active = models.BooleanField(_('is active'), default=True)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    
    class Meta:
        db_table = 'subscription_plans'
        verbose_name = _('Subscription Plan')
        verbose_name_plural = _('Subscription Plans')
        ordering = ['price_monthly']
    
    def __str__(self):
        return f"{self.name} ({self.get_plan_type_display()})"


class Subscription(models.Model):
    """User subscriptions."""
    
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('canceled', 'Canceled'),
        ('past_due', 'Past Due'),
        ('trialing', 'Trialing'),
        ('paused', 'Paused'),
    )
    
    BILLING_PERIOD = (
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='subscription')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT, related_name='subscriptions')
    
    # Stripe fields
    stripe_subscription_id = models.CharField(_('stripe subscription ID'), max_length=255, unique=True, blank=True)
    stripe_customer_id = models.CharField(_('stripe customer ID'), max_length=255, blank=True)
    
    # Subscription details
    status = models.CharField(_('status'), max_length=20, choices=STATUS_CHOICES, default='trialing')
    billing_period = models.CharField(_('billing period'), max_length=20, choices=BILLING_PERIOD, default='monthly')
    
    # Dates
    start_date = models.DateTimeField(_('start date'), auto_now_add=True)
    end_date = models.DateTimeField(_('end date'), null=True, blank=True)
    trial_end = models.DateTimeField(_('trial end'), null=True, blank=True)
    canceled_at = models.DateTimeField(_('canceled at'), null=True, blank=True)
    
    # Usage tracking
    properties_count = models.IntegerField(_('properties count'), default=0)
    users_count = models.IntegerField(_('users count'), default=1)
    auctions_this_month = models.IntegerField(_('auctions this month'), default=0)
    storage_used = models.FloatField(_('storage used (GB)'), default=0.0)
    
    # Meta
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    
    class Meta:
        db_table = 'subscriptions'
        verbose_name = _('Subscription')
        verbose_name_plural = _('Subscriptions')
        indexes = [
            models.Index(fields=['stripe_subscription_id']),
            models.Index(fields=['status', 'end_date']),
        ]
    
    def is_active(self):
        """Check if subscription is active."""
        from django.utils import timezone
        return self.status == 'active' and (self.end_date is None or self.end_date > timezone.now())
    
    def can_add_property(self):
        """Check if user can add more properties."""
        return self.properties_count < self.plan.max_properties
    
    def can_add_auction(self):
        """Check if user can add more auctions this month."""
        return self.auctions_this_month < self.plan.max_auctions
    
    def __str__(self):
        return f"{self.user.email} - {self.plan.name} ({self.status})"


class PaymentHistory(models.Model):
    """Payment history for subscriptions."""
    
    STATUS_CHOICES = (
        ('succeeded', 'Succeeded'),
        ('pending', 'Pending'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name='payments')
    
    # Payment details
    stripe_payment_intent_id = models.CharField(_('stripe payment intent ID'), max_length=255, unique=True)
    amount = models.DecimalField(_('amount'), max_digits=10, decimal_places=2)
    currency = models.CharField(_('currency'), max_length=3, default='SAR')
    status = models.CharField(_('status'), max_length=20, choices=STATUS_CHOICES)
    
    # Invoice
    invoice_number = models.CharField(_('invoice number'), max_length=100, unique=True)
    invoice_pdf_url = models.URLField(_('invoice PDF URL'), blank=True)
    
    # Meta
    paid_at = models.DateTimeField(_('paid at'), null=True, blank=True)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    
    class Meta:
        db_table = 'payment_history'
        verbose_name = _('Payment History')
        verbose_name_plural = _('Payment Histories')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['stripe_payment_intent_id']),
            models.Index(fields=['invoice_number']),
        ]
    
    def __str__(self):
        return f"{self.invoice_number} - {self.amount} {self.currency}"