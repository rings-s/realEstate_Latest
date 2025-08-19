from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.utils import timezone
from datetime import datetime, timedelta
import stripe
from django.conf import settings
from .models import SubscriptionPlan, Subscription, PaymentHistory
from .serializers import (
    SubscriptionPlanSerializer, SubscriptionSerializer,
    PaymentHistorySerializer, CreateSubscriptionSerializer
)

stripe.api_key = settings.STRIPE_SECRET_KEY


@api_view(['GET'])
@permission_classes([AllowAny])
def plan_list(request):
    """List all active subscription plans."""
    plans = SubscriptionPlan.objects.filter(is_active=True).order_by('price_monthly')
    serializer = SubscriptionPlanSerializer(plans, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([AllowAny])
def plan_detail(request, slug):
    """Get subscription plan details."""
    plan = get_object_or_404(SubscriptionPlan, slug=slug, is_active=True)
    serializer = SubscriptionPlanSerializer(plan)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_subscription(request):
    """Get current user's subscription."""
    try:
        subscription = Subscription.objects.get(user=request.user)
        serializer = SubscriptionSerializer(subscription)
        return Response(serializer.data)
    except Subscription.DoesNotExist:
        return Response(
            {'message': 'No active subscription'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_subscription(request):
    """Create a new subscription."""
    serializer = CreateSubscriptionSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    plan = get_object_or_404(
        SubscriptionPlan,
        id=serializer.validated_data['plan_id'],
        is_active=True
    )
    
    # Check if user already has a subscription
    if Subscription.objects.filter(user=request.user, status='active').exists():
        return Response(
            {'error': 'You already have an active subscription'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        with transaction.atomic():
            # Create or get Stripe customer
            if not request.user.stripe_customer_id:
                customer = stripe.Customer.create(
                    email=request.user.email,
                    name=request.user.get_full_name(),
                    metadata={'user_id': str(request.user.id)}
                )
                request.user.stripe_customer_id = customer.id
                request.user.save()
            else:
                customer = stripe.Customer.retrieve(request.user.stripe_customer_id)
            
            # Attach payment method
            payment_method = stripe.PaymentMethod.attach(
                serializer.validated_data['payment_method_id'],
                customer=customer.id
            )
            
            # Set as default payment method
            stripe.Customer.modify(
                customer.id,
                invoice_settings={'default_payment_method': payment_method.id}
            )
            
            # Create Stripe subscription
            billing_period = serializer.validated_data['billing_period']
            price_id = plan.stripe_price_id  # Assuming this is set correctly
            
            stripe_subscription = stripe.Subscription.create(
                customer=customer.id,
                items=[{'price': price_id}],
                trial_period_days=14,  # 14-day trial
                metadata={
                    'user_id': str(request.user.id),
                    'plan_id': str(plan.id)
                }
            )
            
            # Create local subscription
            subscription = Subscription.objects.create(
                user=request.user,
                plan=plan,
                stripe_subscription_id=stripe_subscription.id,
                stripe_customer_id=customer.id,
                status='trialing',
                billing_period=billing_period,
                trial_end=timezone.now() + timedelta(days=14),
                end_date=timezone.now() + timedelta(days=30 if billing_period == 'monthly' else 365)
            )
            
            # Update user subscription status
            request.user.subscription_status = 'trialing'
            request.user.save()
            
            subscription_serializer = SubscriptionSerializer(subscription)
            return Response(
                subscription_serializer.data,
                status=status.HTTP_201_CREATED
            )
    
    except stripe.error.StripeError as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cancel_subscription(request):
    """Cancel subscription."""
    try:
        subscription = Subscription.objects.get(user=request.user, status='active')
    except Subscription.DoesNotExist:
        return Response(
            {'error': 'No active subscription found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    try:
        # Cancel Stripe subscription
        stripe_subscription = stripe.Subscription.delete(
            subscription.stripe_subscription_id
        )
        
        # Update local subscription
        subscription.status = 'canceled'
        subscription.canceled_at = timezone.now()
        subscription.save()
        
        # Update user status
        request.user.subscription_status = 'canceled'
        request.user.save()
        
        return Response({'message': 'Subscription canceled successfully'})
    
    except stripe.error.StripeError as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upgrade_subscription(request):
    """Upgrade subscription plan."""
    new_plan_id = request.data.get('plan_id')
    
    if not new_plan_id:
        return Response(
            {'error': 'New plan ID required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    new_plan = get_object_or_404(SubscriptionPlan, id=new_plan_id, is_active=True)
    
    try:
        subscription = Subscription.objects.get(user=request.user, status='active')
    except Subscription.DoesNotExist:
        return Response(
            {'error': 'No active subscription found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    if new_plan.price_monthly <= subscription.plan.price_monthly:
        return Response(
            {'error': 'Can only upgrade to a higher plan'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # Update Stripe subscription
        stripe_subscription = stripe.Subscription.retrieve(
            subscription.stripe_subscription_id
        )
        
        stripe.Subscription.modify(
            subscription.stripe_subscription_id,
            items=[{
                'id': stripe_subscription['items']['data'][0].id,
                'price': new_plan.stripe_price_id
            }],
            proration_behavior='create_prorations'
        )
        
        # Update local subscription
        subscription.plan = new_plan
        subscription.save()
        
        serializer = SubscriptionSerializer(subscription)
        return Response(serializer.data)
    
    except stripe.error.StripeError as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def payment_history(request):
    """Get payment history."""
    try:
        subscription = Subscription.objects.get(user=request.user)
        payments = PaymentHistory.objects.filter(subscription=subscription).order_by('-created_at')
        serializer = PaymentHistorySerializer(payments, many=True)
        return Response(serializer.data)
    except Subscription.DoesNotExist:
        return Response({'payments': []})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def usage_stats(request):
    """Get subscription usage statistics."""
    try:
        subscription = Subscription.objects.get(user=request.user)
        
        return Response({
            'plan': subscription.plan.name,
            'usage': {
                'properties': {
                    'used': subscription.properties_count,
                    'limit': subscription.plan.max_properties,
                    'percentage': round(
                        (subscription.properties_count / subscription.plan.max_properties * 100)
                        if subscription.plan.max_properties > 0 else 0, 2
                    )
                },
                'users': {
                    'used': subscription.users_count,
                    'limit': subscription.plan.max_users,
                    'percentage': round(
                        (subscription.users_count / subscription.plan.max_users * 100)
                        if subscription.plan.max_users > 0 else 0, 2
                    )
                },
                'auctions': {
                    'used': subscription.auctions_this_month,
                    'limit': subscription.plan.max_auctions,
                    'percentage': round(
                        (subscription.auctions_this_month / subscription.plan.max_auctions * 100)
                        if subscription.plan.max_auctions > 0 else 0, 2
                    )
                },
                'storage': {
                    'used_gb': subscription.storage_used,
                    'limit_gb': subscription.plan.storage_limit,
                    'percentage': round(
                        (subscription.storage_used / subscription.plan.storage_limit * 100)
                        if subscription.plan.storage_limit > 0 else 0, 2
                    )
                }
            }
        })
    except Subscription.DoesNotExist:
        return Response(
            {'error': 'No subscription found'},
            status=status.HTTP_404_NOT_FOUND
        )