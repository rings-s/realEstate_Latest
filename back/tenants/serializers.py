from rest_framework import serializers
from .models import (
    Tenant, Lease, RentPayment, MaintenanceRequest,
    TenantDocument, TenantCommunication, TenantRating
)
from properties.serializers import PropertyListSerializer


class TenantSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    active_lease_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Tenant
        fields = [
            'id', 'user', 'landlord', 'first_name', 'last_name', 'full_name',
            'email', 'phone', 'national_id', 'occupation', 'employer',
            'monthly_income', 'emergency_contact', 'status', 'credit_score',
            'documents', 'notes', 'active_lease_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_full_name(self, obj):
        return obj.get_full_name()
    
    def get_active_lease_count(self, obj):
        return obj.leases.filter(status='active').count()


class LeaseSerializer(serializers.ModelSerializer):
    property_details = PropertyListSerializer(source='property', read_only=True)
    tenant_name = serializers.CharField(source='tenant.get_full_name', read_only=True)
    is_active = serializers.SerializerMethodField()
    
    class Meta:
        model = Lease
        fields = [
            'id', 'property', 'property_details', 'tenant', 'tenant_name',
            'landlord', 'lease_number', 'start_date', 'end_date', 'status',
            'monthly_rent', 'security_deposit', 'payment_frequency',
            'late_fee', 'grace_period_days', 'terms_conditions',
            'special_conditions', 'auto_renew', 'contract_document',
            'signed_date', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'lease_number', 'created_at', 'updated_at']
    
    def get_is_active(self, obj):
        return obj.is_active()


class RentPaymentSerializer(serializers.ModelSerializer):
    tenant_name = serializers.CharField(source='tenant.get_full_name', read_only=True)
    lease_number = serializers.CharField(source='lease.lease_number', read_only=True)
    property_title = serializers.CharField(source='lease.property.title', read_only=True)
    is_overdue = serializers.SerializerMethodField()
    
    class Meta:
        model = RentPayment
        fields = [
            'id', 'lease', 'lease_number', 'tenant', 'tenant_name',
            'property_title', 'amount_due', 'amount_paid', 'payment_date',
            'due_date', 'status', 'payment_method', 'transaction_id',
            'receipt_number', 'late_fee_applied', 'notes', 'is_overdue',
            'paid_at', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'receipt_number', 'created_at', 'updated_at']
    
    def get_is_overdue(self, obj):
        from django.utils import timezone
        return obj.status == 'pending' and obj.due_date < timezone.now().date()


class MaintenanceRequestSerializer(serializers.ModelSerializer):
    property_title = serializers.CharField(source='property.title', read_only=True)
    tenant_name = serializers.CharField(source='tenant.get_full_name', read_only=True)
    days_open = serializers.SerializerMethodField()
    
    class Meta:
        model = MaintenanceRequest
        fields = [
            'id', 'property', 'property_title', 'tenant', 'tenant_name',
            'lease', 'title', 'description', 'category', 'priority',
            'status', 'assigned_to', 'estimated_cost', 'actual_cost',
            'images', 'scheduled_date', 'completed_date', 'days_open',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_days_open(self, obj):
        if obj.status in ['completed', 'cancelled']:
            return None
        from django.utils import timezone
        return (timezone.now() - obj.created_at).days


class TenantDocumentSerializer(serializers.ModelSerializer):
    tenant_name = serializers.CharField(source='tenant.get_full_name', read_only=True)
    is_expired = serializers.SerializerMethodField()
    
    class Meta:
        model = TenantDocument
        fields = [
            'id', 'tenant', 'tenant_name', 'document_type', 'file',
            'file_name', 'file_size', 'is_verified', 'verified_by',
            'verified_at', 'verification_notes', 'expires_at',
            'is_expired', 'created_at'
        ]
        read_only_fields = [
            'id', 'file_name', 'file_size', 'is_verified',
            'verified_by', 'verified_at', 'created_at'
        ]
    
    def get_is_expired(self, obj):
        if not obj.expires_at:
            return False
        from django.utils import timezone
        return obj.expires_at < timezone.now().date()


class TenantCommunicationSerializer(serializers.ModelSerializer):
    tenant_name = serializers.CharField(source='tenant.get_full_name', read_only=True)
    landlord_name = serializers.CharField(source='landlord.get_full_name', read_only=True)
    property_title = serializers.CharField(source='property.title', read_only=True)
    
    class Meta:
        model = TenantCommunication
        fields = [
            'id', 'tenant', 'tenant_name', 'landlord', 'landlord_name',
            'property', 'property_title', 'communication_type', 'subject',
            'message', 'sender_type', 'is_read', 'read_at', 'is_urgent',
            'requires_response', 'response_due_date', 'responded_at',
            'attachments', 'created_at'
        ]
        read_only_fields = [
            'id', 'sender_type', 'is_read', 'read_at',
            'responded_at', 'created_at'
        ]


class TenantRatingSerializer(serializers.ModelSerializer):
    lease_number = serializers.CharField(source='lease.lease_number', read_only=True)
    tenant_name = serializers.CharField(source='lease.tenant.get_full_name', read_only=True)
    property_title = serializers.CharField(source='lease.property.title', read_only=True)
    average_tenant_score = serializers.SerializerMethodField()
    average_landlord_score = serializers.SerializerMethodField()
    
    class Meta:
        model = TenantRating
        fields = [
            'id', 'lease', 'lease_number', 'tenant_name', 'property_title',
            'tenant_rating', 'tenant_review', 'payment_punctuality',
            'property_care', 'communication_rating', 'average_tenant_score',
            'landlord_rating', 'landlord_review', 'responsiveness',
            'maintenance_handling', 'fairness', 'average_landlord_score',
            'property_rating', 'property_review', 'would_rent_again',
            'would_recommend', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_average_tenant_score(self, obj):
        scores = [obj.tenant_rating, obj.payment_punctuality, 
                 obj.property_care, obj.communication_rating]
        valid_scores = [s for s in scores if s is not None]
        return sum(valid_scores) / len(valid_scores) if valid_scores else None
    
    def get_average_landlord_score(self, obj):
        scores = [obj.landlord_rating, obj.responsiveness,
                 obj.maintenance_handling, obj.fairness]
        valid_scores = [s for s in scores if s is not None]
        return sum(valid_scores) / len(valid_scores) if valid_scores else None