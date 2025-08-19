from django.contrib import admin
from .models import Category, Product, ProductImage, Cart, CartItem, Order, OrderItem

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'parent', 'is_active', 'order']
    prepopulated_fields = {'slug': ('name',)}
    list_filter = ['is_active']
    search_fields = ['name']

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'sku', 'price', 'quantity', 'is_active', 'vendor']
    list_filter = ['is_active', 'is_featured', 'product_type', 'category']
    search_fields = ['name', 'sku', 'description']
    prepopulated_fields = {'slug': ('name',)}

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['order_number', 'customer', 'status', 'payment_status', 'total', 'created_at']
    list_filter = ['status', 'payment_status']
    search_fields = ['order_number', 'customer__email']
    readonly_fields = ['order_number']