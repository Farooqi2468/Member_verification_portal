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
    path('dashboard/real-members/', views.all_real_members, name='all_real_members'),
    path('dashboard/real-members/create/', views.create_real_member, name='create_real_member'),
    path('dashboard/real-members/update/<str:pk>/', views.update_real_member, name='update_real_member'),
    path('dashboard/real-members/delete/<str:pk>/', views.delete_real_member, name='delete_real_member'),
    path('dashboard/real-members/delete-all/', views.delete_all_real_members, name='delete_all_real_members'),
    path('dashboard/create/', views.create_person, name='create_person'),
    path('dashboard/members/', views.all_members, name='all_members'),
    path('dashboard/members/import/', views.import_members_csv, name='import_members_csv'),
    path('dashboard/members/import-ajax/', views.import_members_ajax, name='import_members_ajax'),
    path('dashboard/update/<str:pk>/', views.update_person, name='update_person'),
    path('dashboard/delete/<str:pk>/', views.delete_person, name='delete_person'),
    path('dashboard/delete-all/', views.delete_all_members, name='delete_all_members'),
    path('dashboard/person/<str:pk>/', views.admin_person_detail, name='admin_person_detail'),
    path('dashboard/person/<str:pk>/qr-proxy/', views.qr_image_proxy, name='qr_image_proxy'),
    path('dashboard/reports/', views.reports_view, name='reports_view'),
    path('dashboard/settings/', views.settings_view, name='settings'),

    # Location Management
    path('dashboard/locations/', views.manage_locations, name='manage_locations'),
    path('dashboard/locations/town/add/', views.add_town, name='add_town'),
    path('dashboard/locations/town/update/<int:pk>/', views.update_town, name='update_town'),
    path('dashboard/locations/town/delete/<int:pk>/', views.delete_town, name='delete_town'),
    path('dashboard/locations/zone/add/', views.add_zone, name='add_zone'),
    path('dashboard/locations/zone/update/<int:pk>/', views.update_zone, name='update_zone'),
    path('dashboard/locations/zone/delete/<int:pk>/', views.delete_zone, name='delete_zone'),
    path('dashboard/locations/uc/add/', views.add_uc, name='add_uc'),
    path('dashboard/locations/uc/update/<int:pk>/', views.update_uc, name='update_uc'),
    path('dashboard/locations/uc/delete/<int:pk>/', views.delete_uc, name='delete_uc'),
    path('dashboard/locations/ward/add/', views.add_ward, name='add_ward'),
    path('dashboard/locations/ward/update/<int:pk>/', views.update_ward, name='update_ward'),
    path('dashboard/locations/ward/delete/<int:pk>/', views.delete_ward, name='delete_ward'),

    # AJAX Cascade Endpoints
    path('ajax/zones/', views.ajax_get_zones, name='ajax_get_zones'),
    path('ajax/ucs/', views.ajax_get_ucs, name='ajax_get_ucs'),
    path('ajax/wards/', views.ajax_get_wards, name='ajax_get_wards'),
    path('ajax/get-member-info/', views.ajax_get_member_info, name='ajax_get_member_info'),
    path('ajax/dashboard-charts/', views.ajax_dashboard_charts, name='ajax_dashboard_charts'),
    path('ajax/registered-persons/', views.ajax_get_registered_persons, name='ajax_get_registered_persons'),
    path('ajax/missing-data-persons/', views.ajax_get_missing_data_persons, name='ajax_get_missing_data_persons'),
    path('ajax/location-members/', views.ajax_get_location_members, name='ajax_get_location_members'),
    path('ajax/location-members/delete/', views.ajax_delete_location_members, name='ajax_delete_location_members'),

    # Books Module
    path('dashboard/books/', views.book_list, name='book_list'),
    path('dashboard/books/create/', views.book_create, name='book_create'),
    path('dashboard/books/update/<int:pk>/', views.book_update, name='book_update'),
    path('dashboard/books/delete/<int:pk>/', views.book_delete, name='book_delete'),
    path('dashboard/books/membership-summary/', views.membership_summary_view, name='membership_summary'),
    path('dashboard/books/membership-summary/create/', views.membership_summary_create, name='membership_summary_create'),
    path('dashboard/books/membership-summary/update/<int:pk>/', views.membership_summary_update, name='membership_summary_update'),
    path('dashboard/books/membership-summary/delete/<int:pk>/', views.membership_summary_delete, name='membership_summary_delete'),

    # Office Bearers
    path('dashboard/office-bearers/', views.office_bearers_index, name='office_bearers_index'),
    path('dashboard/office-bearers/<str:category>/', views.office_bearers_list, name='office_bearers_list'),
    path('dashboard/office-bearers/add/<str:category>/', views.add_office_bearer, name='add_office_bearer'),
    path('dashboard/office-bearers/update/<str:category>/<int:pk>/', views.update_office_bearer, name='update_office_bearer'),
    path('dashboard/api/get-person/<str:member_id>/', views.get_person_data, name='get_person_data'),
    path('dashboard/api/search-person/', views.search_person_by_name, name='search_person_by_name'),
    path('dashboard/office-bearers/delete/<str:category>/<int:pk>/', views.delete_office_bearer, name='delete_office_bearer'),
    path('dashboard/office-bearers/delete-all/<str:category>/', views.delete_all_office_bearers, name='delete_all_office_bearers'),
    path('dashboard/office-bearers/import-ajax/<str:category>/', views.import_office_bearers_ajax, name='import_office_bearers_ajax'),
]