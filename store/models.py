from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
import uuid
from decimal import Decimal


class Category(models.Model):
    """Category for store products."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_('name'), max_length=100)
    slug = models.SlugField(_('slug'), unique=True)
    description = models.TextField(_('description'), blank=True)
    image = models.ImageField(_('image'), upload_to='store/categories/', null=True, blank=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')
    is_active = models.BooleanField(_('is active'), default=True)
    order = models.IntegerField(_('order'), default=0)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    
    class Meta:
        db_table = 'store_categories'
        verbose_name = _('Category')
        verbose_name_plural = _('Categories')
        ordering = ['order', 'name']
    
    def __str__(self):
        return self.name


class Product(models.Model):
    """Products for the store."""
    
    PRODUCT_TYPES = (
        ('physical', 'Physical Product'),
        ('digital', 'Digital Product'),
        ('service', 'Service'),
        ('subscription', 'Subscription'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vendor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='products')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='products')
    
    # Basic info
    name = models.CharField(_('name'), max_length=255)
    slug = models.SlugField(_('slug'), unique=True)
    sku = models.CharField(_('SKU'), max_length=100, unique=True)
    description = models.TextField(_('description'))
    short_description = models.TextField(_('short description'), max_length=500, blank=True)
    product_type = models.CharField(_('product type'), max_length=20, choices=PRODUCT_TYPES, default='physical')
    
    # Pricing
    price = models.DecimalField(_('price'), max_digits=10, decimal_places=2)
    compare_price = models.DecimalField(_('compare price'), max_digits=10, decimal_places=2, null=True, blank=True)
    cost = models.DecimalField(_('cost'), max_digits=10, decimal_places=2, null=True, blank=True)
    tax_rate = models.DecimalField(_('tax rate'), max_digits=5, decimal_places=2, default=Decimal('15.00'))
    
    # Inventory
    track_inventory = models.BooleanField(_('track inventory'), default=True)
    quantity = models.IntegerField(_('quantity'), default=0)
    low_stock_threshold = models.IntegerField(_('low stock threshold'), default=5)
    
    # Shipping
    weight = models.DecimalField(_('weight (kg)'), max_digits=10, decimal_places=3, null=True, blank=True)
    length = models.DecimalField(_('length (cm)'), max_digits=10, decimal_places=2, null=True, blank=True)
    width = models.DecimalField(_('width (cm)'), max_digits=10, decimal_places=2, null=True, blank=True)
    height = models.DecimalField(_('height (cm)'), max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Features
    features = models.JSONField(_('features'), default=list, blank=True)
    specifications = models.JSONField(_('specifications'), default=dict, blank=True)
    
    # SEO
    meta_title = models.CharField(_('meta title'), max_length=255, blank=True)
    meta_description = models.TextField(_('meta description'), blank=True)
    meta_keywords = models.TextField(_('meta keywords'), blank=True)
    
    # Stats
    views_count = models.IntegerField(_('views count'), default=0)
    sales_count = models.IntegerField(_('sales count'), default=0)
    rating = models.DecimalField(_('rating'), max_digits=3, decimal_places=2, default=Decimal('0.00'))
    reviews_count = models.IntegerField(_('reviews count'), default=0)
    
    # Status
    is_active = models.BooleanField(_('is active'), default=True)
    is_featured = models.BooleanField(_('is featured'), default=False)
    is_digital = models.BooleanField(_('is digital'), default=False)
    
    # Timestamps
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    
    class Meta:
        db_table = 'store_products'
        verbose_name = _('Product')
        verbose_name_plural = _('Products')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['sku']),
            models.Index(fields=['is_active', 'is_featured']),
        ]
    
    def __str__(self):
        return self.name
    
    def is_in_stock(self):
        return not self.track_inventory or self.quantity > 0
    
    def is_low_stock(self):
        return self.track_inventory and self.quantity <= self.low_stock_threshold


class ProductImage(models.Model):
    """Product images."""
    
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(_('image'), upload_to='store/products/')
    alt_text = models.CharField(_('alt text'), max_length=255, blank=True)
    is_primary = models.BooleanField(_('is primary'), default=False)
    order = models.IntegerField(_('order'), default=0)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    
    class Meta:
        db_table = 'store_product_images'
        verbose_name = _('Product Image')
        verbose_name_plural = _('Product Images')
        ordering = ['order', 'created_at']


class Cart(models.Model):
    """Shopping cart."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='carts', null=True, blank=True)
    session_key = models.CharField(_('session key'), max_length=255, null=True, blank=True)
    
    # Totals
    subtotal = models.DecimalField(_('subtotal'), max_digits=10, decimal_places=2, default=Decimal('0.00'))
    tax = models.DecimalField(_('tax'), max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total = models.DecimalField(_('total'), max_digits=10, decimal_places=2, default=Decimal('0.00'))
    
    # Timestamps
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    
    class Meta:
        db_table = 'store_carts'
        verbose_name = _('Cart')
        verbose_name_plural = _('Carts')
        ordering = ['-updated_at']
    
    def calculate_totals(self):
        """Calculate cart totals."""
        subtotal = Decimal('0.00')
        tax = Decimal('0.00')
        
        for item in self.items.all():
            subtotal += item.subtotal
            tax += item.tax
        
        self.subtotal = subtotal
        self.tax = tax
        self.total = subtotal + tax
        self.save(update_fields=['subtotal', 'tax', 'total'])


class CartItem(models.Model):
    """Cart items."""
    
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField(_('quantity'), default=1)
    price = models.DecimalField(_('price'), max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(_('subtotal'), max_digits=10, decimal_places=2)
    tax = models.DecimalField(_('tax'), max_digits=10, decimal_places=2, default=Decimal('0.00'))
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    
    class Meta:
        db_table = 'store_cart_items'
        verbose_name = _('Cart Item')
        verbose_name_plural = _('Cart Items')
        unique_together = [['cart', 'product']]
    
    def save(self, *args, **kwargs):
        self.subtotal = self.price * self.quantity
        self.tax = self.subtotal * (self.product.tax_rate / 100)
        super().save(*args, **kwargs)


class Order(models.Model):
    """Customer orders."""
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('processing', 'Processing'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
    )
    
    PAYMENT_STATUS = (
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_number = models.CharField(_('order number'), max_length=50, unique=True)
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='orders')
    
    # Status
    status = models.CharField(_('status'), max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_status = models.CharField(_('payment status'), max_length=20, choices=PAYMENT_STATUS, default='pending')
    
    # Customer info
    customer_email = models.EmailField(_('customer email'))
    customer_phone = models.CharField(_('customer phone'), max_length=20)
    customer_name = models.CharField(_('customer name'), max_length=255)
    
    # Addresses
    billing_address = models.JSONField(_('billing address'), default=dict)
    shipping_address = models.JSONField(_('shipping address'), default=dict)
    
    # Amounts
    subtotal = models.DecimalField(_('subtotal'), max_digits=10, decimal_places=2)
    tax = models.DecimalField(_('tax'), max_digits=10, decimal_places=2)
    shipping = models.DecimalField(_('shipping'), max_digits=10, decimal_places=2, default=Decimal('0.00'))
    discount = models.DecimalField(_('discount'), max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total = models.DecimalField(_('total'), max_digits=10, decimal_places=2)
    
    # Payment
    payment_method = models.CharField(_('payment method'), max_length=50, blank=True)
    transaction_id = models.CharField(_('transaction ID'), max_length=255, blank=True)
    
    # Tracking
    tracking_number = models.CharField(_('tracking number'), max_length=255, blank=True)
    
    # Notes
    customer_notes = models.TextField(_('customer notes'), blank=True)
    admin_notes = models.TextField(_('admin notes'), blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    paid_at = models.DateTimeField(_('paid at'), null=True, blank=True)
    shipped_at = models.DateTimeField(_('shipped at'), null=True, blank=True)
    delivered_at = models.DateTimeField(_('delivered at'), null=True, blank=True)
    
    class Meta:
        db_table = 'store_orders'
        verbose_name = _('Order')
        verbose_name_plural = _('Orders')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['order_number']),
            models.Index(fields=['status', 'payment_status']),
        ]
    
    def __str__(self):
        return f"Order {self.order_number}"


class OrderItem(models.Model):
    """Order items."""
    
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    product_name = models.CharField(_('product name'), max_length=255)
    product_sku = models.CharField(_('product SKU'), max_length=100)
    quantity = models.IntegerField(_('quantity'))
    price = models.DecimalField(_('price'), max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(_('subtotal'), max_digits=10, decimal_places=2)
    tax = models.DecimalField(_('tax'), max_digits=10, decimal_places=2)
    
    class Meta:
        db_table = 'store_order_items'
        verbose_name = _('Order Item')
        verbose_name_plural = _('Order Items')
    
    def save(self, *args, **kwargs):
        self.subtotal = self.price * self.quantity
        super().save(*args, **kwargs)