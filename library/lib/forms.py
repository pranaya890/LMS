from django.shortcuts import render
from django import forms
from .models import Book, Reader, Issue,Admin

class BookForm(forms.ModelForm):
    class Meta:
        model = Book
        fields = ['name', 'isbn', 'image', 'author', 'category', 'number_in_stock', 'description', 'rating']
        widgets = {
            'rating': forms.NumberInput(attrs={
                'type': 'number',
                'min': '1.0',
                'max': '5.0',
                'step': '0.1',
                'placeholder': 'Enter rating (1.0 - 5.0)',
                'class': 'form-control'
            })
        }

# def view_books(request):
#     books = Book.objects.all()  # fetch all books
#     return render(request, 'view_books.html', {'books': books})

class ReaderForm(forms.ModelForm):
    class Meta:
        model = Reader
        fields = ['reader_id', 'name', 'date_of_birth', 'phone_number', 'address', 'is_staff_member']

class IssueForm(forms.ModelForm):
    class Meta:
        model = Issue
        fields = ['reader', 'book', 'due_date']   

class ReaderRegisterForm(forms.ModelForm):
    ROLE_CHOICES = (
        (False, 'Student'),
        (True, 'Staff / Teacher'),
    )

    password = forms.CharField(widget=forms.PasswordInput)
    is_staff_member = forms.TypedChoiceField(
        choices=ROLE_CHOICES,
        coerce=lambda x: x == 'True',
        widget=forms.RadioSelect,
        label='Role',
        initial=False,
        help_text='Select whether you are a student or staff/teacher.'
    )

    class Meta:
        model = Reader
        fields = ['reader_id', 'name', 'date_of_birth', 'phone_number', 'address', 'password', 'is_staff_member']


class ReaderProfileForm(forms.ModelForm):
    class Meta:
        model = Reader
        # Exclude reader_id from profile edits to avoid changing the unique login identifier
        fields = ['name', 'date_of_birth', 'phone_number', 'address', 'image']
        widgets = {
            'image': forms.ClearableFileInput(attrs={'accept': 'image/*'})
        }
    def clean(self):
        cleaned = super().clean()
        return cleaned


class AdminRegisterForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model = Admin
        fields = ['admin_id', 'name', 'password']


class AdminProfileForm(forms.ModelForm):
    class Meta:
        model = Admin
        fields = ['name', 'image']
        widgets = {
            'image': forms.ClearableFileInput(attrs={'accept': 'image/*'})
        }
    def clean(self):
        cleaned = super().clean()
        return cleaned


class PasswordChangeForm(forms.Form):
    password = forms.CharField(widget=forms.PasswordInput, label='New Password')
    confirm_password = forms.CharField(widget=forms.PasswordInput, label='Confirm New Password')

    def clean(self):
        cleaned = super().clean()
        pw = cleaned.get('password')
        pw2 = cleaned.get('confirm_password')
        if not pw:
            raise forms.ValidationError('Password is required.')
        if pw != pw2:
            raise forms.ValidationError('New password and confirmation do not match.')
        if len(pw) < 4:
            raise forms.ValidationError('Password must be at least 4 characters long.')
        return cleaned


