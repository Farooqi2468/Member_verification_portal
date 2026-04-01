from django.urls import path
from . import views

urlpatterns = [
    # This is the Public Url
    path('', views.home, name='home'), 
    path('person/<str:pk>/', views.person_detail, name='person_detail'),

    # This is the private url
    path('dashboard/create/', views.create_person, name='create_person'),
    path('dashboard/', views.dashboard, name='dashboard'),

]