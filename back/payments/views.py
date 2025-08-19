from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.utils import timezone
import stripe
import uuid
from django.conf import settings
from .models import PaymentMethod, Transaction, Wallet
from .serializers import (
    PaymentMethodSerializer, TransactionSerializer,
    WalletSerializer, CreatePaymentMethodSerializer,
    ProcessPaymentSerializer
)

stripe.api_key = settings.STRIPE_SECRET_KEY


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def payment_methods(request):
    """List user's payment methods."""
    methods = PaymentMethod.objects.filter(user=request.user)
    serializer = PaymentMethodSerializer(methods, many=True)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_payment_method(request):
    """Add a new payment method."""
    serializer = CreatePaymentMethodSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Get or create Stripe customer
        if not request.user.stripe_customer_id:
            customer = stripe.Customer.create(
                email=request.user.email,
                name=request.user.get_full_name()
            )
            request.user.stripe_customer_id = customer.id
            request.user.save()
        
        # Retrieve payment method from Stripe
        stripe_pm = stripe.PaymentMethod.retrieve(
            serializer.validated_data['stripe_payment_method_id']
        )
        
        # Attach to customer
        stripe_pm.attach(customer=request.user.stripe_customer_id)
        
        # Create local payment method
        payment_method = PaymentMethod.objects.create(
            user=request.user,
            method_type='card',
            stripe_payment_method_id=stripe_pm.id,
            last_four=stripe_pm.card.last4,
            brand=stripe_pm.card.brand,
            exp_month=stripe_pm.card.exp_month,
            exp_year=stripe_pm.card.exp_year,
            is_verified=True
        )
        
        # Set as default if requested or if it's the first method
        if serializer.validated_data.get('set_as_default') or \
           not PaymentMethod.objects.filter(user=request.user, is_default=True).exists():
            PaymentMethod.objects.filter(user=request.user).update(is_default=False)
            payment_method.is_default = True
            payment_method.save()
        
        pm_serializer = PaymentMethodSerializer(payment_method)
        return Response(pm_serializer.data, status=status.HTTP_201_CREATED)
    
    except stripe.error.StripeError as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_payment_method(request, pk):
    """Delete a payment method."""
    payment_method = get_object_or_404(PaymentMethod, pk=pk, user=request.user)
    
    try:
        # Detach from Stripe
        if payment_method.stripe_payment_method_id:
            stripe.PaymentMethod.detach(payment_method.stripe_payment_method_id)
        
        # Delete locally
        payment_method.delete()
        
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    except stripe.error.StripeError as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def set_default_payment_method(request, pk):
    """Set payment method as default."""
    payment_method = get_object_or_404(PaymentMethod, pk=pk, user=request.user)
    
    # Remove default from all other methods
    PaymentMethod.objects.filter(user=request.user).update(is_default=False)
    
    # Set this as default
    payment_method.is_default = True
    payment_method.save()
    
    return Response({'message': 'Payment method set as default'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def transaction_list(request):
    """List user's transactions."""
    transactions = Transaction.objects.filter(user=request.user)
    
    # Filters
    transaction_type = request.GET.get('type')
    status_filter = request.GET.get('status')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if transaction_type:
        transactions = transactions.filter(transaction_type=transaction_type)
    if status_filter:
        transactions = transactions.filter(status=status_filter)
    if start_date:
        transactions = transactions.filter(created_at__gte=start_date)
    if end_date:
        transactions = transactions.filter(created_at__lte=end_date)
    
    serializer = TransactionSerializer(transactions[:100], many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def transaction_detail(request, transaction_id):
    """Get transaction details."""
    transaction = get_object_or_404(
        Transaction,
        transaction_id=transaction_id,
        user=request.user
    )
    serializer = TransactionSerializer(transaction)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def process_payment(request):
    """Process a payment."""
    serializer = ProcessPaymentSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    payment_method = get_object_or_404(
        PaymentMethod,
        pk=serializer.validated_data['payment_method_id'],
        user=request.user
    )
    
    try:
        # Create payment intent
        intent = stripe.PaymentIntent.create(
            amount=int(serializer.validated_data['amount'] * 100),  # Convert to cents
            currency='sar',
            customer=request.user.stripe_customer_id,
            payment_method=payment_method.stripe_payment_method_id,
            confirm=True,
            metadata=serializer.validated_data.get('metadata', {})
        )
        
        # Create transaction record
        transaction_obj = Transaction.objects.create(
            transaction_id=f"TXN-{uuid.uuid4().hex[:8].upper()}",
            user=request.user,
            transaction_type='payment',
            status='succeeded' if intent.status == 'succeeded' else 'processing',
            amount=serializer.validated_data['amount'],
            payment_method=payment_method,
            stripe_payment_intent_id=intent.id,
            description=serializer.validated_data.get('description', ''),
            metadata=serializer.validated_data.get('metadata', {}),
            completed_at=timezone.now() if intent.status == 'succeeded' else None
        )
        
        trans_serializer = TransactionSerializer(transaction_obj)
        return Response(trans_serializer.data, status=status.HTTP_201_CREATED)
    
    except stripe.error.StripeError as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def wallet_balance(request):
    """Get wallet balance."""
    wallet, created = Wallet.objects.get_or_create(user=request.user)
    serializer = WalletSerializer(wallet)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def withdraw_from_wallet(request):
    """Withdraw from wallet."""
    amount = request.data.get('amount')
    bank_account_id = request.data.get('bank_account_id')
    
    if not amount or not bank_account_id:
        return Response(
            {'error': 'Amount and bank account required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    wallet = get_object_or_404(Wallet, user=request.user)
    amount = Decimal(amount)
    
    if amount > wallet.balance:
        return Response(
            {'error': 'Insufficient balance'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if amount > wallet.withdrawal_limit:
        return Response(
            {'error': f'Amount exceeds withdrawal limit of {wallet.withdrawal_limit}'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    with transaction.atomic():
        # Create withdrawal transaction
        transaction_obj = Transaction.objects.create(
            transaction_id=f"WD-{uuid.uuid4().hex[:8].upper()}",
            user=request.user,
            transaction_type='payout',
            status='processing',
            amount=amount,
            description='Wallet withdrawal'
        )
        
        # Update wallet balance
        wallet.balance -= amount
        wallet.pending_balance += amount
        wallet.last_activity = timezone.now()
        wallet.save()
        
        # TODO: Process actual bank transfer
        
        return Response({
            'message': 'Withdrawal initiated',
            'transaction_id': transaction_obj.transaction_id,
            'amount': amount,
            'new_balance': wallet.balance
        })