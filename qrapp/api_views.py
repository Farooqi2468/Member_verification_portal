"""
api_views.py
------------
Public REST API views for the qrapp.

Endpoint: POST /api/member/register/
  - No authentication required (public endpoint for the frontend website)
  - Accepts JSON body
  - Creates both a Member record and a linked Person record
  - 'made_by' on the Person is auto-set to the "website" Member (no input needed)
  - Returns JSON response
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema, OpenApiResponse

from .api_serializers import MemberRegistrationSerializer


class MemberRegistrationAPIView(APIView):
    """
    POST /api/member/register/

    Register a new member + person via the frontend website form.
    The 'made_by' field on Person is automatically set to the "website" member.

    Required fields:
        member_id       — numbers only
        member_name     — alphabets & spaces only

    Optional fields:
        member_phone    — +digits format  (e.g. +923001234567)
        member_cnic     — XXXXX-XXXXXXX-X (e.g. 12345-1234567-1)
        membership_number — Person's primary key (numbers only)
        name            — Person's name (alphabets & spaces)
        father_name     — alphabets & spaces
        email           — valid email address
        cnic            — XXXXX-XXXXXXX-X
        phone           — +digits format
        address         — free text

    Success (201):
    {
        "success": true,
        "message": "Member registered successfully.",
        "data": {
            "member_id": "12345",
            "member_name": "Ali Hassan",
            "member_phone": "+923001234567",
            "member_cnic": "12345-1234567-1",
            "person": {
                "membership_number": "...",
                "name": "...",
                "made_by": "website"
            }
        }
    }

    Error (400):
    {
        "success": false,
        "errors": {
            "member_id": ["A member with ID '12345' already exists."],
            ...
        }
    }
    """

    authentication_classes = []   # No auth required — public endpoint
    permission_classes = []       # No permissions required — public endpoint

    @extend_schema(
        request=MemberRegistrationSerializer,
        responses={
            201: OpenApiResponse(description="Member and Person registered successfully."),
            400: OpenApiResponse(description="Validation error."),
        },
        summary="Register a new member",
        description=(
            "Public endpoint for the frontend website. "
            "Creates a Member record and a linked Person record in one request. "
            "The 'made_by' field on Person is automatically set to 'website' — "
            "the frontend does not need to send it."
        ),
    )
    def post(self, request, *args, **kwargs):
        serializer = MemberRegistrationSerializer(data=request.data)

        if serializer.is_valid():
            member, person = serializer.save()
            return Response(
                {
                    "success": True,
                    "message": "Member registered successfully.",
                    "data": {
                        "member_id":    member.member_id,
                        "member_name":  member.member_name,
                        "member_phone": member.member_phone,
                        "member_cnic":  member.member_cnic,
                        "person": {
                            "membership_number": person.membership_number,
                            "name":              person.name,
                            "father_name":       person.father_name,
                            "email":             person.email,
                            "cnic":              person.cnic,
                            "phone":             person.phone,
                            "address":           person.address,
                            "made_by":           "website",  # always defaulted
                        },
                    },
                },
                status=status.HTTP_201_CREATED,
            )

        return Response(
            {
                "success": False,
                "errors": serializer.errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
