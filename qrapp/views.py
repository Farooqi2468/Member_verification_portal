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
    name = request.user.first_name if request.user.first_name else request.user.username

    return render(request, 'dashboard.html', {
        'role': role,
        'name': name
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
            # Don't save to the database just yet
            person = form.save(commit=False)
            
            # Attach the logged-in user as the creator
            person.made_by = request.user 
            
            # Now save to the database
            person.save()
            # Update the URL and image saving to use person_id instead of id
            url = request.build_absolute_uri(f"/person/{person.person_id}/")
            img = qrcode.make(url)
            qr_path = os.path.join(settings.MEDIA_ROOT, f"qr_{person.person_id}.png")
            img.save(qr_path)
            return redirect('person_detail', pk=person.person_id)
    else:
        form = PersonForm()
    return render(request, 'templates.html', {'form': form})

def person_detail(request, pk):
    person = Person.objects.get(person_id=pk)
    return render(request, 'details.html', {'person': person})


