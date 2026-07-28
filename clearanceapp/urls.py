from django.urls import path
from . import views


urlpatterns = [
    path('', views.clearance_upload, name='clearance_upload'),
    path('download_bills/', views.clearance_download_bills, name='clearance_download_bills'),
    path('download_tally/', views.clearance_download_tally, name='clearance_download_tally'),
    path('download_remain/', views.clearance_download_remain, name='clearance_download_remain'),
]
