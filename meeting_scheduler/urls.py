"""meeting_scheduler URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf.urls import url, include
from django.contrib import admin
from bookings import views
from allauth.account import views

urlpatterns = [
    # Invoke the home view in the bookings app by default
    # url(r'^$', views.home, name='home'),
    url(r'^$', views.LoginView.as_view(), name='login'),
    # Defer any URLS to the /bookings directory to the bookings app
    url(r'^bookings/', include('bookings.urls', namespace='bookings')),
    url(r'^admin/', include(admin.site.urls)),
    url(r'accounts/',include('allauth.urls')),
]
