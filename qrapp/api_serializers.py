"""
api_serializers.py
------------------
DRF serializers for the public Member Registration API endpoint.
"""

import re
from rest_framework import serializers
from .models import Member, Person


class MemberRegistrationSerializer(serializers.Serializer):
    """
    Combined serializer for registering a new Member + Person via the REST API.

    Member fields (required):
        member_id    — numbers only
        member_name  — alphabets & spaces only

    Member fields (optional):
        member_phone — optional, +digits format
        member_cnic  — optional, XXXXX-XXXXXXX-X format

    Person fields (all optional):
        membership_number — numbers only (Person's primary key)
        name              — alphabets & spaces only
        father_name       — alphabets & spaces only
        email             — valid email
        cnic              — XXXXX-XXXXXXX-X format
        phone             — +digits format
        address           — free text
    """

    # ── Member fields ─────────────────────────────────────────────────────────
    member_id    = serializers.CharField(max_length=50)
    member_name  = serializers.CharField(max_length=100)
    member_phone = serializers.CharField(max_length=13, required=False, allow_blank=True)
    member_cnic  = serializers.CharField(max_length=15, required=False, allow_blank=True)

    # ── Person fields ─────────────────────────────────────────────────────────
    membership_number = serializers.CharField(max_length=50, required=False, allow_blank=True)
    name              = serializers.CharField(max_length=100, required=False, allow_blank=True)
    father_name       = serializers.CharField(max_length=100, required=False, allow_blank=True)
    email             = serializers.EmailField(required=False, allow_blank=True)
    cnic              = serializers.CharField(max_length=15, required=False, allow_blank=True)
    phone             = serializers.CharField(max_length=13, required=False, allow_blank=True)
    address           = serializers.CharField(required=False, allow_blank=True)

    # ── Member field-level validation ─────────────────────────────────────────

    def validate_member_id(self, value):
        """Ensure member_id contains only digits and does not already exist."""
        if not value.isdigit():
            raise serializers.ValidationError("Member ID must contain numbers only.")
        if Member.objects.filter(member_id=value).exists():
            raise serializers.ValidationError(
                f"A member with ID '{value}' already exists."
            )
        return value

    def validate_member_name(self, value):
        """Ensure member_name contains only alphabets and spaces."""
        if not all(ch.isalpha() or ch.isspace() for ch in value):
            raise serializers.ValidationError(
                "Member name must contain only alphabets and spaces."
            )
        return value.strip()

    def validate_member_cnic(self, value):
        """Validate CNIC format: XXXXX-XXXXXXX-X (if provided)."""
        if value and not re.match(r'^\d{5}-\d{7}-\d{1}$', value):
            raise serializers.ValidationError(
                "CNIC must be in the format XXXXX-XXXXXXX-X (e.g. 12345-1234567-1)."
            )
        return value

    def validate_member_phone(self, value):
        """Validate phone: optional leading +, then digits only."""
        if value and not re.match(r'^\+?[0-9]+$', value):
            raise serializers.ValidationError(
                "Phone number can optionally start with + followed by digits only."
            )
        return value

    # ── Person field-level validation ─────────────────────────────────────────

    def validate_membership_number(self, value):
        """Ensure membership_number contains only digits."""
        if value and not value.isdigit():
            raise serializers.ValidationError("Membership number must contain numbers only.")
        if value and Person.objects.filter(membership_number=value).exists():
            raise serializers.ValidationError(
                f"A person with membership number '{value}' already exists."
            )
        return value

    def validate_name(self, value):
        """Ensure name contains only alphabets and spaces."""
        if value and not all(ch.isalpha() or ch.isspace() for ch in value):
            raise serializers.ValidationError(
                "Name must contain only alphabets and spaces."
            )
        return value.strip() if value else value

    def validate_father_name(self, value):
        """Ensure father_name contains only alphabets and spaces."""
        if value and not all(ch.isalpha() or ch.isspace() for ch in value):
            raise serializers.ValidationError(
                "Father name must contain only alphabets and spaces."
            )
        return value.strip() if value else value

    def validate_cnic(self, value):
        """Validate Person's CNIC format: XXXXX-XXXXXXX-X (if provided) and uniqueness."""
        if value and not re.match(r'^\d{5}-\d{7}-\d{1}$', value):
            raise serializers.ValidationError(
                "CNIC must be in the format XXXXX-XXXXXXX-X (e.g. 12345-1234567-1)."
            )
        if value and Person.objects.filter(cnic=value).exists():
            raise serializers.ValidationError(
                f"A person with CNIC '{value}' is already registered."
            )
        return value

    def validate_phone(self, value):
        """Validate Person's phone (if provided)."""
        if value and not re.match(r'^\+?[0-9]+$', value):
            raise serializers.ValidationError(
                "Phone number can optionally start with + followed by digits only."
            )
        return value

    # ── Save: creates Member + Person atomically ──────────────────────────────

    def save(self):
        data = self.validated_data

        # 1. Get or create the "website" Member record (used as made_by default)
        website_member, _ = Member.objects.get_or_create(
            member_id='website',
            defaults={'member_name': 'website'},
        )

        # 2. Create the Member
        #    NOTE: a post_save signal on Member automatically creates a linked
        #    Person (membership_number=member_id) with basic fields.
        member = Member.objects.create(
            member_id=data['member_id'],
            member_name=data['member_name'],
            member_phone=data.get('member_phone') or None,
            member_cnic=data.get('member_cnic') or None,
        )

        # 3. Fetch the Person that the post_save signal already created,
        #    then update it with the extra fields + set made_by = "website".
        person = Person.objects.get(membership_number=member.member_id)

        person.made_by        = website_member
        person.father_name    = data.get('father_name') or None
        person.email          = data.get('email') or None
        person.address        = data.get('address') or None
        person.member_name    = member.member_name
        person.member_membership_id = member.member_id
        person.member_phone   = member.member_phone
        person.member_cnic    = member.member_cnic

        # Override name / phone / cnic only if explicitly provided by the frontend
        if data.get('name'):
            person.name = data['name']
        if data.get('phone'):
            person.phone = data['phone']
        if data.get('cnic'):
            person.cnic = data['cnic']

        person.save()

        return member, person

