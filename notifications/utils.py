from django.core.mail import send_mail
from django.conf import settings
from .models import Notification, NotificationPreference
import logging

logger = logging.getLogger(__name__)


def send_notification(notification):
    """Send notification through various channels."""
    try:
        preference = NotificationPreference.objects.get(user=notification.user)
    except NotificationPreference.DoesNotExist:
        preference = NotificationPreference.objects.create(user=notification.user)
    
    # Send email
    if preference.email_enabled and should_send_email(notification, preference):
        send_email_notification(notification)
    
    # Send SMS
    if preference.sms_enabled and should_send_sms(notification, preference):
        send_sms_notification(notification)
    
    # Send push notification
    if preference.push_enabled and should_send_push(notification, preference):
        send_push_notification(notification)


def should_send_email(notification, preference):
    """Check if email should be sent."""
    type_map = {
        'payment': preference.email_payment,
        'property': preference.email_property,
        'tenant': preference.email_tenant,
        'maintenance': preference.email_maintenance,
    }
    return type_map.get(notification.notification_type, True)


def should_send_sms(notification, preference):
    """Check if SMS should be sent."""
    if notification.notification_type == 'payment':
        return preference.sms_payment
    elif notification.notification_type in ['error', 'warning']:
        return preference.sms_urgent
    return False


def should_send_push(notification, preference):
    """Check if push notification should be sent."""
    type_map = {
        'payment': preference.push_payment,
        'property': preference.push_property,
        'tenant': preference.push_tenant,
    }
    return type_map.get(notification.notification_type, True)


def send_email_notification(notification):
    """Send email notification."""
    try:
        send_mail(
            subject=notification.title,
            message=notification.message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[notification.user.email],
            fail_silently=False,
        )
        notification.email_sent = True
        notification.save(update_fields=['email_sent'])
        logger.info(f"Email sent to {notification.user.email}")
    except Exception as e:
        logger.error(f"Failed to send email: {e}")


def send_sms_notification(notification):
    """Send SMS notification."""
    # Implement SMS sending logic here (e.g., Twilio)
    pass


def send_push_notification(notification):
    """Send push notification."""
    # Implement push notification logic here (e.g., Firebase)
    pass


def create_notification(user, title, message, notification_type='info', **kwargs):
    """Helper to create and send notification."""
    notification = Notification.objects.create(
        user=user,
        title=title,
        message=message,
        notification_type=notification_type,
        **kwargs
    )
    send_notification(notification)
    return notification