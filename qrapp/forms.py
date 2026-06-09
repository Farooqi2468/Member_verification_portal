from django import forms
from .models import Person, Town, Zone, UnionCouncil, Ward, Book
from django.contrib.auth.models import User, Group
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import password_validation


class PersonForm(forms.ModelForm):
    class Meta:
        model = Person
        fields = [
            'person_id', 'name', 'father_name',
            'cnic', 'phone', 'address',
            'town', 'zone', 'union_council', 'ward',
            'made_by'
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
            'town': forms.Select(attrs={'class': 'form-control', 'id': 'id_town'}),
            'zone': forms.Select(attrs={'class': 'form-control', 'id': 'id_zone'}),
            'union_council': forms.Select(attrs={'class': 'form-control', 'id': 'id_union_council'}),
            'ward': forms.Select(attrs={'class': 'form-control', 'id': 'id_ward'}),
            'made_by': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = kwargs.get('instance')

        self.fields['town'].queryset = Town.objects.all()
        self.fields['town'].empty_label = "— Select Town —"
        self.fields['town'].required = False

        # Resolve IDs from submitted POST data first, then existing instance
        town_id = self.data.get('town') or (instance.town_id if instance else None)
        zone_id = self.data.get('zone') or (instance.zone_id if instance else None)
        uc_id   = self.data.get('union_council') or (instance.union_council_id if instance else None)

        # Zone queryset
        if town_id:
            self.fields['zone'].queryset = Zone.objects.filter(town_id=town_id)
        else:
            self.fields['zone'].queryset = Zone.objects.all()
        self.fields['zone'].empty_label = "— Select Zone —"
        self.fields['zone'].required = False

        # Union Council queryset
        if zone_id:
            self.fields['union_council'].queryset = UnionCouncil.objects.filter(zone_id=zone_id)
        else:
            self.fields['union_council'].queryset = UnionCouncil.objects.all()
        self.fields['union_council'].empty_label = "— Select Union Council —"
        self.fields['union_council'].required = False

        # Ward queryset
        if uc_id:
            self.fields['ward'].queryset = Ward.objects.filter(union_council_id=uc_id)
        else:
            self.fields['ward'].queryset = Ward.objects.all()
        self.fields['ward'].empty_label = "— Select Ward —"
        self.fields['ward'].required = False

        # Registrar (made_by) dropdown
        self.fields['made_by'].queryset = User.objects.filter(is_active=True).order_by('username')
        self.fields['made_by'].required = False
        self.fields['made_by'].empty_label = "— Select Registrar (defaults to you) —"
        self.fields['made_by'].label = "Registered By"


class TownForm(forms.ModelForm):
    class Meta:
        model = Town
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Model Town'}),
        }


class ZoneForm(forms.ModelForm):
    class Meta:
        model = Zone
        fields = ['name', 'town']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Zone A'}),
            'town': forms.Select(attrs={'class': 'form-control'}),
        }


class UnionCouncilForm(forms.ModelForm):
    class Meta:
        model = UnionCouncil
        fields = ['name', 'zone']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., UC-14'}),
            'zone': forms.Select(attrs={'class': 'form-control'}),
        }


class WardForm(forms.ModelForm):
    class Meta:
        model = Ward
        fields = ['name', 'union_council']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Ward 5'}),
            'union_council': forms.Select(attrs={'class': 'form-control'}),
        }


class RoleUserCreationForm(UserCreationForm):
    group = forms.ModelChoiceField(
        queryset=Group.objects.all(),
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'}),
        empty_label="— Select Role —"
    )

    class Meta:
        model = User
        fields = UserCreationForm.Meta.fields + ('first_name', 'last_name', 'email')
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Username'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email Address'}),
        }

    def __init__(self, *args, **kwargs):
        self.request_user = kwargs.pop('request_user', None)
        super().__init__(*args, **kwargs)
        # Style password fields to match the settings page
        self.fields['password1'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Enter password',
            'id': 'id_password1',
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Confirm password',
            'id': 'id_password2',
        })
        if self.request_user and not self.request_user.is_superuser:
            self.fields['group'].queryset = Group.objects.exclude(name='Superuser')

    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            group = self.cleaned_data.get('group')
            if group:
                user.groups.add(group)
                # If the group name is Superuser, also set is_superuser flag
                if group.name == 'Superuser':
                    user.is_superuser = True
                    user.is_staff = True
                    user.save()
        return user


class RoleUserChangeForm(forms.ModelForm):
    group = forms.ModelChoiceField(
        queryset=Group.objects.all(),
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'}),
        empty_label="— Select Role —"
    )

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email')
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.request_user = kwargs.pop('request_user', None)
        super().__init__(*args, **kwargs)
        if self.request_user and not self.request_user.is_superuser:
            self.fields['group'].queryset = Group.objects.exclude(name='Superuser')
            
        if self.instance and self.instance.pk:
            group = self.instance.groups.first()
            if group:
                self.fields['group'].initial = group

    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            group = self.cleaned_data.get('group')
            if group:
                user.groups.clear()
                user.groups.add(group)
                # Sync is_superuser flag
                if group.name == 'Superuser':
                    user.is_superuser = True
                    user.is_staff = True
                else:
                    user.is_superuser = False
                user.save()
        return user


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email')
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email Address'}),
        }


class PasswordUpdateForm(forms.Form):
    current_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Current Password', 'id': 'id_current_password'}),
        label='Current Password'
    )
    new_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'New Password', 'id': 'id_new_password'}),
        label='New Password',
        help_text=password_validation.password_validators_help_texts(),
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm New Password', 'id': 'id_confirm_password'}),
        label='Confirm New Password'
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    def clean_current_password(self):
        current_password = self.cleaned_data.get('current_password')
        if self.user and not self.user.check_password(current_password):
            raise forms.ValidationError('Your current password is incorrect.')
        return current_password

    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get('new_password')
        confirm_password = cleaned_data.get('confirm_password')
        if new_password and confirm_password and new_password != confirm_password:
            self.add_error('confirm_password', 'New passwords do not match.')
        if new_password:
            try:
                password_validation.validate_password(new_password, self.user)
            except forms.ValidationError as e:
                self.add_error('new_password', e)
        return cleaned_data


class BookForm(forms.ModelForm):
    class Meta:
        model = Book
        fields = '__all__'
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Book Name'}),
            'receiving_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'office_person': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Office Person'}),
            'issue_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'return_status': forms.Select(attrs={'class': 'form-control'}),
            'return_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'return_person_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Return Person Name'}),
            'sr_no': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Serial Number'}),
            'no_of_pages': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Number of Pages'}),
        }