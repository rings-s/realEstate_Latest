from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db.models import Q, F
from django.core.paginator import Paginator
from django.db import transaction
from django.utils import timezone
import uuid
from .models import Category, Product, Cart, CartItem, Order, OrderItem
from .serializers import (
    CategorySerializer, ProductListSerializer, ProductDetailSerializer,
    CartSerializer, CartItemSerializer, OrderSerializer, CreateOrderSerializer
)


@api_view(['GET'])
@permission_classes([AllowAny])
def category_list(request):
    """List all active categories."""
    categories = Category.objects.filter(is_active=True, parent=None)
    serializer = CategorySerializer(categories, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([AllowAny])
def product_list(request):
    """List all products with filters."""
    products = Product.objects.filter(is_active=True)
    
    # Filters
    category = request.GET.get('category')
    search = request.GET.get('search')
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    vendor = request.GET.get('vendor')
    is_featured = request.GET.get('featured')
    in_stock = request.GET.get('in_stock')
    
    if category:
        products = products.filter(category__slug=category)
    if search:
        products = products.filter(
            Q(name__icontains=search) |
            Q(description__icontains=search) |
            Q(sku__icontains=search)
        )
    if min_price:
        products = products.filter(price__gte=min_price)
    if max_price:
        products = products.filter(price__lte=max_price)
    if vendor:
        products = products.filter(vendor_id=vendor)
    if is_featured:
        products = products.filter(is_featured=True)
    if in_stock:
        products = products.filter(
            Q(track_inventory=False) | Q(quantity__gt=0)
        )
    
    # Sorting
    sort_by = request.GET.get('sort', '-created_at')
    if sort_by in ['price', '-price', 'name', '-name', 'rating', '-rating', '-created_at']:
        products = products.order_by(sort_by)
    
    # Pagination
    page = request.GET.get('page', 1)
    page_size = request.GET.get('page_size', 20)
    paginator = Paginator(products, page_size)
    page_obj = paginator.get_page(page)
    
    serializer = ProductListSerializer(page_obj.object_list, many=True)
    
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
def product_detail(request, slug):
    """Get product details."""
    product = get_object_or_404(Product, slug=slug, is_active=True)
    
    # Increment view count
    product.views_count = F('views_count') + 1
    product.save(update_fields=['views_count'])
    
    serializer = ProductDetailSerializer(product)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_product(request):
    """Add a new product (vendor only)."""
    if request.user.user_type not in ['company', 'admin']:
        return Response(
            {'error': 'Only vendors can add products'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    data = request.data.copy()
    data['vendor'] = request.user.id
    data['sku'] = f"SKU-{uuid.uuid4().hex[:8].upper()}"
    
    serializer = ProductDetailSerializer(data=data)
    if serializer.is_valid():
        product = serializer.save()
        
        # Handle images
        images = request.FILES.getlist('images')
        for i, image in enumerate(images):
            ProductImage.objects.create(
                product=product,
                image=image,
                is_primary=(i == 0),
                order=i
            )
        
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def cart_view(request):
    """Get or create cart."""
    if request.user.is_authenticated:
        cart, created = Cart.objects.get_or_create(user=request.user)
    else:
        session_key = request.session.session_key
        if not session_key:
            request.session.create()
            session_key = request.session.session_key
        cart, created = Cart.objects.get_or_create(session_key=session_key)
    
    if request.method == 'GET':
        serializer = CartSerializer(cart)
        return Response(serializer.data)
    
    return Response(CartSerializer(cart).data)


@api_view(['POST'])
@permission_classes([AllowAny])
def add_to_cart(request):
    """Add item to cart."""
    product_id = request.data.get('product_id')
    quantity = int(request.data.get('quantity', 1))
    
    if not product_id:
        return Response(
            {'error': 'Product ID required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    product = get_object_or_404(Product, id=product_id, is_active=True)
    
    # Check stock
    if product.track_inventory and product.quantity < quantity:
        return Response(
            {'error': 'Insufficient stock'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Get or create cart
    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)
    else:
        session_key = request.session.session_key
        if not session_key:
            request.session.create()
            session_key = request.session.session_key
        cart, _ = Cart.objects.get_or_create(session_key=session_key)
    
    # Add or update cart item
    cart_item, created = CartItem.objects.get_or_create(
        cart=cart,
        product=product,
        defaults={'price': product.price, 'quantity': quantity}
    )
    
    if not created:
        cart_item.quantity += quantity
        cart_item.save()
    
    # Recalculate totals
    cart.calculate_totals()
    
    serializer = CartSerializer(cart)
    return Response(serializer.data)


@api_view(['PUT'])
@permission_classes([AllowAny])
def update_cart_item(request, item_id):
    """Update cart item quantity."""
    quantity = int(request.data.get('quantity', 1))
    
    if request.user.is_authenticated:
        cart_item = get_object_or_404(
            CartItem,
            id=item_id,
            cart__user=request.user
        )
    else:
        session_key = request.session.session_key
        cart_item = get_object_or_404(
            CartItem,
            id=item_id,
            cart__session_key=session_key
        )
    
    # Check stock
    if cart_item.product.track_inventory and cart_item.product.quantity < quantity:
        return Response(
            {'error': 'Insufficient stock'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    cart_item.quantity = quantity
    cart_item.save()
    
    # Recalculate totals
    cart_item.cart.calculate_totals()
    
    serializer = CartSerializer(cart_item.cart)
    return Response(serializer.data)


@api_view(['DELETE'])
@permission_classes([AllowAny])
def remove_from_cart(request, item_id):
    """Remove item from cart."""
    if request.user.is_authenticated:
        cart_item = get_object_or_404(
            CartItem,
            id=item_id,
            cart__user=request.user
        )
    else:
        session_key = request.session.session_key
        cart_item = get_object_or_404(
            CartItem,
            id=item_id,
            cart__session_key=session_key
        )
    
    cart = cart_item.cart
    cart_item.delete()
    
    # Recalculate totals
    cart.calculate_totals()
    
    serializer = CartSerializer(cart)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def checkout(request):
    """Create order from cart."""
    cart = get_object_or_404(Cart, user=request.user)
    
    if not cart.items.exists():
        return Response(
            {'error': 'Cart is empty'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    serializer = CreateOrderSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    with transaction.atomic():
        # Create order
        order = Order.objects.create(
            order_number=f"ORD-{uuid.uuid4().hex[:8].upper()}",
            customer=request.user,
            customer_email=request.user.email,
            customer_phone=request.user.phone_number,
            customer_name=request.user.get_full_name(),
            billing_address=serializer.validated_data['billing_address'],
            shipping_address=serializer.validated_data['shipping_address'],
            payment_method=serializer.validated_data['payment_method'],
            customer_notes=serializer.validated_data.get('customer_notes', ''),
            subtotal=cart.subtotal,
            tax=cart.tax,
            total=cart.total
        )
        
        # Create order items
        for cart_item in cart.items.all():
            OrderItem.objects.create(
                order=order,
                product=cart_item.product,
                product_name=cart_item.product.name,
                product_sku=cart_item.product.sku,
                quantity=cart_item.quantity,
                price=cart_item.price,
                subtotal=cart_item.subtotal,
                tax=cart_item.tax
            )
            
            # Update product inventory
            if cart_item.product.track_inventory:
                cart_item.product.quantity -= cart_item.quantity
                cart_item.product.sales_count += cart_item.quantity
                cart_item.product.save()
        
        # Clear cart
        cart.items.all().delete()
        cart.calculate_totals()
        
        # TODO: Process payment
        
        order_serializer = OrderSerializer(order)
        return Response(order_serializer.data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def order_list(request):
    """List user's orders."""
    orders = Order.objects.filter(customer=request.user)
    
    # Filters
    status_filter = request.GET.get('status')
    if status_filter:
        orders = orders.filter(status=status_filter)
    
    # Pagination
    page = request.GET.get('page', 1)
    page_size = request.GET.get('page_size', 10)
    paginator = Paginator(orders, page_size)
    page_obj = paginator.get_page(page)
    
    serializer = OrderSerializer(page_obj.object_list, many=True)
    
    return Response({
        'results': serializer.data,
        'count': paginator.count,
        'next': page_obj.has_next(),
        'previous': page_obj.has_previous(),
        'total_pages': paginator.num_pages,
        'current_page': page_obj.number
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def order_detail(request, order_number):
    """Get order details."""
    order = get_object_or_404(
        Order,
        order_number=order_number,
        customer=request.user
    )
    serializer = OrderSerializer(order)
    return Response(serializer.data)