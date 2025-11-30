from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from .forms import BookForm,ReaderForm,IssueForm,ReaderRegisterForm
from .models import Book,Reader,Issue,Fine,IssueRequest,Admin,Category,Notification,BookIssuanceRecord, BookRating
from django.db.models import Q, Count, Avg
from django.utils import timezone
from django.utils.timezone import now
from django.contrib.auth.hashers import make_password, check_password
from datetime import timedelta,date
from django.contrib import messages
from django.urls import reverse
import json
from django.conf import settings

# maximum number of books a reader can have at once (including pending requests)
MAX_ISSUED_PER_READER = getattr(settings, 'MAX_ISSUED_PER_READER', 5)




def home(request):
    categories = Category.objects.all()
    # show a small selection of books on the homepage (e.g., latest or popular)
    books = Book.objects.all().order_by('-id')[:6]
    return render(request, 'home.html', {
        'year': now().year,
        'categories': categories,
        'books': books,
    })

def public_books(request):
    books = Book.objects.all().order_by('name')  # sorted alphabetically
    categories = Category.objects.all()
    return render(request, 'public_books.html', {'books': books, 'categories': categories})


def add_book(request):
    if request.method == 'POST':
        form = BookForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('view_books')  # redirect to view_books after adding
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
        'books': books,
        'categories': Category.objects.all(),
    }
    return render(request, 'view_books.html', context)



def book_details(request, pk):
    # Render different detail pages depending on who is viewing:
    # - Admins: show admin_book_details.html (with admin controls)
    # - Logged-in reader: show reader_book_detail.html (reader-specific layout)
    # - Anonymous/general visitor: show public book_details.html

    # If admin session exists, reuse admin_book_details view
    if request.session.get('admin_id'):
        return admin_book_details(request, pk)

    # If reader session exists, reuse reader_book_detail view
    if request.session.get('reader_id'):
        return reader_book_detail(request, pk)

    # General visitor (not admin and not logged-in reader)
    book = get_object_or_404(Book, pk=pk)  # fetch book or return 404 if not found
    analytics = get_book_analytics_data(book, days=90)
    popular_books = get_popular_books(limit=3, exclude_book_id=pk)
    return render(request, 'book_details.html', {
        'book': book,
        'analytics': analytics,
        'popular_books': popular_books,
    })


def book_description(request, pk):
    """Render a simple page that shows the book title and its full description.

    This can be used for a dedicated description view or AJAX-loaded fragment.
    """
    book = get_object_or_404(Book, pk=pk)
    return render(request, 'book_description.html', {'book': book})


def admin_book_details(request, pk):
    """Admin-only book details view. Requires admin session; otherwise redirects to admin login."""
    admin_id = request.session.get('admin_id')
    if not admin_id:
        return redirect('login_admin')

    book = get_object_or_404(Book, pk=pk)
    analytics = get_book_analytics_data(book, days=90)
    popular_books = get_popular_books(limit=3, exclude_book_id=pk)
    return render(request, 'admin_book_details.html', {
        'book': book,
        'analytics': analytics,
        'popular_books': popular_books,
    })



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

            #  Prevent duplicate issue: same reader + same book + not returned
            if Issue.objects.filter(reader=issue.reader, book=issue.book, returned_date__isnull=True).exists():
                form.add_error('book', f"{issue.reader.name} already has '{issue.book.name}' issued.")
            else:
                #  automatically set issued_date if not provided
                if not issue.issued_date:
                    issue.issued_date = date.today()

                #  validate due_date
                if not issue.due_date:
                    # If the reader is marked as staff_member, give 6 months (approx 182 days), else default 14 days
                    if getattr(issue.reader, 'is_staff_member', False):
                        issue.due_date = issue.issued_date + timedelta(days=182)
                    else:
                        issue.due_date = issue.issued_date + timedelta(days=14)  # default 2 weeks
                elif issue.due_date <= issue.issued_date:
                    form.add_error('due_date', 'Due date must be after today.')
                elif issue.due_date > issue.issued_date + timedelta(days=30):
                    form.add_error('due_date', 'Due date cannot exceed 30 days from today.')

                # proceed if no due_date errors
                if not form.errors:
                    if issue.book.number_in_stock > 0:
                        issue.book.number_in_stock -= 1
                        issue.book.save()
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
            # Store password as plain text for simplicity (consider hashing in future)
            reader.password = form.cleaned_data['password']
            # ensure is_staff_member is set (form provides it)
            reader.is_staff_member = form.cleaned_data.get('is_staff_member', False)
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
            # Cache staff flag in session for quick checks in templates/views
            request.session['is_staff_member'] = bool(getattr(reader, 'is_staff_member', False))
            return redirect('reader_dashboard')  # you can create a dashboard view
        except Reader.DoesNotExist:
            error = "Invalid Reader ID or password"
    return render(request, 'login_reader.html', {'error': error})

def logout_reader(request):
    if 'reader_id' in request.session:
        del request.session['reader_id']
    if 'is_staff_member' in request.session:
        del request.session['is_staff_member']
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
    
    # Check and create notifications for due soon and overdue books
    check_and_create_due_soon_notifications()
    check_and_create_overdue_notifications()
    
    fines = Fine.objects.filter(issue__reader=reader, paid=False)
    unread_notif_count = reader.notifications.filter(read=False).count()

    return render(request, 'reader_dashboard.html', {
        'reader': reader,
        'issues': issues,
        'fines': fines,
        'unread_notif_count': unread_notif_count,
    })

def reader_view_books(request):
    books = Book.objects.all().order_by('name')
    return render(request, 'books.html', {'books': books, 'categories': Category.objects.all()})

def reader_book_detail(request, pk):
    """
    View for a reader to see book details.
    """
    book = get_object_or_404(Book, pk=pk)
    analytics = get_book_analytics_data(book, days=90)
    popular_books = get_popular_books(limit=3, exclude_book_id=pk)
    # compute average rating given by readers
    avg_reader_rating = BookRating.objects.filter(book=book).aggregate(avg=Avg('rating'))['avg']
    if avg_reader_rating is None:
        avg_reader_rating = float(book.rating)
    else:
        avg_reader_rating = float(avg_reader_rating)

    combined_rating = round((float(book.rating) + avg_reader_rating) / 2.0, 1)

    # current user's rating (if logged in)
    user_rating = None
    reader_obj = None
    reader_id = request.session.get('reader_id')
    if reader_id:
        reader_obj = Reader.objects.filter(id=reader_id).first()
        if reader_obj:
            ur = BookRating.objects.filter(book=book, reader=reader_obj).first()
            if ur:
                user_rating = float(ur.rating)

    return render(request, 'reader_book_detail.html', {
        'book': book,
        'analytics': analytics,
        'popular_books': popular_books,
        'combined_rating': combined_rating,
        'avg_reader_rating': round(avg_reader_rating, 1),
        'user_rating': user_rating,
    })


def rate_book(request, pk):
    """AJAX endpoint for readers to submit/update a rating for a book."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    reader_id = request.session.get('reader_id')
    if not reader_id:
        return JsonResponse({'error': 'login required'}, status=403)

    reader = get_object_or_404(Reader, id=reader_id)
    book = get_object_or_404(Book, pk=pk)

    try:
        rating = float(request.POST.get('rating', 0))
    except (TypeError, ValueError):
        return JsonResponse({'error': 'invalid rating'}, status=400)

    if rating < 1 or rating > 5:
        return JsonResponse({'error': 'rating out of range (1-5)'}, status=400)

    br, created = BookRating.objects.update_or_create(
        book=book,
        reader=reader,
        defaults={'rating': rating}
    )

    avg_reader = BookRating.objects.filter(book=book).aggregate(avg=Avg('rating'))['avg'] or float(book.rating)
    avg_reader = float(avg_reader)
    combined = round((float(book.rating) + avg_reader) / 2.0, 1)

    return JsonResponse({
        'combined_rating': combined,
        'avg_reader_rating': round(avg_reader, 1),
        'user_rating': float(br.rating),
    })

def approve_request(request, request_id):
    admin_id = request.session.get('admin_id')
    if not admin_id:
        return redirect('login_admin')

    req = get_object_or_404(IssueRequest, pk=request_id, approved=False, rejected=False)
    book = req.book
    reader = req.reader
    # Enforce per-reader limit: count currently issued books and pending requests
    current_issued = Issue.objects.filter(reader=reader, returned_date__isnull=True).count()
    current_pending = IssueRequest.objects.filter(reader=reader, approved=False, rejected=False).count()
    total_count = current_issued + current_pending

    # If total already exceeds the allowed maximum, reject approval
    if total_count > MAX_ISSUED_PER_READER:
        messages.error(request, (
            f"Cannot approve request: {reader.name} already has {total_count} books/pending requests, "
            f"which exceeds the limit of {MAX_ISSUED_PER_READER}."
        ))
        req.rejected = True
        req.save()
        return redirect('admin_issue_requests')

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
    # compute due_date depending on whether the reader is a staff member
    issued_date = date.today()
    if getattr(reader, 'is_staff_member', False):
        due = issued_date + timedelta(days=182)  # ~6 months
    else:
        due = issued_date + timedelta(days=14)

    issue = Issue.objects.create(
        reader=reader,
        book=book,
        issued_date=issued_date,
        due_date=due
    )
    book.number_in_stock -= 1
    book.save()

    # Create a notification for the issued book
    create_issue_notification(issue)
    
    # Record issuance for analytics
    record_book_issuance(book, issued_date=issue.issued_date)

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

    # Enforce per-reader limit: current issued books + pending requests must be < MAX
    current_issued = Issue.objects.filter(reader=reader, returned_date__isnull=True).count()
    current_pending = IssueRequest.objects.filter(reader=reader, approved=False, rejected=False).count()
    if current_issued + current_pending >= MAX_ISSUED_PER_READER:
        messages.error(request, (
            f"You cannot request more books. You already have {current_issued} issued and {current_pending} pending "
            f"(limit is {MAX_ISSUED_PER_READER}). Return a book or cancel a pending request first."
        ))
        return redirect('reader_view_books')

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
    # Enforce per-reader limit: count currently issued books and pending requests
    current_issued = Issue.objects.filter(reader=reader, returned_date__isnull=True).count()
    current_pending = IssueRequest.objects.filter(reader=reader, approved=False, rejected=False).count()
    total_count = current_issued + current_pending

    # If total already exceeds the allowed maximum, reject approval
    if total_count > MAX_ISSUED_PER_READER:
        messages.error(request, (
            f"Cannot approve request: {reader.name} already has {total_count} books/pending requests, "
            f"which exceeds the limit of {MAX_ISSUED_PER_READER}."
        ))
        req.rejected = True
        req.save()
        return redirect('admin_issue_requests')

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
    # compute due_date depending on whether the reader is a staff member
    issued_date = date.today()
    if getattr(reader, 'is_staff_member', False):
        due = issued_date + timedelta(days=182)  # ~6 months
    else:
        due = issued_date + timedelta(days=14)

    issue = Issue.objects.create(
        reader=reader,
        book=book,
        issued_date=issued_date,
        due_date=due
    )
    book.number_in_stock -= 1
    book.save()

    # Create a notification for the issued book
    create_issue_notification(issue)
    
    # Record issuance for analytics
    record_book_issuance(book, issued_date=issue.issued_date)

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

    # Create a notification for the reader informing them their request was rejected
    try:
        Notification.objects.create(
            reader=req.reader,
            issue=None,
            notification_type='request_rejected',
            title=f"Request Rejected: {req.book.name}",
            message=f"Your request to issue '{req.book.name}' was rejected by the library administrator."
        )
    except Exception:
        # If notification creation fails for any reason, continue silently but log to console for debugging
        print(f"Failed to create rejection notification for IssueRequest {req.pk}")

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

### Searching books


def ajax_search_books(request):
    query = request.GET.get('q', '')
    category_id = request.GET.get('category', '')

    books = Book.objects.all()
    # Restrict AJAX search to book name only (case-insensitive)
    if query:
        books = books.filter(
            Q(name__icontains=query)
        )
    if category_id:
        books = books.filter(category_id=category_id)

    # If no query provided, return books ordered alphabetically by name for consistent results
    if not query:
        books = books.order_by('name')

    data = []
    for book in books:
        # Choose correct detail URL depending on who is viewing
        if request.session.get('admin_id'):
            url = reverse('admin_book_details', args=[book.pk])  # admin book detail
        elif request.session.get('reader_id'):
            url = reverse('reader_book_detail', args=[book.pk])  # logged-in reader detail
        else:
            url = reverse('book_details', args=[book.pk])  # public/detail view for anonymous users

        # Debug print
        print(f"User: {request.user}, is_staff: {getattr(request.user, 'is_staff', False)}, Book URL: {url}")

        # compute reader average and combined rating for this book
        try:
            avg_reader = BookRating.objects.filter(book=book).aggregate(avg=Avg('rating'))['avg'] or float(book.rating)
            avg_reader = float(avg_reader)
        except Exception:
            avg_reader = float(book.rating)
        combined = round((float(book.rating) + avg_reader) / 2.0, 1)

        data.append({
            'name': book.name,
            'author': book.author,
            'isbn': getattr(book, 'isbn', ''),
            'category': book.category.name if book.category else '',
            'category_id': book.category.id if book.category else '',
            'image': book.image.url if getattr(book, 'image', None) else '',
            'pk': book.pk,
            'url': url,
            'stock': book.number_in_stock,
            'avg_reader_rating': round(avg_reader, 1),
            'combined_rating': combined,
        })

    return JsonResponse({'books': data})



# (Removed commented-out example rate_book handler — ratings implemented elsewhere)


### Notification system

def create_issue_notification(issue):
    """Create a notification when a book is issued to a reader."""
    Notification.objects.create(
        reader=issue.reader,
        issue=issue,
        notification_type='issued',
        title=f"Book Issued: {issue.book.name}",
        message=f"You have been issued '{issue.book.name}' by {issue.book.author}. Due date: {issue.due_date}"
    )


def check_and_create_due_soon_notifications():
    """Create notifications for books due in 2 days. Call this periodically (e.g., via cron/celery)."""
    today = timezone.now().date()
    target_date = today + timedelta(days=2)
    
    # Find issues that are due in 2 days and not yet notified
    issues = Issue.objects.filter(
        due_date=target_date,
        returned_date__isnull=True
    ).select_related('reader', 'book')
    
    for issue in issues:
        # Check if notification already exists for this issue
        if not Notification.objects.filter(issue=issue, notification_type='due_soon').exists():
            Notification.objects.create(
                reader=issue.reader,
                issue=issue,
                notification_type='due_soon',
                title=f"Due Soon: {issue.book.name}",
                message=f"'{issue.book.name}' is due on {issue.due_date}. Please return it on time to avoid fines."
            )


def check_and_create_overdue_notifications():
    """Create notifications for overdue books. Call this periodically (e.g., via cron/celery)."""
    today = timezone.now().date()
    
    # Find overdue issues (not returned and due date passed) and not yet notified
    overdue_issues = Issue.objects.filter(
        due_date__lt=today,
        returned_date__isnull=True
    ).select_related('reader', 'book')
    
    for issue in overdue_issues:
        # Check if notification already exists for this issue
        if not Notification.objects.filter(issue=issue, notification_type='overdue').exists():
            days_overdue = (today - issue.due_date).days
            Notification.objects.create(
                reader=issue.reader,
                issue=issue,
                notification_type='overdue',
                title=f"Overdue: {issue.book.name}",
                message=f"'{issue.book.name}' is {days_overdue} day(s) overdue. Please return it immediately to avoid additional fines."
            )


def reader_notifications(request):
    """Display all notifications for the logged-in reader."""
    reader_id = request.session.get('reader_id')
    if not reader_id:
        return redirect('login_reader')
    
    reader = Reader.objects.get(id=reader_id)
    notifications = reader.notifications.all()
    unread_count = notifications.filter(read=False).count()
    
    # Mark as read if requested
    if request.method == 'POST':
        notification_id = request.POST.get('notification_id')
        if notification_id:
            notif = get_object_or_404(Notification, id=notification_id, reader=reader)
            notif.read = True
            notif.save()
            return redirect('reader_notifications')
    
    return render(request, 'reader_notifications.html', {
        'reader': reader,
        'notifications': notifications,
        'unread_count': unread_count,
    })


def mark_all_notifications_read(request):
    """Mark all notifications as read for the logged-in reader."""
    reader_id = request.session.get('reader_id')
    if not reader_id:
        return redirect('login_reader')
    
    reader = Reader.objects.get(id=reader_id)
    reader.notifications.filter(read=False).update(read=True)
    
    return redirect('reader_notifications')


### Analytics

def record_book_issuance(book, issued_date=None):
    """Record a book issuance in the analytics."""
    if issued_date is None:
        issued_date = date.today()
    
    record, created = BookIssuanceRecord.objects.get_or_create(
        book=book,
        date=issued_date,
        defaults={'quantity_issued': 0}
    )
    record.quantity_issued += 1
    record.save()


def get_book_analytics_data(book, days=90):
    """Get analytics data for a book over the last N days."""
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    
    records = BookIssuanceRecord.objects.filter(
        book=book,
        date__gte=start_date,
        date__lte=end_date
    ).order_by('date')
    
    dates = [str(r.date) for r in records]
    quantities = [r.quantity_issued for r in records]
    
    return {
        'dates': dates,
        'quantities': quantities,
        'total_issued': sum(quantities),
        'avg_per_day': sum(quantities) / max(len(records), 1) if records else 0,
    }


def book_analytics_api(request, pk):
    """API endpoint to return analytics data as JSON."""
    book = get_object_or_404(Book, pk=pk)
    days = request.GET.get('days', 90)
    
    try:
        days = int(days)
    except (ValueError, TypeError):
        days = 90
    
    data = get_book_analytics_data(book, days=days)
    return JsonResponse(data)


def get_popular_books(limit=3, exclude_book_id=None):
    """Get random popular books with rating > 4.5."""
    books = Book.objects.filter(rating__gt=4.5)
    
    if exclude_book_id:
        books = books.exclude(pk=exclude_book_id)
    
    # Order by random and limit
    books = books.order_by('?')[:limit]
    return books