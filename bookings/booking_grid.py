import django_tables2 as tables
from django_tables2 import A, columns

class BookingGrid(tables.Table):
    '''
    Slot booking widget
    '''
    current_day_plus_0 = tables.LinkColumn()
    current_day_plus_1 = tables.LinkColumn()
    current_day_plus_2 = tables.LinkColumn()
    current_day_plus_3 = tables.LinkColumn()
    current_day_plus_4 = tables.LinkColumn()
    current_day_plus_5 = tables.LinkColumn()
    current_day_plus_6 = tables.LinkColumn()

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