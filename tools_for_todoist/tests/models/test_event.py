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
            EventBuilder()
            .set_id('id')
            .set_title('Title')
            .set_info('key', 'value')
            .set_description('description')
            .create_event()
        )
        self.assertEqual(event.summary, 'Title')
        self.assertEqual(event.description(), 'description')
        self.assertEqual(event.id(), 'id')
        self.assertEqual(event.get_private_info('key'), 'value')

    def test_empty_private_info(self):
        event = EventBuilder().create_event()
        self.assertEqual(event.get_private_info('key'), None)
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
        self.assertEqual(
            event.next_occurrence(before_event), (date(year=2020, month=1, day=10), event)
        )
        exact_event = date(year=2020, month=1, day=10)
        self.assertEqual(event.next_occurrence(exact_event), (None, None))
        after_event = date(year=2020, month=1, day=11)
        self.assertEqual(event.next_occurrence(after_event), (None, None))

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
        self.assertEqual(event.next_occurrence(before_event), (expected_start, event))
        exact_event = datetime(
            year=2020, month=1, day=1, hour=10, minute=10, tzinfo=gettz(default_timezone)
        )
        self.assertEqual(event.next_occurrence(exact_event), (None, None))
        after_event = event.next_occurrence(
            datetime(year=2020, month=1, day=1, hour=11, tzinfo=gettz(default_timezone))
        )
        self.assertEqual(after_event, (None, None))

    def test_recurring_all_day_next_occurrence(self):
        event = EventBuilder().set_start_date(date='2020-01-10').set_rrule('DAILY').create_event()

        before_event = date(year=2020, month=1, day=1)
        self.assertEqual(
            event.next_occurrence(before_event), (date(year=2020, month=1, day=10), event)
        )
        exact_event = date(year=2020, month=1, day=10)
        self.assertEqual(
            event.next_occurrence(exact_event), (date(year=2020, month=1, day=11), event)
        )
        after_event = date(year=2020, month=1, day=11)
        self.assertEqual(
            event.next_occurrence(after_event), (date(year=2020, month=1, day=12), event)
        )

    def test_ending_recurring_all_day_next_occurrence(self):
        event = (
            EventBuilder()
            .set_start_date(date='2020-01-10')
            .set_rrule('DAILY', until='20200120')
            .create_event()
        )

        before_event = date(year=2020, month=1, day=1)
        self.assertEqual(
            event.next_occurrence(before_event), (date(year=2020, month=1, day=10), event)
        )
        exact_event = date(year=2020, month=1, day=10)
        self.assertEqual(
            event.next_occurrence(exact_event), (date(year=2020, month=1, day=11), event)
        )
        last_event = date(year=2020, month=1, day=19)
        self.assertEqual(
            event.next_occurrence(last_event), (date(year=2020, month=1, day=20), event)
        )
        exact_ending = date(year=2020, month=1, day=20)
        self.assertEqual(event.next_occurrence(exact_ending), (None, None))
        after_ending = date(year=2020, month=1, day=21)
        self.assertEqual(event.next_occurrence(after_ending), (None, None))

    def test_ending_utc_recurring_all_day_next_occurrence(self):
        event = (
            EventBuilder()
            .set_start_date(date='2020-01-10')
            .set_rrule('DAILY', until='20200120T225959Z')
            .create_event()
        )

        before_event = date(year=2020, month=1, day=1)
        self.assertEqual(
            event.next_occurrence(before_event), (date(year=2020, month=1, day=10), event)
        )
        exact_event = date(year=2020, month=1, day=10)
        self.assertEqual(
            event.next_occurrence(exact_event), (date(year=2020, month=1, day=11), event)
        )
        last_event = date(year=2020, month=1, day=19)
        self.assertEqual(
            event.next_occurrence(last_event), (date(year=2020, month=1, day=20), event)
        )
        exact_ending = date(year=2020, month=1, day=20)
        self.assertEqual(event.next_occurrence(exact_ending), (None, None))
        after_ending = date(year=2020, month=1, day=21)
        self.assertEqual(event.next_occurrence(after_ending), (None, None))

    def test_ending_count_recurring_all_day_next_occurrence(self):
        event = (
            EventBuilder()
            .set_start_date(date='2020-01-10')
            .set_rrule('DAILY', count=11)
            .create_event()
        )

        before_event = date(year=2020, month=1, day=1)
        self.assertEqual(
            event.next_occurrence(before_event), (date(year=2020, month=1, day=10), event)
        )
        exact_event = date(year=2020, month=1, day=10)
        self.assertEqual(
            event.next_occurrence(exact_event), (date(year=2020, month=1, day=11), event)
        )
        last_event = date(year=2020, month=1, day=19)
        self.assertEqual(
            event.next_occurrence(last_event), (date(year=2020, month=1, day=20), event)
        )
        exact_ending = date(year=2020, month=1, day=20)
        self.assertEqual(event.next_occurrence(exact_ending), (None, None))
        after_ending = date(year=2020, month=1, day=21)
        self.assertEqual(event.next_occurrence(after_ending), (None, None))

    def test_recurring_next_occurrence(self):
        event = (
            EventBuilder()
            .set_start_date(datetime='2020-01-10T10:10:00+01:00')
            .set_rrule('DAILY')
            .create_event()
        )
        expected_start = datetime(
            year=2020,
            month=1,
            day=10,
            hour=10,
            minute=10,
            tzinfo=gettz(event.google_calendar.default_timezone),
        )

        before_event = datetime(
            year=2020,
            month=1,
            day=1,
            hour=10,
            minute=10,
            tzinfo=gettz(event.google_calendar.default_timezone),
        )
        self.assertEqual(event.next_occurrence(before_event), (expected_start, event))
        exact_event = before_event.replace(day=10)
        expected_start = expected_start.replace(day=11)
        self.assertEqual(event.next_occurrence(exact_event), (expected_start, event))
        after_event = exact_event.replace(day=11)
        expected_start = expected_start.replace(day=12)
        self.assertEqual(event.next_occurrence(after_event), (expected_start, event))

    def test_recurring_ending_date_next_occurrence(self):
        event = (
            EventBuilder()
            .set_start_date(datetime='2020-01-10T10:10:00+01:00')
            .set_rrule('DAILY', until='20200120T091000Z')
            .create_event()
        )
        expected_start = datetime(
            year=2020,
            month=1,
            day=10,
            hour=10,
            minute=10,
            tzinfo=gettz(event.google_calendar.default_timezone),
        )

        before_event = datetime(
            year=2020,
            month=1,
            day=1,
            hour=10,
            minute=10,
            tzinfo=gettz(event.google_calendar.default_timezone),
        )
        self.assertEqual(event.next_occurrence(before_event), (expected_start, event))
        exact_event = before_event.replace(day=10)
        expected_start = expected_start.replace(day=11)
        self.assertEqual(event.next_occurrence(exact_event), (expected_start, event))
        last_event = exact_event.replace(day=19)
        expected_start = expected_start.replace(day=20)
        self.assertEqual(event.next_occurrence(last_event), (expected_start, event))
        exact_ending = last_event.replace(day=20)
        self.assertEqual(event.next_occurrence(exact_ending), (None, None))
        after_ending = exact_ending.replace(day=21)
        self.assertEqual(event.next_occurrence(after_ending), (None, None))

    def test_recurring_ending_count_next_occurrence(self):
        event = (
            EventBuilder()
            .set_start_date(datetime='2020-01-10T10:10:00+01:00')
            .set_rrule('DAILY', count=11)
            .create_event()
        )
        expected_start = datetime(
            year=2020,
            month=1,
            day=10,
            hour=10,
            minute=10,
            tzinfo=gettz(event.google_calendar.default_timezone),
        )

        before_event = datetime(
            year=2020,
            month=1,
            day=1,
            hour=10,
            minute=10,
            tzinfo=gettz(event.google_calendar.default_timezone),
        )
        self.assertEqual(event.next_occurrence(before_event), (expected_start, event))
        exact_event = before_event.replace(day=10)
        expected_start = expected_start.replace(day=11)
        self.assertEqual(event.next_occurrence(exact_event), (expected_start, event))
        last_event = exact_event.replace(day=19)
        expected_start = expected_start.replace(day=20)
        self.assertEqual(event.next_occurrence(last_event), (expected_start, event))
        exact_ending = last_event.replace(day=20)
        self.assertEqual(event.next_occurrence(exact_ending), (None, None))
        after_ending = exact_ending.replace(day=21)
        self.assertEqual(event.next_occurrence(after_ending), (None, None))

    def test_recurring_declined_next_occurrence(self):
        event = (
            EventBuilder()
            .set_start_date(datetime='2020-01-10T10:10:00+01:00')
            .set_rrule('WEEKLY')
            .add_attendee(is_self=True, status='declined')
            .create_event()
        )

        before_event = datetime(
            year=2020,
            month=1,
            day=1,
            hour=10,
            minute=10,
            tzinfo=gettz(event.google_calendar.default_timezone),
        )
        self.assertEqual(event.next_occurrence(before_event), (None, None))

    def test_recurring_others_declined_next_occurrence(self):
        event = (
            EventBuilder()
            .set_start_date(datetime='2020-01-10T10:10:00+01:00')
            .set_rrule('WEEKLY')
            .add_attendee(is_self=True, status='accepted')
            .add_attendee(is_self=False, status='declined')
            .add_attendee(is_self=False, status='accepted', resource=True)
            .create_event()
        )

        before_event = datetime(
            year=2020,
            month=1,
            day=1,
            hour=10,
            minute=10,
            tzinfo=gettz(event.google_calendar.default_timezone),
        )
        self.assertEqual(event.next_occurrence(before_event), (None, None))

        event = (
            EventBuilder()
            .set_start_date(datetime='2020-01-10T10:10:00+01:00')
            .set_rrule('WEEKLY')
            .add_attendee(is_self=True, status='accepted')
            .add_attendee(is_self=False, status='declined')
            .add_attendee(is_self=False, status='accepted')
            .add_attendee(is_self=False, status='declined', resource=False)
            .create_event()
        )
        next_event = datetime(
            year=2020,
            month=1,
            day=10,
            hour=10,
            minute=10,
            tzinfo=gettz(event.google_calendar.default_timezone),
        )
        self.assertEqual(event.next_occurrence(before_event), (next_event, event))

    def test_recurring_others_declined_instance_next_occurrence(self):
        event = (
            EventBuilder()
            .set_start_date(datetime='2020-01-10T10:10:00+01:00')
            .set_rrule('WEEKLY')
            .create_event()
        )
        event_exception = (
            EventBuilder()
            .set_recurring_event_id(event.id())
            .set_original_start_date(datetime='2020-01-10T10:10:00+01:00')
            .set_start_date(datetime='2020-01-10T10:10:00+01:00')
            .add_attendee(is_self=True, status='accepted')
            .add_attendee(is_self=False, status='declined')
            .create_event()
        )
        event.update_exception(event_exception.raw())

        before_event = datetime(
            year=2020,
            month=1,
            day=1,
            hour=10,
            minute=10,
            tzinfo=gettz(event.google_calendar.default_timezone),
        )
        next_event = datetime(
            year=2020,
            month=1,
            day=17,
            hour=10,
            minute=10,
            tzinfo=gettz(event.google_calendar.default_timezone),
        )
        self.assertEqual(event.next_occurrence(before_event), (next_event, event))

        event = (
            EventBuilder()
            .set_start_date(datetime='2020-01-10T10:10:00+01:00')
            .set_rrule('WEEKLY')
            .create_event()
        )
        event_exception = (
            EventBuilder()
            .set_recurring_event_id(event.id())
            .set_original_start_date(datetime='2020-01-10T10:10:00+01:00')
            .set_start_date(datetime='2020-01-10T10:10:00+01:00')
            .add_attendee(is_self=True, status='accepted')
            .add_attendee(is_self=False, status='declined')
            .add_attendee(is_self=False, status='accepted')
            .create_event()
        )
        event.update_exception(event_exception.raw())
        next_event = next_event.replace(day=10)
        self.assertEqual(
            event.next_occurrence(before_event),
            (next_event, event.exceptions[event_exception.id()]),
        )

    def test_recurring_declined_with_accepted_exception_next_occurrence(self):
        event = (
            EventBuilder()
            .set_start_date(datetime='2020-01-10T10:10:00+01:00')
            .set_rrule('WEEKLY')
            .add_attendee(is_self=True, status='declined')
            .create_event()
        )
        event_exception = (
            EventBuilder()
            .set_recurring_event_id(event.id())
            .set_original_start_date(datetime='2020-01-17T10:10:00+01:00')
            .set_start_date(datetime='2020-01-17T10:10:00+01:00')
            .add_attendee(is_self=True, status='accepted')
            .create_event()
        )
        event.update_exception(event_exception.raw())

        expected_next = datetime(
            year=2020,
            month=1,
            day=17,
            hour=10,
            minute=10,
            tzinfo=gettz(event.google_calendar.default_timezone),
        )
        before_event = datetime(
            year=2020,
            month=1,
            day=1,
            hour=10,
            minute=10,
            tzinfo=gettz(event.google_calendar.default_timezone),
        )
        self.assertEqual(
            event.next_occurrence(before_event),
            (expected_next, event.exceptions[event_exception.id()]),
        )

    def test_recurring_next_moved_next_occurrence(self):
        event = (
            EventBuilder()
            .set_start_date(datetime='2020-01-10T10:10:00+01:00')
            .set_rrule('DAILY')
            .create_event()
        )
        event_exception = (
            EventBuilder()
            .set_recurring_event_id(event.id())
            .set_original_start_date(datetime='2020-01-10T10:10:00+01:00')
            .set_start_date(datetime='2020-01-11T10:10:00+01:00')
            .create_event()
        )
        event.update_exception(event_exception.raw())

        before_event = datetime(
            year=2020,
            month=1,
            day=1,
            hour=10,
            minute=10,
            tzinfo=gettz(event.google_calendar.default_timezone),
        )
        expected_next = datetime(
            year=2020,
            month=1,
            day=11,
            hour=10,
            minute=10,
            tzinfo=gettz(event.google_calendar.default_timezone),
        )
        self.assertEqual(
            event.next_occurrence(before_event),
            (expected_next, event.exceptions[event_exception.id()]),
        )

    def test_recurring_instances_rearranged_next_occurrence(self):
        event = (
            EventBuilder()
            .set_start_date(datetime='2020-01-10T10:10:00+01:00')
            .set_rrule('WEEKLY')
            .create_event()
        )
        event_exception = (
            EventBuilder()
            .set_recurring_event_id(event.id())
            .set_original_start_date(datetime='2020-01-24T10:10:00+01:00')
            .set_start_date(datetime='2020-01-15T10:10:00+01:00')
            .create_event()
        )
        event.update_exception(event_exception.raw())

        before_event = datetime(
            year=2020,
            month=1,
            day=11,
            hour=10,
            minute=10,
            tzinfo=gettz(event.google_calendar.default_timezone),
        )
        expected_next = datetime(
            year=2020,
            month=1,
            day=15,
            hour=10,
            minute=10,
            tzinfo=gettz(event.google_calendar.default_timezone),
        )
        self.assertEqual(
            event.next_occurrence(before_event),
            (expected_next, event.exceptions[event_exception.id()]),
        )

    def test_recurring_next_cancelled_next_occurrence(self):
        event = (
            EventBuilder()
            .set_start_date(datetime='2020-01-10T10:10:00+01:00')
            .set_rrule('WEEKLY')
            .create_event()
        )
        event_exception = (
            EventBuilder()
            .set_recurring_event_id(event.id())
            .set_original_start_date(datetime='2020-01-10T10:10:00+01:00')
            .set_start_date(datetime='2020-01-10T10:10:00+01:00')
            .set_status('cancelled')
            .create_event()
        )
        event.update_exception(event_exception.raw())

        before_event = datetime(
            year=2020,
            month=1,
            day=1,
            hour=10,
            minute=10,
            tzinfo=gettz(event.google_calendar.default_timezone),
        )
        expected_next = datetime(
            year=2020,
            month=1,
            day=17,
            hour=10,
            minute=10,
            tzinfo=gettz(event.google_calendar.default_timezone),
        )
        self.assertEqual(event.next_occurrence(before_event), (expected_next, event))

        event_exception._raw['status'] = 'accepted'
        event.update_exception(event_exception.raw())
        expected_next = expected_next.replace(day=10)
        self.assertEqual(
            event.next_occurrence(before_event),
            (expected_next, event.exceptions[event_exception.id()]),
        )

    def test_recurring_next_declined_next_occurrence(self):
        event = (
            EventBuilder()
            .set_start_date(datetime='2020-01-10T10:10:00+01:00')
            .set_rrule('WEEKLY')
            .create_event()
        )
        event_exception = (
            EventBuilder()
            .set_recurring_event_id(event.id())
            .set_original_start_date(datetime='2020-01-10T10:10:00+01:00')
            .set_start_date(datetime='2020-01-10T10:10:00+01:00')
            .add_attendee(is_self=True, status='declined')
            .create_event()
        )
        event.update_exception(event_exception.raw())

        before_event = datetime(
            year=2020,
            month=1,
            day=1,
            hour=10,
            minute=10,
            tzinfo=gettz(event.google_calendar.default_timezone),
        )
        expected_next = datetime(
            year=2020,
            month=1,
            day=17,
            hour=10,
            minute=10,
            tzinfo=gettz(event.google_calendar.default_timezone),
        )
        self.assertEqual(event.next_occurrence(before_event), (expected_next, event))

    def test_daily_recurrence_string(self):
        cases = [
            (None, 'day'),
            (1, 'day'),
            (2, 'other day'),
            (3, '3 days'),
            (10, '10 days'),
        ]
        for interval, expected_clarification in cases:
            event = (
                EventBuilder()
                .set_start_date(date='2020-01-10')
                .set_rrule('DAILY', interval=interval)
                .create_event()
            )
            self.assertEqual(event.recurrence_string(), f'every {expected_clarification}')

    def test_weekly_recurrence_string(self):
        byday_configs = [
            ('MO', 'Mon'),
            ('MO,TU,WE,TH,FR,SA,SU', 'Mon, Tue, Wed, Thu, Fri, Sat, Sun'),
        ]
        for byday, byday_word in byday_configs:
            intervals = [
                (1, f'{byday_word}'),
                (2, f'other {byday_word}'),
                (3, f'3rd {byday_word}'),
                (4, f'4th {byday_word}'),
                (10, '10 weeks'),
            ]
            for interval, expected_clarification in intervals:
                event = (
                    EventBuilder()
                    .set_start_date(date='2020-01-10')
                    .set_rrule('WEEKLY', interval=interval, byday=byday)
                    .create_event()
                )
                self.assertEqual(event.recurrence_string(), f'every {expected_clarification}')

    def test_monthly_recurrence_string(self):
        byday_config = [
            (None, None, 'month'),
            (1, None, 'month'),
            (2, None, 'other month'),
            (3, None, '3rd month'),
            (10, None, '10 months'),
            (None, '1MO', 'first Mon'),
            (1, '1MO', 'first Mon'),
            (1, '2TU', 'second Tue'),
            (1, '3FR', 'third Fri'),
            (1, '4SU', 'fourth Sun'),
            (1, '-1SU', 'last Sun'),
            (2, '4SU', 'fourth Sun'),
        ]
        for interval, byday, expected_clarification in byday_config:
            event = (
                EventBuilder()
                .set_start_date(date='2020-01-01')
                .set_rrule('MONTHLY', interval=interval, byday=byday)
                .create_event()
            )
            self.assertEqual(event.recurrence_string(), f'every {expected_clarification}')

    def test_yearly_recurrence_string(self):
        cases = [
            (None, 'year'),
            (1, 'year'),
            (2, '2 years'),
            (10, '10 years'),
        ]
        for interval, expected_clarification in cases:
            event = (
                EventBuilder()
                .set_start_date(date='2020-01-10')
                .set_rrule('YEARLY', interval=interval)
                .create_event()
            )
            self.assertEqual(event.recurrence_string(), f'every {expected_clarification}')

    def test_datetime_recurrence_string(self):
        event = (
            EventBuilder()
            .set_start_date(datetime='2020-01-10T10:10:00+01:00')
            .set_rrule('DAILY')
            .create_event()
        )
        self.assertEqual(event.recurrence_string(), 'every day at 10:10')

    def test_count_recurrence_string(self):
        event = (
            EventBuilder()
            .set_start_date(date='2020-01-10')
            .set_rrule('DAILY', count=10)
            .create_event()
        )
        self.assertEqual(event.recurrence_string(), 'every day until 2020-01-19')

    def test_count_datetime_recurrence_string(self):
        event = (
            EventBuilder()
            .set_start_date(datetime='2020-01-10T10:10:00+01:00')
            .set_rrule('DAILY', count=3)
            .create_event()
        )
        self.assertEqual(event.recurrence_string(), 'every day at 10:10 until 2020-01-12')

    def test_until_recurrence_string(self):
        event = (
            EventBuilder()
            .set_start_date(date='2020-01-10')
            .set_rrule('DAILY', until='20200120')
            .create_event()
        )
        self.assertEqual(event.recurrence_string(), 'every day until 2020-01-20')

    def test_until_datetime_recurrence_string(self):
        event = (
            EventBuilder()
            .set_start_date(datetime='2020-01-10T10:10:00+01:00', timezone='Europe/Zurich')
            .set_rrule('DAILY', until='20200120T225959Z')
            .create_event()
        )
        self.assertEqual(event.recurrence_string(), 'every day at 10:10 until 2020-01-20')

        event = (
            EventBuilder()
            .set_start_date(datetime='2020-01-10T10:10:00-05:00', timezone='America/New York')
            .set_rrule('DAILY', until='20200121T045959Z')
            .create_event()
        )
        self.assertEqual(event.recurrence_string(), 'every day at 10:10 until 2020-01-20')

    def test_changed_title_exception_next_occurence(self):
        event = (
            EventBuilder()
            .set_title('original title')
            .set_start_date(datetime='2020-01-10T10:10:00+01:00')
            .set_rrule('WEEKLY')
            .create_event()
        )
        event_exception = (
            EventBuilder()
            .set_title('changed title')
            .set_recurring_event_id(event.id())
            .set_original_start_date(datetime='2020-01-10T10:10:00+01:00')
            .set_start_date(datetime='2020-01-10T10:10:00+01:00')
            .create_event()
        )
        event.update_exception(event_exception.raw())

        before_event = datetime(
            year=2020,
            month=1,
            day=1,
            hour=10,
            minute=10,
            tzinfo=gettz(event.google_calendar.default_timezone),
        )
        next_event = datetime(
            year=2020,
            month=1,
            day=10,
            hour=10,
            minute=10,
            tzinfo=gettz(event.google_calendar.default_timezone),
        )
        expected_exception = event.exceptions[event_exception.id()]
        self.assertEqual(event.next_occurrence(before_event), (next_event, expected_exception))
        self.assertEqual(expected_exception.summary, 'changed title')

    def test_response_status(self):
        event = (
            EventBuilder()
            .set_start_date(datetime='2020-01-10T10:10:00+01:00')
            .add_attendee(is_self=True, status='some status')
            .create_event()
        )
        self.assertEqual(event.response_status(), 'some status')

    def test_duration(self):
        event = (
            EventBuilder()
            .set_start_date(datetime='2020-01-10T10:00:00+01:00')
            .set_end_date(datetime='2020-01-10T11:30:00+01:00')
            .create_event()
        )
        self.assertEqual(event.duration(), 90.0)

    def test_attendees(self):
        event = (
            EventBuilder()
            .set_start_date(datetime='2020-01-10T10:00:00+01:00')
            .add_attendee(is_self=True, email='kris')
            .add_attendee(resource=True, email='some_room')
            .add_attendee(email='other', status='declined')
            .create_event()
        )
        expected_attendees = [
            {'email': 'kris', 'responseStatus': 'accepted', 'self': True},
            {'email': 'some_room', 'resource': True, 'responseStatus': 'accepted'},
            {'email': 'other', 'responseStatus': 'declined'},
        ]
        self.assertEqual(event.attendees(), expected_attendees)

    def test_conference_link(self):
        event = EventBuilder().create_event()
        self.assertIsNone(event.conference_link())

        event = EventBuilder().add_no_video_conference().create_event()
        self.assertIsNone(event.conference_link())

        event = EventBuilder().add_zoom().create_event()
        self.assertEqual(event.conference_link(), 'https://hyperscience.zoom.us/j/meeting?pwd=pwd')

        event = EventBuilder().add_google_meet().create_event()
        self.assertEqual(event.conference_link(), 'https://meet.google.com/aaa-bbbb-ccc')
