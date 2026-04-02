from django.db import models
from django.contrib.auth.models import User

class Person(models.Model):
    # person_id acts as the primary key entered from the form
    person_id = models.CharField(max_length=50, primary_key=True, default = 100011)
    
    name = models.CharField(max_length=100, null=True, blank=True)
    father_name = models.CharField(max_length=100, blank=True, null=True)
    email = models.EmailField(null=True, blank=True)
    cnic = models.CharField(max_length=15, unique=True, null=True, blank=True)
    phone = models.CharField(max_length=15, null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    union_council = models.CharField(max_length=100, null=True, blank=True)
    town = models.CharField(max_length=100, null=True, blank=True)
    zone = models.CharField(max_length=100, null=True, blank=True)
    ward = models.CharField(max_length=100, null=True, blank=True)
    
    # Foreign key to the User table
    made_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='persons_created')
    
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return f"{self.name} ({self.person_id})"