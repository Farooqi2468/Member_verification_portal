from django.db import models
from django.contrib.auth.models import User


class Town(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']


class Zone(models.Model):
    name = models.CharField(max_length=100)
    town = models.ForeignKey(Town, on_delete=models.CASCADE, related_name='zones')

    def __str__(self):
        return f"{self.name} ({self.town.name})"

    class Meta:
        ordering = ['name']
        unique_together = ('name', 'town')


class UnionCouncil(models.Model):
    name = models.CharField(max_length=100)
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='union_councils')

    def __str__(self):
        return f"{self.name} ({self.zone.name})"

    class Meta:
        ordering = ['name']
        unique_together = ('name', 'zone')


class Ward(models.Model):
    name = models.CharField(max_length=100)
    union_council = models.ForeignKey(UnionCouncil, on_delete=models.CASCADE, related_name='wards')

    def __str__(self):
        return f"{self.name} ({self.union_council.name})"

    class Meta:
        ordering = ['name']
        unique_together = ('name', 'union_council')


class Person(models.Model):
    # person_id acts as the primary key entered from the form
    person_id = models.CharField(max_length=50, primary_key=True, default=100011)

    name = models.CharField(max_length=100, null=True, blank=True)
    father_name = models.CharField(max_length=100, blank=True, null=True)
    email = models.EmailField(null=True, blank=True)
    cnic = models.CharField(max_length=15, unique=True, null=True, blank=True)
    phone = models.CharField(max_length=15, null=True, blank=True)
    address = models.TextField(null=True, blank=True)

    # Location ForeignKeys (nullable for backward compatibility)
    town = models.ForeignKey(Town, on_delete=models.SET_NULL, null=True, blank=True, related_name='persons')
    zone = models.ForeignKey(Zone, on_delete=models.SET_NULL, null=True, blank=True, related_name='persons')
    union_council = models.ForeignKey(UnionCouncil, on_delete=models.SET_NULL, null=True, blank=True, related_name='persons')
    ward = models.ForeignKey(Ward, on_delete=models.SET_NULL, null=True, blank=True, related_name='persons')

    # Foreign key to the User table
    made_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='persons_created')

    qr_code = models.ImageField(upload_to='qrcodes/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.person_id})"