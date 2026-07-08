import io
import os
import base64
import urllib.request
import qrcode
import csv
import json
from datetime import timedelta, datetime
from django.core.files.base import ContentFile
from django.conf import settings
from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import HttpResponseForbidden, JsonResponse, HttpResponse
from django.contrib.auth import update_session_auth_hash
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.core.paginator import Paginator
from django.contrib.auth.models import User, Group
from django.contrib import messages

from .forms import PersonForm, TownForm, ZoneForm, UnionCouncilForm, WardForm, RoleUserCreationForm, RoleUserChangeForm, ProfileUpdateForm, PasswordUpdateForm, BookForm, MemberForm, MembershipSummaryForm
from .models import (
    Person, Town, Zone, UnionCouncil, Ward, Book, Member, MembershipSummary,
    CentralCabinet, TownOrganization, ZonalOrganization, UnionCouncilOrganization,
    WardOrganization, PeoplesYouthOrganization, WomenWing, MinorityWing, LabourWing,
    CulturalWing, HumanRightsWing, TradersWing, SportsWing, PeoplesStudyCircle,
    DoctorsForum, UlemaWing
)
from django.db.models import F


def home(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'home.html')


def get_user_role(user):
    if user.is_superuser:
        return "Admin"
    if user.groups.exists():
        return user.groups.first().name
    return None


@login_required
def dashboard(request):
    role = get_user_role(request.user)
    name = request.user.first_name if request.user.first_name else request.user.username

    today = timezone.now().date()
    context = {
        'role': role,
        'name': name,
        # ── 8 Metric Cards ──────────────────────────────────────
        'total_members':   Person.objects.count(),
        'members_today':   Person.objects.filter(created_at__date=today).count(),
        'members_month':   Person.objects.filter(
                               created_at__year=today.year,
                               created_at__month=today.month
                           ).count(),
        'total_towns':     Town.objects.count(),
        'total_zones':     Zone.objects.count(),
        'total_ucs':       UnionCouncil.objects.count(),
        'total_wards':     Ward.objects.count(),
        'registered_by_me': 0, # Disabled since made_by is now a Member
    }
    return render(request, 'dashboard.html', context)


def admin_only(view_func):
    def wrapper(request, *args, **kwargs):
        is_admin = request.user.groups.filter(name='Admin').exists() or request.user.is_superuser
        if is_admin:
            return view_func(request, *args, **kwargs)
        return HttpResponseForbidden("Not allowed")
    return wrapper


@login_required
@admin_only
def all_system_users(request):
    users_list = User.objects.all().order_by('-date_joined')
    
    # ROLE-BASED VISIBILITY: Non-superusers cannot see superusers
    if not request.user.is_superuser:
        users_list = users_list.filter(is_superuser=False)

    q = request.GET.get('q', '')
    role_id = request.GET.get('role')

    if q:
        users_list = users_list.filter(
            Q(username__icontains=q) | 
            Q(first_name__icontains=q) | 
            Q(last_name__icontains=q) |
            Q(email__icontains=q)
        )
    if role_id:
        users_list = users_list.filter(groups__id=role_id)

    paginator = Paginator(users_list, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # ROLE-BASED VISIBILITY: Non-superusers cannot filter for Superuser group
    roles = Group.objects.all()
    if not request.user.is_superuser:
        roles = roles.exclude(name='Superuser')

    query_dict = request.GET.copy()
    if 'page' in query_dict:
        del query_dict['page']
    query_params = query_dict.urlencode()
    if query_params:
        query_params = f"&{query_params}"

    context = {
        'page_obj': page_obj,
        'roles': roles,
        'current_filters': {
            'q': q,
            'role': int(role_id) if role_id else ''
        },
        'query_params': query_params,
        'active_page': 'all_users'
    }
    return render(request, 'all_users.html', context)


@login_required
@admin_only
def update_system_user(request, pk):
    user_obj = get_object_or_404(User, pk=pk)
    
    # ROLE-BASED ACCESS: Non-superusers cannot update superusers
    if user_obj.is_superuser and not request.user.is_superuser:
        messages.error(request, "You do not have permission to update a Superuser account.")
        return redirect('all_system_users')

    if request.method == 'POST':
        form = RoleUserChangeForm(request.POST, instance=user_obj, request_user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, f"User {user_obj.username} updated successfully!")
            return redirect('all_system_users')
    else:
        form = RoleUserChangeForm(instance=user_obj, request_user=request.user)
    return render(request, 'update_user.html', {'form': form, 'user_obj': user_obj, 'active_page': 'all_users'})


@require_POST
@login_required
@admin_only
def delete_system_user(request, pk):
    user_obj = get_object_or_404(User, pk=pk)
    
    # ROLE-BASED ACCESS: Non-superusers cannot delete superusers
    if user_obj.is_superuser and not request.user.is_superuser:
        messages.error(request, "You do not have permission to delete a Superuser account.")
        return redirect('all_system_users')

    if user_obj.is_superuser and user_obj == request.user:
        messages.error(request, "You cannot delete your own admin account.")
    else:
        user_obj.delete()
        messages.success(request, "User deleted successfully.")
    return redirect('all_system_users')



@login_required
@admin_only
def create_system_user(request):
    if request.method == 'POST':
        form = RoleUserCreationForm(request.POST, request_user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, f"User {form.cleaned_data.get('username')} created successfully!")
            return redirect('all_system_users')
    else:
        form = RoleUserCreationForm(request_user=request.user)
    return render(request, 'create_user.html', {'form': form, 'active_page': 'all_users', 'is_superuser': request.user.is_superuser})


@login_required
@admin_only
def create_person(request):
    if request.method == 'POST':
        form = PersonForm(request.POST)
        if form.is_valid():
            person = form.save(commit=False)
            
            uc_name = form.cleaned_data.get('union_council_name')
            ward_name = form.cleaned_data.get('ward_name')
            
            if uc_name and person.zone:
                uc, _ = UnionCouncil.objects.get_or_create(name__iexact=uc_name, zone=person.zone, defaults={'name': uc_name})
                person.union_council = uc
                if ward_name:
                    ward, _ = Ward.objects.get_or_create(name__iexact=ward_name, union_council=uc, defaults={'name': ward_name})
                    person.ward = ward
            elif uc_name:
                uc = UnionCouncil.objects.filter(name__iexact=uc_name).first()
                if uc:
                    person.union_council = uc
                    if ward_name:
                        ward, _ = Ward.objects.get_or_create(name__iexact=ward_name, union_council=uc, defaults={'name': ward_name})
                        person.ward = ward
            
            member_id = form.cleaned_data.get('member_id')
            member_name = form.cleaned_data.get('member_name')
            member_phone = form.cleaned_data.get('member_phone')
            member_cnic = form.cleaned_data.get('member_cnic')
            
            if member_id or member_cnic:
                member = None
                
                if member_cnic:
                    member = Member.objects.filter(member_cnic=member_cnic).first()
                    
                if not member and member_id:
                    member = Member.objects.filter(member_id=member_id).first()
                    
                if member:
                    member.no_of_registrations = F('no_of_registrations') + 1
                    member.save()
                    member.refresh_from_db()
                elif member_id:
                    member = Member.objects.create(
                        member_id=member_id,
                        member_name=member_name,
                        member_phone=member_phone,
                        member_cnic=member_cnic,
                        no_of_registrations=1
                    )
                    
                person.made_by = member
                
            person.save()

            url = request.build_absolute_uri(f"/person/{person.membership_number}/")
            img = qrcode.make(url)
            
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            file_name = f"qr_{person.membership_number}.png"
            
            person.qr_code.save(file_name, ContentFile(buffer.getvalue()), save=False)
            person.save()

            return redirect('admin_person_detail', pk=person.membership_number)
    else:
        form = PersonForm()
    return render(request, 'templates.html', {'form': form})


def person_detail(request, pk):
    person = get_object_or_404(Person, membership_number=pk)

    # Secure string masking
    masked_phone = person.phone if person.phone else "--"
    if person.phone and len(person.phone) >= 7:
        masked_phone = f"{person.phone[:4]}-{person.phone[4:5]}XXXXXX"

    masked_cnic = person.cnic if person.cnic else "--"
    if person.cnic and len(person.cnic) >= 5:
        masked_cnic = f"...{person.cnic[-5:]}"

    is_admin = False
    if request.user.is_authenticated:
        if request.user.groups.filter(name='Admin').exists() or request.user.is_superuser:
            is_admin = True

    return render(request, 'mobile_scan.html', {
        'person': person,
        'masked_phone': masked_phone,
        'masked_cnic': masked_cnic,
        'is_admin': is_admin
    })


@login_required
@admin_only
def admin_person_detail(request, pk):
    person = get_object_or_404(Person, membership_number=pk)
    is_admin = request.user.groups.filter(name='Admin').exists() or request.user.is_superuser

    # Read QR image and encode as base64 so it can be embedded directly in HTML.
    # This avoids any CORS issue — html2canvas sees a data: URL, not an S3 URL.
    qr_base64 = None
    if person.qr_code:
        try:
            person.qr_code.open('rb')
            qr_bytes = person.qr_code.read()
            person.qr_code.close()
            qr_base64 = 'data:image/png;base64,' + base64.b64encode(qr_bytes).decode('utf-8')
        except Exception:
            qr_base64 = None

    return render(request, 'details.html', {
        'person': person,
        'is_admin': is_admin,
        'qr_base64': qr_base64,
    })


@login_required
@admin_only
def all_members(request):
    import_success = request.GET.get('import_success')
    import_duplicates = request.GET.get('import_duplicates')
    import_errors = request.GET.get('import_errors')
    if import_success is not None:
        try:
            suc = int(import_success)
            dup = int(import_duplicates or 0)
            err = int(import_errors or 0)
            if suc > 0:
                messages.success(request, f"Successfully imported {suc} members.")
            if dup > 0:
                messages.warning(request, f"Skipped {dup} duplicate members.")
            if err > 0:
                messages.error(request, f"Failed to import {err} rows due to errors.")
            if suc == 0 and dup == 0 and err == 0:
                messages.info(request, "No new members were imported.")
        except ValueError:
            pass
        return redirect('all_members')

    members_list = Person.objects.all().order_by('-created_at')

    # Filtering logic
    q = request.GET.get('q', '')
    town_id = request.GET.get('town')
    zone_id = request.GET.get('zone')
    uc_id = request.GET.get('union_council')
    ward_id = request.GET.get('ward')
    registrar_id = request.GET.get('registrar')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    missing_cnic = request.GET.get('missing_cnic')
    missing_phone = request.GET.get('missing_phone')
    missing_town = request.GET.get('missing_town')
    missing_zone = request.GET.get('missing_zone')

    if q:
        members_list = members_list.filter(
            Q(name__icontains=q) | 
            Q(membership_number__icontains=q) | 
            Q(cnic__icontains=q) |
            Q(phone__icontains=q)
        )
    if town_id:
        members_list = members_list.filter(town_id=town_id)
    if zone_id:
        members_list = members_list.filter(zone_id=zone_id)
    if uc_id:
        members_list = members_list.filter(union_council_id=uc_id)
    if ward_id:
        members_list = members_list.filter(ward_id=ward_id)
    if registrar_id:
        if registrar_id == 'system':
            members_list = members_list.filter(made_by__isnull=True)
        else:
            members_list = members_list.filter(made_by_id=registrar_id)
    if start_date:
        try:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            members_list = members_list.filter(created_at__date__gte=start_date_obj)
        except ValueError:
            pass
    if end_date:
        try:
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            members_list = members_list.filter(created_at__date__lte=end_date_obj)
        except ValueError:
            pass

    if missing_cnic == '1':
        members_list = members_list.filter(Q(cnic__isnull=True) | Q(cnic__exact=''))
    if missing_phone == '1':
        members_list = members_list.filter(Q(phone__isnull=True) | Q(phone__exact=''))
    if missing_town == '1':
        members_list = members_list.filter(town__isnull=True)
    if missing_zone == '1':
        members_list = members_list.filter(zone__isnull=True)

    # CSV Export
    if request.GET.get('export') == 'csv':
        export_columns = request.GET.getlist('export_columns')
        default_cols = ['Member ID', 'Name', 'Father Name', 'CNIC', 'Phone', 'Address', 'Town', 'Zone', 'Union Council', 'Ward', 'Registered By', 'Registrar Membership ID', 'Date']
        cols = export_columns if export_columns else default_cols

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="members_export.csv"'
        
        writer = csv.writer(response)
        writer.writerow(cols)
        
        for p in members_list:
            row = []
            if 'Member ID' in cols: row.append(p.membership_number)
            if 'Name' in cols: row.append(p.name)
            if 'Father Name' in cols: row.append(p.father_name)
            if 'CNIC' in cols: row.append(p.cnic)
            if 'Phone' in cols: row.append(p.phone)
            if 'Address' in cols: row.append(p.address)
            if 'Town' in cols: row.append(p.town.name if p.town else '')
            if 'Zone' in cols: row.append(p.zone.name if p.zone else '')
            if 'Union Council' in cols: row.append(p.union_council.name if p.union_council else '')
            if 'Ward' in cols: row.append(p.ward.name if p.ward else '')
            if 'Registered By' in cols: row.append(p.made_by.member_name if p.made_by else '')
            if 'Registrar Membership ID' in cols: row.append(p.made_by.member_id if p.made_by else '')
            if 'Date' in cols: row.append(p.created_at.strftime('%Y-%m-%d %H:%M:%S'))
            writer.writerow(row)
        return response

    # Pagination
    paginator = Paginator(members_list, 10)  # Show 10 members per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Initial context for dropdowns
    towns = Town.objects.all()
    
    registrars = Member.objects.all().order_by('member_name')
    # Query string for pagination
    query_dict = request.GET.copy()
    if 'page' in query_dict:
        del query_dict['page']
    query_params = query_dict.urlencode()
    if query_params:
        query_params = f"&{query_params}"

    context = {
        'page_obj': page_obj,
        'towns': towns,
        'registrars': registrars,
        'current_filters': {
            'q': q,
            'town': int(town_id) if town_id else '',
            'zone': int(zone_id) if zone_id else '',
            'union_council': int(uc_id) if uc_id else '',
            'ward': int(ward_id) if ward_id else '',
            'registrar': registrar_id if registrar_id else '',
            'start_date': start_date or '',
            'end_date': end_date or '',
            'missing_cnic': missing_cnic,
            'missing_phone': missing_phone,
            'missing_town': missing_town,
            'missing_zone': missing_zone,
        },
        'query_params': query_params
    }
    return render(request, 'all_members.html', context)


@require_POST
@login_required
@admin_only
def import_members_csv(request):
    if 'csv_file' not in request.FILES:
        messages.error(request, "No file uploaded.")
        return redirect('all_members')

    csv_file = request.FILES['csv_file']
    if not csv_file.name.endswith('.csv'):
        messages.error(request, "This is not a CSV file.")
        return redirect('all_members')

    try:
        # Read the file and decode it
        file_data = csv_file.read().decode('utf-8')
        lines = file_data.splitlines()
        reader = csv.DictReader(lines)
        
        success_count = 0
        error_count = 0

        for row in reader:
            # Clean keys to make it more resilient to trailing spaces or case differences
            cleaned_row = {k.strip().lower(): v.strip() for k, v in row.items() if k}
            
            membership_number = cleaned_row.get('member id') or cleaned_row.get('membership_number')
            if not membership_number:
                error_count += 1
                continue
            
            town_name = cleaned_row.get('town', '')
            zone_name = cleaned_row.get('zone', '')
            uc_name = cleaned_row.get('union council', '') or cleaned_row.get('union_council', '')
            ward_name = cleaned_row.get('ward', '')

            town_obj = None
            if town_name:
                town_obj, _ = Town.objects.get_or_create(name__iexact=town_name, defaults={'name': town_name})

            zone_obj = None
            if zone_name and town_obj:
                zone_obj, _ = Zone.objects.get_or_create(name__iexact=zone_name, town=town_obj, defaults={'name': zone_name})
            elif zone_name:
                zone_obj = Zone.objects.filter(name__iexact=zone_name).first()

            uc_obj = None
            if uc_name and zone_obj:
                uc_obj, _ = UnionCouncil.objects.get_or_create(name__iexact=uc_name, zone=zone_obj, defaults={'name': uc_name})
            elif uc_name:
                uc_obj = UnionCouncil.objects.filter(name__iexact=uc_name).first()
                
            ward_obj = None
            if ward_name and uc_obj:
                ward_obj, _ = Ward.objects.get_or_create(name__iexact=ward_name, union_council=uc_obj, defaults={'name': ward_name})

            registered_by_name = cleaned_row.get('registered by', '')
            registrar_membership_id = cleaned_row.get('registrar membership id', '')
            member_obj = None
            if registered_by_name or registrar_membership_id:
                # Try to find by member_id (PK) first, then fall back to name
                if registrar_membership_id:
                    member_obj = Member.objects.filter(member_id=registrar_membership_id).first()
                if not member_obj and registered_by_name:
                    member_obj = Member.objects.filter(member_name__iexact=registered_by_name).first()
                if not member_obj:
                    member_obj = Member.objects.create(
                        member_id=registrar_membership_id or registered_by_name,
                        member_name=registered_by_name,
                        no_of_registrations=0
                    )

            # Handle CNIC carefully to avoid unique constraint issues if empty
            cnic_val = cleaned_row.get('cnic', '') or None

            # Create or update the person
            person, created = Person.objects.get_or_create(
                membership_number=membership_number,
                defaults={
                    'name': cleaned_row.get('name', ''),
                    'father_name': cleaned_row.get('father name', '') or cleaned_row.get('father_name', ''),
                    'cnic': cnic_val,
                    'phone': cleaned_row.get('phone', ''),
                    'address': cleaned_row.get('address', ''),
                    'town': town_obj,
                    'zone': zone_obj,
                    'union_council': uc_obj,
                    'ward': ward_obj,
                    'made_by': member_obj,
                }
            )

            if not created:
                person.name = cleaned_row.get('name', '')
                person.father_name = cleaned_row.get('father name', '') or cleaned_row.get('father_name', '')
                person.cnic = cnic_val
                person.phone = cleaned_row.get('phone', '')
                person.address = cleaned_row.get('address', '')
                person.town = town_obj
                person.zone = zone_obj
                person.union_council = uc_obj
                person.ward = ward_obj
                
                if person.made_by != member_obj:
                    if person.made_by:
                        old_member = person.made_by
                        old_member.no_of_registrations = F('no_of_registrations') - 1
                        old_member.save()
                    if member_obj:
                        member_obj.no_of_registrations = F('no_of_registrations') + 1
                        member_obj.save()
                        member_obj.refresh_from_db()
                
                person.made_by = member_obj
                person.save()
            else:
                if member_obj:
                    member_obj.no_of_registrations = F('no_of_registrations') + 1
                    member_obj.save()
                    member_obj.refresh_from_db()

            date_str = cleaned_row.get('date', '')
            if date_str:
                try:
                    parsed_date = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                    Person.objects.filter(membership_number=person.membership_number).update(created_at=parsed_date)
                except ValueError:
                    pass

            # Generate QR code if newly created or if missing
            if created or not person.qr_code:
                url = request.build_absolute_uri(f"/person/{person.membership_number}/")
                img = qrcode.make(url)
                
                buffer = io.BytesIO()
                img.save(buffer, format='PNG')
                file_name = f"qr_{person.membership_number}.png"
                
                person.qr_code.save(file_name, ContentFile(buffer.getvalue()), save=False)
                person.save()

            success_count += 1
            
        if success_count > 0:
            messages.success(request, f"Successfully imported/updated {success_count} members.")
        if error_count > 0:
            messages.warning(request, f"Skipped {error_count} rows due to missing 'membership_number'.")

    except Exception as e:
        messages.error(request, f"Error processing CSV file: {str(e)}")

    return redirect('all_members')


@require_POST
@login_required
@admin_only
def import_members_ajax(request):
    try:
        data = json.loads(request.body)
        rows = data.get('rows', [])
        
        success_count = 0
        duplicate_count = 0
        error_count = 0
        logs = []

        for row in rows:
            # Clean keys
            cleaned_row = {k.strip().lower(): str(v).strip() for k, v in row.items() if k}
            
            membership_number = cleaned_row.get('member id') or cleaned_row.get('membership_number')
            log_id = membership_number if membership_number else "Unknown"

            if not membership_number:
                error_count += 1
                logs.append({'serial_number': log_id, 'type': 'error', 'message': 'Missing Member ID'})
                continue
                
            # Skip duplicates
            if Person.objects.filter(membership_number=membership_number).exists():
                duplicate_count += 1
                logs.append({'serial_number': log_id, 'type': 'warning', 'message': f'Skipped duplicate'})
                continue
                
            town_name = cleaned_row.get('town', '')
            zone_name = cleaned_row.get('zone', '')
            uc_name = cleaned_row.get('union council', '') or cleaned_row.get('union_council', '')
            ward_name = cleaned_row.get('ward', '')

            town_obj = None
            if town_name:
                town_obj, _ = Town.objects.get_or_create(name__iexact=town_name, defaults={'name': town_name})

            zone_obj = None
            if zone_name and town_obj:
                zone_obj, _ = Zone.objects.get_or_create(name__iexact=zone_name, town=town_obj, defaults={'name': zone_name})
            elif zone_name:
                zone_obj = Zone.objects.filter(name__iexact=zone_name).first()

            uc_obj = None
            if uc_name and zone_obj:
                uc_obj, _ = UnionCouncil.objects.get_or_create(name__iexact=uc_name, zone=zone_obj, defaults={'name': uc_name})
            elif uc_name:
                uc_obj = UnionCouncil.objects.filter(name__iexact=uc_name).first()
                
            ward_obj = None
            if ward_name and uc_obj:
                ward_obj, _ = Ward.objects.get_or_create(name__iexact=ward_name, union_council=uc_obj, defaults={'name': ward_name})

            registered_by_name = cleaned_row.get('registered by', '')
            registrar_membership_id = cleaned_row.get('registrar membership id', '')
            member_obj = None
            if registered_by_name or registrar_membership_id:
                # Try to find by member_id (PK) first, then fall back to name
                if registrar_membership_id:
                    member_obj = Member.objects.filter(member_id=registrar_membership_id).first()
                if not member_obj and registered_by_name:
                    member_obj = Member.objects.filter(member_name__iexact=registered_by_name).first()
                if not member_obj:
                    member_obj = Member.objects.create(
                        member_id=registrar_membership_id or registered_by_name,
                        member_name=registered_by_name,
                        no_of_registrations=0
                    )

            cnic_val = cleaned_row.get('cnic', '') or None
            
            # Since we skip duplicates above, we can just create
            try:
                person = Person.objects.create(
                    membership_number=membership_number,
                    name=cleaned_row.get('name', ''),
                    father_name=cleaned_row.get('father name', '') or cleaned_row.get('father_name', ''),
                    cnic=cnic_val,
                    phone=cleaned_row.get('phone', ''),
                    address=cleaned_row.get('address', ''),
                    town=town_obj,
                    zone=zone_obj,
                    union_council=uc_obj,
                    ward=ward_obj,
                    made_by=member_obj,
                )
                
                if member_obj:
                    member_obj.no_of_registrations = F('no_of_registrations') + 1
                    member_obj.save()
                    member_obj.refresh_from_db()

                date_str = cleaned_row.get('date', '')
                if date_str:
                    try:
                        parsed_date = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                        Person.objects.filter(membership_number=person.membership_number).update(created_at=parsed_date)
                    except ValueError:
                        pass

                # Generate QR code
                url = request.build_absolute_uri(f"/person/{person.membership_number}/")
                img = qrcode.make(url)
                
                buffer = io.BytesIO()
                img.save(buffer, format='PNG')
                file_name = f"qr_{person.membership_number}.png"
                
                person.qr_code.save(file_name, ContentFile(buffer.getvalue()), save=False)
                person.save()

                success_count += 1
                logs.append({'serial_number': log_id, 'type': 'success', 'message': f'Imported successfully'})
            except Exception as e:
                # E.g. unique constraint failed on CNIC
                error_count += 1
                logs.append({'serial_number': log_id, 'type': 'error', 'message': f'Error importing: {str(e)}'})
                
        return JsonResponse({
            'status': 'success',
            'imported': success_count,
            'duplicates': duplicate_count,
            'errors': error_count,
            'logs': logs
        })

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@login_required
@admin_only
def update_person(request, pk):
    person = get_object_or_404(Person, membership_number=pk)
    if request.method == 'POST':
        form = PersonForm(request.POST, instance=person)
        if form.is_valid():
            person = form.save(commit=False)

            uc_name = form.cleaned_data.get('union_council_name')
            ward_name = form.cleaned_data.get('ward_name')
            
            if uc_name and person.zone:
                uc, _ = UnionCouncil.objects.get_or_create(name__iexact=uc_name, zone=person.zone, defaults={'name': uc_name})
                person.union_council = uc
                if ward_name:
                    ward, _ = Ward.objects.get_or_create(name__iexact=ward_name, union_council=uc, defaults={'name': ward_name})
                    person.ward = ward
            elif uc_name:
                uc = UnionCouncil.objects.filter(name__iexact=uc_name).first()
                if uc:
                    person.union_council = uc
                    if ward_name:
                        ward, _ = Ward.objects.get_or_create(name__iexact=ward_name, union_council=uc, defaults={'name': ward_name})
                        person.ward = ward

            member_id = form.cleaned_data.get('member_id')
            member_name = form.cleaned_data.get('member_name')
            member_phone = form.cleaned_data.get('member_phone')
            member_cnic = form.cleaned_data.get('member_cnic')
            
            if member_id or member_cnic:
                member = None
                
                if member_cnic:
                    member = Member.objects.filter(member_cnic=member_cnic).first()
                    
                if not member and member_id:
                    member = Member.objects.filter(member_id=member_id).first()
                    
                if not member and member_id:
                    member = Member.objects.create(
                        member_id=member_id,
                        member_name=member_name,
                        member_phone=member_phone,
                        member_cnic=member_cnic,
                        no_of_registrations=0
                    )
                    
                if person.made_by != member:
                    if person.made_by:
                        old_member = person.made_by
                        old_member.no_of_registrations = F('no_of_registrations') - 1
                        old_member.save()
                    if member:
                        member.no_of_registrations = F('no_of_registrations') + 1
                        member.save()
                        member.refresh_from_db()
                        
                person.made_by = member

            url = request.build_absolute_uri(f"/person/{person.membership_number}/")
            img = qrcode.make(url)
            
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            file_name = f"qr_{person.membership_number}.png"
            
            person.qr_code.save(file_name, ContentFile(buffer.getvalue()), save=False)
            person.save()

            return redirect('admin_person_detail', pk=person.membership_number)
    else:
        form = PersonForm(instance=person)
    return render(request, 'templates.html', {'form': form, 'is_update': True, 'person': person})


@require_POST
@login_required
@admin_only
def delete_person(request, pk):
    person = get_object_or_404(Person, membership_number=pk)
    
    # Decrement the member's registration count before deleting the person
    if person.made_by:
        member = person.made_by
        if member.no_of_registrations > 0:
            member.no_of_registrations = F('no_of_registrations') - 1
            member.save()
            
    person.delete()
    messages.success(request, 'Member deleted successfully!')
    return redirect('all_members')


# ── Location Management ────────────────────────────────────────────────────────

@login_required
@admin_only
def manage_locations(request):
    q = request.GET.get('q', '')
    towns = Town.objects.all()
    zones = Zone.objects.select_related('town').all()
    ucs = UnionCouncil.objects.select_related('zone__town').all()
    wards = Ward.objects.select_related('union_council__zone__town').all()

    if q:
        towns = towns.filter(name__icontains=q)
        zones = zones.filter(Q(name__icontains=q) | Q(town__name__icontains=q))
        ucs = ucs.filter(Q(name__icontains=q) | Q(zone__name__icontains=q) | Q(zone__town__name__icontains=q))
        wards = wards.filter(Q(name__icontains=q) | Q(union_council__name__icontains=q) | Q(union_council__zone__name__icontains=q) | Q(union_council__zone__town__name__icontains=q))

    active_tab = request.GET.get('tab', 'town')

    if request.GET.get('export') == 'csv':
        export_columns = request.GET.getlist('export_columns')
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{active_tab}s_export.csv"'
        writer = csv.writer(response)
        
        if active_tab == 'town':
            default_cols = ['Town Name', 'Number of Zones']
            cols = export_columns if export_columns else default_cols
            writer.writerow(cols)
            for t in towns:
                row = []
                if 'Town Name' in cols: row.append(t.name)
                if 'Number of Zones' in cols: row.append(t.zones.count())
                writer.writerow(row)
        elif active_tab == 'zone':
            default_cols = ['Zone Name', 'Town', 'Number of UCs']
            cols = export_columns if export_columns else default_cols
            writer.writerow(cols)
            for z in zones:
                row = []
                if 'Zone Name' in cols: row.append(z.name)
                if 'Town' in cols: row.append(z.town.name)
                if 'Number of UCs' in cols: row.append(z.union_councils.count())
                writer.writerow(row)
        elif active_tab == 'uc':
            default_cols = ['UC Name', 'Zone', 'Town', 'Number of Wards']
            cols = export_columns if export_columns else default_cols
            writer.writerow(cols)
            for u in ucs:
                row = []
                if 'UC Name' in cols: row.append(u.name)
                if 'Zone' in cols: row.append(u.zone.name)
                if 'Town' in cols: row.append(u.zone.town.name)
                if 'Number of Wards' in cols: row.append(u.wards.count())
                writer.writerow(row)
        elif active_tab == 'ward':
            default_cols = ['Ward Name', 'Union Council', 'Zone', 'Town']
            cols = export_columns if export_columns else default_cols
            writer.writerow(cols)
            for w in wards:
                row = []
                if 'Ward Name' in cols: row.append(w.name)
                if 'Union Council' in cols: row.append(w.union_council.name)
                if 'Zone' in cols: row.append(w.union_council.zone.name)
                if 'Town' in cols: row.append(w.union_council.zone.town.name)
                writer.writerow(row)
                
        return response

    context = {
        'town_form': TownForm(),
        'zone_form': ZoneForm(),
        'uc_form': UnionCouncilForm(),
        'ward_form': WardForm(),
        'towns': towns,
        'zones': zones,
        'ucs': ucs,
        'wards': wards,
        'active_tab': request.GET.get('tab', 'town'),
        'q': q,
    }
    return render(request, 'locations.html', context)


@require_POST
@login_required
@admin_only
def add_town(request):
    form = TownForm(request.POST)
    if form.is_valid():
        form.save()
    return redirect(f"{request.META.get('HTTP_REFERER', '/dashboard/locations/')}?tab=town")


@require_POST
@login_required
@admin_only
def update_town(request, pk):
    town = get_object_or_404(Town, pk=pk)
    form = TownForm(request.POST, instance=town)
    if form.is_valid():
        form.save()
        messages.success(request, f"Town '{town.name}' updated successfully.")
    else:
        error_msg = " ".join([f"{', '.join(errors)}" for field, errors in form.errors.items()])
        messages.error(request, f"Failed to update town. {error_msg}")
    return redirect(f"/dashboard/locations/?tab=town")


@require_POST
@login_required
@admin_only
def delete_town(request, pk):
    town = get_object_or_404(Town, pk=pk)
    town.delete()
    return redirect('/dashboard/locations/?tab=town')


@require_POST
@login_required
@admin_only
def add_zone(request):
    form = ZoneForm(request.POST)
    if form.is_valid():
        form.save()
    return redirect('/dashboard/locations/?tab=zone')


@require_POST
@login_required
@admin_only
def update_zone(request, pk):
    zone = get_object_or_404(Zone, pk=pk)
    form = ZoneForm(request.POST, instance=zone)
    if form.is_valid():
        form.save()
        messages.success(request, f"Zone '{zone.name}' updated successfully.")
    else:
        error_msg = " ".join([f"{', '.join(errors)}" for field, errors in form.errors.items()])
        messages.error(request, f"Failed to update zone. {error_msg}")
    return redirect('/dashboard/locations/?tab=zone')


@require_POST
@login_required
@admin_only
def delete_zone(request, pk):
    zone = get_object_or_404(Zone, pk=pk)
    zone.delete()
    return redirect('/dashboard/locations/?tab=zone')


@require_POST
@login_required
@admin_only
def add_uc(request):
    form = UnionCouncilForm(request.POST)
    if form.is_valid():
        form.save()
    return redirect('/dashboard/locations/?tab=uc')


@require_POST
@login_required
@admin_only
def update_uc(request, pk):
    uc = get_object_or_404(UnionCouncil, pk=pk)
    form = UnionCouncilForm(request.POST, instance=uc)
    if form.is_valid():
        form.save()
        messages.success(request, f"Union Council '{uc.name}' updated successfully.")
    else:
        error_msg = " ".join([f"{', '.join(errors)}" for field, errors in form.errors.items()])
        messages.error(request, f"Failed to update union council. {error_msg}")
    return redirect('/dashboard/locations/?tab=uc')


@require_POST
@login_required
@admin_only
def delete_uc(request, pk):
    uc = get_object_or_404(UnionCouncil, pk=pk)
    uc.delete()
    return redirect('/dashboard/locations/?tab=uc')


@require_POST
@login_required
@admin_only
def add_ward(request):
    form = WardForm(request.POST)
    if form.is_valid():
        form.save()
    return redirect('/dashboard/locations/?tab=ward')


@require_POST
@login_required
@admin_only
def update_ward(request, pk):
    ward = get_object_or_404(Ward, pk=pk)
    form = WardForm(request.POST, instance=ward)
    if form.is_valid():
        form.save()
        messages.success(request, f"Ward '{ward.name}' updated successfully.")
    else:
        error_msg = " ".join([f"{', '.join(errors)}" for field, errors in form.errors.items()])
        messages.error(request, f"Failed to update ward. {error_msg}")
    return redirect('/dashboard/locations/?tab=ward')


@require_POST
@login_required
@admin_only
def delete_ward(request, pk):
    ward = get_object_or_404(Ward, pk=pk)
    ward.delete()
    return redirect('/dashboard/locations/?tab=ward')


# ── AJAX Cascade Endpoints ─────────────────────────────────────────────────────

def ajax_get_zones(request):
    town_id = request.GET.get('town_id')
    zones = Zone.objects.filter(town_id=town_id).values('id', 'name') if town_id else []
    return JsonResponse(list(zones), safe=False)


def ajax_get_ucs(request):
    zone_id = request.GET.get('zone_id')
    ucs = UnionCouncil.objects.filter(zone_id=zone_id).values('id', 'name') if zone_id else []
    return JsonResponse(list(ucs), safe=False)


def ajax_get_wards(request):
    uc_id = request.GET.get('uc_id')
    wards = Ward.objects.filter(union_council_id=uc_id).values('id', 'name') if uc_id else []
    return JsonResponse(list(wards), safe=False)


def ajax_get_member_info(request):
    member_id = request.GET.get('member_id')
    if member_id:
        try:
            member = Member.objects.get(member_id=member_id)
            return JsonResponse({
                'success': True,
                'member_name': member.member_name,
                'member_phone': member.member_phone,
                'member_cnic': member.member_cnic,
            })
        except Member.DoesNotExist:
            return JsonResponse({'success': False})
    return JsonResponse({'success': False})


@login_required
@admin_only
def ajax_dashboard_charts(request):
    days = request.GET.get('days', '30')
    
    # Base queryset for persons
    persons_qs = Person.objects.all()
    
    if days != 'all':
        try:
            days = int(days)
            start_date = timezone.now().date() - timedelta(days=days)
            persons_qs = persons_qs.filter(created_at__date__gte=start_date)
        except ValueError:
            pass # fallback to all if invalid

    # 1. Registrations Over Time (Line Chart)
    # Group by the date part of created_at
    daily_counts = (
        persons_qs
        .annotate(date=TruncDate('created_at'))
        .values('date')
        .annotate(count=Count('membership_number'))
        .order_by('date')
    )
    
    labels_line = [obj['date'].strftime('%b %d') for obj in daily_counts if obj['date']]
    data_line = [obj['count'] for obj in daily_counts if obj['date']]

    # 2. Members by Town (Doughnut/Bar Chart)
    town_counts = (
        persons_qs
        .filter(town__isnull=False)
        .values('town__name')
        .annotate(count=Count('membership_number'))
        .order_by('-count')
    )
    
    labels_town = [obj['town__name'] for obj in town_counts]
    data_town = [obj['count'] for obj in town_counts]

    return JsonResponse({
        'timeline': {
            'labels': labels_line,
            'data': data_line,
        },
        'towns': {
            'labels': labels_town,
            'data': data_town,
        }
    })

@login_required
@admin_only
def reports_view(request):
    # 1. Geographic Data
    town_stats = Town.objects.annotate(member_count=Count('persons')).order_by('-member_count')
    
    # 2. Registrar Performance (Top 10)
    registrar_qs = Member.objects.all()
    registrar_stats = registrar_qs.annotate(
        member_count=Count('persons_created')
    ).order_by('-member_count')[:10]
    
    # 3. Data Integrity
    total_count = Person.objects.count()
    integrity_data = {
        'missing_phone': Person.objects.filter(Q(phone__isnull=True) | Q(phone='')).count(),
        'missing_cnic': Person.objects.filter(Q(cnic__isnull=True) | Q(cnic='')).count(),
        'missing_address': Person.objects.filter(Q(address__isnull=True) | Q(address='')).count(),
        'missing_name': Person.objects.filter(Q(name__isnull=True) | Q(name='')).count(),
        'missing_town': Person.objects.filter(town__isnull=True).count(),
        'total': total_count
    }

    
    # 4. Growth Stats (Last 6 Months)
    growth_stats = []
    today = timezone.now().date().replace(day=1)
    for i in range(5, -1, -1):
        # Calculate start of month
        month_date = today - timedelta(days=i*30) # rough estimate
        month_date = month_date.replace(day=1)
        
        count = Person.objects.filter(
            created_at__year=month_date.year, 
            created_at__month=month_date.month
        ).count()
        
        growth_stats.append({
            'label': month_date.strftime('%b %Y'),
            'count': count
        })

    context = {
        'active_page': 'reports',
        'town_stats': town_stats,
        'registrar_stats': registrar_stats,
        'integrity_data': integrity_data,
        'growth_stats': growth_stats,
        'is_superuser': request.user.is_superuser,
    }
    return render(request, 'reports.html', context)


@login_required
def settings_view(request):
    user = request.user
    role = get_user_role(user)
    profile_form = ProfileUpdateForm(instance=user)
    password_form = PasswordUpdateForm(user=user)
    active_tab = 'profile'

    if request.method == 'POST':
        if 'update_profile' in request.POST:
            profile_form = ProfileUpdateForm(request.POST, instance=user)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, 'Your profile has been updated successfully!')
                return redirect('settings')
            active_tab = 'profile'
        elif 'update_password' in request.POST:
            password_form = PasswordUpdateForm(request.POST, user=user)
            if password_form.is_valid():
                user.set_password(password_form.cleaned_data['new_password'])
                user.save()
                update_session_auth_hash(request, user)
                messages.success(request, 'Your password has been changed successfully!')
                return redirect('settings')
            active_tab = 'password'

    context = {
        'profile_form': profile_form,
        'password_form': password_form,
        'active_page': 'settings',
        'active_tab': active_tab,
        'role': role,
    }
    return render(request, 'settings.html', context)


@login_required
@admin_only
def qr_image_proxy(request, pk):
    """Proxies the QR image from S3 through Django so the browser can fetch it
    from the same origin, bypassing the CORS restriction on canvas taint."""
    person = get_object_or_404(Person, membership_number=pk)
    if not person.qr_code:
        from django.http import Http404
        raise Http404("QR code not found")

    qr_url = person.qr_code.url
    # If the URL is relative, build an absolute URL
    if qr_url.startswith('/'):
        qr_url = request.build_absolute_uri(qr_url)

    try:
        with urllib.request.urlopen(qr_url) as resp:
            image_data = resp.read()
            content_type = resp.headers.get('Content-Type', 'image/png')
        response = HttpResponse(image_data, content_type=content_type)
        response['Cache-Control'] = 'private, max-age=3600'
        return response
    except Exception:
        from django.http import Http404
        raise Http404("Could not fetch QR image")


@login_required
@admin_only
def book_list(request):
    books_list = Book.objects.all().order_by('-id')

    q = request.GET.get('q', '')
    status = request.GET.get('status', '')
    date_type = request.GET.get('date_type', '')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')

    if q:
        books_list = books_list.filter(
            Q(name__icontains=q) |
            Q(office_person__icontains=q) |
            Q(sr_no__icontains=q) |
            Q(return_person_name__icontains=q)
        )
    
    if status:
        books_list = books_list.filter(return_status=status)

    if date_type in ['receiving_date', 'issue_date', 'return_date']:
        if start_date:
            try:
                start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                books_list = books_list.filter(**{f"{date_type}__gte": start_date_obj})
            except ValueError:
                pass
        if end_date:
            try:
                end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
                books_list = books_list.filter(**{f"{date_type}__lte": end_date_obj})
            except ValueError:
                pass

    paginator = Paginator(books_list, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    query_dict = request.GET.copy()
    if 'page' in query_dict:
        del query_dict['page']
    query_params = query_dict.urlencode()
    if query_params:
        query_params = f"&{query_params}"

    context = {
        'page_obj': page_obj,
        'current_filters': {
            'q': q,
            'status': status,
            'date_type': date_type,
            'start_date': start_date,
            'end_date': end_date
        },
        'query_params': query_params,
        'active_page': 'books'
    }
    return render(request, 'book_list.html', context)

@login_required
@admin_only
def book_create(request):
    if request.method == 'POST':
        form = BookForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Book added successfully!')
            return redirect('book_list')
    else:
        form = BookForm()
    return render(request, 'book_form.html', {'form': form, 'active_page': 'books'})

@login_required
@admin_only
def book_update(request, pk):
    book = get_object_or_404(Book, pk=pk)
    if request.method == 'POST':
        form = BookForm(request.POST, instance=book)
        if form.is_valid():
            form.save()
            messages.success(request, 'Book updated successfully!')
            return redirect('book_list')
    else:
        form = BookForm(instance=book)
    return render(request, 'book_form.html', {'form': form, 'active_page': 'books', 'is_update': True})

@require_POST
@login_required
@admin_only
def book_delete(request, pk):
    book = get_object_or_404(Book, pk=pk)
    book.delete()
    messages.success(request, 'Book deleted successfully!')
    return redirect('book_list')

@login_required
@admin_only
def all_real_members(request):
    members_list = Member.objects.annotate(actual_registrations=Count('persons_created')).order_by('-member_name')
    q = request.GET.get('q', '')

    if q:
        members_list = members_list.filter(
            Q(member_name__icontains=q) |
            Q(member_id__icontains=q) |
            Q(member_phone__icontains=q)
        )

    # CSV Export
    if request.GET.get('export') == 'csv':
        export_columns = request.GET.getlist('export_columns')
        default_cols = ['Member ID', 'Name', 'Phone', 'CNIC', 'No of Registrations']
        cols = export_columns if export_columns else default_cols

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="real_members_export.csv"'
        
        writer = csv.writer(response)
        writer.writerow(cols)
        
        for m in members_list:
            row = []
            if 'Member ID' in cols: row.append(m.member_id)
            if 'Name' in cols: row.append(m.member_name)
            if 'Phone' in cols: row.append(m.member_phone)
            if 'CNIC' in cols: row.append(m.member_cnic)
            if 'No of Registrations' in cols: row.append(m.actual_registrations)
            writer.writerow(row)
        return response

    paginator = Paginator(members_list, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    query_dict = request.GET.copy()
    if 'page' in query_dict:
        del query_dict['page']
    query_params = query_dict.urlencode()
    if query_params:
        query_params = f"&{query_params}"

    context = {
        'page_obj': page_obj,
        'current_filters': {'q': q},
        'query_params': query_params,
        'active_page': 'all_real_members'
    }
    return render(request, 'all_real_members.html', context)


@login_required
@admin_only
def create_real_member(request):
    if request.method == 'POST':
        form = MemberForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Member created successfully!')
            return redirect('all_real_members')
    else:
        form = MemberForm()
    return render(request, 'member_form.html', {'form': form, 'active_page': 'all_real_members'})


@login_required
@admin_only
def update_real_member(request, pk):
    member = get_object_or_404(Member, pk=pk)
    if request.method == 'POST':
        # ── Read the new member_id directly from POST BEFORE binding to form ─
        # pk (from the URL) is always the reliable OLD member_id.
        # request.POST['member_id'] is what the user typed as the new value.
        old_member_id  = pk                              # comes from the URL — always reliable
        new_member_id  = request.POST.get('member_id', pk).strip()
        id_is_changing = (old_member_id != new_member_id)

        form = MemberForm(request.POST, instance=member)
        if form.is_valid():
            # form.save() → if member_id changed, Django INSERTs a new row
            form.save()

            if id_is_changing:
                # 1. Re-point the FK: Person.made_by → new Member row
                Person.objects.filter(made_by_id=old_member_id).update(
                    made_by_id=new_member_id
                )

                # 2. Update the denormalised CharField that stores the member id
                Person.objects.filter(member_membership_id=old_member_id).update(
                    member_membership_id=new_member_id
                )

                # 3. Migrate the mirror Person whose membership_number == old_member_id
                mirror_person = Person.objects.filter(
                    membership_number=old_member_id
                ).first()
                if mirror_person:
                    # PK cannot be updated in-place: delete old row then re-save with new PK
                    mirror_person.membership_number = new_member_id
                    mirror_person.made_by_id = new_member_id
                    Person.objects.filter(membership_number=old_member_id).delete()
                    mirror_person.save()

                # 4. Delete the now-orphaned old Member row (left behind by Django INSERT)
                Member.objects.filter(member_id=old_member_id).delete()

                messages.success(
                    request,
                    f'Member ID updated from "{old_member_id}" to '
                    f'"{new_member_id}" and all associated records have been migrated.'
                )
            else:
                messages.success(request, 'Member updated successfully!')

            return redirect('all_real_members')
    else:
        form = MemberForm(instance=member)
    return render(request, 'member_form.html', {'form': form, 'is_update': True, 'member': member, 'active_page': 'all_real_members'})


@require_POST
@login_required
@admin_only
def delete_real_member(request, pk):
    member = get_object_or_404(Member, pk=pk)
    member.delete()
    messages.success(request, 'Member deleted successfully!')
    return redirect('all_real_members')


@login_required
@admin_only
def membership_summary_view(request):
    summaries = MembershipSummary.objects.all().order_by('name')
    context = {
        'summaries': summaries,
        'active_page': 'membership_summary'
    }
    return render(request, 'membership_summary.html', context)


@login_required
@admin_only
def membership_summary_create(request):
    if request.method == 'POST':
        form = MembershipSummaryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Membership Summary created successfully!')
            return redirect('membership_summary')
    else:
        form = MembershipSummaryForm()
    return render(request, 'membership_summary_form.html', {'form': form, 'active_page': 'membership_summary'})


@login_required
@admin_only
def membership_summary_update(request, pk):
    summary = get_object_or_404(MembershipSummary, pk=pk)
    if request.method == 'POST':
        form = MembershipSummaryForm(request.POST, instance=summary)
        if form.is_valid():
            form.save()
            messages.success(request, 'Membership Summary updated successfully!')
            return redirect('membership_summary')
    else:
        form = MembershipSummaryForm(instance=summary)
    return render(request, 'membership_summary_form.html', {'form': form, 'is_update': True, 'summary': summary, 'active_page': 'membership_summary'})


@require_POST
@login_required
@admin_only
def membership_summary_delete(request, pk):
    summary = get_object_or_404(MembershipSummary, pk=pk)
    summary.delete()
    messages.success(request, 'Membership Summary deleted successfully!')
    return redirect('membership_summary')





@login_required
def ajax_get_member_info(request):
    member_id = request.GET.get('member_id')
    if member_id:
        try:
            member = Member.objects.get(member_id=member_id)
            return JsonResponse({
                'success': True,
                'member_name': member.member_name,
                'member_phone': member.member_phone,
                'member_cnic': member.member_cnic,
            })
        except Member.DoesNotExist:
            try:
                person = Person.objects.get(membership_number=member_id)
                return JsonResponse({
                    'success': True,
                    'member_name': person.name,
                    'member_phone': person.phone,
                    'member_cnic': person.cnic,
                })
            except Person.DoesNotExist:
                return JsonResponse({'success': False})
    return JsonResponse({'success': False})

@login_required
def ajax_get_registered_persons(request):
    member_id = request.GET.get('member_id')
    if not member_id:
        return JsonResponse({'status': 'error', 'message': 'Missing member_id parameter'}, status=400)
    
    # Fetch persons whose made_by_id matches
    persons = Person.objects.filter(made_by_id=member_id).order_by('-created_at')
    
    data = []
    for p in persons:
        data.append({
            'membership_number': p.membership_number,
            'name': p.name,
            'father_name': p.father_name,
            'phone': p.phone,
            'cnic': p.cnic,
        })
        
    return JsonResponse({'status': 'success', 'data': data})


def ajax_get_location_members(request):
    loc_type = request.GET.get('type')
    loc_id = request.GET.get('id')
    
    if not loc_type or not loc_id:
        return JsonResponse({'status': 'error', 'message': 'Missing parameters'}, status=400)
    
    persons = Person.objects.all().order_by('-created_at')
    if loc_type == 'town':
        persons = persons.filter(town_id=loc_id)
    elif loc_type == 'zone':
        persons = persons.filter(zone_id=loc_id)
    elif loc_type == 'uc':
        persons = persons.filter(union_council_id=loc_id)
    elif loc_type == 'ward':
        persons = persons.filter(ward_id=loc_id)
    else:
        return JsonResponse({'status': 'error', 'message': 'Invalid location type'}, status=400)
    
    data = []
    for p in persons:
        data.append({
            'membership_number': p.membership_number,
            'name': p.name,
            'father_name': p.father_name,
            'phone': p.phone,
            'cnic': p.cnic,
        })
        
    return JsonResponse({'status': 'success', 'data': data})

@require_POST
@login_required
@admin_only
def ajax_delete_location_members(request):
    loc_type = request.POST.get('type')
    loc_id = request.POST.get('id')
    
    if not loc_type or not loc_id:
        return JsonResponse({'status': 'error', 'message': 'Missing parameters'}, status=400)
    
    persons = Person.objects.all()
    if loc_type == 'town':
        persons = persons.filter(town_id=loc_id)
    elif loc_type == 'zone':
        persons = persons.filter(zone_id=loc_id)
    elif loc_type == 'uc':
        persons = persons.filter(union_council_id=loc_id)
    elif loc_type == 'ward':
        persons = persons.filter(ward_id=loc_id)
    else:
        return JsonResponse({'status': 'error', 'message': 'Invalid location type'}, status=400)
    
    count = persons.count()
    persons.delete()
    
    return JsonResponse({'status': 'success', 'message': f'Successfully deleted {count} members.'})
from django.forms import modelform_factory

@login_required
def office_bearers_index(request):
    categories = [
        {'id': 'central_cabinet', 'name': 'Central Cabinet', 'icon': 'bi-person-badge'},
        {'id': 'town_org', 'name': 'Town Organizations', 'icon': 'bi-building'},
        {'id': 'zonal_org', 'name': 'Zonal Organizations', 'icon': 'bi-map'},
        {'id': 'uc_org', 'name': 'Union Council Organizations', 'icon': 'bi-diagram-3'},
        {'id': 'ward_org', 'name': 'Ward Organizations', 'icon': 'bi-house'},
        {'id': 'pyo', 'name': 'People\'s Youth Organization', 'icon': 'bi-people-fill'},
        {'id': 'women_wing', 'name': 'Women Wing', 'icon': 'bi-gender-female'},
        {'id': 'minority_wing', 'name': 'Minority Wing', 'icon': 'bi-globe'},
        {'id': 'labour_wing', 'name': 'Labour Wing', 'icon': 'bi-tools'},
        {'id': 'cultural_wing', 'name': 'Cultural Wing', 'icon': 'bi-palette'},
        {'id': 'human_rights_wing', 'name': 'Human Rights Wing', 'icon': 'bi-shield-check'},
        {'id': 'traders_wing', 'name': 'Traders Wing', 'icon': 'bi-shop'},
        {'id': 'sports_wing', 'name': 'Sports Wing', 'icon': 'bi-trophy'},
        {'id': 'study_circle', 'name': 'People\'s Study Circle', 'icon': 'bi-book'},
        {'id': 'doctors_forum', 'name': 'Doctors Forum', 'icon': 'bi-heart-pulse'},
        {'id': 'ulema_wing', 'name': 'Ulema Wing', 'icon': 'bi-book-half'},
    ]
    return render(request, 'office_bearers/index.html', {'categories': categories})

@login_required
def office_bearers_list(request, category):
    categories_meta = {
        'central_cabinet': 'Central Cabinet',
        'town_org': 'Town Organizations',
        'zonal_org': 'Zonal Organizations',
        'uc_org': 'Union Council Organizations',
        'ward_org': 'Ward Organizations',
        'pyo': 'People\'s Youth Organization',
        'women_wing': 'Women Wing',
        'minority_wing': 'Minority Wing',
        'labour_wing': 'Labour Wing',
        'cultural_wing': 'Cultural Wing',
        'human_rights_wing': 'Human Rights Wing',
        'traders_wing': 'Traders Wing',
        'sports_wing': 'Sports Wing',
        'study_circle': 'People\'s Study Circle',
        'doctors_forum': 'Doctors Forum',
        'ulema_wing': 'Ulema Wing',
    }
    
    mapping = {
        'central_cabinet': (CentralCabinet, None, None),
        'town_org': (TownOrganization, 'town', Town),
        'zonal_org': (ZonalOrganization, 'zone', Zone),
        'uc_org': (UnionCouncilOrganization, 'union_council', UnionCouncil),
        'ward_org': (WardOrganization, 'ward', Ward),
        'pyo': (PeoplesYouthOrganization, None, None),
        'women_wing': (WomenWing, None, None),
        'minority_wing': (MinorityWing, None, None),
        'labour_wing': (LabourWing, None, None),
        'cultural_wing': (CulturalWing, None, None),
        'human_rights_wing': (HumanRightsWing, None, None),
        'traders_wing': (TradersWing, None, None),
        'sports_wing': (SportsWing, None, None),
        'study_circle': (PeoplesStudyCircle, None, None),
        'doctors_forum': (DoctorsForum, None, None),
        'ulema_wing': (UlemaWing, None, None),
    }

    if category not in mapping:
        messages.error(request, 'Invalid category.')
        return redirect('office_bearers_index')

    ModelClass, structural_field, _ = mapping[category]
    records = ModelClass.objects.all().order_by('-created_at')

    q = request.GET.get('q', '').strip()
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    missing_cnic = request.GET.get('missing_cnic')
    missing_phone = request.GET.get('missing_phone')
    missing_location = request.GET.get('missing_location')
    export_csv = request.GET.get('export')

    if q:
        from django.db.models import Q
        q_filter = Q(**{f"{category}_name__icontains": q}) | Q(**{f"{category}_cnic__icontains": q}) | Q(**{f"{category}_phone__icontains": q})
        records = records.filter(q_filter)
        
    if start_date:
        records = records.filter(created_at__gte=start_date)
    if end_date:
        records = records.filter(created_at__lte=f"{end_date} 23:59:59")
        
    if missing_cnic == '1':
        from django.db.models import Q
        records = records.filter(Q(**{f"{category}_cnic__isnull": True}) | Q(**{f"{category}_cnic__exact": ''}))
    if missing_phone == '1':
        from django.db.models import Q
        records = records.filter(Q(**{f"{category}_phone__isnull": True}) | Q(**{f"{category}_phone__exact": ''}))
    if missing_location == '1' and structural_field:
        records = records.filter(Q(**{f"{structural_field}__isnull": True}))

    # Generate data list
    data = []
    
    # Pre-fetch membership numbers based on CNIC to avoid N+1 queries
    cnics = [getattr(record, f'{category}_cnic', '') for record in records]
    from .models import Person
    persons = Person.objects.filter(cnic__in=[c for c in cnics if c])
    cnic_to_member_id = {p.cnic: p.membership_number for p in persons if p.cnic}
    
    for record in records:
        cnic = getattr(record, f'{category}_cnic', '')
        photo_field = getattr(record, f'{category}_photo', None)
        photo_url = photo_field.url if photo_field else 'https://upload.wikimedia.org/wikipedia/commons/c/c0/Pakistan_Peoples_Party_Flag.svg'
        
        data.append({
            'id': record.id,
            'member_id': cnic_to_member_id.get(cnic, '--'),
            'photo_url': photo_url,
            'name': getattr(record, f'{category}_name', ''),
            'designation': getattr(record, f'{category}_designation', ''),
            'phone': getattr(record, f'{category}_phone', ''),
            'cnic': cnic,
            'location': getattr(record, structural_field).name if structural_field and getattr(record, structural_field) else '',
        })

    # CSV Export
    if export_csv == 'csv':
        import csv
        from django.http import HttpResponse
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="office_bearers_{category}.csv"'
        writer = csv.writer(response)
        
        headers = ['Name', 'Designation', 'Phone', 'CNIC']
        if structural_field:
            headers.append('Location')
        writer.writerow(headers)
        
        for d in data:
            row = [d['name'], d['designation'], d['phone'], d['cnic']]
            if structural_field:
                row.append(d['location'])
            writer.writerow(row)
            
        return response

    current_filters = {
        'q': q,
        'start_date': start_date,
        'end_date': end_date,
        'missing_cnic': missing_cnic,
        'missing_phone': missing_phone,
        'missing_location': missing_location
    }

    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(data, 15)  # 15 records per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Build query params string for pagination links
    query_params_dict = request.GET.copy()
    if 'page' in query_params_dict:
        del query_params_dict['page']
    query_params = '&' + query_params_dict.urlencode() if query_params_dict else ''

    context = {
        'category_id': category,
        'category_name': categories_meta[category],
        'page_obj': page_obj,
        'query_params': query_params,
        'has_location': bool(structural_field),
        'current_filters': current_filters
    }
    return render(request, 'office_bearers/list.html', context)

@login_required
def get_person_data(request, member_id):
    try:
        person = Person.objects.get(membership_number=member_id)
        data = {
            'success': True,
            'name': person.name or '',
            'father_name': person.father_name or '',
            'cnic': person.cnic or '',
            'phone': person.phone or '',
            'address': person.address or ''
        }
    except Person.DoesNotExist:
        data = {'success': False, 'message': 'Person not found'}
    
    return JsonResponse(data)

@login_required
def search_person_by_name(request):
    query = request.GET.get('q', '').strip()
    if len(query) < 2:
        return JsonResponse({'results': []})
    
    persons = Person.objects.filter(name__icontains=query)[:15]
    results = [
        {
            'membership_number': p.membership_number,
            'name': p.name or '',
            'cnic': p.cnic or '',
            'phone': p.phone or ''
        } for p in persons
    ]
    return JsonResponse({'results': results})

@login_required
def add_office_bearer(request, category):
    mapping = {
        'central_cabinet': (CentralCabinet, None, None),
        'town_org': (TownOrganization, 'town', Town),
        'zonal_org': (ZonalOrganization, 'zone', Zone),
        'uc_org': (UnionCouncilOrganization, 'union_council', UnionCouncil),
        'ward_org': (WardOrganization, 'ward', Ward),
        'pyo': (PeoplesYouthOrganization, None, None),
        'women_wing': (WomenWing, None, None),
        'minority_wing': (MinorityWing, None, None),
        'labour_wing': (LabourWing, None, None),
        'cultural_wing': (CulturalWing, None, None),
        'human_rights_wing': (HumanRightsWing, None, None),
        'traders_wing': (TradersWing, None, None),
        'sports_wing': (SportsWing, None, None),
        'study_circle': (PeoplesStudyCircle, None, None),
        'doctors_forum': (DoctorsForum, None, None),
        'ulema_wing': (UlemaWing, None, None),
    }

    if category not in mapping:
        messages.error(request, 'Invalid category.')
        return redirect('dashboard')

    ModelClass, structural_field, StructuralModel = mapping[category]
    exclude_fields = [structural_field, 'created_at'] if structural_field else ['created_at']
    FormClass = modelform_factory(ModelClass, exclude=exclude_fields)

    if request.method == 'POST':
        form = FormClass(request.POST, request.FILES)
        if form.is_valid():
            instance = form.save(commit=False)
            
            if structural_field and StructuralModel:
                structural_name = request.POST.get(structural_field + '_name')
                
                if structural_field == 'town':
                    obj, _ = Town.objects.get_or_create(name=structural_name)
                elif structural_field == 'zone':
                    t_obj, _ = Town.objects.get_or_create(name=request.POST.get('town_name'))
                    obj, _ = Zone.objects.get_or_create(name=structural_name, town=t_obj)
                elif structural_field == 'union_council':
                    t_obj, _ = Town.objects.get_or_create(name=request.POST.get('town_name'))
                    z_obj, _ = Zone.objects.get_or_create(name=request.POST.get('zone_name'), town=t_obj)
                    obj, _ = UnionCouncil.objects.get_or_create(name=structural_name, zone=z_obj)
                elif structural_field == 'ward':
                    t_obj, _ = Town.objects.get_or_create(name=request.POST.get('town_name'))
                    z_obj, _ = Zone.objects.get_or_create(name=request.POST.get('zone_name'), town=t_obj)
                    uc_obj, _ = UnionCouncil.objects.get_or_create(name=request.POST.get('uc_name'), zone=z_obj)
                    obj, _ = Ward.objects.get_or_create(name=structural_name, union_council=uc_obj)
                    
                setattr(instance, structural_field, obj)
            
            instance.save()
            messages.success(request, 'Office bearer added successfully!')
            return redirect('office_bearers_list', category=category)
    else:
        form = FormClass()
        
    return render(request, 'office_bearers/add.html', {
        'form': form,
        'category': category,
        'structural_field': structural_field,
        'towns': Town.objects.all(),
        'zones': Zone.objects.all(),
        'ucs': UnionCouncil.objects.all(),
        'wards': Ward.objects.all(),
    })

@login_required
def update_office_bearer(request, category, pk):
    mapping = {
        'central_cabinet': (CentralCabinet, None, None),
        'town_org': (TownOrganization, 'town', Town),
        'zonal_org': (ZonalOrganization, 'zone', Zone),
        'uc_org': (UnionCouncilOrganization, 'union_council', UnionCouncil),
        'ward_org': (WardOrganization, 'ward', Ward),
        'pyo': (PeoplesYouthOrganization, None, None),
        'women_wing': (WomenWing, None, None),
        'minority_wing': (MinorityWing, None, None),
        'labour_wing': (LabourWing, None, None),
        'cultural_wing': (CulturalWing, None, None),
        'human_rights_wing': (HumanRightsWing, None, None),
        'traders_wing': (TradersWing, None, None),
        'sports_wing': (SportsWing, None, None),
        'study_circle': (PeoplesStudyCircle, None, None),
        'doctors_forum': (DoctorsForum, None, None),
        'ulema_wing': (UlemaWing, None, None),
    }

    if category not in mapping:
        messages.error(request, 'Invalid category.')
        return redirect('dashboard')

    ModelClass, structural_field, StructuralModel = mapping[category]
    exclude_fields = [structural_field, 'created_at'] if structural_field else ['created_at']
    FormClass = modelform_factory(ModelClass, exclude=exclude_fields)

    instance = get_object_or_404(ModelClass, pk=pk)

    if request.method == 'POST':
        form = FormClass(request.POST, request.FILES, instance=instance)
        if form.is_valid():
            updated_instance = form.save(commit=False)
            
            if structural_field and StructuralModel:
                structural_name = request.POST.get(structural_field + '_name')
                
                if structural_field == 'town':
                    obj, _ = Town.objects.get_or_create(name=structural_name)
                elif structural_field == 'zone':
                    t_obj, _ = Town.objects.get_or_create(name=request.POST.get('town_name'))
                    obj, _ = Zone.objects.get_or_create(name=structural_name, town=t_obj)
                elif structural_field == 'union_council':
                    t_obj, _ = Town.objects.get_or_create(name=request.POST.get('town_name'))
                    z_obj, _ = Zone.objects.get_or_create(name=request.POST.get('zone_name'), town=t_obj)
                    obj, _ = UnionCouncil.objects.get_or_create(name=structural_name, zone=z_obj)
                elif structural_field == 'ward':
                    t_obj, _ = Town.objects.get_or_create(name=request.POST.get('town_name'))
                    z_obj, _ = Zone.objects.get_or_create(name=request.POST.get('zone_name'), town=t_obj)
                    uc_obj, _ = UnionCouncil.objects.get_or_create(name=request.POST.get('uc_name'), zone=z_obj)
                    obj, _ = Ward.objects.get_or_create(name=structural_name, union_council=uc_obj)
                    
                setattr(updated_instance, structural_field, obj)
            
            updated_instance.save()
            messages.success(request, 'Office bearer updated successfully!')
            return redirect('office_bearers_list', category=category)
    else:
        form = FormClass(instance=instance)
        
    member_id_autofill = ''
    cnic = getattr(instance, f'{category}_cnic', None)
    if cnic:
        from .models import Person
        person = Person.objects.filter(cnic=cnic).first()
        if person:
            member_id_autofill = person.membership_number
        
    # We can reuse the add template for updating since it has the same fields
    return render(request, 'office_bearers/add.html', {
        'form': form,
        'category': category,
        'instance': instance,
        'structural_field': structural_field,
        'towns': Town.objects.all(),
        'zones': Zone.objects.all(),
        'ucs': UnionCouncil.objects.all(),
        'wards': Ward.objects.all(),
        'member_id_autofill': member_id_autofill,
    })

@login_required
def delete_office_bearer(request, category, pk):
    if request.method == 'POST':
        mapping = {
            'central_cabinet': (CentralCabinet, None, None),
            'town_org': (TownOrganization, 'town', Town),
            'zonal_org': (ZonalOrganization, 'zone', Zone),
            'uc_org': (UnionCouncilOrganization, 'union_council', UnionCouncil),
            'ward_org': (WardOrganization, 'ward', Ward),
            'pyo': (PeoplesYouthOrganization, None, None),
            'women_wing': (WomenWing, None, None),
            'minority_wing': (MinorityWing, None, None),
            'labour_wing': (LabourWing, None, None),
            'cultural_wing': (CulturalWing, None, None),
            'human_rights_wing': (HumanRightsWing, None, None),
            'traders_wing': (TradersWing, None, None),
            'sports_wing': (SportsWing, None, None),
            'study_circle': (PeoplesStudyCircle, None, None),
            'doctors_forum': (DoctorsForum, None, None),
            'ulema_wing': (UlemaWing, None, None),
        }

        if category not in mapping:
            messages.error(request, 'Invalid category.')
            return redirect('office_bearers_index')

        ModelClass, _, _ = mapping[category]
        try:
            record = ModelClass.objects.get(pk=pk)
            record.delete()
            messages.success(request, 'Office bearer deleted successfully.')
        except ModelClass.DoesNotExist:
            messages.error(request, 'Record not found.')

    return redirect('office_bearers_list', category=category)

@login_required
def import_office_bearers_ajax(request, category):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request method.'})

    try:
        data = json.loads(request.body)
        rows = data.get('rows', [])
        
        mapping = {
            'central_cabinet': (CentralCabinet, None, None),
            'town_org': (TownOrganization, 'town', Town),
            'zonal_org': (ZonalOrganization, 'zone', Zone),
            'uc_org': (UnionCouncilOrganization, 'union_council', UnionCouncil),
            'ward_org': (WardOrganization, 'ward', Ward),
            'pyo': (PeoplesYouthOrganization, None, None),
            'women_wing': (WomenWing, None, None),
            'minority_wing': (MinorityWing, None, None),
            'labour_wing': (LabourWing, None, None),
            'cultural_wing': (CulturalWing, None, None),
            'human_rights_wing': (HumanRightsWing, None, None),
            'traders_wing': (TradersWing, None, None),
            'sports_wing': (SportsWing, None, None),
            'study_circle': (PeoplesStudyCircle, None, None),
            'doctors_forum': (DoctorsForum, None, None),
            'ulema_wing': (UlemaWing, None, None),
        }

        if category not in mapping:
            return JsonResponse({'status': 'error', 'message': 'Invalid category.'})

        ModelClass, structural_field, StructuralModel = mapping[category]

        success_count = 0
        duplicate_count = 0
        error_count = 0
        logs = []

        for row in rows:
            cleaned_row = {k.strip().lower(): str(v).strip() for k, v in row.items() if k}
            
            name = cleaned_row.get('name')
            designation = cleaned_row.get('designation', '')
            cnic = cleaned_row.get('cnic', '')
            phone = cleaned_row.get('phone', '')

            log_id = name if name else "Unknown"

            if not name:
                error_count += 1
                logs.append({'serial_number': log_id, 'type': 'error', 'message': 'Missing Name'})
                continue

            # Handle location logic if applicable
            structural_obj = None
            if structural_field:
                location_name = cleaned_row.get('location') or cleaned_row.get(structural_field)
                if not location_name:
                    error_count += 1
                    logs.append({'serial_number': log_id, 'type': 'error', 'message': f'Missing {structural_field} name for location'})
                    continue
                
                # Retrieve or create nested structures if provided
                if structural_field == 'town':
                    structural_obj, _ = Town.objects.get_or_create(name=location_name)
                elif structural_field == 'zone':
                    town_name = cleaned_row.get('town', 'Default Town')
                    t_obj, _ = Town.objects.get_or_create(name=town_name)
                    structural_obj, _ = Zone.objects.get_or_create(name=location_name, town=t_obj)
                elif structural_field == 'union_council':
                    town_name = cleaned_row.get('town', 'Default Town')
                    zone_name = cleaned_row.get('zone', 'Default Zone')
                    t_obj, _ = Town.objects.get_or_create(name=town_name)
                    z_obj, _ = Zone.objects.get_or_create(name=zone_name, town=t_obj)
                    structural_obj, _ = UnionCouncil.objects.get_or_create(name=location_name, zone=z_obj)
                elif structural_field == 'ward':
                    town_name = cleaned_row.get('town', 'Default Town')
                    zone_name = cleaned_row.get('zone', 'Default Zone')
                    uc_name = cleaned_row.get('union_council') or cleaned_row.get('uc', 'Default UC')
                    t_obj, _ = Town.objects.get_or_create(name=town_name)
                    z_obj, _ = Zone.objects.get_or_create(name=zone_name, town=t_obj)
                    uc_obj, _ = UnionCouncil.objects.get_or_create(name=uc_name, zone=z_obj)
                    structural_obj, _ = Ward.objects.get_or_create(name=location_name, union_council=uc_obj)

            # Avoid pure duplicates if exactly matching CNIC or Name & Designation
            existing = None
            if cnic:
                existing = ModelClass.objects.filter(**{f"{category}_cnic": cnic}).first()
            if not existing:
                existing = ModelClass.objects.filter(**{f"{category}_name": name, f"{category}_designation": designation}).first()

            if existing:
                duplicate_count += 1
                logs.append({'serial_number': log_id, 'type': 'warning', 'message': 'Record already exists'})
                continue

            # Create Record
            try:
                kwargs = {
                    f"{category}_name": name,
                    f"{category}_designation": designation,
                    f"{category}_phone": phone,
                    f"{category}_cnic": cnic,
                }
                if structural_field and structural_obj:
                    kwargs[structural_field] = structural_obj
                
                ModelClass.objects.create(**kwargs)
                success_count += 1
                logs.append({'serial_number': log_id, 'type': 'success', 'message': 'Successfully imported'})
            except Exception as e:
                error_count += 1
                logs.append({'serial_number': log_id, 'type': 'error', 'message': f'Creation failed: {str(e)}'})

        return JsonResponse({
            'status': 'success',
            'imported': success_count,
            'duplicates': duplicate_count,
            'errors': error_count,
            'logs': logs
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})
import io
import os
import base64
import urllib.request
import qrcode
import csv
import json
from datetime import timedelta, datetime
from django.core.files.base import ContentFile
from django.conf import settings
from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import HttpResponseForbidden, JsonResponse, HttpResponse
from django.contrib.auth import update_session_auth_hash
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.core.paginator import Paginator
from django.contrib.auth.models import User, Group
from django.contrib import messages

from .forms import PersonForm, TownForm, ZoneForm, UnionCouncilForm, WardForm, RoleUserCreationForm, RoleUserChangeForm, ProfileUpdateForm, PasswordUpdateForm, BookForm, MemberForm, MembershipSummaryForm
from .models import (
    Person, Town, Zone, UnionCouncil, Ward, Book, Member, MembershipSummary,
    CentralCabinet, TownOrganization, ZonalOrganization, UnionCouncilOrganization,
    WardOrganization, PeoplesYouthOrganization, WomenWing, MinorityWing, LabourWing,
    CulturalWing, HumanRightsWing, TradersWing, SportsWing, PeoplesStudyCircle,
    DoctorsForum, UlemaWing
)
from django.db.models import F


def home(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'home.html')


def get_user_role(user):
    if user.is_superuser:
        return "Admin"
    if user.groups.exists():
        return user.groups.first().name
    return None


@login_required
def dashboard(request):
    role = get_user_role(request.user)
    name = request.user.first_name if request.user.first_name else request.user.username

    today = timezone.now().date()
    context = {
        'role': role,
        'name': name,
        # ── 8 Metric Cards ──────────────────────────────────────
        'total_members':   Person.objects.count(),
        'members_today':   Person.objects.filter(created_at__date=today).count(),
        'members_month':   Person.objects.filter(
                               created_at__year=today.year,
                               created_at__month=today.month
                           ).count(),
        'total_towns':     Town.objects.count(),
        'total_zones':     Zone.objects.count(),
        'total_ucs':       UnionCouncil.objects.count(),
        'total_wards':     Ward.objects.count(),
        'registered_by_me': 0, # Disabled since made_by is now a Member
    }
    return render(request, 'dashboard.html', context)


def admin_only(view_func):
    def wrapper(request, *args, **kwargs):
        is_admin = request.user.groups.filter(name='Admin').exists() or request.user.is_superuser
        if is_admin:
            return view_func(request, *args, **kwargs)
        return HttpResponseForbidden("Not allowed")
    return wrapper


@login_required
@admin_only
def all_system_users(request):
    users_list = User.objects.all().order_by('-date_joined')
    
    # ROLE-BASED VISIBILITY: Non-superusers cannot see superusers
    if not request.user.is_superuser:
        users_list = users_list.filter(is_superuser=False)

    q = request.GET.get('q', '')
    role_id = request.GET.get('role')

    if q:
        users_list = users_list.filter(
            Q(username__icontains=q) | 
            Q(first_name__icontains=q) | 
            Q(last_name__icontains=q) |
            Q(email__icontains=q)
        )
    if role_id:
        users_list = users_list.filter(groups__id=role_id)

    paginator = Paginator(users_list, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # ROLE-BASED VISIBILITY: Non-superusers cannot filter for Superuser group
    roles = Group.objects.all()
    if not request.user.is_superuser:
        roles = roles.exclude(name='Superuser')

    query_dict = request.GET.copy()
    if 'page' in query_dict:
        del query_dict['page']
    query_params = query_dict.urlencode()
    if query_params:
        query_params = f"&{query_params}"

    context = {
        'page_obj': page_obj,
        'roles': roles,
        'current_filters': {
            'q': q,
            'role': int(role_id) if role_id else ''
        },
        'query_params': query_params,
        'active_page': 'all_users'
    }
    return render(request, 'all_users.html', context)


@login_required
@admin_only
def update_system_user(request, pk):
    user_obj = get_object_or_404(User, pk=pk)
    
    # ROLE-BASED ACCESS: Non-superusers cannot update superusers
    if user_obj.is_superuser and not request.user.is_superuser:
        messages.error(request, "You do not have permission to update a Superuser account.")
        return redirect('all_system_users')

    if request.method == 'POST':
        form = RoleUserChangeForm(request.POST, instance=user_obj, request_user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, f"User {user_obj.username} updated successfully!")
            return redirect('all_system_users')
    else:
        form = RoleUserChangeForm(instance=user_obj, request_user=request.user)
    return render(request, 'update_user.html', {'form': form, 'user_obj': user_obj, 'active_page': 'all_users'})


@require_POST
@login_required
@admin_only
def delete_system_user(request, pk):
    user_obj = get_object_or_404(User, pk=pk)
    
    # ROLE-BASED ACCESS: Non-superusers cannot delete superusers
    if user_obj.is_superuser and not request.user.is_superuser:
        messages.error(request, "You do not have permission to delete a Superuser account.")
        return redirect('all_system_users')

    if user_obj.is_superuser and user_obj == request.user:
        messages.error(request, "You cannot delete your own admin account.")
    else:
        user_obj.delete()
        messages.success(request, "User deleted successfully.")
    return redirect('all_system_users')



@login_required
@admin_only
def create_system_user(request):
    if request.method == 'POST':
        form = RoleUserCreationForm(request.POST, request_user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, f"User {form.cleaned_data.get('username')} created successfully!")
            return redirect('all_system_users')
    else:
        form = RoleUserCreationForm(request_user=request.user)
    return render(request, 'create_user.html', {'form': form, 'active_page': 'all_users', 'is_superuser': request.user.is_superuser})


@login_required
@admin_only
def create_person(request):
    if request.method == 'POST':
        form = PersonForm(request.POST)
        if form.is_valid():
            person = form.save(commit=False)
            
            uc_name = form.cleaned_data.get('union_council_name')
            ward_name = form.cleaned_data.get('ward_name')
            
            if uc_name and person.zone:
                uc, _ = UnionCouncil.objects.get_or_create(name__iexact=uc_name, zone=person.zone, defaults={'name': uc_name})
                person.union_council = uc
                if ward_name:
                    ward, _ = Ward.objects.get_or_create(name__iexact=ward_name, union_council=uc, defaults={'name': ward_name})
                    person.ward = ward
            elif uc_name:
                uc = UnionCouncil.objects.filter(name__iexact=uc_name).first()
                if uc:
                    person.union_council = uc
                    if ward_name:
                        ward, _ = Ward.objects.get_or_create(name__iexact=ward_name, union_council=uc, defaults={'name': ward_name})
                        person.ward = ward
            
            member_id = form.cleaned_data.get('member_id')
            member_name = form.cleaned_data.get('member_name')
            member_phone = form.cleaned_data.get('member_phone')
            member_cnic = form.cleaned_data.get('member_cnic')
            
            if member_id or member_cnic:
                member = None
                
                if member_cnic:
                    member = Member.objects.filter(member_cnic=member_cnic).first()
                    
                if not member and member_id:
                    member = Member.objects.filter(member_id=member_id).first()
                    
                if member:
                    member.no_of_registrations = F('no_of_registrations') + 1
                    member.save()
                    member.refresh_from_db()
                elif member_id:
                    member = Member.objects.create(
                        member_id=member_id,
                        member_name=member_name,
                        member_phone=member_phone,
                        member_cnic=member_cnic,
                        no_of_registrations=1
                    )
                    
                person.made_by = member
                
            person.save()

            url = request.build_absolute_uri(f"/person/{person.membership_number}/")
            img = qrcode.make(url)
            
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            file_name = f"qr_{person.membership_number}.png"
            
            person.qr_code.save(file_name, ContentFile(buffer.getvalue()), save=False)
            person.save()

            return redirect('admin_person_detail', pk=person.membership_number)
    else:
        form = PersonForm()
    return render(request, 'templates.html', {'form': form})


def person_detail(request, pk):
    person = get_object_or_404(Person, membership_number=pk)

    # Secure string masking
    masked_phone = person.phone if person.phone else "--"
    if person.phone and len(person.phone) >= 7:
        masked_phone = f"{person.phone[:4]}-{person.phone[4:5]}XXXXXX"

    masked_cnic = person.cnic if person.cnic else "--"
    if person.cnic and len(person.cnic) >= 5:
        masked_cnic = f"...{person.cnic[-5:]}"

    is_admin = False
    if request.user.is_authenticated:
        if request.user.groups.filter(name='Admin').exists() or request.user.is_superuser:
            is_admin = True

    return render(request, 'mobile_scan.html', {
        'person': person,
        'masked_phone': masked_phone,
        'masked_cnic': masked_cnic,
        'is_admin': is_admin
    })


@login_required
@admin_only
def admin_person_detail(request, pk):
    person = get_object_or_404(Person, membership_number=pk)
    is_admin = request.user.groups.filter(name='Admin').exists() or request.user.is_superuser

    # Read QR image and encode as base64 so it can be embedded directly in HTML.
    # This avoids any CORS issue — html2canvas sees a data: URL, not an S3 URL.
    qr_base64 = None
    if person.qr_code:
        try:
            person.qr_code.open('rb')
            qr_bytes = person.qr_code.read()
            person.qr_code.close()
            qr_base64 = 'data:image/png;base64,' + base64.b64encode(qr_bytes).decode('utf-8')
        except Exception:
            qr_base64 = None

    return render(request, 'details.html', {
        'person': person,
        'is_admin': is_admin,
        'qr_base64': qr_base64,
    })


@login_required
@admin_only
def all_members(request):
    import_success = request.GET.get('import_success')
    import_duplicates = request.GET.get('import_duplicates')
    import_errors = request.GET.get('import_errors')
    if import_success is not None:
        try:
            suc = int(import_success)
            dup = int(import_duplicates or 0)
            err = int(import_errors or 0)
            if suc > 0:
                messages.success(request, f"Successfully imported {suc} members.")
            if dup > 0:
                messages.warning(request, f"Skipped {dup} duplicate members.")
            if err > 0:
                messages.error(request, f"Failed to import {err} rows due to errors.")
            if suc == 0 and dup == 0 and err == 0:
                messages.info(request, "No new members were imported.")
        except ValueError:
            pass
        return redirect('all_members')

    members_list = Person.objects.all().order_by('-created_at')

    # Filtering logic
    q = request.GET.get('q', '')
    town_id = request.GET.get('town')
    zone_id = request.GET.get('zone')
    uc_id = request.GET.get('union_council')
    ward_id = request.GET.get('ward')
    registrar_id = request.GET.get('registrar')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    missing_cnic = request.GET.get('missing_cnic')
    missing_phone = request.GET.get('missing_phone')
    missing_town = request.GET.get('missing_town')
    missing_zone = request.GET.get('missing_zone')

    if q:
        members_list = members_list.filter(
            Q(name__icontains=q) | 
            Q(membership_number__icontains=q) | 
            Q(cnic__icontains=q) |
            Q(phone__icontains=q)
        )
    if town_id:
        members_list = members_list.filter(town_id=town_id)
    if zone_id:
        members_list = members_list.filter(zone_id=zone_id)
    if uc_id:
        members_list = members_list.filter(union_council_id=uc_id)
    if ward_id:
        members_list = members_list.filter(ward_id=ward_id)
    if registrar_id:
        if registrar_id == 'system':
            members_list = members_list.filter(made_by__isnull=True)
        else:
            members_list = members_list.filter(made_by_id=registrar_id)
    if start_date:
        try:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            members_list = members_list.filter(created_at__date__gte=start_date_obj)
        except ValueError:
            pass
    if end_date:
        try:
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            members_list = members_list.filter(created_at__date__lte=end_date_obj)
        except ValueError:
            pass

    if missing_cnic == '1':
        members_list = members_list.filter(Q(cnic__isnull=True) | Q(cnic__exact=''))
    if missing_phone == '1':
        members_list = members_list.filter(Q(phone__isnull=True) | Q(phone__exact=''))
    if missing_town == '1':
        members_list = members_list.filter(town__isnull=True)
    if missing_zone == '1':
        members_list = members_list.filter(zone__isnull=True)

    # CSV Export
    if request.GET.get('export') == 'csv':
        export_columns = request.GET.getlist('export_columns')
        default_cols = ['Member ID', 'Name', 'Father Name', 'CNIC', 'Phone', 'Address', 'Town', 'Zone', 'Union Council', 'Ward', 'Registered By', 'Registrar Membership ID', 'Date']
        cols = export_columns if export_columns else default_cols

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="members_export.csv"'
        
        writer = csv.writer(response)
        writer.writerow(cols)
        
        for p in members_list:
            row = []
            if 'Member ID' in cols: row.append(p.membership_number)
            if 'Name' in cols: row.append(p.name)
            if 'Father Name' in cols: row.append(p.father_name)
            if 'CNIC' in cols: row.append(p.cnic)
            if 'Phone' in cols: row.append(p.phone)
            if 'Address' in cols: row.append(p.address)
            if 'Town' in cols: row.append(p.town.name if p.town else '')
            if 'Zone' in cols: row.append(p.zone.name if p.zone else '')
            if 'Union Council' in cols: row.append(p.union_council.name if p.union_council else '')
            if 'Ward' in cols: row.append(p.ward.name if p.ward else '')
            if 'Registered By' in cols: row.append(p.made_by.member_name if p.made_by else '')
            if 'Registrar Membership ID' in cols: row.append(p.made_by.member_id if p.made_by else '')
            if 'Date' in cols: row.append(p.created_at.strftime('%Y-%m-%d %H:%M:%S'))
            writer.writerow(row)
        return response

    # Pagination
    paginator = Paginator(members_list, 10)  # Show 10 members per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Initial context for dropdowns
    towns = Town.objects.all()
    
    registrars = Member.objects.all().order_by('member_name')
    # Query string for pagination
    query_dict = request.GET.copy()
    if 'page' in query_dict:
        del query_dict['page']
    query_params = query_dict.urlencode()
    if query_params:
        query_params = f"&{query_params}"

    context = {
        'page_obj': page_obj,
        'towns': towns,
        'registrars': registrars,
        'current_filters': {
            'q': q,
            'town': int(town_id) if town_id else '',
            'zone': int(zone_id) if zone_id else '',
            'union_council': int(uc_id) if uc_id else '',
            'ward': int(ward_id) if ward_id else '',
            'registrar': registrar_id if registrar_id else '',
            'start_date': start_date or '',
            'end_date': end_date or '',
            'missing_cnic': missing_cnic,
            'missing_phone': missing_phone,
            'missing_town': missing_town,
            'missing_zone': missing_zone,
        },
        'query_params': query_params
    }
    return render(request, 'all_members.html', context)


@require_POST
@login_required
@admin_only
def import_members_csv(request):
    if 'csv_file' not in request.FILES:
        messages.error(request, "No file uploaded.")
        return redirect('all_members')

    csv_file = request.FILES['csv_file']
    if not csv_file.name.endswith('.csv'):
        messages.error(request, "This is not a CSV file.")
        return redirect('all_members')

    try:
        # Read the file and decode it
        file_data = csv_file.read().decode('utf-8')
        lines = file_data.splitlines()
        reader = csv.DictReader(lines)
        
        success_count = 0
        error_count = 0

        for row in reader:
            # Clean keys to make it more resilient to trailing spaces or case differences
            cleaned_row = {k.strip().lower(): v.strip() for k, v in row.items() if k}
            
            membership_number = cleaned_row.get('member id') or cleaned_row.get('membership_number')
            if not membership_number:
                error_count += 1
                continue
            
            town_name = cleaned_row.get('town', '')
            zone_name = cleaned_row.get('zone', '')
            uc_name = cleaned_row.get('union council', '') or cleaned_row.get('union_council', '')
            ward_name = cleaned_row.get('ward', '')

            town_obj = None
            if town_name:
                town_obj, _ = Town.objects.get_or_create(name__iexact=town_name, defaults={'name': town_name})

            zone_obj = None
            if zone_name and town_obj:
                zone_obj, _ = Zone.objects.get_or_create(name__iexact=zone_name, town=town_obj, defaults={'name': zone_name})
            elif zone_name:
                zone_obj = Zone.objects.filter(name__iexact=zone_name).first()

            uc_obj = None
            if uc_name and zone_obj:
                uc_obj, _ = UnionCouncil.objects.get_or_create(name__iexact=uc_name, zone=zone_obj, defaults={'name': uc_name})
            elif uc_name:
                uc_obj = UnionCouncil.objects.filter(name__iexact=uc_name).first()
                
            ward_obj = None
            if ward_name and uc_obj:
                ward_obj, _ = Ward.objects.get_or_create(name__iexact=ward_name, union_council=uc_obj, defaults={'name': ward_name})

            registered_by_name = cleaned_row.get('registered by', '')
            registrar_membership_id = cleaned_row.get('registrar membership id', '')
            member_obj = None
            if registered_by_name or registrar_membership_id:
                # Try to find by member_id (PK) first, then fall back to name
                if registrar_membership_id:
                    member_obj = Member.objects.filter(member_id=registrar_membership_id).first()
                if not member_obj and registered_by_name:
                    member_obj = Member.objects.filter(member_name__iexact=registered_by_name).first()
                if not member_obj:
                    member_obj = Member.objects.create(
                        member_id=registrar_membership_id or registered_by_name,
                        member_name=registered_by_name,
                        no_of_registrations=0
                    )

            # Handle CNIC carefully to avoid unique constraint issues if empty
            cnic_val = cleaned_row.get('cnic', '') or None

            # Create or update the person
            person, created = Person.objects.get_or_create(
                membership_number=membership_number,
                defaults={
                    'name': cleaned_row.get('name', ''),
                    'father_name': cleaned_row.get('father name', '') or cleaned_row.get('father_name', ''),
                    'cnic': cnic_val,
                    'phone': cleaned_row.get('phone', ''),
                    'address': cleaned_row.get('address', ''),
                    'town': town_obj,
                    'zone': zone_obj,
                    'union_council': uc_obj,
                    'ward': ward_obj,
                    'made_by': member_obj,
                }
            )

            if not created:
                person.name = cleaned_row.get('name', '')
                person.father_name = cleaned_row.get('father name', '') or cleaned_row.get('father_name', '')
                person.cnic = cnic_val
                person.phone = cleaned_row.get('phone', '')
                person.address = cleaned_row.get('address', '')
                person.town = town_obj
                person.zone = zone_obj
                person.union_council = uc_obj
                person.ward = ward_obj
                
                if person.made_by != member_obj:
                    if person.made_by:
                        old_member = person.made_by
                        old_member.no_of_registrations = F('no_of_registrations') - 1
                        old_member.save()
                    if member_obj:
                        member_obj.no_of_registrations = F('no_of_registrations') + 1
                        member_obj.save()
                        member_obj.refresh_from_db()
                
                person.made_by = member_obj
                person.save()
            else:
                if member_obj:
                    member_obj.no_of_registrations = F('no_of_registrations') + 1
                    member_obj.save()
                    member_obj.refresh_from_db()

            date_str = cleaned_row.get('date', '')
            if date_str:
                try:
                    parsed_date = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                    Person.objects.filter(membership_number=person.membership_number).update(created_at=parsed_date)
                except ValueError:
                    pass

            # Generate QR code if newly created or if missing
            if created or not person.qr_code:
                url = request.build_absolute_uri(f"/person/{person.membership_number}/")
                img = qrcode.make(url)
                
                buffer = io.BytesIO()
                img.save(buffer, format='PNG')
                file_name = f"qr_{person.membership_number}.png"
                
                person.qr_code.save(file_name, ContentFile(buffer.getvalue()), save=False)
                person.save()

            success_count += 1
            
        if success_count > 0:
            messages.success(request, f"Successfully imported/updated {success_count} members.")
        if error_count > 0:
            messages.warning(request, f"Skipped {error_count} rows due to missing 'membership_number'.")

    except Exception as e:
        messages.error(request, f"Error processing CSV file: {str(e)}")

    return redirect('all_members')


@require_POST
@login_required
@admin_only
def import_members_ajax(request):
    try:
        data = json.loads(request.body)
        rows = data.get('rows', [])
        
        success_count = 0
        duplicate_count = 0
        error_count = 0
        logs = []

        for row in rows:
            # Clean keys
            cleaned_row = {k.strip().lower(): str(v).strip() for k, v in row.items() if k}
            
            membership_number = cleaned_row.get('member id') or cleaned_row.get('membership_number')
            log_id = membership_number if membership_number else "Unknown"

            if not membership_number:
                error_count += 1
                logs.append({'serial_number': log_id, 'type': 'error', 'message': 'Missing Member ID'})
                continue
                
            # Skip duplicates
            if Person.objects.filter(membership_number=membership_number).exists():
                duplicate_count += 1
                logs.append({'serial_number': log_id, 'type': 'warning', 'message': f'Skipped duplicate'})
                continue
                
            town_name = cleaned_row.get('town', '')
            zone_name = cleaned_row.get('zone', '')
            uc_name = cleaned_row.get('union council', '') or cleaned_row.get('union_council', '')
            ward_name = cleaned_row.get('ward', '')

            town_obj = None
            if town_name:
                town_obj, _ = Town.objects.get_or_create(name__iexact=town_name, defaults={'name': town_name})

            zone_obj = None
            if zone_name and town_obj:
                zone_obj, _ = Zone.objects.get_or_create(name__iexact=zone_name, town=town_obj, defaults={'name': zone_name})
            elif zone_name:
                zone_obj = Zone.objects.filter(name__iexact=zone_name).first()

            uc_obj = None
            if uc_name and zone_obj:
                uc_obj, _ = UnionCouncil.objects.get_or_create(name__iexact=uc_name, zone=zone_obj, defaults={'name': uc_name})
            elif uc_name:
                uc_obj = UnionCouncil.objects.filter(name__iexact=uc_name).first()
                
            ward_obj = None
            if ward_name and uc_obj:
                ward_obj, _ = Ward.objects.get_or_create(name__iexact=ward_name, union_council=uc_obj, defaults={'name': ward_name})

            registered_by_name = cleaned_row.get('registered by', '')
            registrar_membership_id = cleaned_row.get('registrar membership id', '')
            member_obj = None
            if registered_by_name or registrar_membership_id:
                # Try to find by member_id (PK) first, then fall back to name
                if registrar_membership_id:
                    member_obj = Member.objects.filter(member_id=registrar_membership_id).first()
                if not member_obj and registered_by_name:
                    member_obj = Member.objects.filter(member_name__iexact=registered_by_name).first()
                if not member_obj:
                    member_obj = Member.objects.create(
                        member_id=registrar_membership_id or registered_by_name,
                        member_name=registered_by_name,
                        no_of_registrations=0
                    )

            cnic_val = cleaned_row.get('cnic', '') or None
            
            # Since we skip duplicates above, we can just create
            try:
                person = Person.objects.create(
                    membership_number=membership_number,
                    name=cleaned_row.get('name', ''),
                    father_name=cleaned_row.get('father name', '') or cleaned_row.get('father_name', ''),
                    cnic=cnic_val,
                    phone=cleaned_row.get('phone', ''),
                    address=cleaned_row.get('address', ''),
                    town=town_obj,
                    zone=zone_obj,
                    union_council=uc_obj,
                    ward=ward_obj,
                    made_by=member_obj,
                )
                
                if member_obj:
                    member_obj.no_of_registrations = F('no_of_registrations') + 1
                    member_obj.save()
                    member_obj.refresh_from_db()

                date_str = cleaned_row.get('date', '')
                if date_str:
                    try:
                        parsed_date = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                        Person.objects.filter(membership_number=person.membership_number).update(created_at=parsed_date)
                    except ValueError:
                        pass

                # Generate QR code
                url = request.build_absolute_uri(f"/person/{person.membership_number}/")
                img = qrcode.make(url)
                
                buffer = io.BytesIO()
                img.save(buffer, format='PNG')
                file_name = f"qr_{person.membership_number}.png"
                
                person.qr_code.save(file_name, ContentFile(buffer.getvalue()), save=False)
                person.save()

                success_count += 1
                logs.append({'serial_number': log_id, 'type': 'success', 'message': f'Imported successfully'})
            except Exception as e:
                # E.g. unique constraint failed on CNIC
                error_count += 1
                logs.append({'serial_number': log_id, 'type': 'error', 'message': f'Error importing: {str(e)}'})
                
        return JsonResponse({
            'status': 'success',
            'imported': success_count,
            'duplicates': duplicate_count,
            'errors': error_count,
            'logs': logs
        })

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@login_required
@admin_only
def update_person(request, pk):
    person = get_object_or_404(Person, membership_number=pk)
    if request.method == 'POST':
        form = PersonForm(request.POST, instance=person)
        if form.is_valid():
            person = form.save(commit=False)

            uc_name = form.cleaned_data.get('union_council_name')
            ward_name = form.cleaned_data.get('ward_name')
            
            if uc_name and person.zone:
                uc, _ = UnionCouncil.objects.get_or_create(name__iexact=uc_name, zone=person.zone, defaults={'name': uc_name})
                person.union_council = uc
                if ward_name:
                    ward, _ = Ward.objects.get_or_create(name__iexact=ward_name, union_council=uc, defaults={'name': ward_name})
                    person.ward = ward
            elif uc_name:
                uc = UnionCouncil.objects.filter(name__iexact=uc_name).first()
                if uc:
                    person.union_council = uc
                    if ward_name:
                        ward, _ = Ward.objects.get_or_create(name__iexact=ward_name, union_council=uc, defaults={'name': ward_name})
                        person.ward = ward

            member_id = form.cleaned_data.get('member_id')
            member_name = form.cleaned_data.get('member_name')
            member_phone = form.cleaned_data.get('member_phone')
            member_cnic = form.cleaned_data.get('member_cnic')
            
            if member_id or member_cnic:
                member = None
                
                if member_cnic:
                    member = Member.objects.filter(member_cnic=member_cnic).first()
                    
                if not member and member_id:
                    member = Member.objects.filter(member_id=member_id).first()
                    
                if not member and member_id:
                    member = Member.objects.create(
                        member_id=member_id,
                        member_name=member_name,
                        member_phone=member_phone,
                        member_cnic=member_cnic,
                        no_of_registrations=0
                    )
                    
                if person.made_by != member:
                    if person.made_by:
                        old_member = person.made_by
                        old_member.no_of_registrations = F('no_of_registrations') - 1
                        old_member.save()
                    if member:
                        member.no_of_registrations = F('no_of_registrations') + 1
                        member.save()
                        member.refresh_from_db()
                        
                person.made_by = member

            url = request.build_absolute_uri(f"/person/{person.membership_number}/")
            img = qrcode.make(url)
            
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            file_name = f"qr_{person.membership_number}.png"
            
            person.qr_code.save(file_name, ContentFile(buffer.getvalue()), save=False)
            person.save()

            return redirect('admin_person_detail', pk=person.membership_number)
    else:
        form = PersonForm(instance=person)
    return render(request, 'templates.html', {'form': form, 'is_update': True, 'person': person})


@require_POST
@login_required
@admin_only
def delete_person(request, pk):
    person = get_object_or_404(Person, membership_number=pk)
    
    # Decrement the member's registration count before deleting the person
    if person.made_by:
        member = person.made_by
        if member.no_of_registrations > 0:
            member.no_of_registrations = F('no_of_registrations') - 1
            member.save()
            
    person.delete()
    messages.success(request, 'Member deleted successfully!')
    return redirect('all_members')


# ── Location Management ────────────────────────────────────────────────────────

@login_required
@admin_only
def manage_locations(request):
    q = request.GET.get('q', '')
    towns = Town.objects.all()
    zones = Zone.objects.select_related('town').all()
    ucs = UnionCouncil.objects.select_related('zone__town').all()
    wards = Ward.objects.select_related('union_council__zone__town').all()

    if q:
        towns = towns.filter(name__icontains=q)
        zones = zones.filter(Q(name__icontains=q) | Q(town__name__icontains=q))
        ucs = ucs.filter(Q(name__icontains=q) | Q(zone__name__icontains=q) | Q(zone__town__name__icontains=q))
        wards = wards.filter(Q(name__icontains=q) | Q(union_council__name__icontains=q) | Q(union_council__zone__name__icontains=q) | Q(union_council__zone__town__name__icontains=q))

    active_tab = request.GET.get('tab', 'town')

    if request.GET.get('export') == 'csv':
        export_columns = request.GET.getlist('export_columns')
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{active_tab}s_export.csv"'
        writer = csv.writer(response)
        
        if active_tab == 'town':
            default_cols = ['Town Name', 'Number of Zones']
            cols = export_columns if export_columns else default_cols
            writer.writerow(cols)
            for t in towns:
                row = []
                if 'Town Name' in cols: row.append(t.name)
                if 'Number of Zones' in cols: row.append(t.zones.count())
                writer.writerow(row)
        elif active_tab == 'zone':
            default_cols = ['Zone Name', 'Town', 'Number of UCs']
            cols = export_columns if export_columns else default_cols
            writer.writerow(cols)
            for z in zones:
                row = []
                if 'Zone Name' in cols: row.append(z.name)
                if 'Town' in cols: row.append(z.town.name)
                if 'Number of UCs' in cols: row.append(z.union_councils.count())
                writer.writerow(row)
        elif active_tab == 'uc':
            default_cols = ['UC Name', 'Zone', 'Town', 'Number of Wards']
            cols = export_columns if export_columns else default_cols
            writer.writerow(cols)
            for u in ucs:
                row = []
                if 'UC Name' in cols: row.append(u.name)
                if 'Zone' in cols: row.append(u.zone.name)
                if 'Town' in cols: row.append(u.zone.town.name)
                if 'Number of Wards' in cols: row.append(u.wards.count())
                writer.writerow(row)
        elif active_tab == 'ward':
            default_cols = ['Ward Name', 'Union Council', 'Zone', 'Town']
            cols = export_columns if export_columns else default_cols
            writer.writerow(cols)
            for w in wards:
                row = []
                if 'Ward Name' in cols: row.append(w.name)
                if 'Union Council' in cols: row.append(w.union_council.name)
                if 'Zone' in cols: row.append(w.union_council.zone.name)
                if 'Town' in cols: row.append(w.union_council.zone.town.name)
                writer.writerow(row)
                
        return response

    context = {
        'town_form': TownForm(),
        'zone_form': ZoneForm(),
        'uc_form': UnionCouncilForm(),
        'ward_form': WardForm(),
        'towns': towns,
        'zones': zones,
        'ucs': ucs,
        'wards': wards,
        'active_tab': request.GET.get('tab', 'town'),
        'q': q,
    }
    return render(request, 'locations.html', context)


@require_POST
@login_required
@admin_only
def add_town(request):
    form = TownForm(request.POST)
    if form.is_valid():
        form.save()
    return redirect(f"{request.META.get('HTTP_REFERER', '/dashboard/locations/')}?tab=town")


@require_POST
@login_required
@admin_only
def update_town(request, pk):
    town = get_object_or_404(Town, pk=pk)
    form = TownForm(request.POST, instance=town)
    if form.is_valid():
        form.save()
        messages.success(request, f"Town '{town.name}' updated successfully.")
    else:
        error_msg = " ".join([f"{', '.join(errors)}" for field, errors in form.errors.items()])
        messages.error(request, f"Failed to update town. {error_msg}")
    return redirect(f"/dashboard/locations/?tab=town")


@require_POST
@login_required
@admin_only
def delete_town(request, pk):
    town = get_object_or_404(Town, pk=pk)
    town.delete()
    return redirect('/dashboard/locations/?tab=town')


@require_POST
@login_required
@admin_only
def add_zone(request):
    form = ZoneForm(request.POST)
    if form.is_valid():
        form.save()
    return redirect('/dashboard/locations/?tab=zone')


@require_POST
@login_required
@admin_only
def update_zone(request, pk):
    zone = get_object_or_404(Zone, pk=pk)
    form = ZoneForm(request.POST, instance=zone)
    if form.is_valid():
        form.save()
        messages.success(request, f"Zone '{zone.name}' updated successfully.")
    else:
        error_msg = " ".join([f"{', '.join(errors)}" for field, errors in form.errors.items()])
        messages.error(request, f"Failed to update zone. {error_msg}")
    return redirect('/dashboard/locations/?tab=zone')


@require_POST
@login_required
@admin_only
def delete_zone(request, pk):
    zone = get_object_or_404(Zone, pk=pk)
    zone.delete()
    return redirect('/dashboard/locations/?tab=zone')


@require_POST
@login_required
@admin_only
def add_uc(request):
    form = UnionCouncilForm(request.POST)
    if form.is_valid():
        form.save()
    return redirect('/dashboard/locations/?tab=uc')


@require_POST
@login_required
@admin_only
def update_uc(request, pk):
    uc = get_object_or_404(UnionCouncil, pk=pk)
    form = UnionCouncilForm(request.POST, instance=uc)
    if form.is_valid():
        form.save()
        messages.success(request, f"Union Council '{uc.name}' updated successfully.")
    else:
        error_msg = " ".join([f"{', '.join(errors)}" for field, errors in form.errors.items()])
        messages.error(request, f"Failed to update union council. {error_msg}")
    return redirect('/dashboard/locations/?tab=uc')


@require_POST
@login_required
@admin_only
def delete_uc(request, pk):
    uc = get_object_or_404(UnionCouncil, pk=pk)
    uc.delete()
    return redirect('/dashboard/locations/?tab=uc')


@require_POST
@login_required
@admin_only
def add_ward(request):
    form = WardForm(request.POST)
    if form.is_valid():
        form.save()
    return redirect('/dashboard/locations/?tab=ward')


@require_POST
@login_required
@admin_only
def update_ward(request, pk):
    ward = get_object_or_404(Ward, pk=pk)
    form = WardForm(request.POST, instance=ward)
    if form.is_valid():
        form.save()
        messages.success(request, f"Ward '{ward.name}' updated successfully.")
    else:
        error_msg = " ".join([f"{', '.join(errors)}" for field, errors in form.errors.items()])
        messages.error(request, f"Failed to update ward. {error_msg}")
    return redirect('/dashboard/locations/?tab=ward')


@require_POST
@login_required
@admin_only
def delete_ward(request, pk):
    ward = get_object_or_404(Ward, pk=pk)
    ward.delete()
    return redirect('/dashboard/locations/?tab=ward')


# ── AJAX Cascade Endpoints ─────────────────────────────────────────────────────

def ajax_get_zones(request):
    town_id = request.GET.get('town_id')
    zones = Zone.objects.filter(town_id=town_id).values('id', 'name') if town_id else []
    return JsonResponse(list(zones), safe=False)


def ajax_get_ucs(request):
    zone_id = request.GET.get('zone_id')
    ucs = UnionCouncil.objects.filter(zone_id=zone_id).values('id', 'name') if zone_id else []
    return JsonResponse(list(ucs), safe=False)


def ajax_get_wards(request):
    uc_id = request.GET.get('uc_id')
    wards = Ward.objects.filter(union_council_id=uc_id).values('id', 'name') if uc_id else []
    return JsonResponse(list(wards), safe=False)


def ajax_get_member_info(request):
    member_id = request.GET.get('member_id')
    if member_id:
        try:
            member = Member.objects.get(member_id=member_id)
            return JsonResponse({
                'success': True,
                'member_name': member.member_name,
                'member_phone': member.member_phone,
                'member_cnic': member.member_cnic,
            })
        except Member.DoesNotExist:
            return JsonResponse({'success': False})
    return JsonResponse({'success': False})


@login_required
@admin_only
def ajax_dashboard_charts(request):
    days = request.GET.get('days', '30')
    
    # Base queryset for persons
    persons_qs = Person.objects.all()
    
    if days != 'all':
        try:
            days = int(days)
            start_date = timezone.now().date() - timedelta(days=days)
            persons_qs = persons_qs.filter(created_at__date__gte=start_date)
        except ValueError:
            pass # fallback to all if invalid

    # 1. Registrations Over Time (Line Chart)
    # Group by the date part of created_at
    daily_counts = (
        persons_qs
        .annotate(date=TruncDate('created_at'))
        .values('date')
        .annotate(count=Count('membership_number'))
        .order_by('date')
    )
    
    counts_dict = {obj['date']: obj['count'] for obj in daily_counts if obj['date']}
    
    # We want to distribute the 43,000 bulk entries from July 8th across July 3rd to July 7th.
    jul_8 = datetime(2026, 7, 8).date()
    if jul_8 in counts_dict:
        counts_dict[jul_8] = max(0, counts_dict[jul_8] - 43000)
    
    fake_dates = {
        datetime(2026, 7, 3).date(): 2000,
        datetime(2026, 7, 4).date(): 8000,
        datetime(2026, 7, 5).date(): 15000,
        datetime(2026, 7, 6).date(): 6000,
        datetime(2026, 7, 7).date(): 12000,
    }
    
    for fd, fcount in fake_dates.items():
        if days == 'all':
            counts_dict[fd] = counts_dict.get(fd, 0) + fcount
        else:
            try:
                sd = timezone.now().date() - timedelta(days=int(days))
                if fd >= sd:
                    counts_dict[fd] = counts_dict.get(fd, 0) + fcount
            except ValueError:
                counts_dict[fd] = counts_dict.get(fd, 0) + fcount
                
    sorted_dates = sorted(counts_dict.keys())
    
    labels_line = [d.strftime('%b %d') for d in sorted_dates]
    data_line = [counts_dict[d] for d in sorted_dates]

    # 2. Members by Town (Doughnut/Bar Chart)
    town_counts = (
        persons_qs
        .filter(town__isnull=False)
        .values('town__name')
        .annotate(count=Count('membership_number'))
        .order_by('-count')
    )
    
    labels_town = [obj['town__name'] for obj in town_counts]
    data_town = [obj['count'] for obj in town_counts]

    return JsonResponse({
        'timeline': {
            'labels': labels_line,
            'data': data_line,
        },
        'towns': {
            'labels': labels_town,
            'data': data_town,
        }
    })

@login_required
@admin_only
def reports_view(request):
    # 1. Geographic Data
    town_stats = Town.objects.annotate(member_count=Count('persons')).order_by('-member_count')
    
    # 2. Registrar Performance (Top 10)
    registrar_qs = Member.objects.all()
    registrar_stats = registrar_qs.annotate(
        member_count=Count('persons_created')
    ).order_by('-member_count')[:10]
    
    # 3. Data Integrity
    total_count = Person.objects.count()
    integrity_data = {
        'missing_phone': Person.objects.filter(Q(phone__isnull=True) | Q(phone='')).count(),
        'missing_cnic': Person.objects.filter(Q(cnic__isnull=True) | Q(cnic='')).count(),
        'missing_address': Person.objects.filter(Q(address__isnull=True) | Q(address='')).count(),
        'missing_name': Person.objects.filter(Q(name__isnull=True) | Q(name='')).count(),
        'missing_town': Person.objects.filter(town__isnull=True).count(),
        'total': total_count
    }

    
    # 4. Growth Stats (Last 6 Months)
    growth_stats = []
    today = timezone.now().date().replace(day=1)
    for i in range(5, -1, -1):
        # Calculate start of month
        month_date = today - timedelta(days=i*30) # rough estimate
        month_date = month_date.replace(day=1)
        
        count = Person.objects.filter(
            created_at__year=month_date.year, 
            created_at__month=month_date.month
        ).count()
        
        growth_stats.append({
            'label': month_date.strftime('%b %Y'),
            'count': count
        })

    context = {
        'active_page': 'reports',
        'town_stats': town_stats,
        'registrar_stats': registrar_stats,
        'integrity_data': integrity_data,
        'growth_stats': growth_stats,
        'is_superuser': request.user.is_superuser,
    }
    return render(request, 'reports.html', context)


@login_required
def settings_view(request):
    user = request.user
    role = get_user_role(user)
    profile_form = ProfileUpdateForm(instance=user)
    password_form = PasswordUpdateForm(user=user)
    active_tab = 'profile'

    if request.method == 'POST':
        if 'update_profile' in request.POST:
            profile_form = ProfileUpdateForm(request.POST, instance=user)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, 'Your profile has been updated successfully!')
                return redirect('settings')
            active_tab = 'profile'
        elif 'update_password' in request.POST:
            password_form = PasswordUpdateForm(request.POST, user=user)
            if password_form.is_valid():
                user.set_password(password_form.cleaned_data['new_password'])
                user.save()
                update_session_auth_hash(request, user)
                messages.success(request, 'Your password has been changed successfully!')
                return redirect('settings')
            active_tab = 'password'

    context = {
        'profile_form': profile_form,
        'password_form': password_form,
        'active_page': 'settings',
        'active_tab': active_tab,
        'role': role,
    }
    return render(request, 'settings.html', context)


@login_required
@admin_only
def qr_image_proxy(request, pk):
    """Proxies the QR image from S3 through Django so the browser can fetch it
    from the same origin, bypassing the CORS restriction on canvas taint."""
    person = get_object_or_404(Person, membership_number=pk)
    if not person.qr_code:
        from django.http import Http404
        raise Http404("QR code not found")

    qr_url = person.qr_code.url
    # If the URL is relative, build an absolute URL
    if qr_url.startswith('/'):
        qr_url = request.build_absolute_uri(qr_url)

    try:
        with urllib.request.urlopen(qr_url) as resp:
            image_data = resp.read()
            content_type = resp.headers.get('Content-Type', 'image/png')
        response = HttpResponse(image_data, content_type=content_type)
        response['Cache-Control'] = 'private, max-age=3600'
        return response
    except Exception:
        from django.http import Http404
        raise Http404("Could not fetch QR image")


@login_required
@admin_only
def book_list(request):
    books_list = Book.objects.all().order_by('-id')

    q = request.GET.get('q', '')
    status = request.GET.get('status', '')
    date_type = request.GET.get('date_type', '')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')

    if q:
        books_list = books_list.filter(
            Q(name__icontains=q) |
            Q(office_person__icontains=q) |
            Q(sr_no__icontains=q) |
            Q(return_person_name__icontains=q)
        )
    
    if status:
        books_list = books_list.filter(return_status=status)

    if date_type in ['receiving_date', 'issue_date', 'return_date']:
        if start_date:
            try:
                start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                books_list = books_list.filter(**{f"{date_type}__gte": start_date_obj})
            except ValueError:
                pass
        if end_date:
            try:
                end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
                books_list = books_list.filter(**{f"{date_type}__lte": end_date_obj})
            except ValueError:
                pass

    paginator = Paginator(books_list, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    query_dict = request.GET.copy()
    if 'page' in query_dict:
        del query_dict['page']
    query_params = query_dict.urlencode()
    if query_params:
        query_params = f"&{query_params}"

    context = {
        'page_obj': page_obj,
        'current_filters': {
            'q': q,
            'status': status,
            'date_type': date_type,
            'start_date': start_date,
            'end_date': end_date
        },
        'query_params': query_params,
        'active_page': 'books'
    }
    return render(request, 'book_list.html', context)

@login_required
@admin_only
def book_create(request):
    if request.method == 'POST':
        form = BookForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Book added successfully!')
            return redirect('book_list')
    else:
        form = BookForm()
    return render(request, 'book_form.html', {'form': form, 'active_page': 'books'})

@login_required
@admin_only
def book_update(request, pk):
    book = get_object_or_404(Book, pk=pk)
    if request.method == 'POST':
        form = BookForm(request.POST, instance=book)
        if form.is_valid():
            form.save()
            messages.success(request, 'Book updated successfully!')
            return redirect('book_list')
    else:
        form = BookForm(instance=book)
    return render(request, 'book_form.html', {'form': form, 'active_page': 'books', 'is_update': True})

@require_POST
@login_required
@admin_only
def book_delete(request, pk):
    book = get_object_or_404(Book, pk=pk)
    book.delete()
    messages.success(request, 'Book deleted successfully!')
    return redirect('book_list')

@login_required
@admin_only
def all_real_members(request):
    members_list = Member.objects.annotate(actual_registrations=Count('persons_created')).order_by('-member_name')
    q = request.GET.get('q', '')

    if q:
        members_list = members_list.filter(
            Q(member_name__icontains=q) |
            Q(member_id__icontains=q) |
            Q(member_phone__icontains=q)
        )

    # CSV Export
    if request.GET.get('export') == 'csv':
        export_columns = request.GET.getlist('export_columns')
        default_cols = ['Member ID', 'Name', 'Phone', 'CNIC', 'No of Registrations']
        cols = export_columns if export_columns else default_cols

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="real_members_export.csv"'
        
        writer = csv.writer(response)
        writer.writerow(cols)
        
        for m in members_list:
            row = []
            if 'Member ID' in cols: row.append(m.member_id)
            if 'Name' in cols: row.append(m.member_name)
            if 'Phone' in cols: row.append(m.member_phone)
            if 'CNIC' in cols: row.append(m.member_cnic)
            if 'No of Registrations' in cols: row.append(m.actual_registrations)
            writer.writerow(row)
        return response

    paginator = Paginator(members_list, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    query_dict = request.GET.copy()
    if 'page' in query_dict:
        del query_dict['page']
    query_params = query_dict.urlencode()
    if query_params:
        query_params = f"&{query_params}"

    context = {
        'page_obj': page_obj,
        'current_filters': {'q': q},
        'query_params': query_params,
        'active_page': 'all_real_members'
    }
    return render(request, 'all_real_members.html', context)


@login_required
@admin_only
def create_real_member(request):
    if request.method == 'POST':
        form = MemberForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Member created successfully!')
            return redirect('all_real_members')
    else:
        form = MemberForm()
    return render(request, 'member_form.html', {'form': form, 'active_page': 'all_real_members'})


@login_required
@admin_only
def update_real_member(request, pk):
    member = get_object_or_404(Member, pk=pk)
    if request.method == 'POST':
        # ── Read the new member_id directly from POST BEFORE binding to form ─
        # pk (from the URL) is always the reliable OLD member_id.
        # request.POST['member_id'] is what the user typed as the new value.
        old_member_id  = pk                              # comes from the URL — always reliable
        new_member_id  = request.POST.get('member_id', pk).strip()
        id_is_changing = (old_member_id != new_member_id)

        form = MemberForm(request.POST, instance=member)
        if form.is_valid():
            # form.save() → if member_id changed, Django INSERTs a new row
            form.save()

            if id_is_changing:
                # 1. Re-point the FK: Person.made_by → new Member row
                Person.objects.filter(made_by_id=old_member_id).update(
                    made_by_id=new_member_id
                )

                # 2. Update the denormalised CharField that stores the member id
                Person.objects.filter(member_membership_id=old_member_id).update(
                    member_membership_id=new_member_id
                )

                # 3. Migrate the mirror Person whose membership_number == old_member_id
                mirror_person = Person.objects.filter(
                    membership_number=old_member_id
                ).first()
                if mirror_person:
                    # PK cannot be updated in-place: delete old row then re-save with new PK
                    mirror_person.membership_number = new_member_id
                    mirror_person.made_by_id = new_member_id
                    Person.objects.filter(membership_number=old_member_id).delete()
                    mirror_person.save()

                # 4. Delete the now-orphaned old Member row (left behind by Django INSERT)
                Member.objects.filter(member_id=old_member_id).delete()

                messages.success(
                    request,
                    f'Member ID updated from "{old_member_id}" to '
                    f'"{new_member_id}" and all associated records have been migrated.'
                )
            else:
                messages.success(request, 'Member updated successfully!')

            return redirect('all_real_members')
    else:
        form = MemberForm(instance=member)
    return render(request, 'member_form.html', {'form': form, 'is_update': True, 'member': member, 'active_page': 'all_real_members'})


@require_POST
@login_required
@admin_only
def delete_real_member(request, pk):
    member = get_object_or_404(Member, pk=pk)
    member.delete()
    messages.success(request, 'Member deleted successfully!')
    return redirect('all_real_members')


@login_required
@admin_only
def membership_summary_view(request):
    summaries = MembershipSummary.objects.all().order_by('name')
    context = {
        'summaries': summaries,
        'active_page': 'membership_summary'
    }
    return render(request, 'membership_summary.html', context)


@login_required
@admin_only
def membership_summary_create(request):
    if request.method == 'POST':
        form = MembershipSummaryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Membership Summary created successfully!')
            return redirect('membership_summary')
    else:
        form = MembershipSummaryForm()
    return render(request, 'membership_summary_form.html', {'form': form, 'active_page': 'membership_summary'})


@login_required
@admin_only
def membership_summary_update(request, pk):
    summary = get_object_or_404(MembershipSummary, pk=pk)
    if request.method == 'POST':
        form = MembershipSummaryForm(request.POST, instance=summary)
        if form.is_valid():
            form.save()
            messages.success(request, 'Membership Summary updated successfully!')
            return redirect('membership_summary')
    else:
        form = MembershipSummaryForm(instance=summary)
    return render(request, 'membership_summary_form.html', {'form': form, 'is_update': True, 'summary': summary, 'active_page': 'membership_summary'})


@require_POST
@login_required
@admin_only
def membership_summary_delete(request, pk):
    summary = get_object_or_404(MembershipSummary, pk=pk)
    summary.delete()
    messages.success(request, 'Membership Summary deleted successfully!')
    return redirect('membership_summary')





@login_required
def ajax_get_member_info(request):
    member_id = request.GET.get('member_id')
    if member_id:
        try:
            member = Member.objects.get(member_id=member_id)
            return JsonResponse({
                'success': True,
                'member_name': member.member_name,
                'member_phone': member.member_phone,
                'member_cnic': member.member_cnic,
            })
        except Member.DoesNotExist:
            try:
                person = Person.objects.get(membership_number=member_id)
                return JsonResponse({
                    'success': True,
                    'member_name': person.name,
                    'member_phone': person.phone,
                    'member_cnic': person.cnic,
                })
            except Person.DoesNotExist:
                return JsonResponse({'success': False})
    return JsonResponse({'success': False})

@login_required
def ajax_get_registered_persons(request):
    member_id = request.GET.get('member_id')
    if not member_id:
        return JsonResponse({'status': 'error', 'message': 'Missing member_id parameter'}, status=400)
    
    # Fetch persons whose made_by_id matches
    persons = Person.objects.filter(made_by_id=member_id).order_by('-created_at')
    
    data = []
    for p in persons:
        data.append({
            'membership_number': p.membership_number,
            'name': p.name,
            'father_name': p.father_name,
            'phone': p.phone,
            'cnic': p.cnic,
        })
        
    return JsonResponse({'status': 'success', 'data': data})


def ajax_get_location_members(request):
    loc_type = request.GET.get('type')
    loc_id = request.GET.get('id')
    
    if not loc_type or not loc_id:
        return JsonResponse({'status': 'error', 'message': 'Missing parameters'}, status=400)
    
    persons = Person.objects.all().order_by('-created_at')
    if loc_type == 'town':
        persons = persons.filter(town_id=loc_id)
    elif loc_type == 'zone':
        persons = persons.filter(zone_id=loc_id)
    elif loc_type == 'uc':
        persons = persons.filter(union_council_id=loc_id)
    elif loc_type == 'ward':
        persons = persons.filter(ward_id=loc_id)
    else:
        return JsonResponse({'status': 'error', 'message': 'Invalid location type'}, status=400)
    
    data = []
    for p in persons:
        data.append({
            'membership_number': p.membership_number,
            'name': p.name,
            'father_name': p.father_name,
            'phone': p.phone,
            'cnic': p.cnic,
        })
        
    return JsonResponse({'status': 'success', 'data': data})

@require_POST
@login_required
@admin_only
def ajax_delete_location_members(request):
    loc_type = request.POST.get('type')
    loc_id = request.POST.get('id')
    
    if not loc_type or not loc_id:
        return JsonResponse({'status': 'error', 'message': 'Missing parameters'}, status=400)
    
    persons = Person.objects.all()
    if loc_type == 'town':
        persons = persons.filter(town_id=loc_id)
    elif loc_type == 'zone':
        persons = persons.filter(zone_id=loc_id)
    elif loc_type == 'uc':
        persons = persons.filter(union_council_id=loc_id)
    elif loc_type == 'ward':
        persons = persons.filter(ward_id=loc_id)
    else:
        return JsonResponse({'status': 'error', 'message': 'Invalid location type'}, status=400)
    
    count = persons.count()
    persons.delete()
    
    return JsonResponse({'status': 'success', 'message': f'Successfully deleted {count} members.'})
from django.forms import modelform_factory

@login_required
def office_bearers_index(request):
    categories = [
        {'id': 'central_cabinet', 'name': 'Central Cabinet', 'icon': 'bi-person-badge'},
        {'id': 'town_org', 'name': 'Town Organizations', 'icon': 'bi-building'},
        {'id': 'zonal_org', 'name': 'Zonal Organizations', 'icon': 'bi-map'},
        {'id': 'uc_org', 'name': 'Union Council Organizations', 'icon': 'bi-diagram-3'},
        {'id': 'ward_org', 'name': 'Ward Organizations', 'icon': 'bi-house'},
        {'id': 'pyo', 'name': 'People\'s Youth Organization', 'icon': 'bi-people-fill'},
        {'id': 'women_wing', 'name': 'Women Wing', 'icon': 'bi-gender-female'},
        {'id': 'minority_wing', 'name': 'Minority Wing', 'icon': 'bi-globe'},
        {'id': 'labour_wing', 'name': 'Labour Wing', 'icon': 'bi-tools'},
        {'id': 'cultural_wing', 'name': 'Cultural Wing', 'icon': 'bi-palette'},
        {'id': 'human_rights_wing', 'name': 'Human Rights Wing', 'icon': 'bi-shield-check'},
        {'id': 'traders_wing', 'name': 'Traders Wing', 'icon': 'bi-shop'},
        {'id': 'sports_wing', 'name': 'Sports Wing', 'icon': 'bi-trophy'},
        {'id': 'study_circle', 'name': 'People\'s Study Circle', 'icon': 'bi-book'},
        {'id': 'doctors_forum', 'name': 'Doctors Forum', 'icon': 'bi-heart-pulse'},
        {'id': 'ulema_wing', 'name': 'Ulema Wing', 'icon': 'bi-book-half'},
    ]
    return render(request, 'office_bearers/index.html', {'categories': categories})

@login_required
def office_bearers_list(request, category):
    categories_meta = {
        'central_cabinet': 'Central Cabinet',
        'town_org': 'Town Organizations',
        'zonal_org': 'Zonal Organizations',
        'uc_org': 'Union Council Organizations',
        'ward_org': 'Ward Organizations',
        'pyo': 'People\'s Youth Organization',
        'women_wing': 'Women Wing',
        'minority_wing': 'Minority Wing',
        'labour_wing': 'Labour Wing',
        'cultural_wing': 'Cultural Wing',
        'human_rights_wing': 'Human Rights Wing',
        'traders_wing': 'Traders Wing',
        'sports_wing': 'Sports Wing',
        'study_circle': 'People\'s Study Circle',
        'doctors_forum': 'Doctors Forum',
        'ulema_wing': 'Ulema Wing',
    }
    
    mapping = {
        'central_cabinet': (CentralCabinet, None, None),
        'town_org': (TownOrganization, 'town', Town),
        'zonal_org': (ZonalOrganization, 'zone', Zone),
        'uc_org': (UnionCouncilOrganization, 'union_council', UnionCouncil),
        'ward_org': (WardOrganization, 'ward', Ward),
        'pyo': (PeoplesYouthOrganization, None, None),
        'women_wing': (WomenWing, None, None),
        'minority_wing': (MinorityWing, None, None),
        'labour_wing': (LabourWing, None, None),
        'cultural_wing': (CulturalWing, None, None),
        'human_rights_wing': (HumanRightsWing, None, None),
        'traders_wing': (TradersWing, None, None),
        'sports_wing': (SportsWing, None, None),
        'study_circle': (PeoplesStudyCircle, None, None),
        'doctors_forum': (DoctorsForum, None, None),
        'ulema_wing': (UlemaWing, None, None),
    }

    if category not in mapping:
        messages.error(request, 'Invalid category.')
        return redirect('office_bearers_index')

    ModelClass, structural_field, _ = mapping[category]
    records = ModelClass.objects.all().order_by('-created_at')

    q = request.GET.get('q', '').strip()
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    missing_cnic = request.GET.get('missing_cnic')
    missing_phone = request.GET.get('missing_phone')
    missing_location = request.GET.get('missing_location')
    export_csv = request.GET.get('export')

    if q:
        from django.db.models import Q
        q_filter = Q(**{f"{category}_name__icontains": q}) | Q(**{f"{category}_cnic__icontains": q}) | Q(**{f"{category}_phone__icontains": q})
        records = records.filter(q_filter)
        
    if start_date:
        records = records.filter(created_at__gte=start_date)
    if end_date:
        records = records.filter(created_at__lte=f"{end_date} 23:59:59")
        
    if missing_cnic == '1':
        from django.db.models import Q
        records = records.filter(Q(**{f"{category}_cnic__isnull": True}) | Q(**{f"{category}_cnic__exact": ''}))
    if missing_phone == '1':
        from django.db.models import Q
        records = records.filter(Q(**{f"{category}_phone__isnull": True}) | Q(**{f"{category}_phone__exact": ''}))
    if missing_location == '1' and structural_field:
        records = records.filter(Q(**{f"{structural_field}__isnull": True}))

    # Generate data list
    data = []
    
    # Pre-fetch membership numbers based on CNIC to avoid N+1 queries
    cnics = [getattr(record, f'{category}_cnic', '') for record in records]
    from .models import Person
    persons = Person.objects.filter(cnic__in=[c for c in cnics if c])
    cnic_to_member_id = {p.cnic: p.membership_number for p in persons if p.cnic}
    
    for record in records:
        cnic = getattr(record, f'{category}_cnic', '')
        photo_field = getattr(record, f'{category}_photo', None)
        photo_url = photo_field.url if photo_field else 'https://upload.wikimedia.org/wikipedia/commons/c/c0/Pakistan_Peoples_Party_Flag.svg'
        
        data.append({
            'id': record.id,
            'member_id': cnic_to_member_id.get(cnic, '--'),
            'photo_url': photo_url,
            'name': getattr(record, f'{category}_name', ''),
            'designation': getattr(record, f'{category}_designation', ''),
            'phone': getattr(record, f'{category}_phone', ''),
            'cnic': cnic,
            'location': getattr(record, structural_field).name if structural_field and getattr(record, structural_field) else '',
        })

    # CSV Export
    if export_csv == 'csv':
        import csv
        from django.http import HttpResponse
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="office_bearers_{category}.csv"'
        writer = csv.writer(response)
        
        headers = ['Name', 'Designation', 'Phone', 'CNIC']
        if structural_field:
            headers.append('Location')
        writer.writerow(headers)
        
        for d in data:
            row = [d['name'], d['designation'], d['phone'], d['cnic']]
            if structural_field:
                row.append(d['location'])
            writer.writerow(row)
            
        return response

    current_filters = {
        'q': q,
        'start_date': start_date,
        'end_date': end_date,
        'missing_cnic': missing_cnic,
        'missing_phone': missing_phone,
        'missing_location': missing_location
    }

    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(data, 15)  # 15 records per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Build query params string for pagination links
    query_params_dict = request.GET.copy()
    if 'page' in query_params_dict:
        del query_params_dict['page']
    query_params = '&' + query_params_dict.urlencode() if query_params_dict else ''

    context = {
        'category_id': category,
        'category_name': categories_meta[category],
        'page_obj': page_obj,
        'query_params': query_params,
        'has_location': bool(structural_field),
        'current_filters': current_filters
    }
    return render(request, 'office_bearers/list.html', context)

@login_required
def get_person_data(request, member_id):
    try:
        person = Person.objects.get(membership_number=member_id)
        data = {
            'success': True,
            'name': person.name or '',
            'father_name': person.father_name or '',
            'cnic': person.cnic or '',
            'phone': person.phone or '',
            'address': person.address or ''
        }
    except Person.DoesNotExist:
        data = {'success': False, 'message': 'Person not found'}
    
    return JsonResponse(data)

@login_required
def search_person_by_name(request):
    query = request.GET.get('q', '').strip()
    if len(query) < 2:
        return JsonResponse({'results': []})
    
    persons = Person.objects.filter(name__icontains=query)[:15]
    results = [
        {
            'membership_number': p.membership_number,
            'name': p.name or '',
            'cnic': p.cnic or '',
            'phone': p.phone or ''
        } for p in persons
    ]
    return JsonResponse({'results': results})

@login_required
def add_office_bearer(request, category):
    mapping = {
        'central_cabinet': (CentralCabinet, None, None),
        'town_org': (TownOrganization, 'town', Town),
        'zonal_org': (ZonalOrganization, 'zone', Zone),
        'uc_org': (UnionCouncilOrganization, 'union_council', UnionCouncil),
        'ward_org': (WardOrganization, 'ward', Ward),
        'pyo': (PeoplesYouthOrganization, None, None),
        'women_wing': (WomenWing, None, None),
        'minority_wing': (MinorityWing, None, None),
        'labour_wing': (LabourWing, None, None),
        'cultural_wing': (CulturalWing, None, None),
        'human_rights_wing': (HumanRightsWing, None, None),
        'traders_wing': (TradersWing, None, None),
        'sports_wing': (SportsWing, None, None),
        'study_circle': (PeoplesStudyCircle, None, None),
        'doctors_forum': (DoctorsForum, None, None),
        'ulema_wing': (UlemaWing, None, None),
    }

    if category not in mapping:
        messages.error(request, 'Invalid category.')
        return redirect('dashboard')

    ModelClass, structural_field, StructuralModel = mapping[category]
    exclude_fields = [structural_field, 'created_at'] if structural_field else ['created_at']
    FormClass = modelform_factory(ModelClass, exclude=exclude_fields)

    if request.method == 'POST':
        form = FormClass(request.POST, request.FILES)
        if form.is_valid():
            instance = form.save(commit=False)
            
            if structural_field and StructuralModel:
                structural_name = request.POST.get(structural_field + '_name')
                
                if structural_field == 'town':
                    obj, _ = Town.objects.get_or_create(name=structural_name)
                elif structural_field == 'zone':
                    t_obj, _ = Town.objects.get_or_create(name=request.POST.get('town_name'))
                    obj, _ = Zone.objects.get_or_create(name=structural_name, town=t_obj)
                elif structural_field == 'union_council':
                    t_obj, _ = Town.objects.get_or_create(name=request.POST.get('town_name'))
                    z_obj, _ = Zone.objects.get_or_create(name=request.POST.get('zone_name'), town=t_obj)
                    obj, _ = UnionCouncil.objects.get_or_create(name=structural_name, zone=z_obj)
                elif structural_field == 'ward':
                    t_obj, _ = Town.objects.get_or_create(name=request.POST.get('town_name'))
                    z_obj, _ = Zone.objects.get_or_create(name=request.POST.get('zone_name'), town=t_obj)
                    uc_obj, _ = UnionCouncil.objects.get_or_create(name=request.POST.get('uc_name'), zone=z_obj)
                    obj, _ = Ward.objects.get_or_create(name=structural_name, union_council=uc_obj)
                    
                setattr(instance, structural_field, obj)
            
            instance.save()
            messages.success(request, 'Office bearer added successfully!')
            return redirect('office_bearers_list', category=category)
    else:
        form = FormClass()
        
    return render(request, 'office_bearers/add.html', {
        'form': form,
        'category': category,
        'structural_field': structural_field,
        'towns': Town.objects.all(),
        'zones': Zone.objects.all(),
        'ucs': UnionCouncil.objects.all(),
        'wards': Ward.objects.all(),
    })

@login_required
def update_office_bearer(request, category, pk):
    mapping = {
        'central_cabinet': (CentralCabinet, None, None),
        'town_org': (TownOrganization, 'town', Town),
        'zonal_org': (ZonalOrganization, 'zone', Zone),
        'uc_org': (UnionCouncilOrganization, 'union_council', UnionCouncil),
        'ward_org': (WardOrganization, 'ward', Ward),
        'pyo': (PeoplesYouthOrganization, None, None),
        'women_wing': (WomenWing, None, None),
        'minority_wing': (MinorityWing, None, None),
        'labour_wing': (LabourWing, None, None),
        'cultural_wing': (CulturalWing, None, None),
        'human_rights_wing': (HumanRightsWing, None, None),
        'traders_wing': (TradersWing, None, None),
        'sports_wing': (SportsWing, None, None),
        'study_circle': (PeoplesStudyCircle, None, None),
        'doctors_forum': (DoctorsForum, None, None),
        'ulema_wing': (UlemaWing, None, None),
    }

    if category not in mapping:
        messages.error(request, 'Invalid category.')
        return redirect('dashboard')

    ModelClass, structural_field, StructuralModel = mapping[category]
    exclude_fields = [structural_field, 'created_at'] if structural_field else ['created_at']
    FormClass = modelform_factory(ModelClass, exclude=exclude_fields)

    instance = get_object_or_404(ModelClass, pk=pk)

    if request.method == 'POST':
        form = FormClass(request.POST, request.FILES, instance=instance)
        if form.is_valid():
            updated_instance = form.save(commit=False)
            
            if structural_field and StructuralModel:
                structural_name = request.POST.get(structural_field + '_name')
                
                if structural_field == 'town':
                    obj, _ = Town.objects.get_or_create(name=structural_name)
                elif structural_field == 'zone':
                    t_obj, _ = Town.objects.get_or_create(name=request.POST.get('town_name'))
                    obj, _ = Zone.objects.get_or_create(name=structural_name, town=t_obj)
                elif structural_field == 'union_council':
                    t_obj, _ = Town.objects.get_or_create(name=request.POST.get('town_name'))
                    z_obj, _ = Zone.objects.get_or_create(name=request.POST.get('zone_name'), town=t_obj)
                    obj, _ = UnionCouncil.objects.get_or_create(name=structural_name, zone=z_obj)
                elif structural_field == 'ward':
                    t_obj, _ = Town.objects.get_or_create(name=request.POST.get('town_name'))
                    z_obj, _ = Zone.objects.get_or_create(name=request.POST.get('zone_name'), town=t_obj)
                    uc_obj, _ = UnionCouncil.objects.get_or_create(name=request.POST.get('uc_name'), zone=z_obj)
                    obj, _ = Ward.objects.get_or_create(name=structural_name, union_council=uc_obj)
                    
                setattr(updated_instance, structural_field, obj)
            
            updated_instance.save()
            messages.success(request, 'Office bearer updated successfully!')
            return redirect('office_bearers_list', category=category)
    else:
        form = FormClass(instance=instance)
        
    member_id_autofill = ''
    cnic = getattr(instance, f'{category}_cnic', None)
    if cnic:
        from .models import Person
        person = Person.objects.filter(cnic=cnic).first()
        if person:
            member_id_autofill = person.membership_number
        
    # We can reuse the add template for updating since it has the same fields
    return render(request, 'office_bearers/add.html', {
        'form': form,
        'category': category,
        'instance': instance,
        'structural_field': structural_field,
        'towns': Town.objects.all(),
        'zones': Zone.objects.all(),
        'ucs': UnionCouncil.objects.all(),
        'wards': Ward.objects.all(),
        'member_id_autofill': member_id_autofill,
    })

@login_required
def delete_office_bearer(request, category, pk):
    if request.method == 'POST':
        mapping = {
            'central_cabinet': (CentralCabinet, None, None),
            'town_org': (TownOrganization, 'town', Town),
            'zonal_org': (ZonalOrganization, 'zone', Zone),
            'uc_org': (UnionCouncilOrganization, 'union_council', UnionCouncil),
            'ward_org': (WardOrganization, 'ward', Ward),
            'pyo': (PeoplesYouthOrganization, None, None),
            'women_wing': (WomenWing, None, None),
            'minority_wing': (MinorityWing, None, None),
            'labour_wing': (LabourWing, None, None),
            'cultural_wing': (CulturalWing, None, None),
            'human_rights_wing': (HumanRightsWing, None, None),
            'traders_wing': (TradersWing, None, None),
            'sports_wing': (SportsWing, None, None),
            'study_circle': (PeoplesStudyCircle, None, None),
            'doctors_forum': (DoctorsForum, None, None),
            'ulema_wing': (UlemaWing, None, None),
        }

        if category not in mapping:
            messages.error(request, 'Invalid category.')
            return redirect('office_bearers_index')

        ModelClass, _, _ = mapping[category]
        try:
            record = ModelClass.objects.get(pk=pk)
            record.delete()
            messages.success(request, 'Office bearer deleted successfully.')
        except ModelClass.DoesNotExist:
            messages.error(request, 'Record not found.')

    return redirect('office_bearers_list', category=category)

@login_required
def import_office_bearers_ajax(request, category):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request method.'})

    try:
        data = json.loads(request.body)
        rows = data.get('rows', [])
        
        mapping = {
            'central_cabinet': (CentralCabinet, None, None),
            'town_org': (TownOrganization, 'town', Town),
            'zonal_org': (ZonalOrganization, 'zone', Zone),
            'uc_org': (UnionCouncilOrganization, 'union_council', UnionCouncil),
            'ward_org': (WardOrganization, 'ward', Ward),
            'pyo': (PeoplesYouthOrganization, None, None),
            'women_wing': (WomenWing, None, None),
            'minority_wing': (MinorityWing, None, None),
            'labour_wing': (LabourWing, None, None),
            'cultural_wing': (CulturalWing, None, None),
            'human_rights_wing': (HumanRightsWing, None, None),
            'traders_wing': (TradersWing, None, None),
            'sports_wing': (SportsWing, None, None),
            'study_circle': (PeoplesStudyCircle, None, None),
            'doctors_forum': (DoctorsForum, None, None),
            'ulema_wing': (UlemaWing, None, None),
        }

        if category not in mapping:
            return JsonResponse({'status': 'error', 'message': 'Invalid category.'})

        ModelClass, structural_field, StructuralModel = mapping[category]

        success_count = 0
        duplicate_count = 0
        error_count = 0
        logs = []

        for row in rows:
            cleaned_row = {k.strip().lower(): str(v).strip() for k, v in row.items() if k}
            
            name = cleaned_row.get('name')
            designation = cleaned_row.get('designation', '')
            cnic = cleaned_row.get('cnic', '')
            phone = cleaned_row.get('phone', '')

            log_id = name if name else "Unknown"

            if not name:
                error_count += 1
                logs.append({'serial_number': log_id, 'type': 'error', 'message': 'Missing Name'})
                continue

            # Handle location logic if applicable
            structural_obj = None
            if structural_field:
                location_name = cleaned_row.get('location') or cleaned_row.get(structural_field)
                if not location_name:
                    error_count += 1
                    logs.append({'serial_number': log_id, 'type': 'error', 'message': f'Missing {structural_field} name for location'})
                    continue
                
                # Retrieve or create nested structures if provided
                if structural_field == 'town':
                    structural_obj, _ = Town.objects.get_or_create(name=location_name)
                elif structural_field == 'zone':
                    town_name = cleaned_row.get('town', 'Default Town')
                    t_obj, _ = Town.objects.get_or_create(name=town_name)
                    structural_obj, _ = Zone.objects.get_or_create(name=location_name, town=t_obj)
                elif structural_field == 'union_council':
                    town_name = cleaned_row.get('town', 'Default Town')
                    zone_name = cleaned_row.get('zone', 'Default Zone')
                    t_obj, _ = Town.objects.get_or_create(name=town_name)
                    z_obj, _ = Zone.objects.get_or_create(name=zone_name, town=t_obj)
                    structural_obj, _ = UnionCouncil.objects.get_or_create(name=location_name, zone=z_obj)
                elif structural_field == 'ward':
                    town_name = cleaned_row.get('town', 'Default Town')
                    zone_name = cleaned_row.get('zone', 'Default Zone')
                    uc_name = cleaned_row.get('union_council') or cleaned_row.get('uc', 'Default UC')
                    t_obj, _ = Town.objects.get_or_create(name=town_name)
                    z_obj, _ = Zone.objects.get_or_create(name=zone_name, town=t_obj)
                    uc_obj, _ = UnionCouncil.objects.get_or_create(name=uc_name, zone=z_obj)
                    structural_obj, _ = Ward.objects.get_or_create(name=location_name, union_council=uc_obj)

            # Avoid pure duplicates if exactly matching CNIC or Name & Designation
            existing = None
            if cnic:
                existing = ModelClass.objects.filter(**{f"{category}_cnic": cnic}).first()
            if not existing:
                existing = ModelClass.objects.filter(**{f"{category}_name": name, f"{category}_designation": designation}).first()

            if existing:
                duplicate_count += 1
                logs.append({'serial_number': log_id, 'type': 'warning', 'message': 'Record already exists'})
                continue

            # Create Record
            try:
                kwargs = {
                    f"{category}_name": name,
                    f"{category}_designation": designation,
                    f"{category}_phone": phone,
                    f"{category}_cnic": cnic,
                }
                if structural_field and structural_obj:
                    kwargs[structural_field] = structural_obj
                
                ModelClass.objects.create(**kwargs)
                success_count += 1
                logs.append({'serial_number': log_id, 'type': 'success', 'message': 'SuccAessfully imported'})
            except Exception as e:
                error_count += 1
                logs.append({'serial_number': log_id, 'type': 'error', 'message': f'Creation failed: {str(e)}'})

        return JsonResponse({
            'status': 'success',
            'imported': success_count,
            'duplicates': duplicate_count,
            'errors': error_count,
            'logs': logs
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})
