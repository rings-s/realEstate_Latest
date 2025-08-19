from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404
from django.db.models import Q, Count, Avg, Sum
from django.contrib.gis.geos import Point
from django.contrib.gis.db.models.functions import Distance
from django.core.cache import cache
from django.utils import timezone
from .models import (
    Property, PropertyImage, PropertyDocument, 
    Amenity, AmenityCategory, PropertyAmenity,
    PropertyFavorite, PropertyView, PropertyComparison, ViewingAppointment
)
from .serializers import (
    PropertySerializer, PropertyListSerializer, PropertyDetailSerializer,
    AmenitySerializer, AmenityCategorySerializer,
    PropertyFavoriteSerializer, PropertyComparisonSerializer, 
    ViewingAppointmentSerializer
)
from .permissions import IsOwnerOrReadOnly


class PropertyListCreateAPIView(generics.ListCreateAPIView):
    """List all properties or create a new property."""
    
    def get_queryset(self):
        queryset = Property.objects.filter(is_published=True)
        
        # Filters
        property_type = self.request.GET.get('type')
        purpose = self.request.GET.get('purpose')
        city = self.request.GET.get('city')
        district = self.request.GET.get('district')
        min_price = self.request.GET.get('min_price')
        max_price = self.request.GET.get('max_price')
        bedrooms = self.request.GET.get('bedrooms')
        bathrooms = self.request.GET.get('bathrooms')
        min_area = self.request.GET.get('min_area')
        max_area = self.request.GET.get('max_area')
        is_featured = self.request.GET.get('featured')
        search = self.request.GET.get('search')
        
        # Location-based search
        lat = self.request.GET.get('lat')
        lng = self.request.GET.get('lng')
        radius = self.request.GET.get('radius', 10)
        
        # Amenity filters
        amenities = self.request.GET.getlist('amenities[]')
        
        if property_type:
            queryset = queryset.filter(property_type=property_type)
        if purpose:
            queryset = queryset.filter(purpose=purpose)
        if city:
            queryset = queryset.filter(city__icontains=city)
        if district:
            queryset = queryset.filter(district__icontains=district)
        if min_price:
            queryset = queryset.filter(price__gte=min_price)
        if max_price:
            queryset = queryset.filter(price__lte=max_price)
        if bedrooms:
            queryset = queryset.filter(bedrooms=bedrooms)
        if bathrooms:
            queryset = queryset.filter(bathrooms=bathrooms)
        if min_area:
            queryset = queryset.filter(area_sqm__gte=min_area)
        if max_area:
            queryset = queryset.filter(area_sqm__lte=max_area)
        if is_featured:
            queryset = queryset.filter(is_featured=True)
        
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(description__icontains=search) |
                Q(address__icontains=search) |
                Q(reference_number__icontains=search)
            )
        
        if amenities:
            for amenity_slug in amenities:
                queryset = queryset.filter(
                    property_amenities__amenity__slug=amenity_slug,
                    property_amenities__is_available=True
                )
        
        if lat and lng:
            point = Point(float(lng), float(lat), srid=4326)
            queryset = queryset.filter(location__isnull=False).annotate(
                distance=Distance('location', point)
            ).filter(distance__lte=float(radius) * 1000).order_by('distance')
        
        # Sorting
        sort_by = self.request.GET.get('sort', '-created_at')
        if sort_by == 'recommended':
            queryset = queryset.annotate(
                score=Count('favorited_by') * 2 + Count('property_views')
            ).order_by('-score', '-created_at')
        elif sort_by == 'value':
            queryset = queryset.order_by('price_per_sqm')
        elif sort_by in ['price', '-price', 'area_sqm', '-area_sqm', 'created_at', '-created_at']:
            queryset = queryset.order_by(sort_by)
        
        return queryset.select_related('owner').prefetch_related(
            'images', 'property_amenities__amenity__category'
        )
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return PropertySerializer
        return PropertyListSerializer
    
    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAuthenticated()]
        return [AllowAny()]
    
    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)
        
        # Handle images
        images = self.request.FILES.getlist('images')
        property_obj = serializer.instance
        for i, image in enumerate(images):
            PropertyImage.objects.create(
                property=property_obj,
                image=image,
                is_primary=(i == 0),
                order=i
            )


class PropertyRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a property."""
    queryset = Property.objects.all()
    serializer_class = PropertyDetailSerializer
    permission_classes = [IsOwnerOrReadOnly]
    
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        
        # Track view
        ip_address = request.META.get('REMOTE_ADDR')
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        PropertyView.objects.create(
            property=instance,
            user=request.user if request.user.is_authenticated else None,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        # Increment view count
        instance.views_count += 1
        instance.save(update_fields=['views_count'])
        
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class MyPropertiesListAPIView(generics.ListAPIView):
    """List user's own properties."""
    serializer_class = PropertyListSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Property.objects.filter(owner=self.request.user)


class PropertyStatisticsAPIView(APIView):
    """Get property statistics."""
    permission_classes = [AllowAny]
    
    def get(self, request):
        stats = Property.objects.filter(is_published=True).aggregate(
            total_properties=Count('id'),
            avg_price=Avg('price'),
            avg_area=Avg('area_sqm'),
            total_value=Sum('price')
        )
        
        by_type = Property.objects.filter(is_published=True).values('property_type').annotate(
            count=Count('id'),
            avg_price=Avg('price')
        )
        
        by_city = Property.objects.filter(is_published=True).values('city').annotate(
            count=Count('id'),
            avg_price=Avg('price')
        ).order_by('-count')[:10]
        
        return Response({
            'general': stats,
            'by_type': list(by_type),
            'by_city': list(by_city)
        })


class PropertyAnalyticsAPIView(APIView):
    """Get detailed analytics for a property (owner only)."""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, pk):
        property_obj = get_object_or_404(Property, pk=pk, owner=request.user)
        
        # Use caching
        cache_key = f'property_analytics_{pk}'
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return Response(cached_data)
        
        from datetime import timedelta
        now = timezone.now()
        
        # View statistics
        total_views = property_obj.property_views.count()
        unique_viewers = property_obj.property_views.values('user').distinct().count()
        views_last_week = property_obj.property_views.filter(
            created_at__gte=now - timedelta(days=7)
        ).count()
        views_last_month = property_obj.property_views.filter(
            created_at__gte=now - timedelta(days=30)
        ).count()
        
        # Engagement metrics
        favorites = property_obj.favorited_by.count()
        viewing_requests = property_obj.viewing_appointments.count()
        completed_viewings = property_obj.viewing_appointments.filter(
            status='completed'
        ).count()
        
        # Calculate conversion rates
        view_to_favorite_rate = (favorites / total_views * 100) if total_views > 0 else 0
        view_to_viewing_rate = (viewing_requests / total_views * 100) if total_views > 0 else 0
        
        # Daily views for chart
        daily_views = []
        for i in range(30):
            date = now.date() - timedelta(days=i)
            count = property_obj.property_views.filter(
                created_at__date=date
            ).count()
            daily_views.append({
                'date': date.isoformat(),
                'views': count
            })
        daily_views.reverse()
        
        analytics_data = {
            'overview': {
                'total_views': total_views,
                'unique_viewers': unique_viewers,
                'favorites': favorites,
                'viewing_requests': viewing_requests,
                'completed_viewings': completed_viewings,
            },
            'trends': {
                'views_last_week': views_last_week,
                'views_last_month': views_last_month,
                'daily_views': daily_views,
            },
            'conversion': {
                'view_to_favorite': round(view_to_favorite_rate, 2),
                'view_to_viewing': round(view_to_viewing_rate, 2),
            },
            'comparisons': property_obj.in_comparisons.count(),
        }
        
        # Cache for 1 hour
        cache.set(cache_key, analytics_data, 3600)
        
        return Response(analytics_data)


# Amenity Views
class AmenityCategoryListAPIView(generics.ListAPIView):
    """List all amenity categories."""
    queryset = AmenityCategory.objects.filter(is_active=True)
    serializer_class = AmenityCategorySerializer
    permission_classes = [AllowAny]


class AmenityListAPIView(generics.ListAPIView):
    """List all amenities."""
    queryset = Amenity.objects.filter(is_searchable=True).select_related('category')
    serializer_class = AmenitySerializer
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        property_type = self.request.GET.get('property_type')
        category_slug = self.request.GET.get('category')
        
        if property_type:
            queryset = queryset.filter(
                Q(applicable_property_types__contains=[property_type]) |
                Q(applicable_property_types=[])
            )
        
        if category_slug:
            queryset = queryset.filter(category__slug=category_slug)
        
        return queryset


# Favorite Views
class PropertyFavoriteToggleAPIView(APIView):
    """Toggle property favorite status."""
    permission_classes = [IsAuthenticated]
    
    def post(self, request, pk):
        property_obj = get_object_or_404(Property, pk=pk)
        
        favorite, created = PropertyFavorite.objects.get_or_create(
            user=request.user,
            property=property_obj
        )
        
        if not created:
            favorite.delete()
            property_obj.favorites_count = max(0, property_obj.favorites_count - 1)
            property_obj.save(update_fields=['favorites_count'])
            return Response({'favorited': False, 'message': 'Removed from favorites'})
        
        property_obj.favorites_count += 1
        property_obj.save(update_fields=['favorites_count'])
        return Response({'favorited': True, 'message': 'Added to favorites'})


class MyFavoritesListAPIView(generics.ListAPIView):
    """List user's favorite properties."""
    serializer_class = PropertyFavoriteSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return PropertyFavorite.objects.filter(
            user=self.request.user
        ).select_related('property').order_by('-created_at')


# Comparison Views
class PropertyComparisonListCreateAPIView(generics.ListCreateAPIView):
    """List user's comparisons or create a new one."""
    serializer_class = PropertyComparisonSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return PropertyComparison.objects.filter(
            user=self.request.user,
            is_active=True
        ).prefetch_related('properties')
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class PropertyComparisonDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a comparison."""
    serializer_class = PropertyComparisonSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return PropertyComparison.objects.filter(user=self.request.user)
    
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        properties = instance.properties.all()
        
        # Calculate comparison metrics
        avg_price = properties.aggregate(Avg('price'))['price__avg']
        avg_area = properties.aggregate(Avg('area_sqm'))['area_sqm__avg']
        
        comparison_data = {
            'id': instance.id,
            'name': instance.name,
            'created_at': instance.created_at,
            'properties': [],
            'summary': {
                'avg_price': avg_price,
                'avg_area': avg_area,
                'count': properties.count()
            }
        }
        
        for prop in properties:
            prop_data = {
                'id': prop.id,
                'title': prop.title,
                'price': prop.price,
                'price_comparison': ((prop.price - avg_price) / avg_price * 100) if avg_price else 0,
                'area_sqm': prop.area_sqm,
                'area_comparison': ((prop.area_sqm - avg_area) / avg_area * 100) if avg_area else 0,
                'price_per_sqm': prop.price_per_sqm,
                'bedrooms': prop.bedrooms,
                'bathrooms': prop.bathrooms,
                'property_type': prop.property_type,
                'city': prop.city,
                'district': prop.district,
                'amenities': list(prop.property_amenities.values_list('amenity__name', flat=True)),
            }
            comparison_data['properties'].append(prop_data)
        
        return Response(comparison_data)


# Viewing Appointment Views
class ViewingAppointmentListCreateAPIView(generics.ListCreateAPIView):
    """List viewing appointments or create a new one."""
    serializer_class = ViewingAppointmentSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        queryset = ViewingAppointment.objects.filter(
            Q(user=user) | Q(property__owner=user)
        ).select_related('property', 'user')
        
        status_filter = self.request.GET.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        return queryset.order_by('requested_date')
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
        
        # Send notification
        instance = serializer.instance
        from notifications.utils import create_notification
        create_notification(
            user=instance.property.owner,
            title='New Viewing Request',
            message=f'New viewing request for {instance.property.title}',
            notification_type='property',
            metadata={'appointment_id': str(instance.id)}
        )


class ViewingAppointmentDetailAPIView(generics.RetrieveUpdateAPIView):
    """Retrieve or update a viewing appointment."""
    serializer_class = ViewingAppointmentSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        return ViewingAppointment.objects.filter(
            Q(user=user) | Q(property__owner=user)
        )
    
    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        
        # Only property owner can confirm/reschedule
        if instance.property.owner != request.user and 'status' in request.data:
            return Response(
                {'error': 'Only property owner can change status'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        return super().update(request, *args, **kwargs)