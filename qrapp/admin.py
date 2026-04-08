from django.contrib import admin

# Register your models here.
from .models import Person, Town, UnionCouncil, Zone, Ward
admin.site.register(Person)
admin.site.register(Town)
admin.site.register(UnionCouncil)
admin.site.register(Zone)
admin.site.register(Ward)