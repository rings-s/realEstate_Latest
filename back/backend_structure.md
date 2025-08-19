back/
├── back/
│   ├── __init__.py
│   ├── settings/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── development.py
│   │   ├── production.py
│   │   └── testing.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── accounts/
│   ├── __init__.py
│   ├── models.py
│   ├── serializers.py
│   ├── views.py
│   ├── urls.py
│   ├── permissions.py
│   ├── signals.py
│   ├── admin.py
│   ├── apps.py
│   └── utils/
│       ├── __init__.py
│       ├── tokens.py
│       ├── email.py
│       └── jwt_handler.py
├── base/
│   ├── __init__.py
│   ├── models.py
│   ├── mixins.py
│   ├── pagination.py
│   ├── permissions.py
│   └── exceptions.py
├── properties/
│   ├── __init__.py
│   ├── models.py
│   ├── serializers.py
│   ├── views.py
│   ├── urls.py
│   ├── admin.py
│   └── filters.py
├── auctions/
│   ├── __init__.py
│   ├── models.py
│   ├── serializers.py
│   ├── views.py
│   ├── urls.py
│   ├── admin.py
│   └── tasks.py
├── store/
│   ├── __init__.py
│   ├── models.py
│   ├── serializers.py
│   ├── views.py
│   ├── urls.py
│   └── admin.py
├── tenants/
│   ├── __init__.py
│   ├── models.py
│   ├── serializers.py
│   ├── views.py
│   ├── urls.py
│   └── admin.py
├── subscriptions/
│   ├── __init__.py
│   ├── models.py
│   ├── serializers.py
│   ├── views.py
│   ├── urls.py
│   ├── stripe_webhook.py
│   └── admin.py
├── dashboard/
│   ├── __init__.py
│   ├── views.py
│   ├── urls.py
│   ├── analytics.py
│   └── charts.py
├── notifications/
│   ├── __init__.py
│   ├── models.py
│   ├── serializers.py
│   ├── views.py
│   └── consumers.py
├── payments/
│   ├── __init__.py
│   ├── models.py
│   ├── serializers.py
│   ├── views.py
│   ├── stripe_handler.py
│   └── urls.py
├── templates/
│   └── emails/
│       ├── base.html
│       ├── verification.html
│       ├── welcome.html
│       ├── auction_notification.html
│       └── subscription.html
├── static/
├── media/
├── requirements.txt
├── .env.example
└── manage.py