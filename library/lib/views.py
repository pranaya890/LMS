from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from .forms import BookForm,ReaderForm,IssueForm,ReaderRegisterForm
from .models import Book,Reader,Issue,Fine,IssueRequest,Admin,Category
from django.db.models import Q
from django.utils import timezone
from django.utils.timezone import now
from django.contrib.auth.hashers import make_password, check_password
from datetime import timedelta,date
from django.contrib import messages



def home(request):
    return render(request, 'home.html', {'year': now().year})

def public_books(request):
    books = Book.objects.all().order_by('name')  # sorted alphabetically
    return render(request, 'public_books.html', {'books': books})


def add_book(request):
    if request.method == 'POST':
        form = BookForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('book_list')  # redirect to a book list page after adding
    else:
        form = BookForm()
    return render(request, 'add_book.html', {'form': form})


def edit_book(request, pk):
    book = get_object_or_404(Book, pk=pk)
    if request.method == 'POST':
        form = BookForm(request.POST, request.FILES, instance=book)
        if form.is_valid():
            form.save()
            return redirect('view_books')
    else:
        form = BookForm(instance=book)
    return render(request, 'edit_book.html', {'form': form})

def delete_book(request, pk):
    book = get_object_or_404(Book, pk=pk)
    if request.method == 'POST':
        book.delete()
        return redirect('view_books')
    return render(request, 'delete_book.html', {'book': book})



def view_books(request):
    """
    Display all books in the library.
    """
    books = Book.objects.all().order_by('name')  # optional: sort by name
    context = {
        'books': books
    }
    return render(request, 'view_books.html', context)


def search_books(request):
    query = request.GET.get('q')
    if query:
        books = Book.objects.filter(
            Q(name__icontains=query) |
            Q(author__icontains=query) |
            Q(isbn__icontains=query) |
            Q(category__name__icontains=query)
        )
    else:
        books = Book.objects.none()  # no query, show nothing

    return render(request, 'search_books.html', {'books': books, 'query': query})  

def book_details(request, pk):
    book = get_object_or_404(Book, pk=pk)  # fetch book or return 404 if not found
    return render(request, 'book_details.html', {'book': book})



### reader views

def add_reader(request):
    if request.method == 'POST':
        form = ReaderForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('view_readers')  # will make this view later
    else:
        form = ReaderForm()
    return render(request, 'add_reader.html', {'form': form})

def view_readers(request):
    readers = Reader.objects.all().order_by('name')
    return render(request, 'view_readers.html', {'readers': readers})


def edit_reader(request, pk):
    reader = get_object_or_404(Reader, pk=pk)
    if request.method == 'POST':
        form = ReaderForm(request.POST, instance=reader)
        if form.is_valid():
            form.save()
            return redirect('view_readers')
    else:
        form = ReaderForm(instance=reader)
    return render(request, 'edit_reader.html', {'form': form, 'reader': reader})

def delete_reader(request, pk):
    reader = get_object_or_404(Reader, pk=pk)
    if request.method == 'POST':
        reader.delete()
        return redirect('view_readers')
    return render(request, 'delete_reader.html', {'reader': reader})

def reader_details(request, pk):
    reader = get_object_or_404(Reader, pk=pk)
    issues = reader.issues.all()  # uses related_name='issues' from Issue model
    return render(request, 'reader_details.html', {'reader': reader, 'issues': issues})

###  Issue or borrow related

def issue_book(request):
    if request.method == 'POST':
        form = IssueForm(request.POST)
        if form.is_valid():
            issue = form.save(commit=False)

            # ✅ Prevent duplicate issue: same reader + same book + not returned
            if Issue.objects.filter(reader=issue.reader, book=issue.book, returned_date__isnull=True).exists():
                form.add_error('book', f"{issue.reader.name} already has '{issue.book.name}' issued.")
            else:
                # ✅ reduce stock when a book is issued
                if issue.book.number_in_stock > 0:
                    issue.book.number_in_stock -= 1
                    issue.book.save()
                    
                    # set issued_date and due_date if not provided
                    if not issue.issued_date:
                        issue.issued_date = date.today()
                    if not issue.due_date:
                        issue.due_date = date.today() + timedelta(days=14)

                    issue.save()
                    messages.success(request, f"'{issue.book.name}' issued to {issue.reader.name}.")
                    return redirect('view_issues')
                else:
                    form.add_error('book', 'This book is out of stock!')
    else:
        form = IssueForm()

    return render(request, 'issue_book.html', {'form': form})

def view_issues(request):
    issues = Issue.objects.all().order_by('-issued_date')  # latest first
    return render(request, 'view_issues.html', {'issues': issues})

def return_book(request, pk):
    issue = get_object_or_404(Issue, pk=pk)
    
    if request.method == 'POST':
        if not issue.returned_date:  # only if not already returned
            issue.returned_date = timezone.now().date()
            issue.book.number_in_stock += 1  # increase book stock
            issue.book.save()
            issue.save()
        return redirect('view_issues')
    
    return render(request, 'return_book.html', {'issue': issue})

def overdue_books(request):
    today = timezone.now().date()
    overdue_issues = Issue.objects.filter(returned_date__isnull=True, due_date__lt=today).select_related('reader', 'book').order_by('due_date')
    
    # Calculate days overdue for each issue
    for issue in overdue_issues:
        issue.days_overdue = (today - issue.due_date).days

    return render(request, 'overdue_books.html', {'overdue_issues': overdue_issues})
### for fines
def view_fines(request):
    fines = Fine.objects.select_related('issue__reader', 'issue__book').all().order_by('-calculated_date')
    return render(request, 'view_fines.html', {'fines': fines})

def pay_fine(request, pk):
    fine = get_object_or_404(Fine, pk=pk)
    if request.method == 'POST':
        fine.paid = True
        fine.save()
        return redirect('view_fines')
    return render(request, 'pay_fine.html', {'fine': fine})

## register  for reader


def register_reader(request):
    if request.method == 'POST':
        form = ReaderRegisterForm(request.POST)
        if form.is_valid():
            reader = form.save(commit=False)
            # Store password as plain text for simplicity (or use hashing)
            reader.password = form.cleaned_data['password']
            reader.save()
            return redirect('login_reader')
    else:
        form = ReaderRegisterForm()
    return render(request, 'register_reader.html', {'form': form})

# login for reader
def login_reader(request):
    error = None
    if request.method == 'POST':
        reader_id = request.POST.get('reader_id')
        password = request.POST.get('password')
        try:
            reader = Reader.objects.get(reader_id=reader_id, password=password)
            request.session['reader_id'] = reader.id  # store session
            return redirect('reader_dashboard')  # you can create a dashboard view
        except Reader.DoesNotExist:
            error = "Invalid Reader ID or password"
    return render(request, 'login_reader.html', {'error': error})

def logout_reader(request):
    if 'reader_id' in request.session:
        del request.session['reader_id']
    return redirect('home')


# reader dashboard
def reader_dashboard(request):
    reader_id = request.session.get('reader_id')
    if not reader_id:
        return redirect('login_reader')  # redirect if not logged in

    reader = Reader.objects.get(id=reader_id)

    # All books issued to this reader
    issues = reader.issues.all().order_by('-issued_date')  # uses related_name='issues'

    # Calculate fines for overdue books if not already created
    today = timezone.now().date()
    for issue in issues:
        if not issue.returned_date and issue.due_date < today:
            # Create fine if it doesn't exist
            fine, created = Fine.objects.get_or_create(issue=issue, defaults={
                'amount': (today - issue.due_date).days * 2  # example: $2 per overdue day
            })
    
    fines = Fine.objects.filter(issue__reader=reader, paid=False)

    return render(request, 'reader_dashboard.html', {
        'reader': reader,
        'issues': issues,
        'fines': fines,
    })

def reader_view_books(request):
    books = Book.objects.all().order_by('name')
    return render(request, 'books.html', {'books': books})



def approve_request(request, request_id):
    admin_id = request.session.get('admin_id')
    if not admin_id:
        return redirect('login_admin')

    req = get_object_or_404(IssueRequest, pk=request_id, approved=False, rejected=False)
    book = req.book
    reader = req.reader

    # 🚨 Check if reader already has this book issued
    if Issue.objects.filter(reader=reader, book=book, returned_date__isnull=True).exists():
        messages.error(request, f"{reader.name} already has '{book.name}' issued.")
        req.rejected = True
        req.save()
        return redirect('admin_issue_requests')

    # 🚨 Check stock availability
    if book.number_in_stock <= 0:
        messages.error(request, f"No copies of '{book.name}' are available.")
        req.rejected = True
        req.save()
        return redirect('admin_issue_requests')

    # ✅ Approve request and issue the book
    Issue.objects.create(
        reader=reader,
        book=book,
        issued_date=date.today(),
        due_date=date.today() + timedelta(days=14)
    )
    book.number_in_stock -= 1
    book.save()

    req.approved = True
    req.save()

    messages.success(request, f"Issue request approved: '{book.name}' issued to {reader.name}.")
    return redirect('admin_issue_requests')

def issue_request(request, book_id):
    # Check if reader is logged in
    reader_id = request.session.get('reader_id')
    if not reader_id:
        return redirect('login_reader')  # redirect if not logged in

    reader = get_object_or_404(Reader, id=reader_id)
    book = get_object_or_404(Book, id=book_id)

    # ✅ Restrict duplicate issued books
    if Issue.objects.filter(reader=reader, book=book, returned_date__isnull=True).exists():
        messages.error(request, f"You already have '{book.name}' issued.")
        return redirect('reader_view_books')

    # ✅ Prevent duplicate pending requests
    if IssueRequest.objects.filter(reader=reader, book=book, approved=False, rejected=False).exists():
        messages.warning(request, f"You already have a pending request for '{book.name}'.")
        return redirect('reader_view_books')

    # ✅ Create new request
    IssueRequest.objects.create(reader=reader, book=book)
    messages.success(request, f"Issue request for '{book.name}' submitted successfully!")

    return redirect('reader_view_books')

def reader_issued_books(request):
    reader_id = request.session.get('reader_id')
    if not reader_id:
        return redirect('login_reader')

    reader = Reader.objects.get(id=reader_id)
    issued_books = Issue.objects.filter(reader=reader).order_by('-issued_date')

    return render(request, 'reader_issued_books.html', {
        'reader': reader,
        'issued_books': issued_books,
    })


### admin
def register_admin(request):
    from .forms import AdminRegisterForm
    if request.method == 'POST':
        form = AdminRegisterForm(request.POST)
        if form.is_valid():
            admin = form.save(commit=False)
            admin.password = make_password(form.cleaned_data['password'])
            admin.save()
            return redirect('login_admin')
    else:
        form = AdminRegisterForm()
    return render(request, 'register_admin.html', {'form': form})

# Admin Login
def login_admin(request):
    error = None
    if request.method == 'POST':
        admin_id = request.POST.get('admin_id')
        password = request.POST.get('password')
        try:
            admin = Admin.objects.get(admin_id=admin_id)
            if check_password(password, admin.password):
                request.session['admin_id'] = admin.id
                return redirect('admin_dashboard')
            else:
                error = "Invalid Admin ID or password"
        except Admin.DoesNotExist:
            error = "Invalid Admin ID or password"
    return render(request, 'login_admin.html', {'error': error})

# Admin Dashboard
def admin_dashboard(request):
    admin_id = request.session.get('admin_id')
    if not admin_id:
        return redirect('login_admin')
    admin = Admin.objects.get(id=admin_id)
    
    total_books = Book.objects.count()
    total_readers = Reader.objects.count()

    
    return render(request, 'admin_dashboard.html', {
        'admin': admin,
        'total_books': total_books,
        'total_readers': total_readers,
    })
# Admin Logout
def logout_admin(request):
    if 'admin_id' in request.session:
        del request.session['admin_id']
    return redirect('home')


# View all pending requests
def admin_issue_requests(request):
    admin_id = request.session.get('admin_id')
    if not admin_id:
        return redirect('login_admin')

    pending_requests = IssueRequest.objects.filter(approved=False, rejected=False).order_by('request_date')
    return render(request, 'admin_issue_requests.html', {'pending_requests': pending_requests})


def approve_request(request, request_id):
    admin_id = request.session.get('admin_id')
    if not admin_id:
        return redirect('login_admin')

    req = get_object_or_404(IssueRequest, pk=request_id, approved=False, rejected=False)
    book = req.book
    reader = req.reader

    #  Check if reader already has this book issued
    if Issue.objects.filter(reader=reader, book=book, returned_date__isnull=True).exists():
        messages.error(request, f"{reader.name} already has '{book.name}' issued.")
        req.rejected = True
        req.save()
        return redirect('admin_issue_requests')

    #  Check stock availability
    if book.number_in_stock <= 0:
        messages.error(request, f"No copies of '{book.name}' are available.")
        req.rejected = True
        req.save()
        return redirect('admin_issue_requests')

    #  Approve request and issue the book
    Issue.objects.create(
        reader=reader,
        book=book,
        issued_date=date.today(),
        due_date=date.today() + timedelta(days=14)
    )
    book.number_in_stock -= 1
    book.save()

    req.approved = True
    req.save()

    messages.success(request, f"Issue request approved: '{book.name}' issued to {reader.name}.")
    return redirect('admin_issue_requests')

def reject_request(request, request_id):
    admin_id = request.session.get('admin_id')
    if not admin_id:
        return redirect('login_admin')

    req = get_object_or_404(IssueRequest, pk=request_id, approved=False, rejected=False)
    req.rejected = True
    req.save()

    return redirect('admin_issue_requests')

#category for admin

def view_categories(request):
    admin_id = request.session.get('admin_id')
    if not admin_id:
        return redirect('login_admin')

    categories = Category.objects.all()
    return render(request, 'admin_view_categories.html', {'categories': categories})

# Add new category
def add_category(request):
    admin_id = request.session.get('admin_id')
    if not admin_id:
        return redirect('login_admin')

    if request.method == 'POST':
        name = request.POST.get('name')
        if name:
            Category.objects.create(name=name)
            return redirect('view_categories')

    return render(request, 'admin_add_category.html')

# Edit category
def edit_category(request, category_id):
    admin_id = request.session.get('admin_id')
    if not admin_id:
        return redirect('login_admin')

    category = get_object_or_404(Category, id=category_id)

    if request.method == 'POST':
        name = request.POST.get('name')
        if name:
            category.name = name
            category.save()
            return redirect('view_categories')

    return render(request, 'admin_edit_category.html', {'category': category})

# Delete category
def delete_category(request, category_id):
    admin_id = request.session.get('admin_id')
    if not admin_id:
        return redirect('login_admin')

    category = get_object_or_404(Category, id=category_id)
    category.delete()
    return redirect('view_categories')