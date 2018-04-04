import time

import datetime
from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpResponseRedirect
from django.core.urlresolvers import reverse
from django.template.loader import render_to_string
from django.views.generic import CreateView, DetailView
from django_tables2 import RequestConfig

from bookings.booking_grid import BookingGrid
from bookings.authhelper import get_signin_url, get_token_from_code, get_access_token, get_token_from_refresh_token, \
    set_new_token
# Add import statement to include new function
from bookings.outlookservice import get_me, get_my_events, cancel_booking, book_event, update_booking
from allauth.socialaccount.models import SocialToken, SocialAccount
from bookings.forms import BookingAvailabilityForm, EventBookingForm, UpdateEventBookingForm
from bookings.models import BookingAvailability, Event
from django.utils import timezone
from django.utils.timezone import make_aware
from django.core.mail import send_mail


# Create your views here.

'''Connect to outlook view'''
def home(request):
    redirect_uri = request.build_absolute_uri(reverse('bookings:gettoken'))
    sign_in_url = get_signin_url(redirect_uri)
    context = {'signin_url': sign_in_url}
    return render(request, 'bookings/home.html', context)


def gettoken(request):
    auth_code = request.GET.get('code', '')
    redirect_uri = request.build_absolute_uri(reverse('bookings:gettoken'))
    token = get_token_from_code(auth_code, redirect_uri)
    access_token = token.get('access_token', '')
    user = get_me(access_token)
    refresh_token = token.get('refresh_token', '')
    expires_in = token.get('expires_in', 1000)

    # expires_in is in seconds
    # Get current timestamp (seconds since Unix Epoch) and
    # add expires_in to get expiration time
    # Subtract 5 minutes to allow for clock differences
    expiration = int(time.time()) + expires_in - 300

    # Save the token in the session
    request.session['access_token'] = access_token
    request.session['refresh_token'] = refresh_token
    request.session['token_expires'] = expiration
    request.session['user_email'] = user['mail']
    return HttpResponseRedirect(reverse('bookings:events'))



def events(request):
    # access_token = get_access_token(request, request.build_absolute_uri(reverse('bookings:gettoken')))
    token_obj = SocialToken.objects.filter(account__user__id=request.user.pk, account__provider='microsoft')[0]
    user_email = request.user.email
    # Check if token has expired
    if token_obj.expires_at < timezone.now():
        # refresh token
        set_new_token(token_obj)
    access_token = token_obj.token
    events = get_my_events(access_token, user_email)
    context = {'events': events['value']}
    return render(request, 'bookings/events.html', context)

def set_account_availability(request):
    account = SocialAccount.objects.filter(user__id=request.user.pk, provider='microsoft')[0]
    booking_availability = BookingAvailability.objects.filter(account_social__id=account.pk)
    if request.method == 'POST':
        if booking_availability:
            # i.e. an availability object exists for the account, we update it
            form = BookingAvailabilityForm(data=request.POST, instance=booking_availability[0])
            if form.is_valid():
                form.save()
        else:
            form = BookingAvailabilityForm(data=request.POST)
            if form.is_valid():
                availability = form.save(commit=False)
                availability.account_social = account
                availability.save()
            # availability = form.save(commit=False)
            # availability.account = account
            # availability.save()
        return HttpResponseRedirect(reverse('bookings:set_account_availability'))  # redirect to same page
    else:
        # GET request
        # check if account has a availabiliy object
        # if so then set initial values
        if booking_availability:
            booking_availability = booking_availability[0]
            form = BookingAvailabilityForm(instance=booking_availability)
        else:
            form = BookingAvailabilityForm()
        return render(request, 'bookings/bookingavailability_form.html', {'form': form})


def book_meeting_slot(request, slot, date, pk, event_pk):
    account = SocialAccount.objects.filter(user__id=int(pk))[0]
    token_obj = account.socialtoken_set.get()
    if token_obj.expires_at < timezone.now():
        # refresh token
        set_new_token(token_obj)
    booking_availability = BookingAvailability.objects.filter(account_social__id=account.pk)[0]
    date = datetime.datetime.strptime(slot + ' ' + date, '%H:%M %a %d/%m/%y')
    if request.method == 'POST':
        form = EventBookingForm(date=date, booking_availability=booking_availability, data=request.POST)
        if form.is_valid():
            event = form.save(commit=False)
            event.social_account = account
            event.start_time = make_aware(date)
            event.end_time = make_aware(date + datetime.timedelta(minutes=event.duration))
            event.save()
            event_dict = {'start_time': event.start_time,'end_time': event.end_time,
                          'first_name': event.first_name,'last_name': event.last_name, 'email':event.email,
                          'duration': event.duration,'pk': event.pk, 'subject': event.subject,
                          'username': event.social_account.user.username, 'user_pk': event.social_account.user.pk}
            msg_html = render_to_string('bookings/email_confirmation.html',
                                        {'event': event_dict, 'update': False, ##refactor formatting into function
                                         'start_time_formatted': event_dict['start_time'].strftime('%A, %-d %B %Y %H:%M'),
                                         'end_time_formatted': event_dict['end_time'].strftime('%A, %-d %B %Y %H:%M')})
            response = book_event(access_token=token_obj.token, user_email=account.user.email,
                                  event=event_dict,body_content=msg_html)
            if isinstance(response, dict):  # json response
                event.outlook_id = response.get('id')
                event.save()
                send_mail(subject='New Booking: {}'.format(event.subject), message='', from_email='imeetingbooker@gmail.com',
                          recipient_list=[account.user.email], html_message=msg_html)
                return redirect('bookings:booking_confirmed', pk=event.pk)
            else:
                event.delete() # if outlook event is null delete object
                return HttpResponse('Booking error for {} {}, Error {}'.format(slot, date, response))
        # if not valid
        return render(request, 'bookings/event_booking_form.html', {'form': form})
    else:
        # GET request
        form = EventBookingForm(date=date, booking_availability=booking_availability,
                                initial={'date_time': date.strftime('%A, %-d %B %Y %H:%M')})
        return render(request, 'bookings/event_booking_form.html', {'form': form})
    # return HttpResponse('Booking for {} on {}'.format(slot, date))

'''REFACTOR THIS NAME!!!!'''
def update_meeting_slot(request, slot, date, pk, event_pk):
    account = SocialAccount.objects.filter(user__id=int(pk))[0]
    event = Event.objects.filter(pk=int(event_pk))[0]
    booking_availability = BookingAvailability.objects.filter(account_social__id=account.pk)[0]
    date_obj = datetime.datetime.strptime(slot + ' ' + date, '%H:%M %a %d/%m/%y')
    if request.method == 'POST':
        duration = int(request.POST.get('duration'))
        updated_start = date_obj.strftime('%A, %-d %B %Y %H:%M')
        return render(request, 'bookings/reschedule_confirmation.html', {'event': event,
                                                                         'slot': slot, 'date': date,
                                                                         'duration': duration,
                                                                         'updated_start': updated_start})
    else:
        form = UpdateEventBookingForm(date=date_obj, booking_availability=booking_availability, event=event)
        return render(request, 'bookings/event_booking_form.html', {'form': form})
    # return HttpResponse('Booking for {} on {}'.format(slot, date))


def confirm_slot_reschedule(request, slot, date, event_pk, duration):
    event = Event.objects.filter(pk=int(event_pk))[0]
    social_account = event.social_account
    token_obj = social_account.socialtoken_set.get()
    if token_obj.expires_at < timezone.now():
        # refresh token
        set_new_token(token_obj)
    date_obj = datetime.datetime.strptime(slot + ' ' + date, '%H:%M %a %d/%m/%y')
    event_dict = {'start_time': make_aware(date_obj), 'outlook_id':event.outlook_id, 'end_time':
        make_aware(date_obj + datetime.timedelta(minutes=int(duration))),
        'first_name':event.first_name,'last_name':event.last_name, 'duration':duration,'pk':event.pk,
        'username': event.social_account.user.username, 'user_pk':event.social_account.user.pk, 'subject':event.subject}
    msg_html = render_to_string('bookings/email_confirmation.html',
    {'event': event_dict, 'update': True,'start_time_formatted': event_dict['start_time'].strftime('%A, %-d %B %Y %H:%M'),
     'end_time_formatted':event_dict['end_time'].strftime('%A, %-d %B %Y %H:%M')})
    response = update_booking(token_obj, social_account.user.email, event_dict, body_content=msg_html)
    if isinstance(response, dict):
        event.start_time = event_dict['start_time']
        event.end_time = event_dict['end_time']
        event.duration = int(duration)
        event.outlook_id = response.get('id')
        event.date_time = event_dict['start_time'].strftime('%A, %-d %B %Y %H:%M')
        event.save()
        send_mail(subject='Updated Booking: {}'.format(event.subject), message='', from_email='imeetingbooker@gmail.com',
                  recipient_list=[social_account.user.email], html_message=msg_html)
        return redirect('bookings:booking_confirmed', pk=event.pk)
    return HttpResponse('Booking error for {} {} {}, Error {}'.format(slot, date, duration, response))


def cancel_booking_slot(request, event_pk):
    event = Event.objects.filter(pk=int(event_pk))[0]  # catch event already cancelled error
    if request.method == 'GET':
        return render(request, 'bookings/cancel_booking.html', {'event': event})
    else:
        # send request to cancel/delete outlook event
        social_account = event.social_account
        token_obj = social_account.socialtoken_set.get()
        if token_obj.expires_at < timezone.now():
            # refresh token
            set_new_token(token_obj)
        if cancel_booking(token_obj, social_account.user.email, event.outlook_id):
            event.delete()  # send email
            msg_html = render_to_string('bookings/email_cancellation.html',
                                        {'event': event})
            send_mail(subject='Cancelled Booking: {}'.format(event.email), message='', from_email='imeetingbooker@gmail.com',
                      recipient_list=[social_account.user.email], html_message=msg_html)
            return HttpResponse(content="The event has been cancelled!")


class BookingConfirmedView(DetailView):
    model = Event
    template_name = 'bookings/booking_confirmed.html'


def load_booking_durations(request):
    availability_increment = request.GET.get('availability_increment')
    booking_durations = get_booking_duration_choices(int(availability_increment))
    return render(request, 'bookings/booking_duration_dropdown_list_options.html',
                  {'booking_durations': booking_durations})


def get_booking_duration_choices(increment):
    '''Can be selected up to a specific time'''
    lst = []
    value = increment
    for num in range(12):
        lst.append((value, value))
        value += increment
    return tuple(lst)


def display_available_time_slots(request, name, pk, date=None, action=None, event_pk=0):
    '''TODO IF EVENT DOESNT EXIST DISPLAY MESSAGE EVENT HAS BEEN CANCELLED AND CANNOT BE UPDATED'''
    account = SocialAccount.objects.filter(user__id=int(pk))[0]  # change to pk in url!!!!!! e.g. random user
    booking_availabilty_preferences = BookingAvailability.objects.filter(account_social__id=account.pk)[0]
    if date:
        date = datetime.datetime.strptime(date, '%x')
        if action == 'next':
            date += datetime.timedelta(days=7)
            appear = True  # previous week button appear true
        else:
            date -= datetime.timedelta(days=7)
            if date.date() == datetime.datetime.today().date():
                appear = False
            else:
                appear = True
        date = date.date()
    elif not date:
        date = datetime.datetime.today().date()
        appear = False
    table_data = booking_availabilty_preferences.get_time_slot_data(start_date=date)
    days = BookingAvailability.get_next_7_days(date, format=True)
    if int(event_pk):  # because sometimes '0' string is passed when no event is needed
        table = BookingGrid(table_data, days=days, pk = int(pk), viewname='bookings:update_meeting_slot', event_pk=int(event_pk))
    else:
        table = BookingGrid(table_data, days=days, pk =int(pk))
    # using RequestConfig automatically pulls values from request.GET and updates the table accordingly
    # this enables data ordering and pagination
    RequestConfig(request, paginate=False).configure(table)
    return render(request, 'bookings/display_available_time_slots.html', {'table': table, 'name': name,
                                                                          'date': date.strftime('%x'),
                                                                          'next': 'next', 'prev': 'prev',
                                                                          'appear': appear, 'pk': pk,
                                                                          'event_pk': event_pk})
