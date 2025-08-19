from rest_framework import serializers
from .models import Auction, Bid, AuctionDeposit, AuctionWatchlist, BidHistory
from properties.serializers import PropertyListSerializer


class AuctionListSerializer(serializers.ModelSerializer):
    property = PropertyListSerializer(read_only=True)
    seller_name = serializers.CharField(source='seller.get_full_name', read_only=True)
    time_remaining = serializers.SerializerMethodField()
    
    class Meta:
        model = Auction
        fields = [
            'id', 'property', 'seller_name', 'title', 'status', 'auction_number',
            'starting_price', 'current_bid', 'currency', 'start_time', 'end_time',
            'total_bids', 'unique_bidders', 'time_remaining'
        ]
    
    def get_time_remaining(self, obj):
        from django.utils import timezone
        if obj.status == 'active':
            remaining = (obj.extended_time or obj.end_time) - timezone.now()
            if remaining.total_seconds() > 0:
                return remaining.total_seconds()
        return None


class AuctionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Auction
        fields = '__all__'
        read_only_fields = [
            'id', 'auction_number', 'current_bid', 'winner', 'winning_bid',
            'total_bids', 'unique_bidders', 'views_count', 'created_at', 'updated_at'
        ]


class AuctionDetailSerializer(AuctionSerializer):
    property = PropertyListSerializer(read_only=True)
    seller = serializers.StringRelatedField()
    winner = serializers.StringRelatedField()
    recent_bids = serializers.SerializerMethodField()
    user_has_deposit = serializers.SerializerMethodField()
    user_is_watching = serializers.SerializerMethodField()
    
    class Meta(AuctionSerializer.Meta):
        fields = AuctionSerializer.Meta.fields
    
    def get_recent_bids(self, obj):
        recent = obj.bids.filter(is_retracted=False).order_by('-created_at')[:10]
        return BidSerializer(recent, many=True).data
    
    def get_user_has_deposit(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return AuctionDeposit.objects.filter(
                auction=obj,
                user=request.user,
                status='confirmed'
            ).exists()
        return False
    
    def get_user_is_watching(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return AuctionWatchlist.objects.filter(
                auction=obj,
                user=request.user
            ).exists()
        return False


class BidSerializer(serializers.ModelSerializer):
    bidder_name = serializers.CharField(source='bidder.get_full_name', read_only=True)
    auction_title = serializers.CharField(source='auction.title', read_only=True)
    
    class Meta:
        model = Bid
        fields = [
            'id', 'auction', 'auction_title', 'bidder', 'bidder_name',
            'amount', 'max_amount', 'is_auto_bid', 'is_winning',
            'is_retracted', 'created_at'
        ]
        read_only_fields = ['id', 'bidder', 'is_winning', 'created_at']


class AuctionDepositSerializer(serializers.ModelSerializer):
    auction_title = serializers.CharField(source='auction.title', read_only=True)
    
    class Meta:
        model = AuctionDeposit
        fields = [
            'id', 'auction', 'auction_title', 'amount', 'status',
            'stripe_payment_intent_id', 'created_at', 'confirmed_at'
        ]
        read_only_fields = ['id', 'amount', 'created_at']


class AuctionWatchlistSerializer(serializers.ModelSerializer):
    auction = AuctionListSerializer(read_only=True)
    
    class Meta:
        model = AuctionWatchlist
        fields = [
            'id', 'auction', 'notify_on_new_bid', 'notify_before_end',
            'notify_minutes_before', 'enable_auto_bid', 'max_auto_bid', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class BidHistorySerializer(serializers.ModelSerializer):
    bid = BidSerializer(read_only=True)
    
    class Meta:
        model = BidHistory
        fields = '__all__'