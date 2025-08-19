from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db.models import Q, Sum, Count
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import datetime, timedelta
from .models import Tenant, Lease, RentPayment, MaintenanceRequest
from .serializers import (
    TenantSerializer, LeaseSerializer,
    RentPaymentSerializer, MaintenanceRequestSerializer
)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def tenant_list(request):
    """List all tenants for a landlord."""
    tenants = Tenant.objects.filter(landlord=request.user)
    
    # Filters
    status = request.GET.get('status')
    search = request.GET.get('search')
    
    if status:
        tenants = tenants.filter(status=status)
    if search:
        tenants = tenants.filter(
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(email__icontains=search) |
            Q(phone__icontains=search) |
            Q(national_id__icontains=search)
        )
    
    # Pagination
    page = request.GET.get('page', 1)
    page_size = request.GET.get('page_size', 20)
    paginator = Paginator(tenants, page_size)
    page_obj = paginator.get_page(page)
    
    serializer = TenantSerializer(page_obj.object_list, many=True)
    
    return Response({
        'results': serializer.data,
        'count': paginator.count,
        'next': page_obj.has_next(),
        'previous': page_obj.has_previous(),
        'total_pages': paginator.num_pages,
        'current_page': page_obj.number
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def tenant_create(request):
    """Create a new tenant."""
    data = request.data.copy()
    data['landlord'] = request.user.id
    
    serializer = TenantSerializer(data=data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def tenant_detail(request, pk):
    """Get, update or delete a tenant."""
    tenant = get_object_or_404(Tenant, pk=pk, landlord=request.user)
    
    if request.method == 'GET':
        serializer = TenantSerializer(tenant)
        return Response(serializer.data)
    
    elif request.method == 'PUT':
        serializer = TenantSerializer(tenant, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        tenant.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def lease_list(request):
    """List all leases."""
    leases = Lease.objects.filter(landlord=request.user)
    
    # Filters
    status = request.GET.get('status')
    property_id = request.GET.get('property')
    tenant_id = request.GET.get('tenant')
    
    if status:
        leases = leases.filter(status=status)
    if property_id:
        leases = leases.filter(property_id=property_id)
    if tenant_id:
        leases = leases.filter(tenant_id=tenant_id)
    
    # Select related to optimize queries
    leases = leases.select_related('property', 'tenant', 'landlord')
    
    serializer = LeaseSerializer(leases, many=True)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def lease_create(request):
    """Create a new lease."""
    data = request.data.copy()
    data['landlord'] = request.user.id
    
    serializer = LeaseSerializer(data=data)
    if serializer.is_valid():
        lease = serializer.save()
        
        # Create initial rent payments based on lease terms
        start_date = lease.start_date
        end_date = lease.end_date
        
        if lease.payment_frequency == 'monthly':
            current_date = start_date
            while current_date <= end_date:
                RentPayment.objects.create(
                    lease=lease,
                    tenant=lease.tenant,
                    amount_due=lease.monthly_rent,
                    due_date=current_date,
                    receipt_number=f"RCP-{uuid.uuid4().hex[:8].upper()}"
                )
                # Move to next month
                if current_date.month == 12:
                    current_date = current_date.replace(year=current_date.year + 1, month=1)
                else:
                    current_date = current_date.replace(month=current_date.month + 1)
        
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def rent_payments(request):
    """List rent payments."""
    payments = RentPayment.objects.filter(lease__landlord=request.user)
    
    # Filters
    status = request.GET.get('status')
    lease_id = request.GET.get('lease')
    tenant_id = request.GET.get('tenant')
    month = request.GET.get('month')
    year = request.GET.get('year')
    
    if status:
        payments = payments.filter(status=status)
    if lease_id:
        payments = payments.filter(lease_id=lease_id)
    if tenant_id:
        payments = payments.filter(tenant_id=tenant_id)
    if month and year:
        payments = payments.filter(
            due_date__month=month,
            due_date__year=year
        )
    
    # Select related
    payments = payments.select_related('lease', 'tenant')
    
    serializer = RentPaymentSerializer(payments, many=True)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def record_payment(request, pk):
    """Record a rent payment."""
    payment = get_object_or_404(RentPayment, pk=pk, lease__landlord=request.user)
    
    amount_paid = request.data.get('amount_paid')
    payment_method = request.data.get('payment_method')
    transaction_id = request.data.get('transaction_id')
    
    if not amount_paid:
        return Response({'error': 'Amount paid is required'}, status=status.HTTP_400_BAD_REQUEST)
    
    payment.amount_paid = amount_paid
    payment.payment_method = payment_method
    payment.transaction_id = transaction_id
    payment.paid_at = timezone.now()
    
    # Update status
    if float(amount_paid) >= float(payment.amount_due):
        payment.status = 'paid'
    else:
        payment.status = 'partial'
    
    # Check if late
    if payment.due_date < timezone.now().date():
        payment.status = 'late'
        # Apply late fee if configured
        if payment.lease.late_fee > 0:
            grace_period_end = payment.due_date + timedelta(days=payment.lease.grace_period_days)
            if timezone.now().date() > grace_period_end:
                payment.late_fee_applied = payment.lease.late_fee
    
    payment.save()
    
    serializer = RentPaymentSerializer(payment)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def maintenance_requests(request):
    """List maintenance requests."""
    requests_list = MaintenanceRequest.objects.filter(property__owner=request.user)
    
    # Filters
    status = request.GET.get('status')
    priority = request.GET.get('priority')
    property_id = request.GET.get('property')
    
    if status:
        requests_list = requests_list.filter(status=status)
    if priority:
        requests_list = requests_list.filter(priority=priority)
    if property_id:
        requests_list = requests_list.filter(property_id=property_id)
    
    # Select related
    requests_list = requests_list.select_related('property', 'tenant', 'lease')
    
    serializer = MaintenanceRequestSerializer(requests_list, many=True)
    return Response(serializer.data)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_maintenance_request(request, pk):
    """Update maintenance request status."""
    maintenance = get_object_or_404(MaintenanceRequest, pk=pk, property__owner=request.user)
    
    serializer = MaintenanceRequestSerializer(maintenance, data=request.data, partial=True)
    if serializer.is_valid():
        if request.data.get('status') == 'completed':
            serializer.validated_data['completed_date'] = timezone.now()
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def tenant_dashboard(request):
    """Get tenant dashboard statistics."""
    tenants_count = Tenant.objects.filter(landlord=request.user).count()
    active_leases = Lease.objects.filter(landlord=request.user, status='active').count()
    
    # Revenue statistics
    current_month = timezone.now().month
    current_year = timezone.now().year
    
    monthly_revenue = RentPayment.objects.filter(
        lease__landlord=request.user,
        status='paid',
        paid_at__month=current_month,
        paid_at__year=current_year
    ).aggregate(total=Sum('amount_paid'))['total'] or 0
    
    pending_payments = RentPayment.objects.filter(
        lease__landlord=request.user,
        status='pending',
        due_date__lte=timezone.now().date()
    ).count()
    
    maintenance_pending = MaintenanceRequest.objects.filter(
        property__owner=request.user,
        status='pending'
    ).count()
    
    # Occupancy rate
    total_properties = request.user.properties.count()
    occupied_properties = Lease.objects.filter(
        landlord=request.user,
        status='active'
    ).values('property').distinct().count()
    
    occupancy_rate = (occupied_properties / total_properties * 100) if total_properties > 0 else 0
    
    return Response({
        'tenants_count': tenants_count,
        'active_leases': active_leases,
        'monthly_revenue': monthly_revenue,
        'pending_payments': pending_payments,
        'maintenance_pending': maintenance_pending,
        'occupancy_rate': round(occupancy_rate, 2),
        'total_properties': total_properties,
        'occupied_properties': occupied_properties
    })