from django.db import models
from datetime import date, timedelta
from django.core.validators import MinValueValidator, MaxValueValidator

    


def default_due_date():
    return date.today() + timedelta(days=14)

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class Book(models.Model):
    name = models.CharField(max_length=200)  # Book title
    isbn = models.CharField(max_length=13, unique=True)  # ISBN number
    image = models.ImageField(upload_to='book_images/', blank=True, null=True)  # Cover image
    author = models.CharField(max_length=200)  # Author name
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='books')
    number_in_stock = models.PositiveIntegerField(default=0)  # Available copies
    description = models.TextField(blank=True, null=True, default="No description available")
    rating = models.DecimalField(max_digits=3, decimal_places=1, default=4.0, validators=[MinValueValidator(1.0), MaxValueValidator(5.0)])  # Rating with 1 decimal place

    def __str__(self):
        return f"{self.name} ({self.isbn})"
    
class Admin(models.Model):
    admin_id = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    password = models.CharField(max_length=128, default='temp123')  # hashed password recommended

    def __str__(self):
        return self.name


class Reader(models.Model):
    reader_id = models.CharField(max_length=20, unique=True)  # Custom ID for library users
    name = models.CharField(max_length=200)
    date_of_birth = models.DateField()
    phone_number = models.CharField(max_length=15, unique=True)  # to avoid duplicates
    address = models.TextField()
    password = models.CharField(max_length=128, default='temp123')


    def __str__(self):
        return f"{self.name} ({self.reader_id})"
    

class Issue(models.Model):
    reader = models.ForeignKey('Reader', on_delete=models.CASCADE, related_name='issues')
    book = models.ForeignKey('Book', on_delete=models.CASCADE, related_name='issues')
    issued_date = models.DateField(auto_now_add=True)
    due_date = models.DateField(default=default_due_date)
    returned_date = models.DateField(blank=True, null=True)

    def __str__(self):
        return f"{self.book.name} issued to {self.reader.name} on {self.issued_date}"


class Fine(models.Model):
    issue = models.OneToOneField('Issue', on_delete=models.CASCADE, related_name='fine')
    amount = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    paid = models.BooleanField(default=False)
    calculated_date = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"Fine for {self.issue.book.name} ({self.amount})"
    
class IssueRequest(models.Model):
    reader = models.ForeignKey('Reader', on_delete=models.CASCADE, related_name='issue_requests')
    book = models.ForeignKey('Book', on_delete=models.CASCADE, related_name='issue_requests')
    request_date = models.DateField(auto_now_add=True)
    approved = models.BooleanField(default=False)
    rejected = models.BooleanField(default=False)  # <-- new field

    def __str__(self):
        return f"{self.book.name} requested by {self.reader.name}"


class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('issued', 'Book Issued'),
        ('due_soon', 'Due Soon (2 days)'),
        ('overdue', 'Overdue'),
    ]
    
    reader = models.ForeignKey('Reader', on_delete=models.CASCADE, related_name='notifications')
    issue = models.ForeignKey('Issue', on_delete=models.CASCADE, related_name='notifications', null=True, blank=True)
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Notification for {self.reader.name}: {self.title}"


class BookIssuanceRecord(models.Model):
    """Tracks daily issuance counts for analytics."""
    book = models.ForeignKey('Book', on_delete=models.CASCADE, related_name='issuance_records')
    date = models.DateField()
    quantity_issued = models.PositiveIntegerField(default=0)
    
    class Meta:
        unique_together = ('book', 'date')
        ordering = ['date']
    
    def __str__(self):
        return f"{self.book.name} - {self.date}: {self.quantity_issued} issued"
    

