from django.urls import path
from . import views

urlpatterns = [
    path('', views.create_person, name='create_person'),
    path('person/<int:pk>/', views.person_detail, name='person_detail'),
]