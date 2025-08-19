import jwt
from datetime import datetime, timedelta
from django.conf import settings
from rest_framework import authentication, exceptions
from accounts.models import User
from google.auth.transport import requests
from google.oauth2 import id_token


class JWTAuthentication(authentication.BaseAuthentication):
    """JWT Authentication handler."""
    
    authentication_header_prefix = 'Bearer'

    def authenticate(self, request):
        """Authenticate the request and return a two-tuple of (user, token)."""
        request.user = None
        auth_header = authentication.get_authorization_header(request).split()
        auth_header_prefix = self.authentication_header_prefix.lower()

        if not auth_header:
            return None

        if len(auth_header) == 1:
            return None
        elif len(auth_header) > 2:
            return None

        prefix = auth_header[0].decode('utf-8')
        token = auth_header[1].decode('utf-8')

        if prefix.lower() != auth_header_prefix:
            return None

        return self._authenticate_credentials(request, token)

    def _authenticate_credentials(self, request, token):
        """Authenticate the token."""
        try:
            payload = jwt.decode(
                token,
                settings.JWT_AUTH['JWT_SECRET_KEY'],
                algorithms=[settings.JWT_AUTH['JWT_ALGORITHM']]
            )
        except jwt.ExpiredSignatureError:
            raise exceptions.AuthenticationFailed('Token has expired.')
        except jwt.InvalidTokenError:
            raise exceptions.AuthenticationFailed('Invalid token.')

        try:
            user = User.objects.get(id=payload['user_id'])
        except User.DoesNotExist:
            raise exceptions.AuthenticationFailed('No user matching this token was found.')

        if not user.is_active:
            raise exceptions.AuthenticationFailed('User has been deactivated.')

        return (user, token)


def generate_access_token(user):
    """Generate access token for user."""
    payload = {
        'user_id': str(user.id),
        'email': user.email,
        'exp': datetime.utcnow() + settings.JWT_AUTH['JWT_EXPIRATION_DELTA'],
        'iat': datetime.utcnow(),
    }
    
    return jwt.encode(
        payload,
        settings.JWT_AUTH['JWT_SECRET_KEY'],
        algorithm=settings.JWT_AUTH['JWT_ALGORITHM']
    )


def generate_refresh_token(user):
    """Generate refresh token for user."""
    payload = {
        'user_id': str(user.id),
        'email': user.email,
        'exp': datetime.utcnow() + settings.JWT_AUTH['JWT_REFRESH_EXPIRATION_DELTA'],
        'iat': datetime.utcnow(),
        'type': 'refresh'
    }
    
    return jwt.encode(
        payload,
        settings.JWT_AUTH['JWT_SECRET_KEY'],
        algorithm=settings.JWT_AUTH['JWT_ALGORITHM']
    )


def verify_google_token(token):
    """Verify Google OAuth token."""
    try:
        idinfo = id_token.verify_oauth2_token(
            token,
            requests.Request(),
            settings.GOOGLE_OAUTH2_CLIENT_ID
        )
        
        if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
            raise ValueError('Wrong issuer.')
        
        return idinfo
    except ValueError as e:
        raise exceptions.AuthenticationFailed(f'Google token verification failed: {str(e)}')