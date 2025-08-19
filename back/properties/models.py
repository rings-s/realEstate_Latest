from django.contrib.gis.db import models
from django.contrib.gis.geos import Point
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.utils.text import slugify
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
    
    # Location fields for Leaflet
    latitude = models.FloatField(_('latitude'), null=True, blank=True, db_index=True)
    longitude = models.FloatField(_('longitude'), null=True, blank=True, db_index=True)
    location = models.PointField(_('location'), srid=4326, null=True, blank=True)
    location_accuracy = models.CharField(_('location accuracy'), max_length=20, default='exact', 
                                        choices=[('exact', 'Exact'), ('approximate', 'Approximate'), ('area', 'Area Only')])
    map_zoom_level = models.IntegerField(_('map zoom level'), default=15)
    
    # Nearby places for better UX
    nearby_places = models.JSONField(_('nearby places'), default=dict, blank=True)
    
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
    
    # Features (JSON field for additional features)
    features = models.JSONField(_('features'), default=list, blank=True)
    
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
            models.Index(fields=['latitude', 'longitude']),
        ]
    
    def save(self, *args, **kwargs):
        # Generate slug if not exists
        if not self.slug:
            self.slug = slugify(self.title) + f"-{uuid.uuid4().hex[:6]}"
        
        # Generate reference number if not exists
        if not self.reference_number:
            self.reference_number = f"PROP-{uuid.uuid4().hex[:8].upper()}"
        
        # Handle location
        if self.location and not self.latitude:
            self.longitude = self.location.x
            self.latitude = self.location.y
        elif self.latitude and self.longitude and not self.location:
            self.location = Point(self.longitude, self.latitude, srid=4326)
        
        # Calculate price per sqm
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


# Amenity Models
class AmenityCategory(models.Model):
    """Categories for organizing amenities."""
    
    CATEGORY_TYPES = (
        ('basic', 'Basic Amenities'),
        ('security', 'Security Features'),
        ('leisure', 'Leisure & Recreation'),
        ('accessibility', 'Accessibility'),
        ('smart', 'Smart Home Features'),
        ('outdoor', 'Outdoor Features'),
        ('parking', 'Parking & Storage'),
        ('utilities', 'Utilities'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_('name'), max_length=100)
    slug = models.SlugField(_('slug'), unique=True)
    category_type = models.CharField(_('type'), max_length=20, choices=CATEGORY_TYPES)
    icon = models.CharField(_('icon'), max_length=50, blank=True, help_text="Icon class name")
    order = models.IntegerField(_('order'), default=0)
    is_active = models.BooleanField(_('is active'), default=True)
    
    class Meta:
        db_table = 'amenity_categories'
        verbose_name = _('Amenity Category')
        verbose_name_plural = _('Amenity Categories')
        ordering = ['order', 'name']
    
    def __str__(self):
        return self.name


class Amenity(models.Model):
    """Property amenities master list."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.ForeignKey(AmenityCategory, on_delete=models.CASCADE, related_name='amenities')
    name = models.CharField(_('name'), max_length=100)
    slug = models.SlugField(_('slug'), unique=True)
    description = models.CharField(_('description'), max_length=255, blank=True)
    icon = models.CharField(_('icon'), max_length=50, blank=True)
    
    # For filtering
    is_premium = models.BooleanField(_('is premium'), default=False)
    is_searchable = models.BooleanField(_('is searchable'), default=True)
    
    # Property type applicability
    applicable_property_types = models.JSONField(
        _('applicable property types'), 
        default=list,
        help_text="List of property types this amenity applies to"
    )
    
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    
    class Meta:
        db_table = 'amenities'
        verbose_name = _('Amenity')
        verbose_name_plural = _('Amenities')
        ordering = ['category', 'name']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['is_searchable']),
        ]
    
    def __str__(self):
        return f"{self.category.name} - {self.name}"


class PropertyAmenity(models.Model):
    """Many-to-many relationship between properties and amenities."""
    
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='property_amenities')
    amenity = models.ForeignKey(Amenity, on_delete=models.CASCADE, related_name='property_amenities')
    
    is_available = models.BooleanField(_('is available'), default=True)
    notes = models.CharField(_('notes'), max_length=255, blank=True)
    verified = models.BooleanField(_('verified'), default=False)
    
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    
    class Meta:
        db_table = 'property_amenities'
        verbose_name = _('Property Amenity')
        verbose_name_plural = _('Property Amenities')
        unique_together = [['property', 'amenity']]
    
    def __str__(self):
        return f"{self.property.title} - {self.amenity.name}"


# Interaction Models
class PropertyFavorite(models.Model):
    """User favorite properties."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='favorite_properties')
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='favorited_by')
    
    notes = models.TextField(_('notes'), blank=True)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    
    class Meta:
        db_table = 'property_favorites'
        verbose_name = _('Property Favorite')
        verbose_name_plural = _('Property Favorites')
        unique_together = [['user', 'property']]
        indexes = [
            models.Index(fields=['user', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.property.title}"


class PropertyView(models.Model):
    """Track property views for analytics."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='property_views')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    
    ip_address = models.GenericIPAddressField(_('IP address'), null=True, blank=True)
    user_agent = models.TextField(_('user agent'), blank=True)
    referrer = models.URLField(_('referrer'), blank=True)
    
    view_duration = models.IntegerField(_('view duration (seconds)'), null=True, blank=True)
    viewed_images = models.BooleanField(_('viewed images'), default=False)
    viewed_documents = models.BooleanField(_('viewed documents'), default=False)
    contacted_owner = models.BooleanField(_('contacted owner'), default=False)
    
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    
    class Meta:
        db_table = 'property_views'
        verbose_name = _('Property View')
        verbose_name_plural = _('Property Views')
        indexes = [
            models.Index(fields=['property', '-created_at']),
            models.Index(fields=['user', '-created_at']),
        ]


class PropertyComparison(models.Model):
    """Save property comparisons for users."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='property_comparisons')
    name = models.CharField(_('comparison name'), max_length=100, blank=True)
    properties = models.ManyToManyField(Property, related_name='in_comparisons')
    
    notes = models.TextField(_('notes'), blank=True)
    is_active = models.BooleanField(_('is active'), default=True)
    
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    
    class Meta:
        db_table = 'property_comparisons'
        verbose_name = _('Property Comparison')
        verbose_name_plural = _('Property Comparisons')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.email} - {self.name or 'Comparison'}"


class ViewingAppointment(models.Model):
    """Property viewing appointments."""
    
    STATUS_CHOICES = (
        ('requested', 'Requested'),
        ('confirmed', 'Confirmed'),
        ('rescheduled', 'Rescheduled'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('no_show', 'No Show'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='viewing_appointments')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='viewing_appointments')
    
    requested_date = models.DateTimeField(_('requested date'))
    confirmed_date = models.DateTimeField(_('confirmed date'), null=True, blank=True)
    duration_minutes = models.IntegerField(_('duration (minutes)'), default=30)
    
    status = models.CharField(_('status'), max_length=20, choices=STATUS_CHOICES, default='requested')
    
    contact_phone = models.CharField(_('contact phone'), max_length=20)
    contact_email = models.EmailField(_('contact email'))
    attendees_count = models.IntegerField(_('number of attendees'), default=1)
    
    user_notes = models.TextField(_('user notes'), blank=True)
    agent_notes = models.TextField(_('agent notes'), blank=True)
    
    feedback = models.TextField(_('feedback'), blank=True)
    interested = models.BooleanField(_('interested'), null=True)
    
    is_virtual = models.BooleanField(_('is virtual viewing'), default=False)
    meeting_link = models.URLField(_('meeting link'), blank=True)
    
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    
    class Meta:
        db_table = 'viewing_appointments'
        verbose_name = _('Viewing Appointment')
        verbose_name_plural = _('Viewing Appointments')
        ordering = ['requested_date']
        indexes = [
            models.Index(fields=['status', 'requested_date']),
            models.Index(fields=['property', 'status']),
        ]
    
    def __str__(self):
        return f"{self.property.title} - {self.user.email} - {self.requested_date}"