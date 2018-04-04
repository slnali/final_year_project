import datetime
import django_tables2 as tables
from django_tables2 import A, columns

from bookings.models import BookingAvailability


class BookingGrid(tables.Table):
    days = BookingAvailability.get_next_7_days(datetime.datetime.today().date(),
                                               format=True)  # set BookingSlotsTable.days
    current_day_plus_0 = tables.LinkColumn(accessor=days[0], verbose_name=days[0],
                                           viewname='bookings:book_meeting_slot', args=[A(days[0]), days[0]])
    current_day_plus_1 = tables.LinkColumn(accessor=days[1], verbose_name=days[1],
                                           viewname='bookings:book_meeting_slot', args=[A(days[1]), days[1]])
    current_day_plus_2 = tables.LinkColumn(accessor=days[2], verbose_name=days[2],
                                           viewname='bookings:book_meeting_slot', args=[A(days[2]), days[2], ])
    current_day_plus_3 = tables.LinkColumn(accessor=days[3], verbose_name=days[3],
                                           viewname='bookings:book_meeting_slot', args=[A(days[3]), days[3], ])
    current_day_plus_4 = tables.LinkColumn(accessor=days[4], verbose_name=days[4],
                                           viewname='bookings:book_meeting_slot', args=[A(days[4]), days[4], ])
    current_day_plus_5 = tables.LinkColumn(accessor=days[5], verbose_name=days[5],
                                           viewname='bookings:book_meeting_slot', args=[A(days[5]), days[5], ])
    current_day_plus_6 = tables.LinkColumn(accessor=days[6], verbose_name=days[6],
                                           viewname='bookings:book_meeting_slot', args=[A(days[6]), days[6], ])

    # var = 'current_day_plus_{}'
    # i = 0
    # for day in days:
    #     locals().update({var.format(i): tables.LinkColumn(accessor=days[i], verbose_name=days[i],
    #                                                       viewname='bookings:book_meeting_slot',
    #                                                       args=[A(days[i]), days[i]])})
    #     i += 1

    class Meta:
        template_name = 'django_tables2/bootstrap-responsive.html'
        attrs = {'width': 700, 'align': 'center'}

    def __init__(self, *args, **kwargs):
        super(BookingGrid, self).__init__(*args)
        self.days = kwargs.get('days')  # days
        self.pk = kwargs.get('pk')
        self.viewname = kwargs.get('viewname', 'bookings:book_meeting_slot')
        self.event_pk = kwargs.get('event_pk', 0)
        self.base_columns['current_day_plus_0'] = tables.LinkColumn(accessor=self.days[0], verbose_name=self.days[0],
                                                                    viewname=self.viewname,
                                                                    args=[A(self.days[0]), self.days[0], self.pk, self.event_pk])
        self.base_columns['current_day_plus_1'] = tables.LinkColumn(accessor=self.days[1], verbose_name=self.days[1],
                                                                    viewname=self.viewname,
                                                                    args=[A(self.days[1]), self.days[1], self.pk, self.event_pk])
        self.base_columns['current_day_plus_2'] = tables.LinkColumn(accessor=self.days[2], verbose_name=self.days[2],
                                                                    viewname=self.viewname,
                                                                    args=[A(self.days[2]), self.days[2], self.pk, self.event_pk])
        self.base_columns['current_day_plus_3'] = tables.LinkColumn(accessor=self.days[3], verbose_name=self.days[3],
                                                                    viewname=self.viewname,
                                                                    args=[A(self.days[3]), self.days[3], self.pk, self.event_pk])
        self.base_columns['current_day_plus_4'] = tables.LinkColumn(accessor=self.days[4], verbose_name=self.days[4],
                                                                    viewname=self.viewname,
                                                                    args=[A(self.days[4]), self.days[4], self.pk, self.event_pk])
        self.base_columns['current_day_plus_5'] = tables.LinkColumn(accessor=self.days[5], verbose_name=self.days[5],
                                                                    viewname=self.viewname,
                                                                    args=[A(self.days[5]), self.days[5], self.pk, self.event_pk])
        self.base_columns['current_day_plus_6'] = tables.LinkColumn(accessor=self.days[6], verbose_name=self.days[6],
                                                                    viewname=self.viewname,
                                                                    args=[A(self.days[6]), self.days[6], self.pk, self.event_pk])
        self.columns = columns.BoundColumns(self, self.base_columns)