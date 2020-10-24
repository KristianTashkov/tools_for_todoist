"""
Copyright (C) 2020-2020 Kristian Tashkov <kristian.tashkov@gmail.com>

This file is part of "Tools for Todoist".

"Tools for Todoist" is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by the
Free Software Foundation, either version 3 of the License, or (at your
option) any later version.

"Tools for Todoist" is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for
more details.

You should have received a copy of the GNU General Public License along
with this program. If not, see <http://www.gnu.org/licenses/>.
"""
from datetime import date, datetime
from unittest.case import TestCase

from dateutil.tz import gettz

from tools_for_todoist.tests.models.event_builder import EventBuilder


class CalendarEventTests(TestCase):
    def test_from_raw(self):
        event = (
            EventBuilder().set_id('id').set_title('Title').set_info('key', 'value').create_event()
        )
        self.assertEqual(event.summary, 'Title')
        self.assertEqual(event.id(), 'id')
        self.assertEqual(event.get_private_info('key'), 'value')

    def test_empty_private_info(self):
        event = EventBuilder().create_event()
        event.save_private_info('key', 'value')
        self.assertEqual(event.get_private_info('key'), 'value')

    def test_non_empty_private_info(self):
        event = EventBuilder().set_info('other_key', 'other_value').create_event()
        event.save_private_info('key', 'value')
        self.assertEqual(event.get_private_info('key'), 'value')

    def test_with_public_info(self):
        event = EventBuilder().set_info('other_key', 'other_value', domain='public').create_event()
        event.save_private_info('key', 'value')
        self.assertEqual(event.get_private_info('key'), 'value')

    def test_overriding_private_info(self):
        event = EventBuilder().set_info('key', 'other_value').create_event()
        event.save_private_info('key', 'value')
        self.assertEqual(event.get_private_info('key'), 'value')

    def test_date_start(self):
        event = EventBuilder().set_start_date(date='2020-01-01').create_event()
        self.assertEqual(event.start(), date(year=2020, month=1, day=1))

    def test_datetime_start(self):
        event = EventBuilder().set_start_date(datetime='2020-01-01T10:10:00+01:00').create_event()
        expected_start = datetime(
            year=2020,
            month=1,
            day=1,
            hour=10,
            minute=10,
            tzinfo=gettz(event.google_calendar.default_timezone),
        )
        actual_start = event.start()
        self.assertEqual(actual_start, expected_start)
        self.assertEqual(actual_start.tzinfo, expected_start.tzinfo)

    def test_datetime_with_timezone_start(self):
        event = (
            EventBuilder()
            .set_start_date(datetime='2020-01-01T10:10:00+01:00', timezone='Europe/Sofia')
            .create_event()
        )
        expected_start = datetime(
            year=2020,
            month=1,
            day=1,
            hour=11,
            minute=10,
            tzinfo=gettz('Europe/Sofia'),
        )
        actual_start = event.start()
        self.assertEqual(actual_start, expected_start)
        self.assertEqual(actual_start.tzinfo, expected_start.tzinfo)

    def test_single_all_day_next_occurrence(self):
        event = EventBuilder().set_start_date(date='2020-01-10').create_event()

        before_event = date(year=2020, month=1, day=9)
        self.assertEqual(event.next_occurrence(before_event), date(year=2020, month=1, day=10))
        exact_event = date(year=2020, month=1, day=10)
        self.assertEqual(event.next_occurrence(exact_event), None)
        after_event = date(year=2020, month=1, day=11)
        self.assertEqual(event.next_occurrence(after_event), None)

    def test_single_datetime_next_occurrence(self):
        event = EventBuilder().set_start_date(datetime='2020-01-01T10:10:00+01:00').create_event()
        expected_start = datetime(
            year=2020,
            month=1,
            day=1,
            hour=10,
            minute=10,
            tzinfo=gettz(event.google_calendar.default_timezone),
        )
        default_timezone = event.google_calendar.default_timezone

        before_event = datetime(year=2020, month=1, day=1, hour=9, tzinfo=gettz(default_timezone))
        self.assertEqual(event.next_occurrence(before_event), expected_start)
        exact_event = datetime(
            year=2020, month=1, day=1, hour=10, minute=10, tzinfo=gettz(default_timezone)
        )
        self.assertEqual(event.next_occurrence(exact_event), None)
        after_event = event.next_occurrence(
            datetime(year=2020, month=1, day=1, hour=11, tzinfo=gettz(default_timezone))
        )
        self.assertEqual(after_event, None)

    def test_recurring_all_day_next_occurrence(self):
        event = EventBuilder().set_start_date(date='2020-01-10').set_rrule('DAILY').create_event()

        before_event = date(year=2020, month=1, day=1)
        self.assertEqual(event.next_occurrence(before_event), date(year=2020, month=1, day=10))
        exact_event = date(year=2020, month=1, day=10)
        self.assertEqual(event.next_occurrence(exact_event), date(year=2020, month=1, day=11))
        after_event = date(year=2020, month=1, day=11)
        self.assertEqual(event.next_occurrence(after_event), date(year=2020, month=1, day=12))

    def test_ending_recurring_all_day_next_occurence(self):
        event = (
            EventBuilder()
            .set_start_date(date='2020-01-10')
            .set_rrule('DAILY', until='20200120')
            .create_event()
        )

        before_event = date(year=2020, month=1, day=1)
        self.assertEqual(event.next_occurrence(before_event), date(year=2020, month=1, day=10))
        exact_event = date(year=2020, month=1, day=10)
        self.assertEqual(event.next_occurrence(exact_event), date(year=2020, month=1, day=11))
        last_event = date(year=2020, month=1, day=19)
        self.assertEqual(event.next_occurrence(last_event), date(year=2020, month=1, day=20))
        exact_ending = date(year=2020, month=1, day=20)
        self.assertEqual(event.next_occurrence(exact_ending), None)
        after_ending = date(year=2020, month=1, day=21)
        self.assertEqual(event.next_occurrence(after_ending), None)

    def test_ending_utc_recurring_all_day_next_occurence(self):
        event = (
            EventBuilder()
            .set_start_date(date='2020-01-10')
            .set_rrule('DAILY', until='20200120T225959Z')
            .create_event()
        )

        before_event = date(year=2020, month=1, day=1)
        self.assertEqual(event.next_occurrence(before_event), date(year=2020, month=1, day=10))
        exact_event = date(year=2020, month=1, day=10)
        self.assertEqual(event.next_occurrence(exact_event), date(year=2020, month=1, day=11))
        last_event = date(year=2020, month=1, day=19)
        self.assertEqual(event.next_occurrence(last_event), date(year=2020, month=1, day=20))
        exact_ending = date(year=2020, month=1, day=20)
        self.assertEqual(event.next_occurrence(exact_ending), None)
        after_ending = date(year=2020, month=1, day=21)
        self.assertEqual(event.next_occurrence(after_ending), None)

    def test_ending_count_recurring_all_day_next_occurence(self):
        event = (
            EventBuilder()
            .set_start_date(date='2020-01-10')
            .set_rrule('DAILY', count=11)
            .create_event()
        )

        before_event = date(year=2020, month=1, day=1)
        self.assertEqual(event.next_occurrence(before_event), date(year=2020, month=1, day=10))
        exact_event = date(year=2020, month=1, day=10)
        self.assertEqual(event.next_occurrence(exact_event), date(year=2020, month=1, day=11))
        last_event = date(year=2020, month=1, day=19)
        self.assertEqual(event.next_occurrence(last_event), date(year=2020, month=1, day=20))
        exact_ending = date(year=2020, month=1, day=20)
        self.assertEqual(event.next_occurrence(exact_ending), None)
        after_ending = date(year=2020, month=1, day=21)
        self.assertEqual(event.next_occurrence(after_ending), None)
