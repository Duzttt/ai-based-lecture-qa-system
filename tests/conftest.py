import os
import django

# Initialize Django before any tests are collected or run.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_backend.settings")
django.setup()
