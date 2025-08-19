from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db.models import Q, Sum, Count, Avg
from django.utils import timezone
from datetime import timedelta
from .models import (
    Tenant, Lease, RentPayment, MaintenanceRequest,
    TenantDocument, TenantCommunication, TenantRating
)
from .serializers import (
    TenantSerializer, LeaseSerializer, RentPaymentSerializer,
    MaintenanceRequestSerializer, TenantDocumentSerializer,
    TenantCommunicationSerializer, TenantRatingSerializer
)


# Tenant Views
class TenantListCreateAPIView(generics.ListCreateAPIView):
    """List all tenants or create a new tenant."""
    serializer_class = TenantSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = Tenant.objects.filter(landlord=self.request.user)
        
        # Filters
        status = self.request.GET.get('status')
        search = self.request.GET.get('search')
        
        if status:
            queryset = queryset.filter(status=status)
        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(email__icontains=search) |
                Q(phone__icontains=search) |
                Q(national_id__icontains=search)
            )
        
        return queryset.order_by('-created_at')
    
    def perform_create(self, serializer):
        serializer.save(landlord=self.request.user)


class TenantRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a tenant."""
    serializer_class = TenantSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Tenant.objects.filter(landlord=self.request.user)


# Lease Views
class LeaseListCreateAPIView(generics.ListCreateAPIView):
    """List all leases or create a new lease."""
    serializer_class = LeaseSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = Lease.objects.filter(landlord=self.request.user)
        
        # Filters
        status = self.request.GET.get('status')
        property_id = self.request.GET.get('property')
        tenant_id = self.request.GET.get('tenant')
        
        if status:
            queryset = queryset.filter(status=status)
        if property_id:
            queryset = queryset.filter(property_id=property_id)
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)
        
        return queryset.select_related('property', 'tenant').order_by('-created_at')
    
    def perform_create(self, serializer):
        lease = serializer.save(landlord=self.request.user)
        
        # Create initial rent payments
        self._create_rent_payments(lease)
    
    def _create_rent_payments(self, lease):
        """Create rent payment records based on lease terms."""
        from dateutil.relativedelta import relativedelta
        
        current_date = lease.start_date
        
        while current_date <= lease.end_date:
            RentPayment.objects.create(
                lease=lease,
                tenant=lease.tenant,
                amount_due=lease.monthly_rent,
                due_date=current_date,
                payment_date=None
            )
            
            # Calculate next payment date
            if lease.payment_frequency == 'monthly':
                current_date += relativedelta(months=1)
            elif lease.payment_frequency == 'quarterly':
                current_date += relativedelta(months=3)
            elif lease.payment_frequency == 'semi_annual':
                current_date += relativedelta(months=6)
            elif lease.payment_frequency == 'annual':
                current_date += relativedelta(years=1)
            else:
                break


class LeaseRetrieveUpdateAPIView(generics.RetrieveUpdateAPIView):
    """Retrieve or update a lease."""
    serializer_class = LeaseSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Lease.objects.filter(landlord=self.request.user)


# Rent Payment Views
class RentPaymentListAPIView(generics.ListAPIView):
    """List rent payments."""
    serializer_class = RentPaymentSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = RentPayment.objects.filter(lease__landlord=self.request.user)
        
        # Filters
        status = self.request.GET.get('status')
        lease_id = self.request.GET.get('lease')
        tenant_id = self.request.GET.get('tenant')
        month = self.request.GET.get('month')
        year = self.request.GET.get('year')
        
        if status:
            queryset = queryset.filter(status=status)
        if lease_id:
            queryset = queryset.filter(lease_id=lease_id)
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)
        if month and year:
            queryset = queryset.filter(
                due_date__month=month,
                due_date__year=year
            )
        
        return queryset.select_related('lease', 'tenant').order_by('-due_date')


class RentPaymentRecordAPIView(APIView):
    """Record a rent payment."""
    permission_classes = [IsAuthenticated]
    
    def post(self, request, pk):
        payment = get_object_or_404(RentPayment, pk=pk, lease__landlord=request.user)
        
        amount_paid = request.data.get('amount_paid')
        payment_method = request.data.get('payment_method')
        transaction_id = request.data.get('transaction_id')
        
        if not amount_paid:
            return Response(
                {'error': 'Amount paid is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        payment.amount_paid = amount_paid
        payment.payment_method = payment_method
        payment.transaction_id = transaction_id
        payment.paid_at = timezone.now()
        payment.payment_date = timezone.now().date()
        
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


# Maintenance Request Views
class MaintenanceRequestListCreateAPIView(generics.ListCreateAPIView):
    """List maintenance requests or create a new one."""
    serializer_class = MaintenanceRequestSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        
        # Check if user is a tenant or landlord
        if hasattr(user, 'tenant_profile'):
            queryset = MaintenanceRequest.objects.filter(tenant=user.tenant_profile)
        else:
            queryset = MaintenanceRequest.objects.filter(property__owner=user)
        
        # Filters
        status = self.request.GET.get('status')
        priority = self.request.GET.get('priority')
        property_id = self.request.GET.get('property')
        
        if status:
            queryset = queryset.filter(status=status)
        if priority:
            queryset = queryset.filter(priority=priority)
        if property_id:
            queryset = queryset.filter(property_id=property_id)
        
        return queryset.select_related('property', 'tenant', 'lease').order_by('-priority', '-created_at')
    
    def perform_create(self, serializer):
        # Validate that user is a tenant
        if not hasattr(self.request.user, 'tenant_profile'):
            raise PermissionError("Only tenants can create maintenance requests")
        
        serializer.save(tenant=self.request.user.tenant_profile)
        
        # Send notification to landlord
        instance = serializer.instance
        from notifications.utils import create_notification
        create_notification(
            user=instance.property.owner,
            title='New Maintenance Request',
            message=f'{instance.title} - {instance.get_priority_display()} priority',
            notification_type='maintenance',
            metadata={'request_id': str(instance.id)}
        )


class MaintenanceRequestRetrieveUpdateAPIView(generics.RetrieveUpdateAPIView):
    """Retrieve or update a maintenance request."""
    serializer_class = MaintenanceRequestSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        if hasattr(user, 'tenant_profile'):
            return MaintenanceRequest.objects.filter(tenant=user.tenant_profile)
        else:
            return MaintenanceRequest.objects.filter(property__owner=user)
    
    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        
        # Set completed date if status is being changed to completed
        if request.data.get('status') == 'completed' and instance.status != 'completed':
            request.data['completed_date'] = timezone.now()
        
        return super().update(request, *args, **kwargs)


# Tenant Document Views
class TenantDocumentListCreateAPIView(generics.ListCreateAPIView):
    """List tenant documents or upload a new one."""
    serializer_class = TenantDocumentSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        tenant_id = self.kwargs.get('tenant_id')
        tenant = get_object_or_404(Tenant, id=tenant_id)
        
        # Check permissions
        if self.request.user != tenant.landlord and self.request.user != tenant.user:
            return TenantDocument.objects.none()
        
        return TenantDocument.objects.filter(tenant=tenant).order_by('-created_at')
    
    def perform_create(self, serializer):
        tenant_id = self.kwargs.get('tenant_id')
        tenant = get_object_or_404(Tenant, id=tenant_id)
        
        # Only tenant can upload their own documents
        if self.request.user != tenant.user:
            raise PermissionError("Only tenant can upload documents")
        
        file = self.request.FILES.get('file')
        serializer.save(
            tenant=tenant,
            file_name=file.name,
            file_size=file.size
        )


class TenantDocumentVerifyAPIView(APIView):
    """Verify a tenant document (landlord only)."""
    permission_classes = [IsAuthenticated]
    
    def post(self, request, pk):
        document = get_object_or_404(TenantDocument, pk=pk)
        
        # Only landlord can verify
        if request.user != document.tenant.landlord:
            return Response(
                {'error': 'Only landlord can verify documents'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        document.is_verified = True
        document.verified_by = request.user
        document.verified_at = timezone.now()
        document.verification_notes = request.data.get('notes', '')
        document.save()
        
        # Send notification to tenant
        if document.tenant.user:
            from notifications.utils import create_notification
            create_notification(
                user=document.tenant.user,
                title='Document Verified',
                message=f'Your {document.get_document_type_display()} has been verified',
                notification_type='tenant'
            )
        
        return Response({'message': 'Document verified successfully'})


# Tenant Communication Views
class TenantCommunicationListCreateAPIView(generics.ListCreateAPIView):
    """List communications or create a new one."""
    serializer_class = TenantCommunicationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        
        # Get communications for landlord or tenant
        if hasattr(user, 'tenant_profile'):
            queryset = TenantCommunication.objects.filter(tenant=user.tenant_profile)
        else:
            queryset = TenantCommunication.objects.filter(landlord=user)
        
        # Filters
        is_read = self.request.GET.get('is_read')
        is_urgent = self.request.GET.get('is_urgent')
        property_id = self.request.GET.get('property')
        
        if is_read is not None:
            queryset = queryset.filter(is_read=is_read == 'true')
        if is_urgent is not None:
            queryset = queryset.filter(is_urgent=is_urgent == 'true')
        if property_id:
            queryset = queryset.filter(property_id=property_id)
        
        return queryset.select_related('tenant', 'landlord', 'property').order_by('-created_at')
    
    def perform_create(self, serializer):
        user = self.request.user
        
        if hasattr(user, 'tenant_profile'):
            # Tenant sending message
            tenant = user.tenant_profile
            landlord = tenant.landlord
            sender_type = 'tenant'
        else:
            # Landlord sending message
            tenant = serializer.validated_data['tenant']
            landlord = user
            sender_type = 'landlord'
        
        communication = serializer.save(
            tenant=tenant,
            landlord=landlord,
            sender_type=sender_type
        )
        
        # Send notification to recipient
        recipient = landlord if sender_type == 'tenant' else tenant.user
        if recipient:
            from notifications.utils import create_notification
            create_notification(
                user=recipient,
                title=f'New {communication.get_communication_type_display()}',
                message=communication.subject,
                notification_type='tenant',
                metadata={'communication_id': str(communication.id)}
            )


class TenantCommunicationRetrieveUpdateAPIView(generics.RetrieveUpdateAPIView):
    """Retrieve or update a communication."""
    serializer_class = TenantCommunicationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        if hasattr(user, 'tenant_profile'):
            return TenantCommunication.objects.filter(tenant=user.tenant_profile)
        else:
            return TenantCommunication.objects.filter(landlord=user)
    
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        
        # Mark as read if recipient is viewing
        user = request.user
        if hasattr(user, 'tenant_profile'):
            is_recipient = instance.sender_type == 'landlord'
        else:
            is_recipient = instance.sender_type == 'tenant'
        
        if is_recipient and not instance.is_read:
            instance.is_read = True
            instance.read_at = timezone.now()
            instance.save(update_fields=['is_read', 'read_at'])
        
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


# Tenant Rating Views
class TenantRatingCreateAPIView(generics.CreateAPIView):
    """Create a rating for a completed lease."""
    serializer_class = TenantRatingSerializer
    permission_classes = [IsAuthenticated]
    
    def perform_create(self, serializer):
        lease = serializer.validated_data['lease']
        user = self.request.user
        
        # Verify user is part of the lease
        if user != lease.landlord and user != lease.tenant.user:
            raise PermissionError("You can only rate leases you're part of")
        
        # Check if lease is completed
        if lease.status not in ['expired', 'terminated']:
            raise ValueError("Can only rate completed leases")
        
        serializer.save()


class TenantRatingRetrieveUpdateAPIView(generics.RetrieveUpdateAPIView):
    """Retrieve or update a rating."""
    serializer_class = TenantRatingSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        return TenantRating.objects.filter(
            Q(lease__landlord=user) | Q(lease__tenant__user=user)
        )
    
    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        user = request.user
        
        # Determine what the user can update
        if user == instance.lease.landlord:
            # Landlord can only update tenant rating fields
            allowed_fields = ['tenant_rating', 'tenant_review', 'payment_punctuality', 
                            'property_care', 'communication_rating']
        elif user == instance.lease.tenant.user:
            # Tenant can only update landlord rating fields
            allowed_fields = ['landlord_rating', 'landlord_review', 'responsiveness',
                            'maintenance_handling', 'fairness', 'property_rating', 
                            'property_review', 'would_rent_again', 'would_recommend']
        else:
            return Response(
                {'error': 'Not authorized to update this rating'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Filter request data to only allowed fields
        update_data = {k: v for k, v in request.data.items() if k in allowed_fields}
        
        serializer = self.get_serializer(instance, data=update_data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response(serializer.data)


# Dashboard View
class TenantDashboardAPIView(APIView):
    """Get tenant dashboard statistics."""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        # For landlords
        if not hasattr(user, 'tenant_profile'):
            tenants_count = Tenant.objects.filter(landlord=user).count()
            active_leases = Lease.objects.filter(landlord=user, status='active').count()
            
            # Revenue statistics
            current_month = timezone.now().month
            current_year = timezone.now().year
            
            monthly_revenue = RentPayment.objects.filter(
                lease__landlord=user,
                status='paid',
                paid_at__month=current_month,
                paid_at__year=current_year
            ).aggregate(total=Sum('amount_paid'))['total'] or 0
            
            pending_payments = RentPayment.objects.filter(
                lease__landlord=user,
                status='pending',
                due_date__lte=timezone.now().date()
            ).count()
            
            maintenance_pending = MaintenanceRequest.objects.filter(
                property__owner=user,
                status='pending'
            ).count()
            
            # Occupancy rate
            total_properties = user.properties.count()
            occupied_properties = Lease.objects.filter(
                landlord=user,
                status='active'
            ).values('property').distinct().count()
            
            occupancy_rate = (occupied_properties / total_properties * 100) if total_properties > 0 else 0
            
            # Tenant payment performance
            payment_stats = RentPayment.objects.filter(
                lease__landlord=user
            ).aggregate(
                total_due=Sum('amount_due'),
                total_collected=Sum('amount_paid'),
                on_time_payments=Count('id', filter=Q(status='paid', paid_at__lte=models.F('due_date')))
            )
            
            collection_rate = (
                (payment_stats['total_collected'] / payment_stats['total_due'] * 100)
                if payment_stats['total_due'] else 0
            )
            
            return Response({
                'landlord_dashboard': {
                    'tenants_count': tenants_count,
                    'active_leases': active_leases,
                    'monthly_revenue': float(monthly_revenue),
                    'pending_payments': pending_payments,
                    'maintenance_pending': maintenance_pending,
                    'occupancy_rate': round(occupancy_rate, 2),
                    'total_properties': total_properties,
                    'occupied_properties': occupied_properties,
                    'collection_rate': round(collection_rate, 2),
                    'payment_performance': payment_stats
                }
            })
        
        # For tenants
        else:
            tenant = user.tenant_profile
            active_lease = Lease.objects.filter(tenant=tenant, status='active').first()
            
            if active_lease:
                # Upcoming payments
                upcoming_payments = RentPayment.objects.filter(
                    tenant=tenant,
                    status='pending',
                    due_date__gte=timezone.now().date()
                ).order_by('due_date')[:3]
                
                # Payment history
                payment_history = RentPayment.objects.filter(
                    tenant=tenant,
                    status__in=['paid', 'late']
                ).order_by('-paid_at')[:5]
                
                # Maintenance requests
                recent_maintenance = MaintenanceRequest.objects.filter(
                    tenant=tenant
                ).order_by('-created_at')[:5]
                
                # Calculate payment score
                total_payments = RentPayment.objects.filter(tenant=tenant).count()
                on_time_payments = RentPayment.objects.filter(
                    tenant=tenant,
                    status='paid',
                    paid_at__lte=models.F('due_date')
                ).count()
                
                payment_score = (on_time_payments / total_payments * 100) if total_payments > 0 else 100
                
                return Response({
                    'tenant_dashboard': {
                        'active_lease': LeaseSerializer(active_lease).data if active_lease else None,
                        'upcoming_payments': RentPaymentSerializer(upcoming_payments, many=True).data,
                        'payment_history': RentPaymentSerializer(payment_history, many=True).data,
                        'recent_maintenance': MaintenanceRequestSerializer(recent_maintenance, many=True).data,
                        'payment_score': round(payment_score, 2),
                        'unread_messages': TenantCommunication.objects.filter(
                            tenant=tenant,
                            is_read=False,
                            sender_type='landlord'
                        ).count()
                    }
                })
            
            return Response({
                'tenant_dashboard': {
                    'message': 'No active lease found'
                }
            })