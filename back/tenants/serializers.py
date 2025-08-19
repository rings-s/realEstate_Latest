from rest_framework import serializers
from .models import Tenant, Lease, RentPayment, MaintenanceRequest
from properties.serializers import PropertyListSerializer


class TenantSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Tenant
        fields = [
            'id', 'user', 'landlord', 'first_name', 'last_name', 'full_name',
            'email', 'phone', 'national_id', 'occupation', 'employer',
            'monthly_income', 'emergency_contact', 'status', 'credit_score',
            'documents', 'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_full_name(self, obj):
        return obj.get_full_name()


class LeaseSerializer(serializers.ModelSerializer):
    property_details = PropertyListSerializer(source='property', read_only=True)
    tenant_name = serializers.CharField(source='tenant.get_full_name', read_only=True)
    
    class Meta:
        model = Lease
        fields = [
            'id', 'property', 'property_details', 'tenant', 'tenant_name',
            'landlord', 'lease_number', 'start_date', 'end_date', 'status',
            'monthly_rent', 'security_deposit', 'payment_frequency',
            'late_fee', 'grace_period_days', 'terms_conditions',
            'special_conditions', 'auto_renew', 'contract_document',
            'signed_date', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'lease_number', 'created_at', 'updated_at']
    
    def create(self, validated_data):
        # Generate unique lease number
        import uuid
        validated_data['lease_number'] = f"LEASE-{uuid.uuid4().hex[:8].upper()}"
        return super().create(validated_data)


class RentPaymentSerializer(serializers.ModelSerializer):
    tenant_name = serializers.CharField(source='tenant.get_full_name', read_only=True)
    lease_number = serializers.CharField(source='lease.lease_number', read_only=True)
    
    class Meta:
        model = RentPayment
        fields = [
            'id', 'lease', 'lease_number', 'tenant', 'tenant_name',
            'amount_due', 'amount_paid', 'payment_date', 'due_date',
            'status', 'payment_method', 'transaction_id', 'receipt_number',
            'late_fee_applied', 'notes', 'paid_at', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'receipt_number', 'created_at', 'updated_at']
    
    def create(self, validated_data):
        # Generate unique receipt number
        import uuid
        validated_data['receipt_number'] = f"RCP-{uuid.uuid4().hex[:8].upper()}"
        return super().create(validated_data)


class MaintenanceRequestSerializer(serializers.ModelSerializer):
    property_title = serializers.CharField(source='property.title', read_only=True)
    tenant_name = serializers.CharField(source='tenant.get_full_name', read_only=True)
    
    class Meta:
        model = MaintenanceRequest
        fields = [
            'id', 'property', 'property_title', 'tenant', 'tenant_name',
            'lease', 'title', 'description', 'category', 'priority',
            'status', 'assigned_to', 'estimated_cost', 'actual_cost',
            'images', 'scheduled_date', 'completed_date',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']