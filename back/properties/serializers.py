from rest_framework import serializers
from django.contrib.gis.geos import Point
from .models import (
    Property, PropertyImage, PropertyDocument,
    Amenity, AmenityCategory, PropertyAmenity,
    PropertyFavorite, PropertyComparison, ViewingAppointment, PropertyView
)
from accounts.serializers import UserSerializer


class PropertyImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = PropertyImage
        fields = ['id', 'image', 'title', 'is_primary', 'order']


class PropertyDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = PropertyDocument
        fields = ['id', 'document', 'document_type', 'title', 'description', 'is_public', 'created_at']


class AmenityCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = AmenityCategory
        fields = ['id', 'name', 'slug', 'category_type', 'icon', 'order']


class AmenitySerializer(serializers.ModelSerializer):
    category = AmenityCategorySerializer(read_only=True)
    
    class Meta:
        model = Amenity
        fields = ['id', 'category', 'name', 'slug', 'description', 'icon', 'is_premium', 'is_searchable']


class PropertyAmenitySerializer(serializers.ModelSerializer):
    amenity = AmenitySerializer(read_only=True)
    
    class Meta:
        model = PropertyAmenity
        fields = ['amenity', 'is_available', 'notes', 'verified']


class PropertySerializer(serializers.ModelSerializer):
    images = PropertyImageSerializer(many=True, read_only=True)
    documents = PropertyDocumentSerializer(many=True, read_only=True)
    owner_name = serializers.CharField(source='owner.get_full_name', read_only=True)
    
    class Meta:
        model = Property
        fields = [
            'id', 'owner', 'owner_name', 'title', 'slug', 'description',
            'property_type', 'purpose', 'status', 'reference_number',
            'address', 'city', 'district', 'country', 'postal_code',
            'latitude', 'longitude', 'location_accuracy', 'map_zoom_level',
            'nearby_places', 'area_sqm', 'bedrooms', 'bathrooms', 'parking_spaces',
            'floor_number', 'total_floors', 'year_built',
            'price', 'price_per_sqm', 'currency', 'is_negotiable',
            'features', 'meta_title', 'meta_description', 'meta_keywords',
            'views_count', 'favorites_count',
            'is_featured', 'is_verified', 'is_published',
            'images', 'documents',
            'created_at', 'updated_at', 'published_at'
        ]
        read_only_fields = [
            'id', 'slug', 'reference_number', 'price_per_sqm',
            'views_count', 'favorites_count', 'is_verified',
            'created_at', 'updated_at'
        ]


class PropertyListSerializer(serializers.ModelSerializer):
    primary_image = serializers.SerializerMethodField()
    owner_name = serializers.CharField(source='owner.get_full_name', read_only=True)
    
    class Meta:
        model = Property
        fields = [
            'id', 'title', 'slug', 'property_type', 'purpose', 'status',
            'city', 'district', 'area_sqm', 'bedrooms', 'bathrooms',
            'price', 'currency', 'primary_image', 'owner_name',
            'is_featured', 'latitude', 'longitude', 'created_at'
        ]
    
    def get_primary_image(self, obj):
        primary = obj.images.filter(is_primary=True).first()
        if primary:
            return primary.image.url if primary.image else None
        first_image = obj.images.first()
        return first_image.image.url if first_image and first_image.image else None


class PropertyDetailSerializer(PropertySerializer):
    property_amenities = PropertyAmenitySerializer(many=True, read_only=True)
    owner = UserSerializer(read_only=True)
    
    class Meta(PropertySerializer.Meta):
        fields = PropertySerializer.Meta.fields + ['property_amenities', 'owner']


class PropertyFavoriteSerializer(serializers.ModelSerializer):
    property = PropertyListSerializer(read_only=True)
    
    class Meta:
        model = PropertyFavorite
        fields = ['id', 'property', 'notes', 'created_at']


class PropertyComparisonSerializer(serializers.ModelSerializer):
    properties = PropertyListSerializer(many=True, read_only=True)
    property_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False
    )
    
    class Meta:
        model = PropertyComparison
        fields = ['id', 'name', 'properties', 'property_ids', 'notes', 'is_active', 'created_at']
    
    def create(self, validated_data):
        property_ids = validated_data.pop('property_ids', [])
        comparison = PropertyComparison.objects.create(**validated_data)
        if property_ids:
            properties = Property.objects.filter(id__in=property_ids)
            comparison.properties.set(properties)
        return comparison


class ViewingAppointmentSerializer(serializers.ModelSerializer):
    property_title = serializers.CharField(source='property.title', read_only=True)
    property_address = serializers.CharField(source='property.address', read_only=True)
    
    class Meta:
        model = ViewingAppointment
        fields = [
            'id', 'property', 'property_title', 'property_address',
            'requested_date', 'confirmed_date', 'duration_minutes',
            'status', 'contact_phone', 'contact_email', 'attendees_count',
            'user_notes', 'agent_notes', 'feedback', 'interested',
            'is_virtual', 'meeting_link', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']