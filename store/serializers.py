from rest_framework import serializers
from .models import Category, Product, ProductImage, Cart, CartItem, Order, OrderItem


class CategorySerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()
    
    class Meta:
        model = Category
        fields = [
            'id', 'name', 'slug', 'description', 'image',
            'parent', 'children', 'is_active', 'order'
        ]
    
    def get_children(self, obj):
        if obj.children.exists():
            return CategorySerializer(obj.children.filter(is_active=True), many=True).data
        return []


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ['id', 'image', 'alt_text', 'is_primary', 'order']


class ProductListSerializer(serializers.ModelSerializer):
    primary_image = serializers.SerializerMethodField()
    vendor_name = serializers.CharField(source='vendor.get_full_name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    
    class Meta:
        model = Product
        fields = [
            'id', 'name', 'slug', 'price', 'compare_price',
            'primary_image', 'vendor_name', 'category_name',
            'rating', 'reviews_count', 'is_featured', 'is_in_stock'
        ]
    
    def get_primary_image(self, obj):
        primary = obj.images.filter(is_primary=True).first()
        if primary:
            return primary.image.url if primary.image else None
        return None


class ProductDetailSerializer(serializers.ModelSerializer):
    images = ProductImageSerializer(many=True, read_only=True)
    vendor_name = serializers.CharField(source='vendor.get_full_name', read_only=True)
    category = CategorySerializer(read_only=True)
    is_in_stock = serializers.SerializerMethodField()
    
    class Meta:
        model = Product
        fields = '__all__'
        read_only_fields = [
            'id', 'slug', 'views_count', 'sales_count',
            'rating', 'reviews_count', 'created_at', 'updated_at'
        ]
    
    def get_is_in_stock(self, obj):
        return obj.is_in_stock()


class CartItemSerializer(serializers.ModelSerializer):
    product_details = ProductListSerializer(source='product', read_only=True)
    total = serializers.DecimalField(source='subtotal', max_digits=10, decimal_places=2, read_only=True)
    
    class Meta:
        model = CartItem
        fields = [
            'id', 'product', 'product_details', 'quantity',
            'price', 'subtotal', 'tax', 'total'
        ]
        read_only_fields = ['price', 'subtotal', 'tax']


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    items_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Cart
        fields = [
            'id', 'items', 'items_count', 'subtotal',
            'tax', 'total', 'created_at', 'updated_at'
        ]
        read_only_fields = ['subtotal', 'tax', 'total']
    
    def get_items_count(self, obj):
        return obj.items.count()


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = [
            'product', 'product_name', 'product_sku',
            'quantity', 'price', 'subtotal', 'tax'
        ]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    
    class Meta:
        model = Order
        fields = '__all__'
        read_only_fields = [
            'id', 'order_number', 'created_at', 'updated_at',
            'paid_at', 'shipped_at', 'delivered_at'
        ]


class CreateOrderSerializer(serializers.Serializer):
    """Serializer for creating orders from cart."""
    
    billing_address = serializers.JSONField()
    shipping_address = serializers.JSONField()
    payment_method = serializers.CharField()
    customer_notes = serializers.CharField(required=False, allow_blank=True)