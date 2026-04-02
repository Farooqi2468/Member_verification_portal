from django.urls import path
from . import views

urlpatterns = [
    # This is the Public Url
    path('', views.home, name='home'), 
    path('person/<str:pk>/', views.person_detail, name='person_detail'),

    # This is the private url
    path('dashboard/create/', views.create_person, name='create_person'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard/members/', views.all_members, name='all_members'),
    path('dashboard/update/<str:pk>/', views.update_person, name='update_person'),
    path('dashboard/delete/<str:pk>/', views.delete_person, name='delete_person'),
    path('dashboard/person/<str:pk>/', views.admin_person_detail, name='admin_person_detail'),
]