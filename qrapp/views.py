from django.shortcuts import render

# Create your views here.
import qrcode
from django.shortcuts import render, redirect
from .forms import PersonForm
from .models import Person
from django.conf import settings
import os

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