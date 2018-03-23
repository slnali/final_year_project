from django.conf.urls import url
from bookings import views


urlpatterns = [

    # The home view ('/bookings/')
    url(r'^$', views.home, name='home'),
    # Explicit home ('/bookings/home/')
    url(r'^home/$', views.home, name='home'),
    # Redirect to get token ('/bookings/gettoken/')
    url(r'^gettoken/$', views.gettoken, name='gettoken'),
    # Mail view ('/bookings/mail/')
    url(r'^mail/$', views.mail, name='mail'),
    #Events view ('/tutorial/events/')
    url(r'^events/$',views.events,name='events'),
    #Booking preferences view
    url(r'^preferences/$',views.set_account_availability,name='set_account_availability'),
    #ajax load durations
    url(r'^ajax/load-booking-durations/$',views.load_booking_durations, name='ajax_load_booking_durations'),
    #make appointment
    url(r'^(?P<name>[\w.@+-]+)/(?P<pk>\d+)/appointment/$',views.display_available_time_slots,
        name = 'display_available_time_slots'),
    url(r'^(?P<name>[\w.@+-]+)/(?P<pk>\d+)/(?P<event_pk>\d+)/appointment/$',views.display_available_time_slots,
        name = 'display_available_time_slots'),
    url(r'^(?P<name>[\w.@+-]+)/(?P<pk>\d+)/(?P<date>\d{2}\/\d{2}\/\d{2})/(?P<action>[\w.@+-]+)/(?P<event_pk>\d+)/appointment/$',
        views.display_available_time_slots,name = 'display_available_time_slots'),
    url(r'^confirm_slot/(?P<slot>\d+:\d+)/(?P<date>[\w|\W]+\d{2}\/\d{2}\/\d{2})/(?P<pk>\d+)/(?P<event_pk>\d+)/$',views.book_meeting_slot, name='book_meeting_slot'),
    url(r'^booking_confirmed/(?P<pk>\d+)/$',views.BookingConfirmedView.as_view(),name='booking_confirmed'),
    url(r'^cancel_booking_slot/(?P<event_pk>\d+)/$', views.cancel_booking_slot, name='cancel_booking_slot'),
    url(r'^update_slot/(?P<slot>\d+:\d+)/(?P<date>[\w|\W]+\d{2}\/\d{2}\/\d{2})/(?P<pk>\d+)/(?P<event_pk>\d+)/$', views.update_meeting_slot,
        name='update_meeting_slot'),
    url(r'^confirm_slot_reschedule/(?P<slot>\d+:\d+)/(?P<date>[\w|\W]+\d{2}\/\d{2}\/\d{2})/(?P<event_pk>\d+)/(?P<duration>\d+)/$',views.confirm_slot_reschedule, name='confirm_slot_reschedule'),

]