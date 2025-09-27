from django.contrib import admin
from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView
from api.views import CompanySearchView, TrackCompanyCreateView, TrackCompanyDeleteView, TrackCompanyListView, ReviewView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('auth/login', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    
    path('companies/search', CompanySearchView.as_view()),
    path('companies/tracked', TrackCompanyListView.as_view()),
    path('companies/track', TrackCompanyCreateView.as_view()),
    path('companies/untrack/<str:domain>', TrackCompanyDeleteView.as_view()),
    path('reviews/<str:domain>', ReviewView.as_view()),
]
