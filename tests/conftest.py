import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_backend.settings")
django.setup()

import pytest


@pytest.fixture
def api_client():
    from django.test import Client

    return Client()
