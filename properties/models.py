from django.contrib.gis.db import models
from django.contrib.gis.geos import Point
from django.utils.translation import gettext_lazy as _
from django.conf import settings
import uuid


class Property(models.Model):
    """Property model for real estate listings."""
    
    PROPERTY_TYPES = (
        ('apartment', 'Apartment'),
        ('villa', 'Villa'),
        ('office', 'Office'),
        ('shop', 'Shop'),
        ('warehouse', 'Warehouse'),
        ('land', 'Land'),
        ('building', 'Building'),
        ('farm', 'Farm'),
    )
    
    PROPERTY_STATUS = (
        ('available', 'Available'),
        ('sold', 'Sold'),
        ('rented', 'Rented'),
        ('auction', 'In Auction'),
        ('pending', 'Pending'),
        ('unavailable', 'Unavailable'),
    )
    
    PURPOSE_CHOICES = (
        ('sale', 'For Sale'),
        ('rent', 'For Rent'),
        ('auction', 'For Auction'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='properties')
    
    # Basic Information
    title = models.CharField(_('title'), max_length=255)
    slug = models.SlugField(_('slug'), max_length=255, unique=True)
    description = models.TextField(_('description'))
    property_type = models.CharField(_('property type'), max_length=20, choices=PROPERTY_TYPES)
    purpose = models.CharField(_('purpose'), max_length=20, choices=PURPOSE_CHOICES)
    status = models.CharField(_('status'), max_length=20, choices=PROPERTY_STATUS, default='available')
    reference_number = models.CharField(_('reference number'), max_length=50, unique=True)
    
    # Location
    address = models.TextField(_('address'))
    city = models.CharField(_('city'), max_length=100)
    district = models.CharField(_('district'), max_length=100)
    country = models.CharField(_('country'), max_length=100, default='Saudi Arabia')
    postal_code = models.CharField(_('postal code'), max_length=20, blank=True)
    location = models.PointField(_('location'), srid=4326, null=True, blank=True)
    
    # Property Details
    area_sqm = models.DecimalField(_('area (sqm)'), max_digits=10, decimal_places=2)
    bedrooms = models.IntegerField(_('bedrooms'), default=0)
    bathrooms = models.IntegerField(_('bathrooms'), default=0)
    parking_spaces = models.IntegerField(_('parking spaces'), default=0)
    floor_number = models.IntegerField(_('floor number'), null=True, blank=True)
    total_floors = models.IntegerField(_('total floors'), null=True, blank=True)
    year_built = models.IntegerField(_('year built'), null=True, blank=True)
    
    # Pricing
    price = models.DecimalField(_('price'), max_digits=12, decimal_places=2)
    price_per_sqm = models.DecimalField(_('price per sqm'), max_digits=10, decimal_places=2, null=True, blank=True)
    currency = models.CharField(_('currency'), max_length=3, default='SAR')
    is_negotiable = models.BooleanField(_('is negotiable'), default=False)
    
    # Features (JSON field for flexibility)
    features = models.JSONField(_('features'), default=list, blank=True)
    amenities = models.JSONField(_('amenities'), default=list, blank=True)
    
    # SEO
    meta_title = models.CharField(_('meta title'), max_length=255, blank=True)
    meta_description = models.TextField(_('meta description'), blank=True)
    meta_keywords = models.TextField(_('meta keywords'), blank=True)
    
    # Stats
    views_count = models.IntegerField(_('views count'), default=0)
    favorites_count = models.IntegerField(_('favorites count'), default=0)
    
    # Flags
    is_featured = models.BooleanField(_('is featured'), default=False)
    is_verified = models.BooleanField(_('is verified'), default=False)
    is_published = models.BooleanField(_('is published'), default=True)
    
    # Timestamps
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    published_at = models.DateTimeField(_('published at'), null=True, blank=True)
    sold_at = models.DateTimeField(_('sold at'), null=True, blank=True)
    
    class Meta:
        db_table = 'properties'
        verbose_name = _('Property')
        verbose_name_plural = _('Properties')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'purpose', 'is_published']),
            models.Index(fields=['city', 'district']),
            models.Index(fields=['property_type', 'status']),
            models.Index(fields=['-created_at']),
            models.Index(fields=['reference_number']),
        ]
    
    def save(self, *args, **kwargs):
        if self.price and self.area_sqm:
            self.price_per_sqm = self.price / self.area_sqm
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.title


class PropertyImage(models.Model):
    """Images for properties."""
    
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(_('image'), upload_to='properties/images/')
    title = models.CharField(_('title'), max_length=255, blank=True)
    is_primary = models.BooleanField(_('is primary'), default=False)
    order = models.IntegerField(_('order'), default=0)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    
    class Meta:
        db_table = 'property_images'
        verbose_name = _('Property Image')
        verbose_name_plural = _('Property Images')
        ordering = ['order', 'created_at']
    
    def __str__(self):
        return f"{self.property.title} - Image {self.order}"


class PropertyDocument(models.Model):
    """Documents for properties."""
    
    DOCUMENT_TYPES = (
        ('deed', 'Property Deed'),
        ('contract', 'Contract'),
        ('plan', 'Floor Plan'),
        ('certificate', 'Certificate'),
        ('other', 'Other'),
    )
    
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='documents')
    document = models.FileField(_('document'), upload_to='properties/documents/')
    document_type = models.CharField(_('document type'), max_length=20, choices=DOCUMENT_TYPES)
    title = models.CharField(_('title'), max_length=255)
    description = models.TextField(_('description'), blank=True)
    is_public = models.BooleanField(_('is public'), default=False)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    
    class Meta:
        db_table = 'property_documents'
        verbose_name = _('Property Document')
        verbose_name_plural = _('Property Documents')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.property.title} - {self.title}"