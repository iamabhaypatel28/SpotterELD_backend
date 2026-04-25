from django.urls import path
from .views import CalculateTripView

urlpatterns = [
    path('calculate-trip/', CalculateTripView.as_view(), name='calculate-trip'),
]
