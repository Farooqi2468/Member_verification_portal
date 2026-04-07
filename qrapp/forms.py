from django import forms
from .models import Person

class PersonForm(forms.ModelForm):
    class Meta:
        model = Person
        fields = [
            'person_id', 'name', 'father_name', 
            'cnic', 'phone', 'address', 'union_council', 
            'town', 'zone', 'ward'
        ]
        widgets = {
            'person_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 100011'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full Name'}),
            'father_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': "Father's Name"}),
            'cnic': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'XXXXX-XXXXXXX-X',
                'pattern': '[0-9]{5}-[0-9]{7}-[0-9]{1}',
                'title': 'CNIC must be in the format XXXXX-XXXXXXX-X'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': '03XXXXXXXXX',
                'pattern': '03[0-9]{9}',
                'title': 'Phone number must be in the format 03XXXXXXXXX'
            }),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Enter current address'}),
            'union_council': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., UC-14'}),
            'town': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Model Town'}),
            'zone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Zone 1'}),
            'ward': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Ward 5'}),
        }