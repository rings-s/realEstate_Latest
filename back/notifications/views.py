from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q
from .models import Notification, NotificationPreference
from .serializers import (
    NotificationSerializer,
    NotificationPreferenceSerializer,
    CreateNotificationSerializer
)
from .utils import send_notification


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def notification_list(request):
    """List user notifications."""
    notifications = Notification.objects.filter(user=request.user)
    
    # Filters
    is_read = request.GET.get('is_read')
    notification_type = request.GET.get('type')
    
    if is_read is not None:
        notifications = notifications.filter(is_read=is_read == 'true')
    if notification_type:
        notifications = notifications.filter(notification_type=notification_type)
    
    # Limit to last 100 notifications
    notifications = notifications[:100]
    
    serializer = NotificationSerializer(notifications, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def notification_detail(request, pk):
    """Get notification detail and mark as read."""
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    
    # Mark as read
    if not notification.is_read:
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save()
    
    serializer = NotificationSerializer(notification)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_as_read(request, pk):
    """Mark notification as read."""
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    
    notification.is_read = True
    notification.read_at = timezone.now()
    notification.save()
    
    return Response({'message': 'Notification marked as read'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_all_as_read(request):
    """Mark all notifications as read."""
    notifications = Notification.objects.filter(
        user=request.user,
        is_read=False
    )
    
    count = notifications.update(
        is_read=True,
        read_at=timezone.now()
    )
    
    return Response({'message': f'{count} notifications marked as read'})


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_notification(request, pk):
    """Delete a notification."""
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notification.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def clear_notifications(request):
    """Clear all read notifications."""
    count, _ = Notification.objects.filter(
        user=request.user,
        is_read=True
    ).delete()
    
    return Response({'message': f'{count} notifications deleted'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def unread_count(request):
    """Get unread notification count."""
    count = Notification.objects.filter(
        user=request.user,
        is_read=False
    ).count()
    
    return Response({'unread_count': count})


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def notification_preferences(request):
    """Get or update notification preferences."""
    preference, created = NotificationPreference.objects.get_or_create(
        user=request.user
    )
    
    if request.method == 'GET':
        serializer = NotificationPreferenceSerializer(preference)
        return Response(serializer.data)
    
    elif request.method == 'PUT':
        serializer = NotificationPreferenceSerializer(
            preference,
            data=request.data,
            partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def test_notification(request):
    """Send a test notification."""
    notification = Notification.objects.create(
        user=request.user,
        title='Test Notification',
        message='This is a test notification to verify your notification settings.',
        notification_type='info'
    )
    
    # Send via configured channels
    send_notification(notification)
    
    serializer = NotificationSerializer(notification)
    return Response(serializer.data)