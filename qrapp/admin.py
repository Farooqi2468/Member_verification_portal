from django.contrib import admin

# Register your models here.
from .models import Person, Town, UnionCouncil, Zone, Ward, MembershipSummary, Member, CentralCabinet, TownOrganization, ZonalOrganization, UnionCouncilOrganization,WardOrganization, PeoplesYouthOrganization, WomenWing, MinorityWing, LabourWing,CulturalWing, HumanRightsWing, TradersWing, SportsWing, PeoplesStudyCircle,DoctorsForum, UlemaWing


admin.site.register(Person)
admin.site.register(Town)
admin.site.register(MembershipSummary)
admin.site.register(Member)
admin.site.register(UnionCouncil)
admin.site.register(Zone)
admin.site.register(Ward)

admin.site.register(CentralCabinet)
admin.site.register(TownOrganization)
admin.site.register(ZonalOrganization)
admin.site.register(UnionCouncilOrganization)
admin.site.register(WardOrganization)
admin.site.register(PeoplesYouthOrganization)
admin.site.register(WomenWing)
admin.site.register(MinorityWing)
admin.site.register(LabourWing)
admin.site.register(CulturalWing)
admin.site.register(HumanRightsWing)
admin.site.register(TradersWing)
admin.site.register(SportsWing)
admin.site.register(PeoplesStudyCircle)
admin.site.register(DoctorsForum)
admin.site.register(UlemaWing)
