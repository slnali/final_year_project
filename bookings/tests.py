import datetime
from unittest.mock import patch

import responses
from allauth.socialaccount.models import SocialAccount, SocialToken
from django.contrib.auth.models import User
from django.test import RequestFactory
from django.test import TestCase
from django.urls import reverse
from freezegun import freeze_time

from bookings import outlookservice
from bookings import views
from .models import BookingAvailability, Event


class BookingDurationChoiceTests(TestCase):
    def validate_booking_durations(self, increment, result=None):
        output = result or views.get_booking_duration_choices(increment)
        for elem in output:
            self.assertTrue(elem[0] % increment == 0)

    def test_get_booking_duration_choices(self):
        increments = [10, 20, 60]
        for increment in increments:
            self.validate_booking_durations(increment)

    def test_load_booking_durations(self):
        response = self.client.get(reverse('bookings:ajax_load_booking_durations'), {'availability_increment': 10})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 20)
        self.validate_booking_durations(10, result=response.context.get('booking_durations'))


class BookingSetAvailabilityViewTests(TestCase):

    def setUp(self):
        self.user = User.objects.create(username='test_user', password='test_password', email='test_email')
        self.social_account = SocialAccount.objects.create(user=self.user, provider="microsoft")
        self.client.force_login(self.user)

    def create_booking_availability_for_account(self, time_from, time_to, increment, duration):
        monday_from = time_from
        monday_to = time_to
        return BookingAvailability.objects.create(
            account_social=self.social_account,
            monday_from=monday_from,
            monday_to=monday_to,
            availability_increment=increment,
            booking_duration=duration
        )

    def test_booking_availability_get(self):
        response = views.set_account_availability(self.request_factory)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Your Availability Preferences')
        self.assertContains(response, 'datetimepicker12')

    def test_booking_availability_get_preferences(self):
        self.create_booking_availability_for_account(datetime.time(7, 0), datetime.time(17, 0), 20, 40)
        response = self.client.get(reverse('bookings:set_account_availability'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="monday_from" value="07:00 AM"')
        self.assertContains(response, 'name="monday_to" value="05:00 PM"')
        self.assertContains(response, 'value="20" selected')
        self.assertContains(response, 'value="40" selected')

    def test_booking_availability_post_save_preferences_new(self):
        response = self.client.post(reverse('bookings:set_account_availability'),
                                    {'monday_from': datetime.time(8, 0),
                                     'monday_to': datetime.time(18, 0),
                                     'availability_increment': 10,
                                     'booking_duration': 30}, follow=True)
        self.assertRedirects(response, reverse('bookings:set_account_availability'))
        self.assertEqual(response.status_code, 200)  # redirect
        self.assertContains(response, 'name="monday_from" value="08:00 AM"')
        self.assertContains(response, 'name="monday_to" value="06:00 PM"')
        self.assertContains(response, 'value="10" selected')
        self.assertContains(response, 'value="30" selected')

    def test_account_availability_post_save_preferences_update(self):
        self.create_booking_availability_for_account(datetime.time(7, 0), datetime.time(17, 0), 20, 40)
        response = self.client.post(reverse('bookings:set_account_availability'),
                                    {'monday_from': datetime.time(8, 0),
                                     'monday_to': datetime.time(18, 0),
                                     'availability_increment': 10,
                                     'booking_duration': 30}, follow=True)
        self.assertEqual(response.status_code, 200)  # redirect
        self.assertContains(response, 'name="monday_from" value="08:00 AM"')
        self.assertContains(response, 'name="monday_to" value="06:00 PM"')
        self.assertContains(response, 'value="10" selected')
        self.assertContains(response, 'value="30" selected')


class BookingReCaptchaValidationTests(TestCase):

    def setUp(self):
        self.factory = RequestFactory()

    @responses.activate
    def test_validate_recaptcha_true(self):
        responses.add(responses.POST, 'https://www.google.com/recaptcha/api/siteverify', json={'success': True},
                      status=200)
        request = self.factory.post(reverse('bookings:set_account_availability'), {'g-recaptcha-response': True},
                                    force=True)
        self.assertTrue(views.validate_recaptcha(request))

    @patch('bookings.views.messages')
    @responses.activate
    def test_validate_recaptcha_false(self, messages):
        responses.add(responses.POST, 'https://www.google.com/recaptcha/api/siteverify', json={},
                      status=404)
        request = self.factory.post(reverse('bookings:set_account_availability'), {'g-recaptcha-response': True},
                                    force=True)
        resp = views.validate_recaptcha(request)
        self.assertFalse(resp)
        messages.error.assert_called_with(request, 'Invalid reCAPTCHA. Please try again.')


class BookingBookMeetingSlotTests(TestCase):

    @freeze_time("2018-02-10 10:20:00")
    def setUp(self):
        self.user = User.objects.create(username='test_user', password='test_password', email='test_email')
        self.social_account = SocialAccount.objects.create(user=self.user, provider="microsoft")
        self.social_token = SocialToken.objects.create(account_id=1, app_id=1, expires_at=datetime.date(2018, 2, 9))
        self.client.force_login(self.user)
        self.booking_availability = self.create_booking_availability_for_account(datetime.time(7, 0),
                                                                                 datetime.time(17, 0), 20, 40)
        self.date = datetime.datetime.now()
        self.time = self.date.time().strftime('%H:%M')
        self.date_formatted = self.date.date().strftime('%a %d/%m/%y')

    def create_booking_availability_for_account(self, time_from, time_to, increment, duration):
        monday_from = time_from
        monday_to = time_to
        return BookingAvailability.objects.create(
            account_social=self.social_account,
            monday_from=monday_from,
            monday_to=monday_to,
            availability_increment=increment,
            booking_duration=duration
        )

    @patch('bookings.views.EventBookingForm')
    @patch('bookings.views.set_new_token')
    def test_book_meeting_slot_get(self, token_patch, booking_form):
        response = self.client.get(
            reverse('bookings:book_meeting_slot', args=[self.time, self.date_formatted, '1', '2']))
        self.assertEqual(response.status_code, 200)
        booking_form.assert_called_with(date=self.date, booking_availability=self.booking_availability,
                                        initial={'date_time': self.date.strftime('%A, %-d %B %Y %H:%M')})
        self.assertContains(response, 'recaptcha')

    @patch('bookings.views.messages')
    @patch('bookings.views.set_new_token')
    @patch('bookings.views.EventBookingForm')
    def test_book_meeting_slot_invalid_form(self, booking_form, token_patch, messages):
        booking_form().is_valid.return_value = False
        response = self.client.post(
            reverse('bookings:book_meeting_slot', args=[self.time, self.date_formatted, '1', '2']),
            data={})
        self.assertEqual(response.status_code, 200)
        messages.warning.assert_called()

    @patch('bookings.views.set_new_token')
    @patch('bookings.views.EventBookingForm')
    @patch('bookings.views.validate_recaptcha')
    @patch('bookings.views.render_to_string')
    @patch('bookings.views.book_event')
    @patch('bookings.views.send_mail')
    def test_book_meeting_slot_invalid_form(self, send_mail, book_event, render_string, captcha, booking_form,
                                            token_patch):
        captcha.return_value = True
        booking_form().is_valid.return_value = True
        booking_form().save.return_value = Event(
            first_name='fn',last_name='ln',email='em',duration=10,subject='sub'
        )
        render_string.return_value = 'htmlMessage'
        book_event.return_value = {'id':1}
        response = self.client.post(
            reverse('bookings:book_meeting_slot', args=[self.time, self.date_formatted, '1', '2']),
            data={}, follow=True)
        send_mail.assert_called_with(subject='New Booking: sub', message='', from_email='imeetingbooker@gmail.com',
                          recipient_list=['test_email'], html_message='htmlMessage')
        self.assertRedirects(response,reverse('bookings:booking_confirmed', args=[1]))
        self.assertEqual(response.status_code, 200)
    # first_name =last_name = email =duration =subject =


class BookingAvailabilityModelTests(TestCase):

    def setUp(self):
        self.booking_obj = BookingAvailability.objects.create(
            monday_from=datetime.time(8, 0),
            monday_to=datetime.time(16, 0),
            tuesday_from=datetime.time(8, 0),
            tuesday_to=datetime.time(16, 0),
            wednesday_from=datetime.time(8, 0),
            wednesday_to=datetime.time(16, 0),
            thursday_from=datetime.time(8, 0),
            thursday_to=datetime.time(16, 0),
            friday_from=datetime.time(8, 0),
            friday_to=datetime.time(16, 0),
            saturday_to=None,
            saturday_from=None,
            sunday_to=None,
            sunday_from=None,
            availability_increment=10,
            booking_duration=10,
        )
        user = User.objects.create(username='test_user', password='test_password', email='test_email')
        social_account = SocialAccount.objects.create(user=user, provider="microsoft", )
        # create token and link to account
        social_token = SocialToken.objects.create(account_id=1, app_id=1, expires_at=datetime.date(2018, 2, 9))
        self.booking_obj.account_social = social_account

    def test_get_time_ranges(self):
        min, max = self.booking_obj.get_time_ranges()
        self.assertEqual(min, datetime.time(8, 0))
        self.assertEqual(max, datetime.time(16, 0))

    @freeze_time("2018-02-10")  # test end of the year
    def test_get_next_7_days(self):
        # freezetime library mocks datetime module to freeze time for a specific date mentioned in decorator
        next_7_days = self.booking_obj.get_next_7_days(datetime.date.today())
        self.assertEqual(next_7_days,
                         [datetime.date(2018, 2, 10), datetime.date(2018, 2, 11), datetime.date(2018, 2, 12),
                          datetime.date(2018, 2, 13), datetime.date(2018, 2, 14), datetime.date(2018, 2, 15),
                          datetime.date(2018, 2, 16)])

    @patch('bookings.models.get_events_between_dates')
    @patch('bookings.models.set_new_token')
    @freeze_time("2018-02-10 10:21:34")
    def test_get_outlook_events(self, set_new_token_mock, get_events_call_mock):
        dates = [datetime.date(2018, 2, 10), datetime.date(2018, 2, 11), datetime.date(2018, 2, 12)]
        data = self.booking_obj.get_outlook_events(dates)
        get_events_call_mock.assert_called_with(access_token=self.booking_obj.account_social.socialtoken_set.get(),
                                                user_email='test_email', start_date='2018-02-10',
                                                end_date='2018-02-12')

    def test_get_times_by_increment(self):
        self.booking_obj.availability_increment = 20
        times = self.booking_obj.get_times_by_increment(min_time=datetime.time(9, 0), max_time=datetime.time(17, 0))
        self.assertEqual(times[0].time(), datetime.time(9, 0))
        self.assertEqual(times[-1].time(), datetime.time(17, 0))
        self.assertEqual(times[1] - times[0], datetime.timedelta(minutes=self.booking_obj.availability_increment))
        self.assertEqual(times[-1] - times[-2], datetime.timedelta(minutes=self.booking_obj.availability_increment))

    def test_parse_outlook_events_into_dict(self):
        example_outlook_response = {
            '@odata.context': "https://graph.microsoft.com/v1.0/$metadata#users('7038aa2b-a83a-4fa3-9311-2664762efa74')/calendarView",
            'value': [{'isAllDay': False, 'isCancelled': False, 'isOrganizer': True, 'responseRequested': True,
                       'body': {'contentType': 'html',},
                       'start': {'dateTime': '2018-02-16T10:00:00.0000000', 'timeZone': 'Europe/London'},
                       'end': {'dateTime': '2018-02-16T10:30:00.0000000', 'timeZone': 'Europe/London'}}]}
        output = self.booking_obj.parse_outlook_events_into_dict(example_outlook_response)
        output = output[0]
        self.assertEqual(output.get('start'), datetime.datetime(2018, 2, 16, 10, 0))
        self.assertEqual(output.get('end'), datetime.datetime(2018, 2, 16, 10, 30))
        self.assertEqual(output.get('is_all_day'), False)

    @patch.object(BookingAvailability, 'get_outlook_events')
    def test_get_day_time_availability_dict(self, get_events_patch):
        days = [datetime.date(2018, 2, 10), datetime.date(2018, 2, 11), datetime.date(2018, 2, 12),
                datetime.date(2018, 2, 13), datetime.date(2018, 2, 14), datetime.date(2018, 2, 15),
                datetime.date(2018, 2, 16)]
        times = [datetime.datetime(1, 1, 1, 9, 0), datetime.datetime(1, 1, 1, 9, 30), datetime.datetime(1, 1, 1, 10, 0),
                 datetime.datetime(1, 1, 1, 10, 30), datetime.datetime(1, 1, 1, 11, 0),
                 datetime.datetime(1, 1, 1, 11, 30), datetime.datetime(1, 1, 1, 12, 0)]
        outlook_event = [{'start': datetime.datetime(2018, 2, 16, 10, 0), 'end': datetime.datetime(2018, 2, 16, 10, 30),
                          'is_all_day': False}]
        with patch.object(self.booking_obj, 'parse_outlook_events_into_dict', return_value=outlook_event):
            data = self.booking_obj.get_day_time_availability_dict(days=days, times=times)
            data_for_10AM_booking, data_for_1030AM_booking = data[2], data[3]
            self.assertNotIn('Fri 16/02/18', data_for_10AM_booking)
            self.assertIn('Fri 16/02/18', data_for_1030AM_booking)

    def test_get_day_availability_dict(self):
        dic = self.booking_obj.get_day_availability_dict()
        days = ['Monday{}', 'Tuesday{}', 'Wednesday{}', 'Thursday{}', 'Friday{}', 'Saturday{}', 'Sunday{}']
        self.assertIsInstance(dic, dict)
        for day in days:
            day_data = dic.get(day.format(''))
            self.assertEqual(day_data.get('start'), getattr(self.booking_obj, day.format('_from').lower()))
            self.assertEqual(day_data.get('end'), getattr(self.booking_obj, day.format('_to').lower()))

    @freeze_time("2018-02-8 10:21:34")
    def test_slot_is_available_slot_in_past(self):
        past_time = datetime.time(10, 0)
        past_date = datetime.date(2018, 2, 8)
        self.assertEqual(self.booking_obj.slot_is_available(past_time, past_date, outlook_events=[]), False)

    @freeze_time("2018-02-8 10:21:34")
    def test_slot_is_available_outside_booking_availabilty(self):
        past_time = datetime.time(10, 0)
        past_date = datetime.date(2018, 2, 10)
        self.assertEqual(self.booking_obj.slot_is_available(past_time, past_date, outlook_events=[]), False)

    @freeze_time("2018-02-6 10:21:34")
    def test_slot_is_available_not_in_booking_availabilty(self):
        past_time = datetime.time(7, 0)
        past_date = datetime.date(2018, 2, 8)
        self.assertEqual(self.booking_obj.slot_is_available(past_time, past_date, outlook_events=[]), False)

    @freeze_time("2018-02-6 10:21:34")
    def test_slot_is_available_slot_in_booking_availabilty(self):
        past_time = datetime.time(10, 0)
        past_date = datetime.date(2018, 2, 8)
        self.assertEqual(self.booking_obj.slot_is_available(past_time, past_date, outlook_events=[]), True)

    @freeze_time("2018-02-4 10:21:34")
    def test_slot_is_available_slot_within_outlook_event(self):
        past_time = datetime.time(10, 15)
        past_date = datetime.date(2018, 2, 6)
        outlook_event = [{'start': datetime.datetime(2018, 2, 6, 10, 0), 'end': datetime.datetime(2018, 2, 6, 10, 30),
                          'is_all_day': False}]
        self.assertEqual(self.booking_obj.slot_is_available(past_time, past_date, outlook_events=outlook_event), False)

    @freeze_time("2018-02-4 10:21:34")
    def test_slot_is_available_slot_within_outlook_event_is_all_day(self):
        past_time = datetime.time(10, 15)
        past_date = datetime.date(2018, 2, 6)
        outlook_event = [{'start': datetime.datetime(2018, 2, 6, 10, 0), 'end': datetime.datetime(2018, 2, 6, 10, 30),
                          'is_all_day': True}]
        self.assertEqual(self.booking_obj.slot_is_available(past_time, past_date, outlook_events=outlook_event), False)

    @freeze_time("2018-02-4 10:21:34")
    def test_slot_is_available_slot_outside_outlook_event(self):
        past_time = datetime.time(14, 15)
        past_date = datetime.date(2018, 2, 6)
        outlook_event = [{'start': datetime.datetime(2018, 2, 6, 10, 0), 'end': datetime.datetime(2018, 2, 6, 10, 30),
                          'is_all_day': False}]
        self.assertEqual(self.booking_obj.slot_is_available(past_time, past_date, outlook_events=outlook_event), True)

    @freeze_time("2018-02-4 10:21:34")
    def test_slot_is_available_in_short_break_slot(self):
        past_time = datetime.time(10, 15)
        past_date = datetime.date(2018, 2, 6)
        short_break_slots = [datetime.datetime(2018, 2, 6, 10, 15)]
        outlook_event = []
        self.assertEqual(
            self.booking_obj.slot_is_available(past_time, past_date, outlook_event, short_break_slots), False
        )

    @freeze_time("2018-02-4 10:21:34")
    def test_get_breaks_between_close_sets_of_meetings(self):
        '''response from outlook gives us data sorted by date and time'''
        outlook_events = [{'start': datetime.datetime(2018, 2, 6, 9, 30), 'end': datetime.datetime(2018, 2, 6, 10, 0),
                          'is_all_day': False},
                         {'start': datetime.datetime(2018, 2, 6, 10, 0), 'end': datetime.datetime(2018, 2, 6, 10, 15),
                          'is_all_day': False},
                         {'start': datetime.datetime(2018, 2, 6, 10, 30), 'end': datetime.datetime(2018, 2, 6, 10, 45),
                          'is_all_day': False}
                         ]
        '''cluster each day into dict of lists for each list of lists we find breaks'''
        output = [datetime.datetime(2018, 2, 6, 10, 15)]
        self.assertEqual(self.booking_obj.get_breaks_between_close_sets_of_events(self.booking_obj.get_next_7_days(datetime.date.today()),outlook_events), output)

    def test_get_day_events_dict(self):
        outlook_events = [{'start': datetime.datetime(2018, 2, 6, 9, 30), 'end': datetime.datetime(2018, 2, 6, 10, 0),
                           'is_all_day': False},
                          {'start': datetime.datetime(2018, 2, 6, 10, 0), 'end': datetime.datetime(2018, 2, 6, 10, 15),
                           'is_all_day': False},
                          {'start': datetime.datetime(2018, 2, 7, 10, 30), 'end': datetime.datetime(2018, 2, 7, 10, 45),
                           'is_all_day': False}
                          ]
        output = self.booking_obj.get_day_events_dict(outlook_events)
        self.assertEqual(len(output.keys()),2)
        self.assertEqual(len(output[datetime.date(2018, 2, 6)]), 2)
        self.assertEqual(len(output[datetime.date(2018, 2, 7)]), 1)


class OutlookServiceTests(TestCase):

    @responses.activate
    def test_get_my_events_404_error(self):
        responses.add(responses.GET, 'https://graph.microsoft.com/v1.0/me/events', json={'error': 'not found'},
                      status=404)
        resp = outlookservice.get_outlook_events('token', 'email')
        self.assertEquals(resp, '404: {"error": "not found"}')

    @responses.activate
    def test_get_my_events_200(self):
        responses.add(responses.GET, 'https://graph.microsoft.com/v1.0/me/events', json={'example': 1},
                      status=200)
        resp = outlookservice.get_outlook_events('token', 'email')
        self.assertEquals(resp, {'example': 1})

    @responses.activate
    def test_get_my_events_between_dates_404(self):
        responses.add(responses.GET, 'https://graph.microsoft.com/v1.0/me/calendarview', json={'error': 'not found'},
                      status=404)
        resp = outlookservice.get_events_between_dates('token', 'email', 'date1', 'date2')
        self.assertEquals(resp, '404: {"error": "not found"}')

    @responses.activate
    def test_get_my_events_between_dates_200(self):
        responses.add(responses.GET, 'https://graph.microsoft.com/v1.0/me/calendarview', json={'example': 2},
                      status=200)
        resp = outlookservice.get_events_between_dates('token', 'email', 'date1', 'date2')
        self.assertEquals(resp, {'example': 2})

    @responses.activate
    @freeze_time("2018-02-4 10:21:34")
    def test_update_booking_404(self):
        responses.add(responses.PATCH, 'https://graph.microsoft.com/v1.0/me/events/5', json={'error': 'not found'},
                      status=404)
        start = datetime.datetime.now()
        end = start + datetime.timedelta(hours=1)
        payload = {
            "subject": 'test',
            "body": {
                "contentType": "HTML",
                "content": 'content'
            },
            "start": {
                "dateTime": "2018-02-04T10:21:34+00:00",
                "timeZone": "Europe/London"
            },
            "end": {
                "dateTime": "2018-02-04T11:21:34+00:00",
                "timeZone": "Europe/London"
            },
        }
        event = {'subject': 'test', 'outlook_id': 5, 'start_time': start, 'end_time': end}
        resp = outlookservice.update_booking('token', 'email', event, 'content')
        self.assertEquals(resp, '404: {{"error": "not found"}} Request: {}'.format(payload))

    @responses.activate
    @freeze_time("2018-04-4 10:21:34")
    def test_update_booking_404_daylight_savings(self):
        # daylight savings end of march test onwards
        responses.add(responses.PATCH, 'https://graph.microsoft.com/v1.0/me/events/5', json={'error': 'not found'},
                      status=404)
        start = datetime.datetime.now()
        end = start + datetime.timedelta(hours=1)
        payload = {
            "subject": 'test',
            "body": {
                "contentType": "HTML",
                "content": 'content'
            },
            "start": {
                "dateTime": "2018-04-04T10:21:34+01:00",
                "timeZone": "Europe/London"
            },
            "end": {
                "dateTime": "2018-04-04T11:21:34+01:00",
                "timeZone": "Europe/London"
            },
        }
        event = {'subject': 'test', 'outlook_id': 5, 'start_time': start, 'end_time': end}
        resp = outlookservice.update_booking('token', 'email', event, 'content')
        self.assertEquals(resp, '404: {{"error": "not found"}} Request: {}'.format(payload))

    @responses.activate
    @freeze_time("2018-02-4 10:21:34")
    def test_get_my_events_between_dates_200(self):
        responses.add(responses.PATCH, 'https://graph.microsoft.com/v1.0/me/events/5', json={'output': 1},
                      status=200)
        start = datetime.datetime.now()
        end = start + datetime.timedelta(hours=1)
        event = {'subject': 'test', 'outlook_id': 5, 'start_time': start, 'end_time': end}
        resp = outlookservice.update_booking('token', 'email', event, 'content')
        self.assertEquals(resp, {'output': 1})

    @responses.activate
    def test_cancel_booking_failed_404(self):
        responses.add(responses.DELETE, 'https://graph.microsoft.com/v1.0/me/events/5', json={'error': 'not found'},
                      status=404)
        resp = outlookservice.cancel_booking('token', 'email', '5')
        self.assertEquals(resp, False)

    @responses.activate
    def test_cancel_booking_success_204(self):
        responses.add(responses.DELETE, 'https://graph.microsoft.com/v1.0/me/events/5', json={'output': 1},
                      status=204)
        resp = outlookservice.cancel_booking('token', 'email', '5')
        self.assertEquals(resp, True)

    @responses.activate
    @freeze_time("2018-02-4 10:21:34")
    def test_book_event_404(self):
        responses.add(responses.POST, 'https://graph.microsoft.com/v1.0/me/events', json={'error': 'not found'},
                      status=404)
        start = datetime.datetime.now()
        end = start + datetime.timedelta(hours=1)
        event = {'subject': 'test', 'outlook_id': 5, 'start_time': start, 'end_time': end, 'content': 'content',
                 'email': 'email', 'first_name': 'name'}
        payload = {
            "subject": event['subject'],
            "body": {
                "contentType": "HTML",
                "content": event['content'],
            },
            "start": {
                "dateTime": event['start_time'].astimezone().isoformat(),
                "timeZone": "Europe/London"
            },
            "end": {
                "dateTime": event['end_time'].astimezone().isoformat(),
                "timeZone": "Europe/London"
            },
            "attendees": [
                {
                    "emailAddress": {
                        "address": event['email'],
                        "name": event['first_name'],
                    },
                    "type": "optional"
                }
            ]
        }

        resp = outlookservice.book_event('token', 'email', event, event['content'])
        self.assertEquals(resp, '404: {{"error": "not found"}} Request: {}'.format(payload))

    @responses.activate
    @freeze_time("2018-02-4 10:21:34")
    def test_book_event_201(self):
        responses.add(responses.POST, 'https://graph.microsoft.com/v1.0/me/events', json={'output': 1},
                      status=201)
        start = datetime.datetime.now()
        end = start + datetime.timedelta(hours=1)
        event = {'subject': 'test', 'outlook_id': 5, 'start_time': start, 'end_time': end, 'content': 'content',
                 'email': 'email', 'first_name': 'name'}
        resp = outlookservice.book_event('token', 'email', event, event['content'])
        self.assertEquals(resp, {'output': 1})
