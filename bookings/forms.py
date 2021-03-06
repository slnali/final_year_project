import datetime
from django import forms
from bookings import views
from bookings.models import BookingAvailability, Event


class BookingAvailabilityForm(forms.ModelForm):
    '''
    Availability Preferences form for user to store
    availability schedule
    '''
    class Meta:
        model = BookingAvailability
        fields = ['monday_from', 'monday_to', 'tuesday_from',
                  'tuesday_to', 'wednesday_from', 'wednesday_to',
                  'thursday_from', 'thursday_to',
                  'friday_from', 'friday_to', 'saturday_from',
                  'saturday_to', 'sunday_from', 'sunday_to',
                  'lunch_from', 'lunch_to',
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
            'lunch_from': forms.TimeInput(attrs={'class': 'form-control datetimepicker12'}),
            'lunch_to': forms.TimeInput(attrs={'class': 'form-control datetimepicker12'}),
        }

    def __init__(self, *args, **kwargs):
        '''
        Set booking duration here on initialisation of form
        :param args:
        :param kwargs:
        '''
        super(BookingAvailabilityForm, self).__init__(*args, **kwargs)
        self.fields['booking_duration'] = forms.TypedChoiceField(
            choices=views.get_booking_duration_choices(10))
        kwargs = kwargs.get('initial') or kwargs.get('data')
        if 'availability_increment' in self.data:
            try:
                availability_increment = int(self.data.get('availability_increment'))  #
                self.fields['booking_duration'].choices = views.get_booking_duration_choices(
                    availability_increment)
            except (ValueError, TypeError):
                pass
        elif self.instance.pk:
            self.fields['booking_duration'].choices = views.get_booking_duration_choices(
                self.instance.availability_increment)


class EventBookingForm(forms.ModelForm):
    '''
    Form for Bookers input their data to schedule events
    '''
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
        #if duration choices empty alert error that slot has been booked recently

    #edge case meeting booked recently raise errorand EVENT UPDATE FOOOOOK
    def get_duration_choices(self):
        '''
        Get choices for duration according to availability on Booking widget
        :return: list of duration choices
        '''
        default_choices = self.booking_availability.get_range_of_durations()
        time_slots = self.booking_availability.get_time_slot_data(start_date=self.booking_date.date(), format=False)
        free_slots = [slot.get(self.booking_date.date()) for slot in time_slots if self.booking_date.date() in slot]
        event_start = self.existing_event.start_time.astimezone().replace(tzinfo=None) if self.existing_event else None
        event_end = self.existing_event.end_time.astimezone().replace(tzinfo=None) if self.existing_event else None
        choices = self.get_choices_within_event_range(default_choices, free_slots, event_start, event_end)
        return choices

    def get_choices_within_event_range(self, default_choices, free_slots, event_start=None, event_end=None):
        '''
        Get duration choices according to booking widget and whether event is being updated
        :param default_choices: list of durations e.g availability incr of 15 = [15,30,45,60]
        :param free_slots: list of datetime objects that are available for booking
        :param event_start: existing event start datetime
        :param event_end: existing event end datetime
        :return: List of choices that have been tuplified
        e.g. if 15,30 only possible return is [(15,15),(30,30)]/
        format necessary for choice field
        '''
        possible_choices = []
        event_not_clashed = True
        override_existing_event = False
        for choice in default_choices:
            if event_start and not override_existing_event and event_start.date() == self.booking_date.date():
                if event_start <= self.booking_date + datetime.timedelta(minutes=choice) <= event_end:
                    possible_choices.append(choice)
                    continue
                elif self.booking_date + datetime.timedelta(minutes=choice) > event_end and possible_choices:
                    override_existing_event = True
            if (self.booking_date + datetime.timedelta(minutes=choice)).time() in free_slots and \
                    event_not_clashed: #or not override_existing_event if event_start else True:
                possible_choices.append(choice)
            elif event_not_clashed and not override_existing_event:
                possible_choices.append(choice)
                event_not_clashed = False
            else:
                break
        return self.tuplify_choices(possible_choices)

    def tuplify_choices(self, durations):
        '''
        Return double duration tuple format for durations
        :param durations: list of durations e.g. [10,20]
        :return: list of tuples e.g. input [10,20] output [(10,10),(20,20)]
        '''
        return tuple([(duration, duration) for duration in durations])

class UpdateEventBookingForm(EventBookingForm):
    '''
    Form to update exisitng event
    '''

    def __init__(self, *args, **kwargs):
        '''
        For update only duration needs to be checked, other fields are hidden
        :param args:
        :param kwargs:
        '''
        super(UpdateEventBookingForm, self).__init__(*args, **kwargs)
        self.fields['date_time'].widget = forms.HiddenInput()
        self.fields['first_name'].widget = forms.HiddenInput()
        self.fields['last_name'].widget = forms.HiddenInput()
        self.fields['email'].widget = forms.HiddenInput()
        self.fields['subject'].widget = forms.HiddenInput()
