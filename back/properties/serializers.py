from rest_framework import serializers
from .models import Property, PropertyImage, PropertyDocument
from django.contrib.gis.geos import Point


class PropertyImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = PropertyImage
        fields = ['id', 'image', 'title', 'is_primary', 'order']


class PropertyDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = PropertyDocument
        fields = ['id', 'document', 'document_type', 'title', 'description', 'is_public', 'created_at']


class PropertySerializer(serializers.ModelSerializer):
    images = PropertyImageSerializer(many=True, read_only=True)
    documents = PropertyDocumentSerializer(many=True, read_only=True)
    owner_name = serializers.CharField(source='owner.get_full_name', read_only=True)
    latitude = serializers.FloatField(write_only=True, required=False)
    longitude = serializers.FloatField(write_only=True, required=False)
    
    class Meta:
        model = Property
        fields = [
            'id', 'owner', 'owner_name', 'title', 'slug', 'description',
            'property_type', 'purpose', 'status', 'reference_number',
            'address', 'city', 'district', 'country', 'postal_code',
            'latitude', 'longitude', 'location',
            'area_sqm', 'bedrooms', 'bathrooms', 'parking_spaces',
            'floor_number', 'total_floors', 'year_built',
            'price', 'price_per_sqm', 'currency', 'is_negotiable',
            'features', 'amenities',
            'meta_title', 'meta_description', 'meta_keywords',
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
    
    def create(self, validated_data):
        latitude = validated_data.pop('latitude', None)
        longitude = validated_data.pop('longitude', None)
        
        if latitude and longitude:
            validated_data['location'] = Point(longitude, latitude, srid=4326)
        
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        latitude = validated_data.pop('latitude', None)
        longitude = validated_data.pop('longitude', None)
        
        if latitude and longitude:
            validated_data['location'] = Point(longitude, latitude, srid=4326)
        
        return super().update(instance, validated_data)


class PropertyListSerializer(serializers.ModelSerializer):
    primary_image = serializers.SerializerMethodField()
    owner_name = serializers.CharField(source='owner.get_full_name', read_only=True)
    
    class Meta:
        model = Property
        fields = [
            'id', 'title', 'slug', 'property_type', 'purpose', 'status',
            'city', 'district', 'area_sqm', 'bedrooms', 'bathrooms',
            'price', 'currency', 'primary_image', 'owner_name',
            'is_featured', 'created_at'
        ]
    
    def get_primary_image(self, obj):
        primary = obj.images.filter(is_primary=True).first()
        if primary:
            return primary.image.url if primary.image else None
        first_image = obj.images.first()
        return first_image.image.url if first_image and first_image.image else None