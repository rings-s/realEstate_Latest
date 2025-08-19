from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db.models import Q, Avg, Count, Sum
from django.core.paginator import Paginator
from django.contrib.gis.geos import Point
from django.contrib.gis.db.models.functions import Distance
from django.utils.text import slugify
import uuid
from .models import Property, PropertyImage, PropertyDocument
from .serializers import PropertySerializer, PropertyListSerializer
from .permissions import IsOwnerOrReadOnly


@api_view(['GET'])
@permission_classes([AllowAny])
def property_list(request):
    """List all properties with filters."""
    properties = Property.objects.filter(is_published=True)
    
    # Filters
    property_type = request.GET.get('type')
    purpose = request.GET.get('purpose')
    city = request.GET.get('city')
    district = request.GET.get('district')
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    bedrooms = request.GET.get('bedrooms')
    bathrooms = request.GET.get('bathrooms')
    min_area = request.GET.get('min_area')
    max_area = request.GET.get('max_area')
    is_featured = request.GET.get('featured')
    search = request.GET.get('search')
    
    # Location-based search
    lat = request.GET.get('lat')
    lng = request.GET.get('lng')
    radius = request.GET.get('radius', 10)  # km
    
    if property_type:
        properties = properties.filter(property_type=property_type)
    if purpose:
        properties = properties.filter(purpose=purpose)
    if city:
        properties = properties.filter(city__icontains=city)
    if district:
        properties = properties.filter(district__icontains=district)
    if min_price:
        properties = properties.filter(price__gte=min_price)
    if max_price:
        properties = properties.filter(price__lte=max_price)
    if bedrooms:
        properties = properties.filter(bedrooms=bedrooms)
    if bathrooms:
        properties = properties.filter(bathrooms=bathrooms)
    if min_area:
        properties = properties.filter(area_sqm__gte=min_area)
    if max_area:
        properties = properties.filter(area_sqm__lte=max_area)
    if is_featured:
        properties = properties.filter(is_featured=True)
    
    if search:
        properties = properties.filter(
            Q(title__icontains=search) |
            Q(description__icontains=search) |
            Q(address__icontains=search) |
            Q(reference_number__icontains=search)
        )
    
    if lat and lng:
        point = Point(float(lng), float(lat), srid=4326)
        properties = properties.filter(location__isnull=False).annotate(
            distance=Distance('location', point)
        ).filter(distance__lte=float(radius) * 1000).order_by('distance')
    
    # Sorting
    sort_by = request.GET.get('sort', '-created_at')
    if sort_by in ['price', '-price', 'area_sqm', '-area_sqm', 'created_at', '-created_at']:
        properties = properties.order_by(sort_by)
    
    # Select related to optimize queries
    properties = properties.select_related('owner').prefetch_related('images')
    
    # Pagination
    page = request.GET.get('page', 1)
    page_size = request.GET.get('page_size', 20)
    paginator = Paginator(properties, page_size)
    page_obj = paginator.get_page(page)
    
    serializer = PropertyListSerializer(page_obj.object_list, many=True)
    
    return Response({
        'results': serializer.data,
        'count': paginator.count,
        'next': page_obj.has_next(),
        'previous': page_obj.has_previous(),
        'total_pages': paginator.num_pages,
        'current_page': page_obj.number
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def property_detail(request, pk):
    """Get property details."""
    property = get_object_or_404(Property, pk=pk, is_published=True)
    
    # Increment view count
    property.views_count += 1
    property.save(update_fields=['views_count'])
    
    serializer = PropertySerializer(property)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def property_create(request):
    """Create a new property."""
    data = request.data.copy()
    data['owner'] = request.user.id
    
    # Generate reference number and slug
    data['reference_number'] = f"PROP-{uuid.uuid4().hex[:8].upper()}"
    data['slug'] = slugify(data.get('title', '')) + f"-{uuid.uuid4().hex[:6]}"
    
    serializer = PropertySerializer(data=data)
    if serializer.is_valid():
        property = serializer.save()
        
        # Handle images
        images = request.FILES.getlist('images')
        for i, image in enumerate(images):
            PropertyImage.objects.create(
                property=property,
                image=image,
                is_primary=(i == 0),
                order=i
            )
        
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated, IsOwnerOrReadOnly])
def property_update(request, pk):
    """Update property."""
    property = get_object_or_404(Property, pk=pk)
    
    # Check ownership
    if property.owner != request.user and not request.user.is_staff:
        return Response({'error': 'Not authorized'}, status=status.HTTP_403_FORBIDDEN)
    
    serializer = PropertySerializer(property, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def property_delete(request, pk):
    """Delete property."""
    property = get_object_or_404(Property, pk=pk)
    
    # Check ownership
    if property.owner != request.user and not request.user.is_staff:
        return Response({'error': 'Not authorized'}, status=status.HTTP_403_FORBIDDEN)
    
    property.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_properties(request):
    """Get user's properties."""
    properties = Property.objects.filter(owner=request.user)
    
    # Pagination
    page = request.GET.get('page', 1)
    page_size = request.GET.get('page_size', 20)
    paginator = Paginator(properties, page_size)
    page_obj = paginator.get_page(page)
    
    serializer = PropertyListSerializer(page_obj.object_list, many=True)
    
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
def toggle_favorite(request, pk):
    """Toggle property favorite status."""
    property = get_object_or_404(Property, pk=pk)
    
    # This is a simple implementation
    # You might want to create a separate Favorite model
    # For now, just increment/decrement the counter
    
    return Response({'message': 'Feature to be implemented with Favorite model'})


@api_view(['GET'])
@permission_classes([AllowAny])
def property_statistics(request):
    """Get property statistics."""
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
        'by_type': by_type,
        'by_city': by_city
    })