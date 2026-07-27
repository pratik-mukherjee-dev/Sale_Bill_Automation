from django.urls import path
from . import views


urlpatterns = [
    path('', views.upload_file, name='upload_file'),
    path('download_bills/', views.download_bills, name='download_bills'),
    path('download_tally/', views.download_tally, name='download_tally'),
    path('download_remain/', views.download_remain, name='download_remain'),
]

