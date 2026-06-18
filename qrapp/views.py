import io
import os
import base64
import urllib.request
import qrcode
import csv
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
from .models import Person, Town, Zone, UnionCouncil, Ward, Book, Member, MembershipSummary
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
    members_list = Person.objects.all().order_by('-created_at')

    # Filtering logic
    q = request.GET.get('q', '')
    town_id = request.GET.get('town')
    registrar_id = request.GET.get('registrar')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    if q:
        members_list = members_list.filter(
            Q(name__icontains=q) | 
            Q(membership_number__icontains=q) | 
            Q(cnic__icontains=q) |
            Q(phone__icontains=q)
        )
    if town_id:
        members_list = members_list.filter(town_id=town_id)
    if registrar_id:
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

    # CSV Export
    if request.GET.get('export') == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="members_export.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Member ID', 'Name', 'Father Name', 'CNIC', 'Phone', 'Address', 'Town', 'Zone', 'Union Council', 'Ward', 'Registered By', 'Date'])
        
        for p in members_list:
            writer.writerow([
                p.membership_number, p.name, p.father_name, p.cnic, p.phone, p.address,
                p.town.name if p.town else '',
                p.zone.name if p.zone else '',
                p.union_council.name if p.union_council else '',
                p.ward.name if p.ward else '',
                p.made_by.member_name if p.made_by else '',
                p.created_at.strftime('%Y-%m-%d %H:%M:%S')
            ])
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
            'registrar': int(registrar_id) if registrar_id else '',
            'start_date': start_date or '',
            'end_date': end_date or ''
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
            
            membership_number = cleaned_row.get('membership_number')
            if not membership_number:
                error_count += 1
                continue
            
            # Map location names to existing objects. Do not auto-create as per user request.
            town_name = cleaned_row.get('town', '')
            zone_name = cleaned_row.get('zone', '')
            uc_name = cleaned_row.get('union_council', '')
            ward_name = cleaned_row.get('ward', '')

            town_obj = Town.objects.filter(name__iexact=town_name).first() if town_name else None
            zone_obj = Zone.objects.filter(name__iexact=zone_name).first() if zone_name else None
            uc_obj = UnionCouncil.objects.filter(name__iexact=uc_name).first() if uc_name else None
            ward_obj = Ward.objects.filter(name__iexact=ward_name).first() if ward_name else None

            # Handle CNIC carefully to avoid unique constraint issues if empty
            cnic_val = cleaned_row.get('cnic', '') or None

            # Create or update the person
            person, created = Person.objects.update_or_create(
                membership_number=membership_number,
                defaults={
                    'name': cleaned_row.get('name', ''),
                    'father_name': cleaned_row.get('father_name', ''),
                    'cnic': cnic_val,
                    'phone': cleaned_row.get('phone', ''),
                    'address': cleaned_row.get('address', ''),
                    'town': town_obj,
                    'zone': zone_obj,
                    'union_council': uc_obj,
                    'ward': ward_obj,
                    'made_by': None,
                }
            )

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
    person.delete()
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
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{active_tab}s_export.csv"'
        writer = csv.writer(response)
        
        if active_tab == 'town':
            writer.writerow(['Town Name', 'Number of Zones'])
            for t in towns:
                writer.writerow([t.name, t.zones.count()])
        elif active_tab == 'zone':
            writer.writerow(['Zone Name', 'Town', 'Number of UCs'])
            for z in zones:
                writer.writerow([z.name, z.town.name, z.union_councils.count()])
        elif active_tab == 'uc':
            writer.writerow(['UC Name', 'Zone', 'Town', 'Number of Wards'])
            for u in ucs:
                writer.writerow([u.name, u.zone.name, u.zone.town.name, u.wards.count()])
        elif active_tab == 'ward':
            writer.writerow(['Ward Name', 'Union Council', 'Zone', 'Town'])
            for w in wards:
                writer.writerow([w.name, w.union_council.name, w.union_council.zone.name, w.union_council.zone.town.name])
                
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
        messages.error(request, "Failed to update town. Please check the inputs.")
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
        messages.error(request, "Failed to update zone. Please check the inputs.")
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
        messages.error(request, "Failed to update union council. Please check the inputs.")
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
        messages.error(request, "Failed to update ward. Please check the inputs.")
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
    members_list = Member.objects.all().order_by('-member_name')
    q = request.GET.get('q', '')

    if q:
        members_list = members_list.filter(
            Q(member_name__icontains=q) |
            Q(member_id__icontains=q) |
            Q(member_phone__icontains=q)
        )

    # CSV Export
    if request.GET.get('export') == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="real_members_export.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Member ID', 'Name', 'Phone', 'CNIC', 'No of Registrations'])
        
        for m in members_list:
            writer.writerow([m.member_id, m.member_name, m.member_phone, m.member_cnic, m.no_of_registrations])
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
        form = MemberForm(request.POST, instance=member)
        if form.is_valid():
            form.save()
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
