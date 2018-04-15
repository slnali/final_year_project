import datetime
import time

import requests
from allauth.socialaccount.models import SocialToken, SocialAccount
from django.conf import settings
from django.core.mail import send_mail
from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, redirect
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.timezone import make_aware
from django.views.generic import DetailView
from django_tables2 import RequestConfig
from django.contrib import messages
from bookings.authhelper import get_signin_url, get_token_from_code, set_new_token
from bookings.booking_grid import BookingGrid
from bookings.forms import BookingAvailabilityForm, EventBookingForm, UpdateEventBookingForm
from bookings.models import BookingAvailability, Event
# Add import statement to include new function
from bookings.outlookservice import get_me, get_my_events, cancel_booking, book_event, update_booking





def events(request):
    """
    Display grid of upcoming outlook events
    :param request:
    :return: events view
    """
    token_obj = SocialToken.objects.filter(account__user__id=request.user.pk)[0]
    user_email = request.user.email
    # Check if token has expired
    if token_obj.expires_at < timezone.now():
        # refresh token
        set_new_token(token_obj)
    access_token = token_obj.token
    outlook_events = get_my_events(access_token, user_email)
    context = {'events': outlook_events['value']}
    return render(request, 'bookings/events.html', context)

def set_account_availability(request):
    """
    Set accounts booking preferences details
    :param request:
    :return: Blank form on GET (no saved), Filled Form on GET (saved),
    POST redirects to existing view GET once prefs saved
    """
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


def validate_recaptcha(request):
    """
    Sends request input to recaptcha endpoint for validation through reCAPTCHA field
    :param request:
    :return: True if validated successfully else False
    """
    recaptcha_response = request.POST.get('g-recaptcha-response')
    data = {
        'secret': settings.GOOGLE_RECAPTCHA_SECRET_KEY,
        'response': recaptcha_response
    }
    r = requests.post('https://www.google.com/recaptcha/api/siteverify', data=data)
    result = r.json()
    if result.get('success'):
        return True
    else:
        messages.error(request, 'reCAPTCHA validation failed. Please try again.')
        return False


def book_meeting_slot(request, slot, date, pk, event_pk):
    """
    View booking form and Book selected event slot
    :param request:
    :param slot: time
    :param date: date
    :param pk: user pk/id
    :param event_pk: event pk/id
    :return:Booking confirmation screen on success, error message below form on error,
    Booking Form on GET req
    """
    account = SocialAccount.objects.filter(user__id=int(pk))[0]
    token_obj = account.socialtoken_set.get()
    if token_obj.expires_at < timezone.now():
        # refresh token
        set_new_token(token_obj)
    booking_availability = BookingAvailability.objects.filter(account_social__id=account.pk)[0]
    date = datetime.datetime.strptime(slot + ' ' + date, '%H:%M %a %d/%m/%y')
    if request.method == 'POST':
        form = EventBookingForm(date=date, booking_availability=booking_availability, data=request.POST)
        if form.is_valid() and validate_recaptcha(request):
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
        messages.warning(request, 'Please correct the error.')
        return render(request, 'bookings/event_booking_form.html', {'form': form, 'captcha':True})
    else:
        # GET request
        form = EventBookingForm(date=date, booking_availability=booking_availability,
                                initial={'date_time': date.strftime('%A, %-d %B %Y %H:%M')})
        return render(request, 'bookings/event_booking_form.html', {'form': form, 'captcha':True})
    # return HttpResponse('Booking for {} on {}'.format(slot, date))

'''REFACTOR THIS NAME!!!!'''
def update_meeting_slot(request, slot, date, pk, event_pk):
    """
    Display Update Booking form for updating event, then continue to reschedule confirmation screen
    :param request:
    :param slot: time
    :param date:
    :param pk:
    :param event_pk:
    :return:
    GET Update booking form once slot chosen,
    POST continue to reschedule confirmation
    """
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
    """
    Confirm reschedule of event slot by updating existing event object
    once outlook event has been rescheduled successfully (POST)
    :param request:
    :param slot:
    :param date:
    :param event_pk:
    :param duration: duration of updated event
    :return: Booking confirmation screen if updated on outlook
    """
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
    """
    Cancel event slot
    :param request:
    :param event_pk: event id to be cancelled
    :return: GET cancel booking confirmation screen, POST event cancelled screen
    """
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
    """
    Class based view for displaying booking confirmed screen
    renders named template and passes Event model context
    """
    model = Event
    template_name = 'bookings/booking_confirmed.html'


def load_booking_durations(request):
    """
    Respond to AJAX request from availabiltiy increment change
    Gets durations for AJAX request and responds
    :param request:
    :return:
    """
    availability_increment = request.GET.get('availability_increment')
    booking_durations = get_booking_duration_choices(int(availability_increment))
    return render(request, 'bookings/booking_duration_dropdown_list_options.html',
                  {'booking_durations': booking_durations})


def get_booking_duration_choices(increment):
    """
    Get duration choices that are mutliple of
    availability increment
    :param increment:
    :return: tuple of tuples for each duration e.g. ((10,10), (20,20), ...)
    """
    lst = []
    value = increment
    for num in range(12):
        lst.append((value, value))
        value += increment
    return tuple(lst)


def display_available_time_slots(request, name, pk, date=None, action=None, event_pk=0):
    """
    Display booking grid with bookable time slots
    :param request:
    :param name: user name
    :param pk:
    :param date:
    :param action: 'next' to get next weeks events otherwise previous week
    :param event_pk:
    :return: GET specified weeks events according to booking availability
    """
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
