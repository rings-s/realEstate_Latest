from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Count, Sum, Avg, Q, F
from django.utils import timezone
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from properties.models import Property
from tenants.models import Tenant, Lease, RentPayment, MaintenanceRequest
from auctions.models import Auction, Bid


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def revenue_analytics(request):
    """Get revenue analytics data."""
    # Get date range
    period = request.GET.get('period', '12')  # months
    end_date = timezone.now()
    start_date = end_date - timedelta(days=int(period) * 30)
    
    # Get payments data
    payments = RentPayment.objects.filter(
        lease__landlord=request.user,
        created_at__gte=start_date,
        created_at__lte=end_date
    ).values('created_at__date', 'status').annotate(
        total=Sum('amount_paid'),
        count=Count('id')
    ).order_by('created_at__date')
    
    # Convert to DataFrame for analysis
    df = pd.DataFrame(list(payments))
    
    if not df.empty:
        df['created_at__date'] = pd.to_datetime(df['created_at__date'])
        
        # Group by month
        monthly_revenue = df.groupby(pd.Grouper(key='created_at__date', freq='M')).agg({
            'total': 'sum',
            'count': 'sum'
        }).reset_index()
        
        # Calculate growth rate
        monthly_revenue['growth_rate'] = monthly_revenue['total'].pct_change() * 100
        
        # Forecast next 3 months using simple linear regression
        from sklearn.linear_model import LinearRegression
        
        X = np.arange(len(monthly_revenue)).reshape(-1, 1)
        y = monthly_revenue['total'].values
        
        model = LinearRegression()
        model.fit(X, y)
        
        # Predict next 3 months
        future_X = np.arange(len(monthly_revenue), len(monthly_revenue) + 3).reshape(-1, 1)
        forecast = model.predict(future_X)
        
        return Response({
            'monthly_revenue': monthly_revenue.to_dict('records'),
            'total_revenue': df['total'].sum(),
            'average_monthly': df.groupby(pd.Grouper(key='created_at__date', freq='M'))['total'].sum().mean(),
            'forecast': {
                'next_3_months': forecast.tolist(),
                'trend': 'increasing' if model.coef_[0] > 0 else 'decreasing'
            }
        })
    
    return Response({
        'monthly_revenue': [],
        'total_revenue': 0,
        'average_monthly': 0,
        'forecast': None
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def property_performance(request):
    """Get property performance analytics."""
    properties = Property.objects.filter(owner=request.user).annotate(
        total_revenue=Sum('leases__payments__amount_paid'),
        occupancy_days=Count('leases__id'),
        avg_rent=Avg('leases__monthly_rent')
    )
    
    # Calculate ROI for each property
    property_data = []
    for prop in properties:
        roi = (float(prop.total_revenue or 0) / float(prop.price)) * 100 if prop.price > 0 else 0
        
        property_data.append({
            'id': str(prop.id),
            'title': prop.title,
            'type': prop.property_type,
            'price': float(prop.price),
            'total_revenue': float(prop.total_revenue or 0),
            'roi': round(roi, 2),
            'occupancy_days': prop.occupancy_days,
            'avg_rent': float(prop.avg_rent or 0),
            'location': {
                'city': prop.city,
                'district': prop.district
            }
        })
    
    # Sort by ROI
    property_data.sort(key=lambda x: x['roi'], reverse=True)
    
    # Group by type
    by_type = {}
    for prop in property_data:
        if prop['type'] not in by_type:
            by_type[prop['type']] = {
                'count': 0,
                'total_value': 0,
                'total_revenue': 0,
                'avg_roi': 0
            }
        by_type[prop['type']]['count'] += 1
        by_type[prop['type']]['total_value'] += prop['price']
        by_type[prop['type']]['total_revenue'] += prop['total_revenue']
    
    # Calculate average ROI by type
    for ptype in by_type:
        if by_type[ptype]['total_value'] > 0:
            by_type[ptype]['avg_roi'] = round(
                (by_type[ptype]['total_revenue'] / by_type[ptype]['total_value']) * 100, 2
            )
    
    return Response({
        'properties': property_data[:10],  # Top 10 by ROI
        'by_type': by_type,
        'best_performer': property_data[0] if property_data else None,
        'total_portfolio_value': sum(p['price'] for p in property_data),
        'total_revenue': sum(p['total_revenue'] for p in property_data)
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def tenant_analytics(request):
    """Get tenant analytics."""
    tenants = Tenant.objects.filter(landlord=request.user)
    
    # Payment behavior analysis
    payment_stats = RentPayment.objects.filter(
        tenant__landlord=request.user
    ).values('tenant').annotate(
        total_paid=Sum('amount_paid'),
        on_time_payments=Count('id', filter=Q(status='paid') & Q(paid_at__lte=F('due_date'))),
        late_payments=Count('id', filter=Q(status='late')),
        total_payments=Count('id')
    )
    
    # Convert to DataFrame
    df = pd.DataFrame(list(payment_stats))
    
    if not df.empty:
        df['payment_score'] = (df['on_time_payments'] / df['total_payments'] * 100).round(2)
        
        # Categorize tenants
        def categorize_tenant(score):
            if score >= 90:
                return 'Excellent'
            elif score >= 75:
                return 'Good'
            elif score >= 60:
                return 'Fair'
            else:
                return 'Poor'
        
        df['category'] = df['payment_score'].apply(categorize_tenant)
        
        # Group statistics
        category_stats = df['category'].value_counts().to_dict()
        
        return Response({
            'total_tenants': tenants.count(),
            'active_tenants': tenants.filter(status='active').count(),
            'tenant_categories': category_stats,
            'average_payment_score': df['payment_score'].mean(),
            'total_revenue_by_tenant': df.nlargest(10, 'total_paid')[['tenant', 'total_paid']].to_dict('records'),
            'retention_rate': round(
                (tenants.filter(status='active').count() / tenants.count() * 100) if tenants.count() > 0 else 0, 2
            )
        })
    
    return Response({
        'total_tenants': tenants.count(),
        'active_tenants': tenants.filter(status='active').count(),
        'tenant_categories': {},
        'average_payment_score': 0,
        'total_revenue_by_tenant': [],
        'retention_rate': 0
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def maintenance_analytics(request):
    """Get maintenance analytics."""
    maintenance = MaintenanceRequest.objects.filter(property__owner=request.user)
    
    # Group by category
    by_category = maintenance.values('category').annotate(
        count=Count('id'),
        avg_cost=Avg('actual_cost'),
        total_cost=Sum('actual_cost')
    )
    
    # Group by priority
    by_priority = maintenance.values('priority').annotate(
        count=Count('id'),
        avg_completion_time=Avg(
            F('completed_date') - F('created_at'),
            output_field=models.DurationField()
        )
    )
    
    # Monthly trend
    last_6_months = timezone.now() - timedelta(days=180)
    monthly_trend = maintenance.filter(
        created_at__gte=last_6_months
    ).extra(
        select={'month': "date_trunc('month', created_at)"}
    ).values('month').annotate(
        count=Count('id'),
        total_cost=Sum('actual_cost')
    ).order_by('month')
    
    # Calculate average resolution time
    completed = maintenance.filter(status='completed', completed_date__isnull=False)
    if completed.exists():
        avg_resolution = completed.aggregate(
            avg_time=Avg(F('completed_date') - F('created_at'))
        )['avg_time']
        avg_resolution_days = avg_resolution.days if avg_resolution else 0
    else:
        avg_resolution_days = 0
    
    return Response({
        'total_requests': maintenance.count(),
        'pending_requests': maintenance.filter(status='pending').count(),
        'completed_requests': maintenance.filter(status='completed').count(),
        'by_category': list(by_category),
        'by_priority': list(by_priority),
        'monthly_trend': list(monthly_trend),
        'average_resolution_days': avg_resolution_days,
        'total_maintenance_cost': maintenance.aggregate(Sum('actual_cost'))['actual_cost__sum'] or 0
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def market_insights(request):
    """Get market insights and trends."""
    # This would typically connect to external data sources
    # For now, we'll analyze internal data
    
    # Price trends by area
    properties = Property.objects.filter(is_published=True)
    
    price_by_city = properties.values('city').annotate(
        avg_price=Avg('price'),
        avg_price_per_sqm=Avg('price_per_sqm'),
        count=Count('id')
    ).order_by('-avg_price')[:10]
    
    # Property type distribution
    type_distribution = properties.values('property_type').annotate(
        count=Count('id'),
        percentage=Count('id') * 100.0 / properties.count()
    )
    
    # Price ranges
    price_ranges = {
        '0-500K': properties.filter(price__lt=500000).count(),
        '500K-1M': properties.filter(price__gte=500000, price__lt=1000000).count(),
        '1M-2M': properties.filter(price__gte=1000000, price__lt=2000000).count(),
        '2M-5M': properties.filter(price__gte=2000000, price__lt=5000000).count(),
        '5M+': properties.filter(price__gte=5000000).count(),
    }
    
    # Demand indicators (based on views)
    high_demand = properties.order_by('-views_count')[:10].values(
        'title', 'city', 'property_type', 'price', 'views_count'
    )
    
    return Response({
        'price_by_city': list(price_by_city),
        'type_distribution': list(type_distribution),
        'price_ranges': price_ranges,
        'high_demand_properties': list(high_demand),
        'market_summary': {
            'total_properties': properties.count(),
            'average_price': properties.aggregate(Avg('price'))['price__avg'],
            'average_price_per_sqm': properties.aggregate(Avg('price_per_sqm'))['price_per_sqm__avg'],
            'most_expensive_city': price_by_city[0] if price_by_city else None
        }
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def portfolio_summary(request):
    """Get portfolio summary dashboard."""
    user = request.user
    
    # Properties
    properties = Property.objects.filter(owner=user)
    total_property_value = properties.aggregate(Sum('price'))['price__sum'] or 0
    
    # Tenants & Leases
    active_leases = Lease.objects.filter(landlord=user, status='active')
    monthly_rental_income = active_leases.aggregate(Sum('monthly_rent'))['monthly_rent__sum'] or 0
    
    # Payments
    current_month = timezone.now().month
    current_year = timezone.now().year
    
    collected_this_month = RentPayment.objects.filter(
        lease__landlord=user,
        status='paid',
        paid_at__month=current_month,
        paid_at__year=current_year
    ).aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0
    
    pending_this_month = RentPayment.objects.filter(
        lease__landlord=user,
        status='pending',
        due_date__month=current_month,
        due_date__year=current_year
    ).aggregate(Sum('amount_due'))['amount_due__sum'] or 0
    
    # Calculate metrics
    annual_rental_income = monthly_rental_income * 12
    gross_yield = (annual_rental_income / total_property_value * 100) if total_property_value > 0 else 0
    
    # Occupancy
    total_units = properties.count()
    occupied_units = active_leases.values('property').distinct().count()
    occupancy_rate = (occupied_units / total_units * 100) if total_units > 0 else 0
    
    return Response({
        'portfolio_value': total_property_value,
        'monthly_rental_income': monthly_rental_income,
        'annual_rental_income': annual_rental_income,
        'gross_yield': round(gross_yield, 2),
        'occupancy_rate': round(occupancy_rate, 2),
        'total_properties': total_units,
        'occupied_properties': occupied_units,
        'vacant_properties': total_units - occupied_units,
        'active_tenants': Tenant.objects.filter(landlord=user, status='active').count(),
        'collected_this_month': collected_this_month,
        'pending_this_month': pending_this_month,
        'collection_rate': round(
            (collected_this_month / (collected_this_month + pending_this_month) * 100)
            if (collected_this_month + pending_this_month) > 0 else 0, 2
        )
    })