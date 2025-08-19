from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.utils import timezone
import uuid


class Auction(models.Model):
    """Auction model for property auctions."""
    
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('active', 'Active'),
        ('ended', 'Ended'),
        ('cancelled', 'Cancelled'),
        ('sold', 'Sold'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    property = models.ForeignKey('properties.Property', on_delete=models.CASCADE, related_name='auctions')
    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='auctions_as_seller')
    
    title = models.CharField(_('title'), max_length=255)
    description = models.TextField(_('description'))
    status = models.CharField(_('status'), max_length=20, choices=STATUS_CHOICES, default='draft')
    auction_number = models.CharField(_('auction number'), max_length=50, unique=True)
    
    starting_price = models.DecimalField(_('starting price'), max_digits=12, decimal_places=2)
    reserve_price = models.DecimalField(_('reserve price'), max_digits=12, decimal_places=2, null=True, blank=True)
    current_bid = models.DecimalField(_('current bid'), max_digits=12, decimal_places=2, null=True, blank=True)
    bid_increment = models.DecimalField(_('bid increment'), max_digits=10, decimal_places=2, default=1000)
    currency = models.CharField(_('currency'), max_length=3, default='SAR')
    
    start_time = models.DateTimeField(_('start time'))
    end_time = models.DateTimeField(_('end time'))
    extended_time = models.DateTimeField(_('extended time'), null=True, blank=True)
    
    auto_extend = models.BooleanField(_('auto extend'), default=True)
    extend_minutes = models.IntegerField(_('extend minutes'), default=5)
    allow_proxy_bidding = models.BooleanField(_('allow proxy bidding'), default=True)
    require_deposit = models.BooleanField(_('require deposit'), default=True)
    deposit_amount = models.DecimalField(_('deposit amount'), max_digits=10, decimal_places=2, null=True, blank=True)
    
    winner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='won_auctions')
    winning_bid = models.DecimalField(_('winning bid'), max_digits=12, decimal_places=2, null=True, blank=True)
    
    total_bids = models.IntegerField(_('total bids'), default=0)
    unique_bidders = models.IntegerField(_('unique bidders'), default=0)
    views_count = models.IntegerField(_('views count'), default=0)
    
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    
    class Meta:
        db_table = 'auctions'
        verbose_name = _('Auction')
        verbose_name_plural = _('Auctions')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'start_time', 'end_time']),
            models.Index(fields=['auction_number']),
            models.Index(fields=['-created_at']),
        ]
    
    def save(self, *args, **kwargs):
        if not self.auction_number:
            self.auction_number = f"AUC-{uuid.uuid4().hex[:8].upper()}"
        
        # Set deposit amount if not specified
        if self.require_deposit and not self.deposit_amount:
            self.deposit_amount = self.starting_price * 0.05  # 5% of starting price
        
        super().save(*args, **kwargs)
    
    def is_active(self):
        """Check if auction is currently active."""
        now = timezone.now()
        return self.status == 'active' and self.start_time <= now <= (self.extended_time or self.end_time)
    
    def can_bid(self, user):
        """Check if a user can bid on this auction."""
        return self.is_active() and user != self.seller
    
    def __str__(self):
        return f"{self.title} - {self.auction_number}"


class Bid(models.Model):
    """Bid model for auction bidding."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    auction = models.ForeignKey(Auction, on_delete=models.CASCADE, related_name='bids')
    bidder = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bids')
    
    amount = models.DecimalField(_('amount'), max_digits=12, decimal_places=2)
    max_amount = models.DecimalField(_('max amount'), max_digits=12, decimal_places=2, null=True, blank=True)
    is_auto_bid = models.BooleanField(_('is auto bid'), default=False)
    
    is_winning = models.BooleanField(_('is winning'), default=False)
    is_retracted = models.BooleanField(_('is retracted'), default=False)
    
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    
    class Meta:
        db_table = 'bids'
        verbose_name = _('Bid')
        verbose_name_plural = _('Bids')
        ordering = ['-amount', '-created_at']
        indexes = [
            models.Index(fields=['auction', '-amount']),
            models.Index(fields=['bidder', 'auction']),
            models.Index(fields=['-created_at']),
        ]
    
    def __str__(self):
        return f"{self.bidder.email} - {self.amount} on {self.auction.title}"


class AuctionDeposit(models.Model):
    """Deposits for auction participation."""
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('refunded', 'Refunded'),
        ('forfeited', 'Forfeited'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    auction = models.ForeignKey(Auction, on_delete=models.CASCADE, related_name='deposits')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='auction_deposits')
    
    amount = models.DecimalField(_('amount'), max_digits=10, decimal_places=2)
    status = models.CharField(_('status'), max_length=20, choices=STATUS_CHOICES, default='pending')
    stripe_payment_intent_id = models.CharField(_('stripe payment intent ID'), max_length=255, blank=True)
    
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    confirmed_at = models.DateTimeField(_('confirmed at'), null=True, blank=True)
    refunded_at = models.DateTimeField(_('refunded at'), null=True, blank=True)
    
    class Meta:
        db_table = 'auction_deposits'
        verbose_name = _('Auction Deposit')
        verbose_name_plural = _('Auction Deposits')
        unique_together = [['auction', 'user']]
        indexes = [
            models.Index(fields=['auction', 'user', 'status']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.amount} for {self.auction.title}"


class AuctionWatchlist(models.Model):
    """Users can watch auctions for notifications."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='auction_watchlist')
    auction = models.ForeignKey(Auction, on_delete=models.CASCADE, related_name='watchers')
    
    notify_on_new_bid = models.BooleanField(_('notify on new bid'), default=True)
    notify_before_end = models.BooleanField(_('notify before end'), default=True)
    notify_minutes_before = models.IntegerField(_('notify minutes before end'), default=60)
    
    enable_auto_bid = models.BooleanField(_('enable auto bid'), default=False)
    max_auto_bid = models.DecimalField(_('max auto bid'), max_digits=12, decimal_places=2, null=True, blank=True)
    
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    
    class Meta:
        db_table = 'auction_watchlist'
        verbose_name = _('Auction Watchlist')
        verbose_name_plural = _('Auction Watchlist')
        unique_together = [['user', 'auction']]
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['auction', 'notify_on_new_bid']),
        ]
    
    def __str__(self):
        return f"{self.user.email} watching {self.auction.title}"


class BidHistory(models.Model):
    """Detailed bid history for analytics."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    bid = models.OneToOneField(Bid, on_delete=models.CASCADE, related_name='history')
    
    bid_source = models.CharField(_('bid source'), max_length=20, 
                                 choices=[('web', 'Web'), ('mobile', 'Mobile'), ('auto', 'Auto-bid')])
    ip_address = models.GenericIPAddressField(_('IP address'), null=True, blank=True)
    user_agent = models.TextField(_('user agent'), blank=True)
    
    outbid_count = models.IntegerField(_('times outbid'), default=0)
    time_as_winning = models.IntegerField(_('seconds as winning bid'), default=0)
    
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    
    class Meta:
        db_table = 'bid_history'
        verbose_name = _('Bid History')
        verbose_name_plural = _('Bid Histories')