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
        fields = ['reader_id', 'name', 'date_of_birth', 'phone_number', 'address']

class IssueForm(forms.ModelForm):
    class Meta:
        model = Issue
        fields = ['reader', 'book', 'due_date']   

class ReaderRegisterForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model = Reader
        fields = ['reader_id', 'name', 'date_of_birth', 'phone_number', 'address', 'password']


class AdminRegisterForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model = Admin
        fields = ['admin_id', 'name', 'password']


