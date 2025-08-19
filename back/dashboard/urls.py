from django.urls import path
from . import analytics

urlpatterns = [
    path('revenue/', analytics.revenue_analytics, name='revenue_analytics'),
    path('properties/', analytics.property_performance, name='property_performance'),
    path('tenants/', analytics.tenant_analytics, name='tenant_analytics'),
    path('maintenance/', analytics.maintenance_analytics, name='maintenance_analytics'),
    path('market/', analytics.market_insights, name='market_insights'),
    path('portfolio/', analytics.portfolio_summary, name='portfolio_summary'),
]