import os
import qrcode
import csv
from datetime import timedelta, datetime
from django.conf import settings
from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import HttpResponseForbidden, JsonResponse, HttpResponse
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.core.paginator import Paginator
from django.contrib.auth.models import User

from .forms import PersonForm, TownForm, ZoneForm, UnionCouncilForm, WardForm
from .models import Person, Town, Zone, UnionCouncil, Ward


def home(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'home.html')


def get_user_role(user):
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
        'registered_by_me': Person.objects.filter(made_by=request.user).count(),
    }
    return render(request, 'dashboard.html', context)


def admin_only(view_func):
    def wrapper(request, *args, **kwargs):
        if request.user.groups.filter(name='Admin').exists():
            return view_func(request, *args, **kwargs)
        return HttpResponseForbidden("Not allowed")
    return wrapper


@login_required
@admin_only
def manage_users(request):
    return render(request, 'admin/users.html')


@login_required
@admin_only
def create_person(request):
    if request.method == 'POST':
        form = PersonForm(request.POST)
        if form.is_valid():
            person = form.save(commit=False)
            person.made_by = request.user
            person.save()

            url = request.build_absolute_uri(f"/person/{person.person_id}/")
            img = qrcode.make(url)
            qr_path = os.path.join(settings.MEDIA_ROOT, f"qr_{person.person_id}.png")
            img.save(qr_path)
            return redirect('admin_person_detail', pk=person.person_id)
    else:
        form = PersonForm()
    return render(request, 'templates.html', {'form': form})


def person_detail(request, pk):
    person = get_object_or_404(Person, person_id=pk)

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
    person = get_object_or_404(Person, person_id=pk)
    is_admin = request.user.groups.filter(name='Admin').exists() or request.user.is_superuser
    return render(request, 'details.html', {
        'person': person,
        'is_admin': is_admin
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
            Q(person_id__icontains=q) | 
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
                p.person_id, p.name, p.father_name, p.cnic, p.phone, p.address,
                p.town.name if p.town else '',
                p.zone.name if p.zone else '',
                p.union_council.name if p.union_council else '',
                p.ward.name if p.ward else '',
                p.made_by.username if p.made_by else '',
                p.created_at.strftime('%Y-%m-%d %H:%M:%S')
            ])
        return response

    # Pagination
    paginator = Paginator(members_list, 10)  # Show 10 members per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Initial context for dropdowns
    towns = Town.objects.all()
    registrars = User.objects.filter(is_active=True).order_by('username')
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


@login_required
@admin_only
def update_person(request, pk):
    person = get_object_or_404(Person, person_id=pk)
    if request.method == 'POST':
        form = PersonForm(request.POST, instance=person)
        if form.is_valid():
            person = form.save()
            url = request.build_absolute_uri(f"/person/{person.person_id}/")
            img = qrcode.make(url)
            qr_path = os.path.join(settings.MEDIA_ROOT, f"qr_{person.person_id}.png")
            img.save(qr_path)
            return redirect('admin_person_detail', pk=person.person_id)
    else:
        form = PersonForm(instance=person)
    return render(request, 'templates.html', {'form': form, 'is_update': True, 'person': person})


@require_POST
@login_required
@admin_only
def delete_person(request, pk):
    person = get_object_or_404(Person, person_id=pk)
    person.delete()
    return redirect('all_members')


# ── Location Management ────────────────────────────────────────────────────────

@login_required
@admin_only
def manage_locations(request):
    context = {
        'town_form': TownForm(),
        'zone_form': ZoneForm(),
        'uc_form': UnionCouncilForm(),
        'ward_form': WardForm(),
        'towns': Town.objects.all(),
        'zones': Zone.objects.select_related('town').all(),
        'ucs': UnionCouncil.objects.select_related('zone__town').all(),
        'wards': Ward.objects.select_related('union_council__zone__town').all(),
        'active_tab': request.GET.get('tab', 'town'),
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
        .annotate(count=Count('person_id'))
        .order_by('date')
    )
    
    labels_line = [obj['date'].strftime('%b %d') for obj in daily_counts if obj['date']]
    data_line = [obj['count'] for obj in daily_counts if obj['date']]

    # 2. Members by Town (Doughnut/Bar Chart)
    town_counts = (
        persons_qs
        .filter(town__isnull=False)
        .values('town__name')
        .annotate(count=Count('person_id'))
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
