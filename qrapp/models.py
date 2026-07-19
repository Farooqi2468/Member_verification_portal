from django.db import models
from django.core.validators import RegexValidator

numeric_validator = RegexValidator(
    regex=r'^\d+$',
    message='Only numbers are allowed.'
)

cnic_validator = RegexValidator(
    regex=r'^\d{5}-\d{7}-\d{1}$',
    message='CNIC must be in the format XXXXX-XXXXXXX-X'
)

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

class Member(models.Model):
    member_id = models.CharField(max_length=50, primary_key=True, validators=[numeric_validator])
    member_name = models.CharField(max_length=100)
    member_phone = models.CharField(max_length=15, null=True, blank=True, validators=[numeric_validator])
    member_cnic = models.CharField(max_length=15, null=True, blank=True, validators=[cnic_validator])
    no_of_registrations = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.member_name} ({self.member_id})"

class Person(models.Model):
    # membership_number acts as the primary key entered from the form
    membership_number = models.CharField(max_length=50, primary_key=True, default=100011, validators=[numeric_validator])

    name = models.CharField(max_length=100, null=True, blank=True)
    father_name = models.CharField(max_length=100, blank=True, null=True)
    email = models.EmailField(null=True, blank=True)
    cnic = models.CharField(max_length=15, unique=True, null=True, blank=True, validators=[cnic_validator])
    phone = models.CharField(max_length=15, null=True, blank=True, validators=[numeric_validator])
    address = models.TextField(null=True, blank=True)

    # Location ForeignKeys (nullable for backward compatibility)
    town = models.ForeignKey(Town, on_delete=models.CASCADE, null=True, blank=True, related_name='persons')
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, null=True, blank=True, related_name='persons')
    union_council = models.ForeignKey(UnionCouncil, on_delete=models.CASCADE, null=True, blank=True, related_name='persons')
    ward = models.ForeignKey(Ward, on_delete=models.CASCADE, null=True, blank=True, related_name='persons')

    # New fields
    member_name = models.CharField(max_length=100, null=True, blank=True)
    member_membership_id = models.CharField(max_length=50, null=True, blank=True)
    member_phone = models.CharField(max_length=15, null=True, blank=True, validators=[numeric_validator])
    member_cnic = models.CharField(max_length=15, null=True, blank=True, validators=[cnic_validator])

    # Foreign key to the Member table
    made_by = models.ForeignKey(Member, on_delete=models.CASCADE, null=True, related_name='persons_created')

    qr_code = models.ImageField(upload_to='qrcodes/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.membership_number})"

class Book(models.Model):
    name = models.CharField(max_length=200)
    receiving_date = models.DateField()
    office_person = models.CharField(max_length=100)
    issue_date = models.DateField(null=True, blank=True)
    
    RETURN_STATUS_CHOICES = [
        ('Returned', 'Returned'),
        ('Not Returned', 'Not Returned'),
    ]
    return_status = models.CharField(max_length=20, choices=RETURN_STATUS_CHOICES, default='Not Returned')
    
    return_date = models.DateField(null=True, blank=True)
    return_person_name = models.CharField(max_length=100, null=True, blank=True)
    sr_no = models.CharField(max_length=50, unique=True)
    no_of_pages = models.PositiveIntegerField(null=True, blank=True)

    def __str__(self):
        return f"{self.name} (Sr No: {self.sr_no})"

class MembershipSummary(models.Model):
    name = models.CharField(max_length=200, unique=True)
    total_issued = models.PositiveIntegerField(default=0)
    total_returned = models.PositiveIntegerField(default=0)
    total_outstanding = models.PositiveIntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Summary for {self.name}"

from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=Member)
def create_person_for_member(sender, instance, created, **kwargs):
    if created:
        Person.objects.get_or_create(
            membership_number=instance.member_id,
            defaults={
                'name': instance.member_name,
                'phone': instance.member_phone,
                'cnic': instance.member_cnic,
            }
        )

# --- Office Bearers Models ---

class CentralCabinet(models.Model):
    central_cabinet_name = models.CharField(max_length=100)
    central_cabinet_designation = models.CharField(max_length=100, null=True, blank=True)
    central_cabinet_phone = models.CharField(max_length=20, null=True, blank=True, validators=[numeric_validator])
    central_cabinet_cnic = models.CharField(max_length=20, null=True, blank=True, validators=[cnic_validator])
    central_cabinet_address = models.TextField(null=True, blank=True)
    central_cabinet_photo = models.ImageField(upload_to='office_bearers/central_cabinet/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.central_cabinet_name} - {self.central_cabinet_designation}"

class TownOrganization(models.Model):
    town = models.ForeignKey(Town, on_delete=models.CASCADE, related_name='town_office_bearers')
    town_org_name = models.CharField(max_length=100)
    town_org_designation = models.CharField(max_length=100, null=True, blank=True)
    town_org_phone = models.CharField(max_length=20, null=True, blank=True, validators=[numeric_validator])
    town_org_cnic = models.CharField(max_length=20, null=True, blank=True, validators=[cnic_validator])
    town_org_address = models.TextField(null=True, blank=True)
    town_org_photo = models.ImageField(upload_to='office_bearers/town_org/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.town_org_name} - {self.town.name}"

class ZonalOrganization(models.Model):
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='zonal_office_bearers')
    zonal_org_name = models.CharField(max_length=100)
    zonal_org_designation = models.CharField(max_length=100, null=True, blank=True)
    zonal_org_phone = models.CharField(max_length=20, null=True, blank=True, validators=[numeric_validator])
    zonal_org_cnic = models.CharField(max_length=20, null=True, blank=True, validators=[cnic_validator])
    zonal_org_address = models.TextField(null=True, blank=True)
    zonal_org_photo = models.ImageField(upload_to='office_bearers/zonal_org/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.zonal_org_name} - {self.zone.name}"

class UnionCouncilOrganization(models.Model):
    union_council = models.ForeignKey(UnionCouncil, on_delete=models.CASCADE, related_name='uc_office_bearers')
    uc_org_name = models.CharField(max_length=100)
    uc_org_designation = models.CharField(max_length=100, null=True, blank=True)
    uc_org_phone = models.CharField(max_length=20, null=True, blank=True, validators=[numeric_validator])
    uc_org_cnic = models.CharField(max_length=20, null=True, blank=True, validators=[cnic_validator])
    uc_org_address = models.TextField(null=True, blank=True)
    uc_org_photo = models.ImageField(upload_to='office_bearers/uc_org/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.uc_org_name} - {self.union_council.name}"

class WardOrganization(models.Model):
    ward = models.ForeignKey(Ward, on_delete=models.CASCADE, related_name='ward_office_bearers')
    ward_org_name = models.CharField(max_length=100)
    ward_org_designation = models.CharField(max_length=100, null=True, blank=True)
    ward_org_phone = models.CharField(max_length=20, null=True, blank=True, validators=[numeric_validator])
    ward_org_cnic = models.CharField(max_length=20, null=True, blank=True, validators=[cnic_validator])
    ward_org_address = models.TextField(null=True, blank=True)
    ward_org_photo = models.ImageField(upload_to='office_bearers/ward_org/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.ward_org_name} - {self.ward.name}"

class PeoplesYouthOrganization(models.Model):
    pyo_name = models.CharField(max_length=100)
    pyo_designation = models.CharField(max_length=100, null=True, blank=True)
    pyo_phone = models.CharField(max_length=20, null=True, blank=True, validators=[numeric_validator])
    pyo_cnic = models.CharField(max_length=20, null=True, blank=True, validators=[cnic_validator])
    pyo_address = models.TextField(null=True, blank=True)
    pyo_photo = models.ImageField(upload_to='office_bearers/pyo/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class WomenWing(models.Model):
    women_wing_name = models.CharField(max_length=100)
    women_wing_designation = models.CharField(max_length=100, null=True, blank=True)
    women_wing_phone = models.CharField(max_length=20, null=True, blank=True, validators=[numeric_validator])
    women_wing_cnic = models.CharField(max_length=20, null=True, blank=True, validators=[cnic_validator])
    women_wing_address = models.TextField(null=True, blank=True)
    women_wing_photo = models.ImageField(upload_to='office_bearers/women_wing/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class MinorityWing(models.Model):
    minority_wing_name = models.CharField(max_length=100)
    minority_wing_designation = models.CharField(max_length=100, null=True, blank=True)
    minority_wing_phone = models.CharField(max_length=20, null=True, blank=True, validators=[numeric_validator])
    minority_wing_cnic = models.CharField(max_length=20, null=True, blank=True, validators=[cnic_validator])
    minority_wing_address = models.TextField(null=True, blank=True)
    minority_wing_photo = models.ImageField(upload_to='office_bearers/minority_wing/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class LabourWing(models.Model):
    labour_wing_name = models.CharField(max_length=100)
    labour_wing_designation = models.CharField(max_length=100, null=True, blank=True)
    labour_wing_phone = models.CharField(max_length=20, null=True, blank=True, validators=[numeric_validator])
    labour_wing_cnic = models.CharField(max_length=20, null=True, blank=True, validators=[cnic_validator])
    labour_wing_address = models.TextField(null=True, blank=True)
    labour_wing_photo = models.ImageField(upload_to='office_bearers/labour_wing/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class CulturalWing(models.Model):
    cultural_wing_name = models.CharField(max_length=100)
    cultural_wing_designation = models.CharField(max_length=100, null=True, blank=True)
    cultural_wing_phone = models.CharField(max_length=20, null=True, blank=True, validators=[numeric_validator])
    cultural_wing_cnic = models.CharField(max_length=20, null=True, blank=True, validators=[cnic_validator])
    cultural_wing_address = models.TextField(null=True, blank=True)
    cultural_wing_photo = models.ImageField(upload_to='office_bearers/cultural_wing/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class HumanRightsWing(models.Model):
    human_rights_wing_name = models.CharField(max_length=100)
    human_rights_wing_designation = models.CharField(max_length=100, null=True, blank=True)
    human_rights_wing_phone = models.CharField(max_length=20, null=True, blank=True, validators=[numeric_validator])
    human_rights_wing_cnic = models.CharField(max_length=20, null=True, blank=True, validators=[cnic_validator])
    human_rights_wing_address = models.TextField(null=True, blank=True)
    human_rights_wing_photo = models.ImageField(upload_to='office_bearers/human_rights_wing/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class TradersWing(models.Model):
    traders_wing_name = models.CharField(max_length=100)
    traders_wing_designation = models.CharField(max_length=100, null=True, blank=True)
    traders_wing_phone = models.CharField(max_length=20, null=True, blank=True, validators=[numeric_validator])
    traders_wing_cnic = models.CharField(max_length=20, null=True, blank=True, validators=[cnic_validator])
    traders_wing_address = models.TextField(null=True, blank=True)
    traders_wing_photo = models.ImageField(upload_to='office_bearers/traders_wing/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class SportsWing(models.Model):
    sports_wing_name = models.CharField(max_length=100)
    sports_wing_designation = models.CharField(max_length=100, null=True, blank=True)
    sports_wing_phone = models.CharField(max_length=20, null=True, blank=True, validators=[numeric_validator])
    sports_wing_cnic = models.CharField(max_length=20, null=True, blank=True, validators=[cnic_validator])
    sports_wing_address = models.TextField(null=True, blank=True)
    sports_wing_photo = models.ImageField(upload_to='office_bearers/sports_wing/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class PeoplesStudyCircle(models.Model):
    study_circle_name = models.CharField(max_length=100)
    study_circle_designation = models.CharField(max_length=100, null=True, blank=True)
    study_circle_phone = models.CharField(max_length=20, null=True, blank=True, validators=[numeric_validator])
    study_circle_cnic = models.CharField(max_length=20, null=True, blank=True, validators=[cnic_validator])
    study_circle_address = models.TextField(null=True, blank=True)
    study_circle_photo = models.ImageField(upload_to='office_bearers/study_circle/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class DoctorsForum(models.Model):
    doctors_forum_name = models.CharField(max_length=100)
    doctors_forum_designation = models.CharField(max_length=100, null=True, blank=True)
    doctors_forum_phone = models.CharField(max_length=20, null=True, blank=True, validators=[numeric_validator])
    doctors_forum_cnic = models.CharField(max_length=20, null=True, blank=True, validators=[cnic_validator])
    doctors_forum_address = models.TextField(null=True, blank=True)
    doctors_forum_photo = models.ImageField(upload_to='office_bearers/doctors_forum/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class UlemaWing(models.Model):
    ulema_wing_name = models.CharField(max_length=100)
    ulema_wing_designation = models.CharField(max_length=100, null=True, blank=True)
    ulema_wing_phone = models.CharField(max_length=20, null=True, blank=True, validators=[numeric_validator])
    ulema_wing_cnic = models.CharField(max_length=20, null=True, blank=True, validators=[cnic_validator])
    ulema_wing_address = models.TextField(null=True, blank=True)
    ulema_wing_photo = models.ImageField(upload_to='office_bearers/ulema_wing/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
