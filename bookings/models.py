import dateutil.parser
from django.core.exceptions import ValidationError
from django.db import models
from allauth.socialaccount.models import SocialAccount
from bookings.outlookservice import get_events_between_dates
# from bookings.views import set_new_token
from bookings.authhelper import set_new_token
from django.utils import timezone
from django.core.validators import validate_email
import datetime


class BookingAvailability(models.Model):
    AVAILABILITY_INCREMENTS = (
        (5, 5),
        (10, 10),
        (15, 15),
        (20, 20),
        (30, 30),
        (40, 40),
        (45, 45),
        (60, 60),
    )
    account_social = models.OneToOneField(SocialAccount, related_name='availability_prefs', blank=True, null=True)
    monday_from = models.TimeField(blank=True, null=True)
    monday_to = models.TimeField(blank=True, null=True)
    tuesday_from = models.TimeField(blank=True, null=True)
    tuesday_to = models.TimeField(blank=True, null=True)
    wednesday_from = models.TimeField(blank=True, null=True)
    wednesday_to = models.TimeField(blank=True, null=True)
    thursday_from = models.TimeField(blank=True, null=True)
    thursday_to = models.TimeField(blank=True, null=True)
    friday_from = models.TimeField(blank=True, null=True)
    friday_to = models.TimeField(blank=True, null=True)
    saturday_from = models.TimeField(blank=True, null=True)
    saturday_to = models.TimeField(blank=True, null=True)
    sunday_from = models.TimeField(blank=True, null=True)
    sunday_to = models.TimeField(blank=True, null=True)
    lunch_from = models.TimeField(blank=True, null=True)
    lunch_to = models.TimeField(blank=True, null=True)
    availability_increment = models.IntegerField(
        choices=AVAILABILITY_INCREMENTS,
        default=10
    )
    booking_duration = models.IntegerField(
        choices=(),
    )


    def get_time_slot_data(self, start_date=None, format=True):
        '''
        :return: list of dicts from current date e.g. TUE 13/02/18 => 7 days
        '''
        days = self.get_next_7_days(start_date)
        min_time, max_time = self.get_time_ranges()
        times = self.get_times_by_increment(min_time, max_time)
        date_time_data_dict = self.get_day_time_availability_dict(days, times, format)
        return date_time_data_dict

    @staticmethod
    def get_next_7_days(start_date, format=False):
        '''
        Get next 7 days of datetime objects starting from current day
        :param start_date: starting date
        :param format: format date in form e.g. Tue 06/01/2018
        :return: list of datetime objects
        '''
        return [start_date.strftime('%a %d/%m/%y') if format else start_date] + \
               [(start_date + datetime.timedelta(days=num)).strftime('%a %d/%m/%y')
                if format else (start_date + datetime.timedelta(days=num)) for num in range(1, 8)]

    def get_time_ranges(self):
        '''
        Get minimum from time and maximum to time
        :return: tuple(min time, max time)
        '''
        filter_none = lambda lst: [elem for elem in lst if elem is not None]
        default_start, default_end = [datetime.time(23, 59)], [datetime.time(0, 0)]
        start_times = [self.monday_from, self.tuesday_from,
                       self.wednesday_from, self.thursday_from,
                       self.friday_from, self.saturday_from,
                       self.sunday_from]
        end_times = [self.monday_to, self.tuesday_to,
                     self.wednesday_to, self.thursday_to,
                     self.friday_to, self.saturday_to,
                     self.sunday_to]
        return min(filter_none(start_times) or default_start), max(filter_none(end_times) or default_end)

    def get_times_by_increment(self, min_time, max_time):
        '''
        :param min_time: earliest time possible start
        :param max_time: latest time possible end
        :return: list of times between start and end by increment on availability model
        e.g. 20 min increment 9:00AM start 5:00PM end
        returns [9:00,9:20,9:40,10:00,10:20 ... 16:40, 17:00] as datetime objects
        '''
        min_datetime = datetime.datetime.combine(datetime.date.min, min_time)
        max_datetime = datetime.datetime.combine(datetime.date.min, max_time)
        times = []
        while min_datetime <= max_datetime:
            times.append(min_datetime)
            min_datetime += datetime.timedelta(minutes=self.availability_increment)
        return times

    def get_day_time_availability_dict(self, days, times, format=True):
        '''
        Get day time dictionary according to availability of time slots
        :param days: list of date objects for range of dates
        :param times: list of datetime objects for range of times
        :param format: format date objects as Fri 16/02/18 and time objects as 08:00
        :return:  list of dicts of day and time [{'Fri 16/02/18': 08:00, 'Thu 16/02/18': 08:00, },{}...]
        '''
        data = []
        outlook_events = self.parse_outlook_events_into_dict(self.get_outlook_events(days))
        short_breaks = self.get_breaks_between_close_sets_of_events(days, outlook_events)
        for time in times:
            dic = {}
            for day in days:
                if self.slot_is_available(time.time(), day, outlook_events, short_breaks):
                    dic[day.strftime('%a %d/%m/%y') if format else day] = time.time().strftime('%H:%M') if format else \
                        time.time()
            data.append(dic)
        return data

    def get_breaks_between_close_sets_of_events(self, days, events):
        '''
        	9:30 – 10 10 – 10:15 10:30 – 10:45 (15) seq = 3   3+ 15 minutes or or less
        Find cumulative difference between meetings if greater than 15 and 3 or more meetings
        don't worry otherwise
        :return: list of datetime object slots that are possible for breaktimes
        '''
        break_slots = []
        day_events_dict = self.get_day_events_dict(events)
        for day in days:
            if day_events_dict.get(day):
                day_events = day_events_dict.get(day)
                if len(events) < 3:  # if less than 3 events skip day
                    continue
                cumulative_difference = 0
                possible_times = []
                i = 0
                for event in day_events:
                    if i == 0:
                        previous_event_end_time = event['end']
                        i+=1
                        continue
                    difference = event['start'] - previous_event_end_time
                    diff_in_minutes = int(difference.seconds / 60)
                    if 0< diff_in_minutes <= 15:
                        possible_times.append(previous_event_end_time)#, 'end': previous_event_end_time})
                        cumulative_difference += diff_in_minutes
                    previous_event_end_time = event['end']
                if cumulative_difference > 20:
                    continue
                break_slots.append( possible_times )
        return [inner for outer in break_slots for inner in outer]


    def get_day_events_dict(self, events):
        '''
        Get events that occur each day (datetime object)
        :param events: outlook events (dict of start time, end time)
        :return: { 'datetime()' : [{start, end} {start, end}], '']
        '''
        dic = {}
        for event in events:
            if dic.get(event['start'].date()):
                dic[event['start'].date()].append(event)
            else:
                dic[event['start'].date()] = [event]
        return dic

    def get_day_availability_dict(self):
        '''
        Return a dictionary representation of key model fields
        :return: dict
        '''
        return {
            'Monday': {'start': self.monday_from, 'end': self.monday_to},
            'Tuesday': {'start': self.tuesday_from, 'end': self.tuesday_to},
            'Wednesday': {'start': self.wednesday_from, 'end': self.wednesday_to},
            'Thursday': {'start': self.thursday_from, 'end': self.thursday_to},
            'Friday': {'start': self.friday_from, 'end': self.friday_to},
            'Saturday': {'start': self.saturday_from, 'end': self.saturday_to},
            'Sunday': {'start': self.sunday_from, 'end': self.sunday_to},
            'Lunch': {'start': self.lunch_from, 'end': self.lunch_to},
        }

    def slot_is_available(self, time, day, outlook_events, short_break_slots=[]):
        '''
        Checks whether time slot for day is available
        5 main checks
        1)Current slot is stated as a break slot
        1)Current time is after slot? Not availablle
        2)Checks Mon-Sun availabilities on booking availability model instance
        3)Checks whether in lunch break
        4)Interfaces with outlook calendar json response to check availability with reference to existing booked events
        :param time: datetime.time object e.g. datetime.time(8,0) 8:00AM
        :param day: datetime.date object datetime.date(2018,2,10)
        :return: True/False (True => Slot is available for booking) otherwise False
        '''
        combined_date_time = datetime.datetime.combine(day, time)
        if combined_date_time in short_break_slots:
            return False
        if datetime.date.today() == day and datetime.datetime.now() > combined_date_time:
            return False
        if not self.is_slot_within_booking_availability(combined_date_time):
            return False
        if self.is_slot_within_lunch_break(combined_date_time):
            return False
        if self.is_slot_within_outlook_event(combined_date_time, outlook_events):
            return False
        return True

    def get_combined_start_end_and_current_datetime(self, start, end, current):
        '''
        Return combined date and time object
        :param start: start time
        :param end: end time
        :param current: current time
        :return: tuple of datetime objects tuple => (start,end,current)
        '''
        combine = lambda time: datetime.datetime.combine(datetime.date.min, time)
        return combine(start), combine(end), combine(current)

    def is_slot_within_lunch_break(self, datetime_obj):
        '''
        Check whether slot is in a lunch break
        :param datetime_obj: datetime object
        :return:True if slot is in lunch break (Unbookable) otherwise False
        '''
        lunch_prefs = self.get_day_availability_dict().get('Lunch')
        if not lunch_prefs.get('start') or not lunch_prefs.get('end'):
            return False
        start_time, end_time, current_time = self.get_combined_start_end_and_current_datetime(
            start=lunch_prefs['start'], end=lunch_prefs['end'], current=datetime_obj.time()
        )
        return True if start_time <= current_time < end_time else False

    def is_slot_within_booking_availability(self, datetime_obj):
        '''
        Check is slot is within current dates booking availability constraint
        :param datetime_obj:
        :return: True if slot is within booking availability (Bookable) otherwise False
        '''
        day = datetime_obj.strftime('%A')
        availability_dict = self.get_day_availability_dict()
        day_preferences = availability_dict.get(day)
        if not day_preferences.get('start') or not day_preferences.get('end'):
            return False
        start_time, end_time, current_time = self.get_combined_start_end_and_current_datetime(
            start=day_preferences['start'], end=day_preferences['end'], current=datetime_obj.time()
        )
        return True if start_time <= current_time < end_time else False

    def get_outlook_events(self, dates):
        '''
        Retrieve outlook events between a range of dates
        :param dates: list of datetimeobjects [start date,end date]
        :param as_timezone:
        :return:
        '''
        token = self.account_social.socialtoken_set.get()
        if token.expires_at < timezone.now():
            set_new_token(token)
        email = self.account_social.user.email
        outlook_events = get_events_between_dates(
            access_token=token,
            user_email=email,
            start_date=dates[0].isoformat(),
            end_date=dates[-1].isoformat())
        return outlook_events

    def parse_outlook_events_into_dict(self, outlook_output):
        '''
        Parse JSON outlook service response event info into a usable data structure
        :param outlook_output: output JSON from service
        :return: list of dictionaries for each event [{start:'',end:'',is_all_day:True},{},{},...]
        '''
        events = outlook_output.get('value')
        event_lst = []
        if events:
            for event in events:
                event_lst.append({
                    'start': dateutil.parser.parse(event.get('start').get('dateTime')),
                    'end': dateutil.parser.parse(event.get('end').get('dateTime')),
                    'is_all_day': event.get('isAllDay')})
        return event_lst

    def is_slot_within_outlook_event(self, datetime_obj, events):
        '''
        Identifies outlook availability
        1)if event is allday
        2)if slot is within event duration
        3)if at least one meeting slot is possible remain available
        :param datetime_obj:
        :param events:
        :return: True if slot is clashing with outlook event (Unbookable) else False
        '''
        if events:
            for event in events:
                if event['is_all_day'] and event['start'].date() == datetime_obj.date():
                    return True
                if event['start'] <= datetime_obj < event['end']:
                    return True
                if event['start'] < datetime_obj + datetime.timedelta(minutes=self.availability_increment) \
                        < event['end']:
                    return True
        return False

    def get_range_of_durations(self):
        '''
        Get range of durations according to availability incremnent
        :return: list of integers (durations)
        '''
        durations = []
        value = self.availability_increment
        while value <= self.booking_duration:
            durations.append(value)
            value += self.availability_increment
        return durations


# re add later
def custom_validate_kcl_email(email):
    '''
    Filter to ensure only kcl email addresses can be input
    :param email: email address
    :return: Validation error if 'kcl' not in email else None
    '''
    if 'kcl' not in email:
        raise ValidationError('Email must be @kcl email address')


class Event(models.Model):
    social_account = models.ForeignKey(SocialAccount, related_name='events')
    date_time = models.CharField(max_length=200)
    start_time = models.DateTimeField(blank=True)
    end_time = models.DateTimeField(blank=True)
    first_name = models.CharField(max_length=200, blank=False)  # change names
    last_name = models.CharField(max_length=200, blank=True)  # change names
    email = models.EmailField(max_length=200, blank=False, validators=[validate_email])
    duration = models.IntegerField(choices=())
    subject = models.CharField(max_length=500, blank=True)
    outlook_id = models.CharField(max_length=1000, blank=True, null=True)
