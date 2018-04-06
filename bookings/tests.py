import json

from django.test import TestCase, RequestFactory
import datetime
from django.test import TestCase
from .views import get_booking_duration_choices, set_account_availability
from django.utils import timezone
from django.urls import reverse
from allauth.socialaccount.models import SocialAccount, SocialToken
from .models import BookingAvailability
from django.contrib.auth.models import User
from freezegun import freeze_time
from unittest.mock import patch
import responses
from bookings import outlookservice


# Create your tests here.

class BookingAvailabilityViewTests(TestCase):

    def setUp(self):
        self.request_factory = RequestFactory()
        self.user = User.objects.create(username='test_user', password='test_password', email='test_email')
        self.social_account = SocialAccount.objects.create(user=self.user, provider="microsoft")

    def validate_booking_durations(self, increment, result=None):
        output = result or get_booking_duration_choices(increment)
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

    def create_booking_availability_for_account(self):
        monday_from = datetime.time(7, 0)
        monday_to = datetime.timezone(17, 0)
        increment = 20
        duration = 40
        return BookingAvailability.objects.create(account_social=self.social_account,
                                                  monday_from=monday_from, monday_to=monday_to,
                                                  availability_increment=increment, booking_duration=duration)

    def test_account_availability_get(self):
        request = self.request_factory.get(reverse('bookings:set_account_availability'))
        request.user = self.user
        response = set_account_availability(request)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Your Availability Preferences')
        self.assertContains(response, 'datetimepicker12')

    def test_account_availability_get_preferences(self):
        pass

    def test_account_availability_post_save_preferences_new(self):
        pass

    def test_account_availability_post_save_preferences_update(self):
        pass


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
        social_token = SocialToken.objects.create(account_id=1, app_id=1, expires_at=datetime.date(2018, 2,
                                                                                                   9))  # create token and link to account
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
        ####EDIT THIS RESPONSE ... CONFIDENTIAL INFO
        example_outlook_response = {
            '@odata.context': "https://graph.microsoft.com/v1.0/$metadata#users('7038aa2b-a83a-4fa3-9311-2664762efa74')/calendarView",
            'value': [{'@odata.etag': 'W/"7aT8fM//o0qUPm978Q+uhgADO7q/dw=="',
                       'id': 'AAMkAGZmMjI1Njg5LTU4Y2QtNDk5ZS1iZWRhLWM1YWJmNmVhNTNhOABGAAAAAAB2selteOuqT4LvathzWRFyBwDtpPx8z-_jSpQ_b3vxD66GAAAAAAENAADtpPx8z-_jSpQ_b3vxD66GAAM7ch3dAAA=',
                       'createdDateTime': '2018-02-15T00:47:04.6107372Z',
                       'lastModifiedDateTime': '2018-02-15T00:47:19.2052453Z',
                       'changeKey': '7aT8fM//o0qUPm978Q+uhgADO7q/dw==', 'categories': [],
                       'originalStartTimeZone': 'GMT Standard Time', 'originalEndTimeZone': 'GMT Standard Time',
                       'iCalUId': '040000008200E00074C5B7101A82E00800000000A669AC7FF6A5D301000000000000000010000000C7013EC7F8635143B9DFF8401FC5D8FE',
                       'reminderMinutesBeforeStart': 15, 'isReminderOn': True, 'hasAttachments': False,
                       'subject': 'something', 'bodyPreview': '', 'importance': 'normal', 'sensitivity': 'normal',
                       'isAllDay': False, 'isCancelled': False, 'isOrganizer': True, 'responseRequested': True,
                       'seriesMasterId': None, 'showAs': 'busy', 'type': 'singleInstance',
                       'webLink': 'https://outlook.office365.com/owa/?itemid=AAMkAGZmMjI1Njg5LTU4Y2QtNDk5ZS1iZWRhLWM1YWJmNmVhNTNhOABGAAAAAAB2selteOuqT4LvathzWRFyBwDtpPx8z%2F%2BjSpQ%2Bb3vxD66GAAAAAAENAADtpPx8z%2F%2BjSpQ%2Bb3vxD66GAAM7ch3dAAA%3D&exvsurl=1&path=/calendar/item',
                       'onlineMeetingUrl': None,
                       'responseStatus': {'response': 'organizer', 'time': '0001-01-01T00:00:00Z'},
                       'body': {'contentType': 'html',
                                'content': '<html>\r\n<head>\r\n<meta http-equiv="Content-Type" content="text/html; charset=utf-8">\r\n<meta content="text/html; charset=us-ascii">\r\n<style type="text/css" style="display:none">\r\n<!--\r\np\r\n\t{margin-top:0;\r\n\tmargin-bottom:0}\r\n-->\r\n</style>\r\n</head>\r\n<body dir="ltr">\r\n<div id="divtagdefaultwrapper" dir="ltr" style="font-size:12pt; color:#000000; font-family:Calibri,Helvetica,sans-serif">\r\n<p style="margin-top:0; margin-bottom:0"><br>\r\n</p>\r\n</div>\r\n</body>\r\n</html>\r\n'},
                       'start': {'dateTime': '2018-02-16T10:00:00.0000000', 'timeZone': 'Europe/London'},
                       'end': {'dateTime': '2018-02-16T10:30:00.0000000', 'timeZone': 'Europe/London'},
                       'location': {'displayName': '', 'address': {}}, 'recurrence': None, 'attendees': [],
                       'organizer': {'emailAddress': {'name': 'Wijesinghe, Nalintha',
                                                      'address': 'nalintha.wijesinghe@kcl.ac.uk'}}}]}
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


'''

empty
{'@odata.context': "https://graph.microsoft.com/v1.0/$metadata#users('7038aa2b-a83a-4fa3-9311-2664762efa74')/calendarView", 'value': []}

1 event 
{'@odata.context': "https://graph.microsoft.com/v1.0/$metadata#users('7038aa2b-a83a-4fa3-9311-2664762efa74')/calendarView", 'value': [{'@odata.etag': 'W/"7aT8fM//o0qUPm978Q+uhgADO7q/dw=="', 'id': 'AAMkAGZmMjI1Njg5LTU4Y2QtNDk5ZS1iZWRhLWM1YWJmNmVhNTNhOABGAAAAAAB2selteOuqT4LvathzWRFyBwDtpPx8z-_jSpQ_b3vxD66GAAAAAAENAADtpPx8z-_jSpQ_b3vxD66GAAM7ch3dAAA=', 'createdDateTime': '2018-02-15T00:47:04.6107372Z', 'lastModifiedDateTime': '2018-02-15T00:47:19.2052453Z', 'changeKey': '7aT8fM//o0qUPm978Q+uhgADO7q/dw==', 'categories': [], 'originalStartTimeZone': 'GMT Standard Time', 'originalEndTimeZone': 'GMT Standard Time', 'iCalUId': '040000008200E00074C5B7101A82E00800000000A669AC7FF6A5D301000000000000000010000000C7013EC7F8635143B9DFF8401FC5D8FE', 'reminderMinutesBeforeStart': 15, 'isReminderOn': True, 'hasAttachments': False, 'subject': 'something', 'bodyPreview': '', 'importance': 'normal', 'sensitivity': 'normal', 'isAllDay': False, 'isCancelled': False, 'isOrganizer': True, 'responseRequested': True, 'seriesMasterId': None, 'showAs': 'busy', 'type': 'singleInstance', 'webLink': 'https://outlook.office365.com/owa/?itemid=AAMkAGZmMjI1Njg5LTU4Y2QtNDk5ZS1iZWRhLWM1YWJmNmVhNTNhOABGAAAAAAB2selteOuqT4LvathzWRFyBwDtpPx8z%2F%2BjSpQ%2Bb3vxD66GAAAAAAENAADtpPx8z%2F%2BjSpQ%2Bb3vxD66GAAM7ch3dAAA%3D&exvsurl=1&path=/calendar/item', 'onlineMeetingUrl': None, 'responseStatus': {'response': 'organizer', 'time': '0001-01-01T00:00:00Z'}, 'body': {'contentType': 'html', 'content': '<html>\r\n<head>\r\n<meta http-equiv="Content-Type" content="text/html; charset=utf-8">\r\n<meta content="text/html; charset=us-ascii">\r\n<style type="text/css" style="display:none">\r\n<!--\r\np\r\n\t{margin-top:0;\r\n\tmargin-bottom:0}\r\n-->\r\n</style>\r\n</head>\r\n<body dir="ltr">\r\n<div id="divtagdefaultwrapper" dir="ltr" style="font-size:12pt; color:#000000; font-family:Calibri,Helvetica,sans-serif">\r\n<p style="margin-top:0; margin-bottom:0"><br>\r\n</p>\r\n</div>\r\n</body>\r\n</html>\r\n'}, 'start': {'dateTime': '2018-02-16T10:00:00.0000000', 'timeZone': 'Europe/London'}, 'end': {'dateTime': '2018-02-16T10:30:00.0000000', 'timeZone': 'Europe/London'}, 'location': {'displayName': '', 'address': {}}, 'recurrence': None, 'attendees': [], 'organizer': {'emailAddress': {'name': 'Wijesinghe, Nalintha', 'address': 'nalintha.wijesinghe@kcl.ac.uk'}}}]}


'''


class OutlookServiceTests(TestCase):

    @responses.activate
    def test_get_my_events_404_error(self):
        responses.add(responses.GET, 'https://graph.microsoft.com/v1.0/me/events', json={'error': 'not found'},
                      status=404)
        resp = outlookservice.get_my_events('token', 'email')
        self.assertEquals(resp, '404: {"error": "not found"}')

    @responses.activate
    def test_get_my_events_200(self):
        responses.add(responses.GET, 'https://graph.microsoft.com/v1.0/me/events', json={'example': 1},
                      status=200)
        resp = outlookservice.get_my_events('token', 'email')
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
