from django.urls import path
from . import views

urlpatterns = [
    # Public URLs
    path('', views.home, name='home'),
    path('person/<str:pk>/', views.person_detail, name='person_detail'),

    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard/users/', views.all_system_users, name='all_system_users'),
    path('dashboard/users/create/', views.create_system_user, name='create_system_user'),
    path('dashboard/users/update/<int:pk>/', views.update_system_user, name='update_system_user'),
    path('dashboard/users/delete/<int:pk>/', views.delete_system_user, name='delete_system_user'),
    path('dashboard/create/', views.create_person, name='create_person'),
    path('dashboard/members/', views.all_members, name='all_members'),
    path('dashboard/update/<str:pk>/', views.update_person, name='update_person'),
    path('dashboard/delete/<str:pk>/', views.delete_person, name='delete_person'),
    path('dashboard/person/<str:pk>/', views.admin_person_detail, name='admin_person_detail'),
    path('dashboard/reports/', views.reports_view, name='reports_view'),
    path('dashboard/settings/', views.settings_view, name='settings'),

    # Location Management
    path('dashboard/locations/', views.manage_locations, name='manage_locations'),
    path('dashboard/locations/town/add/', views.add_town, name='add_town'),
    path('dashboard/locations/town/delete/<int:pk>/', views.delete_town, name='delete_town'),
    path('dashboard/locations/zone/add/', views.add_zone, name='add_zone'),
    path('dashboard/locations/zone/delete/<int:pk>/', views.delete_zone, name='delete_zone'),
    path('dashboard/locations/uc/add/', views.add_uc, name='add_uc'),
    path('dashboard/locations/uc/delete/<int:pk>/', views.delete_uc, name='delete_uc'),
    path('dashboard/locations/ward/add/', views.add_ward, name='add_ward'),
    path('dashboard/locations/ward/delete/<int:pk>/', views.delete_ward, name='delete_ward'),

    # AJAX Cascade Endpoints
    path('ajax/zones/', views.ajax_get_zones, name='ajax_get_zones'),
    path('ajax/ucs/', views.ajax_get_ucs, name='ajax_get_ucs'),
    path('ajax/wards/', views.ajax_get_wards, name='ajax_get_wards'),
    path('ajax/dashboard-charts/', views.ajax_dashboard_charts, name='ajax_dashboard_charts'),
]