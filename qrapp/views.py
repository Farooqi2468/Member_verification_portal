# Create your views here.
import qrcode
from django.shortcuts import render, redirect
from .forms import PersonForm
from .models import Person
from django.conf import settings
import os


from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden



def home(request):
    if request.user.is_authenticated:
        return redirect('dashboard')  # logged-in users go to dashboard

    return render(request, 'home.html')  # public landing page


def get_user_role(user):
    if user.groups.exists():
        return user.groups.first().name
    return None

@login_required
def dashboard(request):
    role = get_user_role(request.user)

    return render(request, 'dashboard.html', {
        'role': role
    })

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
            person = form.save()

            # URL for QR (localhost)
            url = request.build_absolute_uri(f"/person/{person.id}/")

            # Generate QR
            img = qrcode.make(url)

            qr_path = os.path.join(settings.MEDIA_ROOT, f"qr_{person.id}.png")
            img.save(qr_path)

            return redirect('person_detail', pk=person.id)
    else:
        form = PersonForm()

    return render(request, 'templates.html', {'form': form})


def person_detail(request, pk):
    person = Person.objects.get(id=pk)
    return render(request, 'details.html', {'person': person})


