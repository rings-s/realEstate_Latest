from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.contrib.gis.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
import uuid


class UserManager(BaseUserManager):
    """Custom user manager for User model."""
    
    def create_user(self, email, username, password=None, **extra_fields):
        """Create and save a regular user."""
        if not email:
            raise ValueError(_('Email address is required'))
        if not username:
            raise ValueError(_('Username is required'))
        
        email = self.normalize_email(email)
        user = self.model(
            email=email,
            username=username,
            **extra_fields
        )
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, username, password=None, **extra_fields):
        """Create and save a superuser."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_verified', True)
        extra_fields.setdefault('email_verified', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))
        
        return self.create_user(email, username, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Custom User model for the real estate platform."""
    
    USER_TYPE_CHOICES = (
        ('customer', 'Customer'),
        ('company', 'Real Estate Company'),
        ('tenant', 'Tenant'),
        ('landlord', 'Landlord'),
        ('admin', 'Administrator'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(_('email address'), unique=True, db_index=True)
    username = models.CharField(_('username'), max_length=150, unique=True, db_index=True)
    first_name = models.CharField(_('first name'), max_length=150)
    last_name = models.CharField(_('last name'), max_length=150)
    user_type = models.CharField(_('user type'), max_length=20, choices=USER_TYPE_CHOICES, default='customer')
    
    # Profile fields
    phone_number = models.CharField(_('phone number'), max_length=20, blank=True)
    national_id = models.CharField(_('national ID'), max_length=20, blank=True, unique=True, null=True)
    address = models.TextField(_('address'), blank=True)
    city = models.CharField(_('city'), max_length=100, blank=True)
    country = models.CharField(_('country'), max_length=100, default='Saudi Arabia')
    profile_image = models.ImageField(_('profile image'), upload_to='profiles/', blank=True, null=True)
    bio = models.TextField(_('bio'), blank=True)
    
    # Verification fields
    is_active = models.BooleanField(_('active'), default=True)
    is_staff = models.BooleanField(_('staff status'), default=False)
    is_verified = models.BooleanField(_('verified'), default=False)
    email_verified = models.BooleanField(_('email verified'), default=False)
    phone_verified = models.BooleanField(_('phone verified'), default=False)
    
    # Company specific fields
    company_name = models.CharField(_('company name'), max_length=255, blank=True)
    company_registration = models.CharField(_('company registration'), max_length=100, blank=True)
    company_verified = models.BooleanField(_('company verified'), default=False)
    company_logo = models.ImageField(_('company logo'), upload_to='companies/', blank=True, null=True)
    
    # Subscription fields (for SaaS)
    stripe_customer_id = models.CharField(_('stripe customer ID'), max_length=255, blank=True)
    subscription_status = models.CharField(_('subscription status'), max_length=50, default='free')
    subscription_end_date = models.DateTimeField(_('subscription end date'), null=True, blank=True)
    
    # Timestamps
    date_joined = models.DateTimeField(_('date joined'), default=timezone.now)
    last_login = models.DateTimeField(_('last login'), null=True, blank=True)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    
    # Settings
    notification_preferences = models.JSONField(_('notification preferences'), default=dict, blank=True)
    language = models.CharField(_('language'), max_length=10, default='ar')
    timezone = models.CharField(_('timezone'), max_length=50, default='Asia/Riyadh')
    
    objects = UserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']
    
    class Meta:
        db_table = 'users'
        verbose_name = _('User')
        verbose_name_plural = _('Users')
        indexes = [
            models.Index(fields=['email', 'user_type']),
            models.Index(fields=['created_at']),
            models.Index(fields=['stripe_customer_id']),
        ]
    
    def get_full_name(self):
        """Return the full name of the user."""
        return f"{self.first_name} {self.last_name}".strip()
    
    def get_short_name(self):
        """Return the short name of the user."""
        return self.first_name
    
    def has_active_subscription(self):
        """Check if user has an active subscription."""
        if self.subscription_end_date:
            return self.subscription_end_date > timezone.now()
        return self.subscription_status == 'free'
    
    def __str__(self):
        return self.email


class EmailVerificationToken(models.Model):
    """Model for email verification tokens."""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='email_tokens')
    token = models.CharField(_('token'), max_length=255, unique=True, db_index=True)
    is_used = models.BooleanField(_('is used'), default=False)
    expires_at = models.DateTimeField(_('expires at'))
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    
    class Meta:
        db_table = 'email_verification_tokens'
        verbose_name = _('Email Verification Token')
        verbose_name_plural = _('Email Verification Tokens')
        indexes = [
            models.Index(fields=['token', 'is_used']),
            models.Index(fields=['expires_at']),
        ]
    
    def is_valid(self):
        """Check if token is valid."""
        return not self.is_used and self.expires_at > timezone.now()


class PasswordResetToken(models.Model):
    """Model for password reset tokens."""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='password_tokens')
    token = models.CharField(_('token'), max_length=255, unique=True, db_index=True)
    is_used = models.BooleanField(_('is used'), default=False)
    expires_at = models.DateTimeField(_('expires at'))
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    
    class Meta:
        db_table = 'password_reset_tokens'
        verbose_name = _('Password Reset Token')
        verbose_name_plural = _('Password Reset Tokens')
        indexes = [
            models.Index(fields=['token', 'is_used']),
            models.Index(fields=['expires_at']),
        ]
    
    def is_valid(self):
        """Check if token is valid."""
        return not self.is_used and self.expires_at > timezone.now()