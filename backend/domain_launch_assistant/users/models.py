import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Custom user model for a founder using the application.

    AbstractUser already provides: username, email, first_name, last_name,
    password, is_active, date_joined, last_login. We override `id` to use
    a UUID primary key and add created_at/updated_at, which AbstractUser
    does not provide.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # AbstractUser already defines email, but not as unique or indexed.
    # Redeclare it here so it matches the data-model spec (email is required
    # and used for lookups).
    email = models.EmailField(unique=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return self.username