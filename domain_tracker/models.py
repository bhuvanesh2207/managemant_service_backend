from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Domain(models.Model):
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    )

    client_name = models.CharField(max_length=255)
    domain_name = models.CharField(max_length=255, unique=True)
    registrar = models.CharField(max_length=255, blank=True, null=True)
    purchase_date = models.DateField(blank=True, null=True)
    expiry_date = models.DateField(blank=True, null=True)
    active_status = models.BooleanField(default=True)

    # SSH info
    ssh_name = models.CharField(max_length=255, blank=True, null=True)
    ssh_purchase_date = models.DateField(blank=True, null=True)
    ssh_expiry_date = models.DateField(blank=True, null=True)

    # Hosting info (new)
    hosting_name = models.CharField(max_length=255, blank=True, null=True)
    hosting_purchase_date = models.DateField(blank=True, null=True)
    hosting_expiry_date = models.DateField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.domain_name


class DomainHistory(models.Model):
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, related_name="histories")
    changes = models.TextField()
    updated_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"History for {self.domain.domain_name} at {self.updated_at}"
