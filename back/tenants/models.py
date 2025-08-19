from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.utils import timezone
import uuid
from decimal import Decimal


class Tenant(models.Model):
    """Tenant model for property rentals."""
    
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('pending', 'Pending'),
        ('blacklisted', 'Blacklisted'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tenant_profile', null=True, blank=True)
    landlord = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tenants')
    
    # Personal Information
    first_name = models.CharField(_('first name'), max_length=150)
    last_name = models.CharField(_('last name'), max_length=150)
    email = models.EmailField(_('email'))
    phone = models.CharField(_('phone'), max_length=20)
    national_id = models.CharField(_('national ID'), max_length=20, unique=True)
    
    # Tenant Details
    occupation = models.CharField(_('occupation'), max_length=100, blank=True)
    employer = models.CharField(_('employer'), max_length=200, blank=True)
    monthly_income = models.DecimalField(_('monthly income'), max_digits=10, decimal_places=2, null=True, blank=True)
    emergency_contact = models.JSONField(_('emergency contact'), default=dict, blank=True)
    
    # Status
    status = models.CharField(_('status'), max_length=20, choices=STATUS_CHOICES, default='pending')
    credit_score = models.IntegerField(_('credit score'), null=True, blank=True)
    
    # Documents
    documents = models.JSONField(_('documents'), default=list, blank=True)
    
    # Meta
    notes = models.TextField(_('notes'), blank=True)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    
    class Meta:
        db_table = 'tenants'
        verbose_name = _('Tenant')
        verbose_name_plural = _('Tenants')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'landlord']),
            models.Index(fields=['national_id']),
        ]
    
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    def __str__(self):
        return self.get_full_name()


class Lease(models.Model):
    """Lease agreements between landlords and tenants."""
    
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('terminated', 'Terminated'),
        ('renewed', 'Renewed'),
    )
    
    PAYMENT_FREQUENCY = (
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('semi_annual', 'Semi-Annual'),
        ('annual', 'Annual'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    property = models.ForeignKey('properties.Property', on_delete=models.CASCADE, related_name='leases')
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='leases')
    landlord = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='leases_as_landlord')
    
    # Lease Details
    lease_number = models.CharField(_('lease number'), max_length=50, unique=True)
    start_date = models.DateField(_('start date'))
    end_date = models.DateField(_('end date'))
    status = models.CharField(_('status'), max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Financial Terms
    monthly_rent = models.DecimalField(_('monthly rent'), max_digits=10, decimal_places=2)
    security_deposit = models.DecimalField(_('security deposit'), max_digits=10, decimal_places=2)
    payment_frequency = models.CharField(_('payment frequency'), max_length=20, choices=PAYMENT_FREQUENCY, default='monthly')
    late_fee = models.DecimalField(_('late fee'), max_digits=8, decimal_places=2, default=Decimal('0.00'))
    grace_period_days = models.IntegerField(_('grace period days'), default=5)
    
    # Terms
    terms_conditions = models.TextField(_('terms and conditions'), blank=True)
    special_conditions = models.TextField(_('special conditions'), blank=True)
    auto_renew = models.BooleanField(_('auto renew'), default=False)
    
    # Documents
    contract_document = models.FileField(_('contract document'), upload_to='leases/', null=True, blank=True)
    signed_date = models.DateTimeField(_('signed date'), null=True, blank=True)
    
    # Meta
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    
    class Meta:
        db_table = 'leases'
        verbose_name = _('Lease')
        verbose_name_plural = _('Leases')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'start_date', 'end_date']),
            models.Index(fields=['lease_number']),
        ]
    
    def is_active(self):
        today = timezone.now().date()
        return self.status == 'active' and self.start_date <= today <= self.end_date
    
    def __str__(self):
        return f"{self.lease_number} - {self.tenant}"


class RentPayment(models.Model):
    """Rent payment records."""
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('partial', 'Partial'),
        ('late', 'Late'),
        ('failed', 'Failed'),
    )
    
    PAYMENT_METHOD = (
        ('bank_transfer', 'Bank Transfer'),
        ('cash', 'Cash'),
        ('check', 'Check'),
        ('online', 'Online Payment'),
        ('stripe', 'Stripe'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lease = models.ForeignKey(Lease, on_delete=models.CASCADE, related_name='payments')
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='rent_payments')
    
    # Payment Details
    amount_due = models.DecimalField(_('amount due'), max_digits=10, decimal_places=2)
    amount_paid = models.DecimalField(_('amount paid'), max_digits=10, decimal_places=2, default=Decimal('0.00'))
    payment_date = models.DateField(_('payment date'))
    due_date = models.DateField(_('due date'))
    status = models.CharField(_('status'), max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_method = models.CharField(_('payment method'), max_length=20, choices=PAYMENT_METHOD, null=True, blank=True)
    
    # Transaction Details
    transaction_id = models.CharField(_('transaction ID'), max_length=100, blank=True)
    receipt_number = models.CharField(_('receipt number'), max_length=50, unique=True)
    
    # Late Payment
    late_fee_applied = models.DecimalField(_('late fee applied'), max_digits=8, decimal_places=2, default=Decimal('0.00'))
    
    # Notes
    notes = models.TextField(_('notes'), blank=True)
    
    # Timestamps
    paid_at = models.DateTimeField(_('paid at'), null=True, blank=True)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    
    class Meta:
        db_table = 'rent_payments'
        verbose_name = _('Rent Payment')
        verbose_name_plural = _('Rent Payments')
        ordering = ['-due_date']
        indexes = [
            models.Index(fields=['status', 'due_date']),
            models.Index(fields=['lease', 'tenant']),
        ]
    
    def __str__(self):
        return f"{self.receipt_number} - {self.tenant}"


class MaintenanceRequest(models.Model):
    """Maintenance requests from tenants."""
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )
    
    PRIORITY_CHOICES = (
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    )
    
    CATEGORY_CHOICES = (
        ('plumbing', 'Plumbing'),
        ('electrical', 'Electrical'),
        ('hvac', 'HVAC'),
        ('appliance', 'Appliance'),
        ('structural', 'Structural'),
        ('other', 'Other'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    property = models.ForeignKey('properties.Property', on_delete=models.CASCADE, related_name='maintenance_requests')
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='maintenance_requests')
    lease = models.ForeignKey(Lease, on_delete=models.CASCADE, related_name='maintenance_requests')
    
    # Request Details
    title = models.CharField(_('title'), max_length=255)
    description = models.TextField(_('description'))
    category = models.CharField(_('category'), max_length=20, choices=CATEGORY_CHOICES)
    priority = models.CharField(_('priority'), max_length=20, choices=PRIORITY_CHOICES, default='medium')
    status = models.CharField(_('status'), max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Assignment
    assigned_to = models.CharField(_('assigned to'), max_length=255, blank=True)
    estimated_cost = models.DecimalField(_('estimated cost'), max_digits=10, decimal_places=2, null=True, blank=True)
    actual_cost = models.DecimalField(_('actual cost'), max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Images
    images = models.JSONField(_('images'), default=list, blank=True)
    
    # Timeline
    scheduled_date = models.DateTimeField(_('scheduled date'), null=True, blank=True)
    completed_date = models.DateTimeField(_('completed date'), null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    
    class Meta:
        db_table = 'maintenance_requests'
        verbose_name = _('Maintenance Request')
        verbose_name_plural = _('Maintenance Requests')
        ordering = ['-priority', '-created_at']
        indexes = [
            models.Index(fields=['status', 'priority']),
            models.Index(fields=['property', 'tenant']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.property}"