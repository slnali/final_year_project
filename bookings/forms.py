import datetime
from django import forms
import bookings.views
from bookings.models import BookingAvailability, Event


class BookingAvailabilityForm(forms.ModelForm):
    class Meta:
        model = BookingAvailability
        fields = ['monday_from', 'monday_to', 'tuesday_from',
                  'tuesday_to', 'wednesday_from', 'wednesday_to',
                  'thursday_from', 'thursday_to',
                  'friday_from', 'friday_to', 'saturday_from',
                  'saturday_to', 'sunday_from', 'sunday_to',
                  'availability_increment', 'booking_duration']

        widgets = {
            'monday_from': forms.TimeInput(attrs={'class': 'form-control datetimepicker12'}),
            'monday_to': forms.TimeInput(attrs={'class': 'form-control datetimepicker12'}),
            'tuesday_from': forms.TimeInput(attrs={'class': 'form-control datetimepicker12'}),
            'tuesday_to': forms.TimeInput(attrs={'class': 'form-control datetimepicker12'}),
            'wednesday_from': forms.TimeInput(attrs={'class': 'form-control datetimepicker12'}),
            'wednesday_to': forms.TimeInput(attrs={'class': 'form-control datetimepicker12'}),
            'thursday_from': forms.TimeInput(attrs={'class': 'form-control datetimepicker12'}),
            'thursday_to': forms.TimeInput(attrs={'class': 'form-control datetimepicker12'}),
            'friday_from': forms.TimeInput(attrs={'class': 'form-control datetimepicker12'}),
            'friday_to': forms.TimeInput(attrs={'class': 'form-control datetimepicker12'}),
            'saturday_from': forms.TimeInput(attrs={'class': 'form-control datetimepicker12'}),
            'saturday_to': forms.TimeInput(attrs={'class': 'form-control datetimepicker12'}),
            'sunday_from': forms.TimeInput(attrs={'class': 'form-control datetimepicker12'}),
            'sunday_to': forms.TimeInput(attrs={'class': 'form-control datetimepicker12'}),
        }

    def __init__(self, *args, **kwargs):
        super(BookingAvailabilityForm, self).__init__(*args, **kwargs)
        self.fields['booking_duration'] = forms.TypedChoiceField(
            choices=bookings.views.get_booking_duration_choices(10))
        kwargs = kwargs.get('initial') or kwargs.get('data')
        if 'availability_increment' in self.data:
            try:
                availability_increment = int(self.data.get('availability_increment'))  #
                self.fields['booking_duration'].choices = bookings.views.get_booking_duration_choices(
                    availability_increment)
            except (ValueError, TypeError):
                pass
        elif self.instance.pk:
            self.fields['booking_duration'].choices = bookings.views.get_booking_duration_choices(
                self.instance.availability_increment)


class EventBookingForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = ['date_time', 'first_name', 'last_name',
                  'email', 'duration', 'subject']

        widgets = {
            'date_time': forms.TextInput(attrs={'readonly': 'readonly', 'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.TextInput(attrs={'class': 'form-control'}),
            'subject': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.existing_event = kwargs.pop('event', None)
        self.booking_date = kwargs.pop('date')
        self.booking_availability = kwargs.pop('booking_availability')
        super(EventBookingForm, self).__init__(*args, **kwargs)
        choices = self.get_duration_choices()
        self.fields['duration'] = forms.TypedChoiceField(choices=choices)

    '''[{'start': datetime.datetime(2018, 2, 21, 12, 0), 'end': datetime.datetime(2018, 2, 21, 12, 15), 'is_all_day': False}, {'start': datetime.datetime(2018, 2, 21, 12, 30), 'end': datetime.datetime(2018, 2, 21, 13, 0), 'is_all_day': False}]
     test case for retrieving events booked in between slots'''

    def get_duration_choices(self):
        default_choices = self.booking_availability.get_range_of_durations()
        # from now till midnight of current day| should be now and max booking duration if not events return tuplify
        start_time = self.booking_date + datetime.timedelta(
            minutes=1)  # add one minute to avoid collision with currently ending event
        last_possible_time = self.booking_date + datetime.timedelta(minutes=self.booking_availability.booking_duration)
        outlook_events_within_booking_duration = self.booking_availability.parse_outlook_events_into_dict(
            self.booking_availability.get_outlook_events([start_time, last_possible_time], as_timzone=True))
        possible_durations = self.get_choices_within_event_range(default_choices,
                                                                 outlook_events_within_booking_duration)
        possible_durations = self.tuplify_choices(possible_durations)
        return possible_durations

    def tuplify_choices(self, durations):
        return tuple([(duration, duration) for duration in durations])

    # FIX CASE 9:20 - 9:40 BOOKED 1 MEETING, 9:00 - 9:20 BOOKED ANOTHER MEETING THEN UPDATED TO 8:40 CHOICES LIMIT TO 40 MIN WHEREAS NOW WOULD BE 60 MINUTES...
    # SO 2 EVENTS
    def get_choices_within_event_range(self, choices, events):
        possible_choices = []
        date_end_time = self.booking_availability.get_day_availability_dict().get(self.booking_date.strftime('%A'))[
            'end']
        date_end_date = self.booking_date.replace(hour=date_end_time.hour, minute=date_end_time.minute)
        for choice in choices:
            if events:  # multi tenancy someone booked same slot at moment
                event = events[0]  # min of one event disrupts booking, we dont care if 2 events disrupt
                if self.booking_date + datetime.timedelta(minutes=choice) <= event['start'] or \
                        (self.existing_event.start_time.astimezone().replace(tzinfo=None) == event[
                            'start'] if self.existing_event else False):
                    if self.booking_date + datetime.timedelta(
                            minutes=choice) <= date_end_date:  # MIGHT NOT NEED THIS BIT
                        possible_choices.append(choice)
            else:
                if self.booking_date + datetime.timedelta(
                        minutes=choice) <= date_end_date:  # availabilty dict mon,tue,wed
                    possible_choices.append(choice)
        return possible_choices


class UpdateEventBookingForm(EventBookingForm):
    # or can have a if condition on init pass through kwargs

    def __init__(self, *args, **kwargs):
        super(UpdateEventBookingForm, self).__init__(*args, **kwargs)
        self.fields['date_time'].widget = forms.HiddenInput()
        self.fields['first_name'].widget = forms.HiddenInput()
        self.fields['last_name'].widget = forms.HiddenInput()
        self.fields['email'].widget = forms.HiddenInput()
        self.fields['subject'].widget = forms.HiddenInput()
