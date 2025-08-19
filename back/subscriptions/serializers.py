from rest_framework import serializers
from .models import SubscriptionPlan, Subscription, PaymentHistory


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    features = serializers.SerializerMethodField()
    
    class Meta:
        model = SubscriptionPlan
        fields = '__all__'
    
    def get_features(self, obj):
        return {
            'max_properties': obj.max_properties,
            'max_users': obj.max_users,
            'max_auctions': obj.max_auctions,
            'max_tenants': obj.max_tenants,
            'analytics': obj.has_analytics,
            'api_access': obj.has_api_access,
            'custom_branding': obj.has_custom_branding,
            'priority_support': obj.has_priority_support,
            'tenant_portal': obj.has_tenant_portal,
            'maintenance_module': obj.has_maintenance_module,
            'document_storage': obj.has_document_storage,
            'advanced_reporting': obj.has_advanced_reporting,
            'sms_notifications': obj.has_sms_notifications,
            'storage_limit_gb': obj.storage_limit
        }


class SubscriptionSerializer(serializers.ModelSerializer):
    plan_details = SubscriptionPlanSerializer(source='plan', read_only=True)
    is_active = serializers.SerializerMethodField()
    can_add_property = serializers.SerializerMethodField()
    can_add_auction = serializers.SerializerMethodField()
    
    class Meta:
        model = Subscription
        fields = [
            'id', 'user', 'plan', 'plan_details', 'stripe_subscription_id',
            'status', 'billing_period', 'start_date', 'end_date',
            'trial_end', 'canceled_at', 'properties_count', 'users_count',
            'auctions_this_month', 'storage_used', 'is_active',
            'can_add_property', 'can_add_auction', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'stripe_subscription_id', 'start_date', 'created_at', 'updated_at'
        ]
    
    def get_is_active(self, obj):
        return obj.is_active()
    
    def get_can_add_property(self, obj):
        return obj.can_add_property()
    
    def get_can_add_auction(self, obj):
        return obj.can_add_auction()


class PaymentHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentHistory
        fields = '__all__'
        read_only_fields = ['id', 'created_at']


class CreateSubscriptionSerializer(serializers.Serializer):
    plan_id = serializers.UUIDField()
    billing_period = serializers.ChoiceField(choices=['monthly', 'yearly'])
    payment_method_id = serializers.CharField()