import os
import qrcode
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import HttpResponseForbidden, JsonResponse

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
    return render(request, 'dashboard.html', {'role': role, 'name': name})


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
    members = Person.objects.all().order_by('-created_at')
    return render(request, 'all_members.html', {'members': members})


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
