from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
import uuid


class Notification(models.Model):
    """User notifications."""
    
    NOTIFICATION_TYPES = (
        ('info', 'Information'),
        ('success', 'Success'),
        ('warning', 'Warning'),
        ('error', 'Error'),
        ('payment', 'Payment'),
        ('property', 'Property'),
        ('tenant', 'Tenant'),
        ('maintenance', 'Maintenance'),
        ('auction', 'Auction'),
        ('system', 'System'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    
    # Content
    title = models.CharField(_('title'), max_length=255)
    message = models.TextField(_('message'))
    notification_type = models.CharField(_('type'), max_length=20, choices=NOTIFICATION_TYPES, default='info')
    
    # Metadata
    action_url = models.CharField(_('action URL'), max_length=255, blank=True)
    metadata = models.JSONField(_('metadata'), default=dict, blank=True)
    
    # Status
    is_read = models.BooleanField(_('is read'), default=False)
    read_at = models.DateTimeField(_('read at'), null=True, blank=True)
    
    # Delivery
    email_sent = models.BooleanField(_('email sent'), default=False)
    sms_sent = models.BooleanField(_('SMS sent'), default=False)
    push_sent = models.BooleanField(_('push sent'), default=False)
    
    # Timestamps
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    
    class Meta:
        db_table = 'notifications'
        verbose_name = _('Notification')
        verbose_name_plural = _('Notifications')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['-created_at']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.user.email}"


class NotificationPreference(models.Model):
    """User notification preferences."""
    
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_preference'
    )
    
    # Email notifications
    email_enabled = models.BooleanField(_('email enabled'), default=True)
    email_payment = models.BooleanField(_('payment emails'), default=True)
    email_property = models.BooleanField(_('property emails'), default=True)
    email_tenant = models.BooleanField(_('tenant emails'), default=True)
    email_maintenance = models.BooleanField(_('maintenance emails'), default=True)
    email_marketing = models.BooleanField(_('marketing emails'), default=False)
    
    # SMS notifications
    sms_enabled = models.BooleanField(_('SMS enabled'), default=False)
    sms_payment = models.BooleanField(_('payment SMS'), default=True)
    sms_urgent = models.BooleanField(_('urgent SMS'), default=True)
    
    # Push notifications
    push_enabled = models.BooleanField(_('push enabled'), default=True)
    push_payment = models.BooleanField(_('payment push'), default=True)
    push_property = models.BooleanField(_('property push'), default=True)
    push_tenant = models.BooleanField(_('tenant push'), default=True)
    
    # Quiet hours
    quiet_hours_enabled = models.BooleanField(_('quiet hours enabled'), default=False)
    quiet_hours_start = models.TimeField(_('quiet hours start'), null=True, blank=True)
    quiet_hours_end = models.TimeField(_('quiet hours end'), null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    
    class Meta:
        db_table = 'notification_preferences'
        verbose_name = _('Notification Preference')
        verbose_name_plural = _('Notification Preferences')