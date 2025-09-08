from django.urls import path
from . import views

urlpatterns=[
    path('', views.home, name='home'),
    path('add_book/', views.add_book, name='add_book'),
    path('books/', views.view_books, name='view_books'),
    path('books/edit/<int:pk>/', views.edit_book, name='edit_book'),
    path('books/delete/<int:pk>/', views.delete_book, name='delete_book'),
    path('books/search/', views.search_books, name='search_books'),
    path('books/<int:pk>/', views.book_details, name='book_details'),
    path('all-books/', views.public_books, name='public_books'),#home page ko lagi


    #reader urls
    path('readers/', views.view_readers, name='view_readers'),
    #path('readers/add/', views.add_reader, name='add_reader'),
    path('readers/<int:pk>/edit/', views.edit_reader, name='edit_reader'),
    path('readers/<int:pk>/delete/', views.delete_reader, name='delete_reader'),
    path('readers/<int:pk>/', views.reader_details, name='reader_details'),

    # issue related
    path('issues/add/', views.issue_book, name='issue_book'),
    path('issues/', views.view_issues, name='view_issues'),
    path('issues/<int:pk>/return/', views.return_book, name='return_book'),
    path('issues/overdue/', views.overdue_books, name='overdue_books'),
    #fine related
    path('fines/', views.view_fines, name='view_fines'),
    path('fines/<int:pk>/pay/', views.pay_fine, name='pay_fine'),
    #register and login for reader
    path('readers/register/', views.register_reader, name='register_reader'),
    path('readers/login/', views.login_reader, name='login_reader'),
    path('readers/logout/', views.logout_reader, name='logout_reader'),
    path('reader/books/', views.reader_view_books, name='reader_view_books'),
    path('readers/dashboard/', views.reader_dashboard, name='reader_dashboard'),
    path('reader/books/<int:book_id>/request/', views.issue_request, name='issue_request'),
    path('reader/issued/', views.reader_issued_books, name='reader_issued_books'),
    ## admin
    path('admin/register/', views.register_admin, name='register_admin'),
    path('admin/login/', views.login_admin, name='login_admin'),
    path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin/logout/', views.logout_admin, name='logout_admin'),
    path('admin/issue-requests/', views.admin_issue_requests, name='admin_issue_requests'),
    path('admin/issue-requests/<int:request_id>/approve/', views.approve_request, name='approve_request'),
    path('admin/issue-requests/<int:request_id>/reject/', views.reject_request, name='reject_request'),

    #category related
    path('admin/categories/', views.view_categories, name='view_categories'),
    path('admin/categories/add/', views.add_category, name='add_category'),
    path('admin/categories/<int:category_id>/edit/', views.edit_category, name='edit_category'),
    path('admin/categories/<int:category_id>/delete/', views.delete_category, name='delete_category'),







]