from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django.contrib.auth import login, logout
from django.db import transaction
from django.shortcuts import get_object_or_404
from .models import User, EmailVerificationToken, PasswordResetToken
from .serializers import (
    UserSerializer, RegisterSerializer, LoginSerializer,
    TokenSerializer, GoogleAuthSerializer,
    PasswordResetRequestSerializer, PasswordResetSerializer
)
from .utils import generate_access_token, generate_refresh_token
import secrets
from datetime import timedelta
from django.utils import timezone


@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    """Register a new user."""
    serializer = RegisterSerializer(data=request.data)
    if serializer.is_valid():
        with transaction.atomic():
            user = serializer.save()
            access_token = generate_access_token(user)
            refresh_token = generate_refresh_token(user)
            
            return Response({
                'user': UserSerializer(user).data,
                'access_token': access_token,
                'refresh_token': refresh_token
            }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    """Login user and return tokens."""
    serializer = LoginSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.validated_data['user']
        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])
        
        access_token = generate_access_token(user)
        refresh_token = generate_refresh_token(user)
        
        return Response({
            'user': UserSerializer(user).data,
            'access_token': access_token,
            'refresh_token': refresh_token
        })
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def google_auth(request):
    """Authenticate with Google OAuth."""
    serializer = GoogleAuthSerializer(data=request.data)
    if serializer.is_valid():
        idinfo = serializer.validated_data['token']
        email = idinfo['email']
        
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                'username': email.split('@')[0],
                'first_name': idinfo.get('given_name', ''),
                'last_name': idinfo.get('family_name', ''),
                'email_verified': True,
                'is_verified': True
            }
        )
        
        if created:
            user.set_unusable_password()
            user.save()
        
        access_token = generate_access_token(user)
        refresh_token = generate_refresh_token(user)
        
        return Response({
            'user': UserSerializer(user).data,
            'access_token': access_token,
            'refresh_token': refresh_token,
            'is_new_user': created
        })
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def refresh_token(request):
    """Refresh access token."""
    refresh_token = request.data.get('refresh_token')
    if not refresh_token:
        return Response({'error': 'Refresh token required'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        import jwt
        from django.conf import settings
        
        payload = jwt.decode(
            refresh_token,
            settings.JWT_AUTH['JWT_SECRET_KEY'],
            algorithms=[settings.JWT_AUTH['JWT_ALGORITHM']]
        )
        
        if payload.get('type') != 'refresh':
            raise jwt.InvalidTokenError('Not a refresh token')
        
        user = User.objects.get(id=payload['user_id'])
        access_token = generate_access_token(user)
        
        return Response({'access_token': access_token})
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, User.DoesNotExist) as e:
        return Response({'error': str(e)}, status=status.HTTP_401_UNAUTHORIZED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """Logout user."""
    # In JWT, we don't need to do anything server-side
    # The client should discard the tokens
    return Response({'message': 'Logged out successfully'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def profile(request):
    """Get current user profile."""
    return Response(UserSerializer(request.user).data)


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def update_profile(request):
    """Update user profile."""
    serializer = UserSerializer(request.user, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def password_reset_request(request):
    """Request password reset."""
    serializer = PasswordResetRequestSerializer(data=request.data)
    if serializer.is_valid():
        email = serializer.validated_data['email']
        try:
            user = User.objects.get(email=email)
            token = secrets.token_urlsafe(32)
            PasswordResetToken.objects.create(
                user=user,
                token=token,
                expires_at=timezone.now() + timedelta(hours=1)
            )
            # TODO: Send reset email
        except User.DoesNotExist:
            pass  # Don't reveal whether email exists
        
        return Response({'message': 'If the email exists, a reset link has been sent'})
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def password_reset(request):
    """Reset password with token."""
    serializer = PasswordResetSerializer(data=request.data)
    if serializer.is_valid():
        reset_token = serializer.validated_data['reset_token']
        user = reset_token.user
        user.set_password(serializer.validated_data['password'])
        user.save()
        
        reset_token.is_used = True
        reset_token.save()
        
        return Response({'message': 'Password reset successfully'})
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def verify_email(request):
    """Verify email with token."""
    token = request.data.get('token')
    if not token:
        return Response({'error': 'Token required'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        verification = EmailVerificationToken.objects.get(
            token=token,
            user=request.user,
            is_used=False
        )
        
        if not verification.is_valid():
            return Response({'error': 'Token expired'}, status=status.HTTP_400_BAD_REQUEST)
        
        request.user.email_verified = True
        request.user.save()
        
        verification.is_used = True
        verification.save()
        
        return Response({'message': 'Email verified successfully'})
    except EmailVerificationToken.DoesNotExist:
        return Response({'error': 'Invalid token'}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    """Change user password."""
    old_password = request.data.get('old_password')
    new_password = request.data.get('new_password')
    
    if not old_password or not new_password:
        return Response({'error': 'Both passwords required'}, status=status.HTTP_400_BAD_REQUEST)
    
    if not request.user.check_password(old_password):
        return Response({'error': 'Invalid old password'}, status=status.HTTP_400_BAD_REQUEST)
    
    request.user.set_password(new_password)
    request.user.save()
    
    return Response({'message': 'Password changed successfully'})