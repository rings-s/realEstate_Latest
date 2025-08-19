from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404
from django.db.models import Q, Count, Max, Min
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
from .models import Auction, Bid, AuctionDeposit, AuctionWatchlist, BidHistory
from .serializers import (
    AuctionSerializer, AuctionDetailSerializer, AuctionListSerializer,
    BidSerializer, AuctionDepositSerializer, AuctionWatchlistSerializer
)


class AuctionListAPIView(generics.ListAPIView):
    """List all auctions."""
    serializer_class = AuctionListSerializer
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        queryset = Auction.objects.select_related('property', 'seller')
        
        # Filters
        status_filter = self.request.GET.get('status')
        property_type = self.request.GET.get('property_type')
        city = self.request.GET.get('city')
        min_price = self.request.GET.get('min_price')
        max_price = self.request.GET.get('max_price')
        
        if status_filter:
            if status_filter == 'live':
                now = timezone.now()
                queryset = queryset.filter(
                    status='active',
                    start_time__lte=now,
                    end_time__gte=now
                )
            else:
                queryset = queryset.filter(status=status_filter)
        
        if property_type:
            queryset = queryset.filter(property__property_type=property_type)
        
        if city:
            queryset = queryset.filter(property__city__icontains=city)
        
        if min_price:
            queryset = queryset.filter(
                Q(current_bid__gte=min_price) | 
                Q(current_bid__isnull=True, starting_price__gte=min_price)
            )
        
        if max_price:
            queryset = queryset.filter(
                Q(current_bid__lte=max_price) | 
                Q(current_bid__isnull=True, starting_price__lte=max_price)
            )
        
        # Sorting
        sort_by = self.request.GET.get('sort', '-created_at')
        if sort_by == 'ending_soon':
            queryset = queryset.filter(status='active').order_by('end_time')
        elif sort_by == 'most_bids':
            queryset = queryset.order_by('-total_bids')
        elif sort_by == 'price_low':
            queryset = queryset.order_by('current_bid', 'starting_price')
        elif sort_by == 'price_high':
            queryset = queryset.order_by('-current_bid', '-starting_price')
        else:
            queryset = queryset.order_by(sort_by)
        
        return queryset


class AuctionCreateAPIView(generics.CreateAPIView):
    """Create a new auction."""
    serializer_class = AuctionSerializer
    permission_classes = [IsAuthenticated]
    
    def perform_create(self, serializer):
        property_obj = serializer.validated_data['property']
        
        # Verify ownership
        if property_obj.owner != self.request.user:
            raise PermissionError("You can only auction your own properties")
        
        # Update property status
        property_obj.status = 'auction'
        property_obj.purpose = 'auction'
        property_obj.save(update_fields=['status', 'purpose'])
        
        serializer.save(seller=self.request.user)


class AuctionDetailAPIView(generics.RetrieveAPIView):
    """Get auction details."""
    queryset = Auction.objects.select_related('property', 'seller', 'winner')
    serializer_class = AuctionDetailSerializer
    permission_classes = [AllowAny]
    
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        
        # Increment view count
        instance.views_count += 1
        instance.save(update_fields=['views_count'])
        
        # Check and update auction status
        if instance.status == 'active':
            now = timezone.now()
            if now > (instance.extended_time or instance.end_time):
                instance.status = 'ended'
                instance.save(update_fields=['status'])
        
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class AuctionUpdateAPIView(generics.UpdateAPIView):
    """Update auction (seller only, limited fields)."""
    queryset = Auction.objects.all()
    serializer_class = AuctionSerializer
    permission_classes = [IsAuthenticated]
    
    def get_object(self):
        obj = super().get_object()
        if obj.seller != self.request.user:
            raise PermissionError("You can only update your own auctions")
        if obj.status not in ['draft', 'scheduled']:
            raise PermissionError("Cannot update active or ended auctions")
        return obj


class PlaceBidAPIView(APIView):
    """Place a bid on an auction."""
    permission_classes = [IsAuthenticated]
    
    @transaction.atomic
    def post(self, request, auction_id):
        auction = get_object_or_404(Auction, id=auction_id)
        
        # Validate auction is active
        if not auction.is_active():
            return Response(
                {'error': 'Auction is not active'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if user can bid
        if not auction.can_bid(request.user):
            return Response(
                {'error': 'You cannot bid on this auction'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check deposit if required
        if auction.require_deposit:
            deposit_exists = AuctionDeposit.objects.filter(
                auction=auction,
                user=request.user,
                status='confirmed'
            ).exists()
            
            if not deposit_exists:
                return Response(
                    {'error': 'Deposit required to bid'},
                    status=status.HTTP_402_PAYMENT_REQUIRED
                )
        
        bid_amount = request.data.get('amount')
        max_amount = request.data.get('max_amount')  # For proxy bidding
        
        if not bid_amount:
            return Response(
                {'error': 'Bid amount is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        bid_amount = float(bid_amount)
        
        # Validate bid amount
        min_bid = float(auction.current_bid or auction.starting_price)
        if auction.current_bid:
            min_bid += float(auction.bid_increment)
        
        if bid_amount < min_bid:
            return Response(
                {'error': f'Minimum bid is {min_bid}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create bid
        bid = Bid.objects.create(
            auction=auction,
            bidder=request.user,
            amount=bid_amount,
            max_amount=max_amount if auction.allow_proxy_bidding else None,
            is_auto_bid=False
        )
        
        # Create bid history
        BidHistory.objects.create(
            bid=bid,
            bid_source='web',
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        # Update previous winning bid
        Bid.objects.filter(auction=auction, is_winning=True).update(is_winning=False)
        
        # Mark new bid as winning
        bid.is_winning = True
        bid.save(update_fields=['is_winning'])
        
        # Update auction
        auction.current_bid = bid_amount
        auction.total_bids += 1
        
        # Update unique bidders count
        unique_bidders = Bid.objects.filter(auction=auction).values('bidder').distinct().count()
        auction.unique_bidders = unique_bidders
        
        # Auto-extend if enabled and bid placed near end
        if auction.auto_extend:
            time_remaining = (auction.extended_time or auction.end_time) - timezone.now()
            if time_remaining < timedelta(minutes=auction.extend_minutes):
                auction.extended_time = timezone.now() + timedelta(minutes=auction.extend_minutes)
        
        auction.save()
        
        # Handle proxy bidding for other users
        if auction.allow_proxy_bidding:
            self._process_proxy_bids(auction, bid)
        
        # Send notifications to watchers
        self._notify_watchers(auction, bid)
        
        serializer = BidSerializer(bid)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    def _process_proxy_bids(self, auction, new_bid):
        """Process automatic proxy bids."""
        # Get all proxy bids except the new bidder's
        proxy_bids = Bid.objects.filter(
            auction=auction,
            max_amount__isnull=False,
            max_amount__gt=new_bid.amount
        ).exclude(bidder=new_bid.bidder).order_by('-max_amount')
        
        if proxy_bids.exists():
            highest_proxy = proxy_bids.first()
            
            # Place auto-bid
            auto_bid_amount = min(
                float(new_bid.amount) + float(auction.bid_increment),
                float(highest_proxy.max_amount)
            )
            
            auto_bid = Bid.objects.create(
                auction=auction,
                bidder=highest_proxy.bidder,
                amount=auto_bid_amount,
                max_amount=highest_proxy.max_amount,
                is_auto_bid=True
            )
            
            # Update auction
            auction.current_bid = auto_bid_amount
            auction.total_bids += 1
            auction.save()
            
            # Update winning status
            new_bid.is_winning = False
            new_bid.save(update_fields=['is_winning'])
            auto_bid.is_winning = True
            auto_bid.save(update_fields=['is_winning'])
    
    def _notify_watchers(self, auction, bid):
        """Send notifications to auction watchers."""
        from notifications.utils import create_notification
        
        watchers = AuctionWatchlist.objects.filter(
            auction=auction,
            notify_on_new_bid=True
        ).exclude(user=bid.bidder)
        
        for watcher in watchers:
            create_notification(
                user=watcher.user,
                title='New bid on watched auction',
                message=f'New bid of {bid.amount} on {auction.title}',
                notification_type='auction',
                metadata={'auction_id': str(auction.id), 'bid_id': str(bid.id)}
            )


class MyBidsListAPIView(generics.ListAPIView):
    """List user's bids."""
    serializer_class = BidSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = Bid.objects.filter(
            bidder=self.request.user
        ).select_related('auction', 'auction__property')
        
        # Filter by status
        status_filter = self.request.GET.get('status')
        if status_filter == 'winning':
            queryset = queryset.filter(is_winning=True)
        elif status_filter == 'outbid':
            queryset = queryset.filter(is_winning=False)
        
        return queryset.order_by('-created_at')


class AuctionDepositCreateAPIView(generics.CreateAPIView):
    """Create auction deposit."""
    serializer_class = AuctionDepositSerializer
    permission_classes = [IsAuthenticated]
    
    def perform_create(self, serializer):
        auction = serializer.validated_data['auction']
        
        # Check if deposit already exists
        existing = AuctionDeposit.objects.filter(
            auction=auction,
            user=self.request.user
        ).first()
        
        if existing and existing.status == 'confirmed':
            raise ValueError("Deposit already confirmed for this auction")
        
        serializer.save(
            user=self.request.user,
            amount=auction.deposit_amount
        )


class AuctionWatchlistToggleAPIView(APIView):
    """Toggle auction watchlist status."""
    permission_classes = [IsAuthenticated]
    
    def post(self, request, auction_id):
        auction = get_object_or_404(Auction, id=auction_id)
        
        watchlist, created = AuctionWatchlist.objects.get_or_create(
            user=request.user,
            auction=auction,
            defaults={
                'notify_on_new_bid': request.data.get('notify_on_new_bid', True),
                'notify_before_end': request.data.get('notify_before_end', True),
                'notify_minutes_before': request.data.get('notify_minutes_before', 60)
            }
        )
        
        if not created:
            watchlist.delete()
            return Response({'watching': False, 'message': 'Removed from watchlist'})
        
        return Response({'watching': True, 'message': 'Added to watchlist'})


class MyWatchlistAPIView(generics.ListAPIView):
    """List user's watched auctions."""
    serializer_class = AuctionWatchlistSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return AuctionWatchlist.objects.filter(
            user=self.request.user
        ).select_related('auction', 'auction__property').order_by('-created_at')


class AuctionStatisticsAPIView(APIView):
    """Get auction statistics."""
    permission_classes = [AllowAny]
    
    def get(self, request):
        total_auctions = Auction.objects.count()
        active_auctions = Auction.objects.filter(status='active').count()
        
        # Get top auctions by bids
        top_auctions = Auction.objects.filter(
            status='active'
        ).order_by('-total_bids')[:5].values(
            'id', 'title', 'total_bids', 'current_bid', 'end_time'
        )
        
        # Get ending soon
        ending_soon = Auction.objects.filter(
            status='active',
            end_time__lte=timezone.now() + timedelta(hours=24)
        ).order_by('end_time')[:5].values(
            'id', 'title', 'current_bid', 'end_time'
        )
        
        # Price statistics
        price_stats = Auction.objects.filter(status='ended').aggregate(
            avg_winning_bid=models.Avg('winning_bid'),
            max_winning_bid=models.Max('winning_bid'),
            min_winning_bid=models.Min('winning_bid')
        )
        
        return Response({
            'total_auctions': total_auctions,
            'active_auctions': active_auctions,
            'top_auctions': list(top_auctions),
            'ending_soon': list(ending_soon),
            'price_statistics': price_stats
        })