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
import copy
import re


from recurrent import format
from datetime import datetime
from dateutil.rrule import rrulestr
from dateutil.parser import parse
from dateutil.tz import UTC, gettz

from tools_for_todoist.utils import ensure_datetime, is_allday, datetime_as


CALENDAR_LAST_COMPLETED = 'last_completed'


class CalendarEvent:
    def __init__(self, google_calendar):
        self.google_calendar = google_calendar
        self.exceptions = {}
        self.recurring_event = None
        self._raw = None
        self._id = -1
        self.summary = None
        self._extended_properties = None

    def id(self):
        return self._id

    def raw(self):
        return self._raw

    def _get_recurrence(self):
        recurrence = self._raw.get('recurrence')
        if recurrence is None:
            return None
        return '\n'.join(recurrence)

    def _get_rrule(self):
        rrule = self._get_recurrence()
        if rrule is None:
            return None

        start_date = self._get_start()
        if not is_allday(start_date):
            start_date = ensure_datetime(start_date).astimezone(UTC)
        else:
            start_date = ensure_datetime(start_date)
        return rrulestr(rrule, dtstart=start_date, unfold=True)

    @staticmethod
    def from_raw(google_calendar, raw):
        event = CalendarEvent(google_calendar)
        event._id = raw['id']
        event.update_from_raw(raw)
        return event

    def update_from_raw(self, raw):
        self._raw = copy.deepcopy(raw)
        self._extended_properties = self._raw.get('extendedProperties')
        self.summary = self._raw.get('summary')

    def update_exception(self, exception):
        if exception['id'] not in self.exceptions:
            event = CalendarEvent.from_raw(self.google_calendar, exception)
            event.recurring_event = self
            self.exceptions[exception['id']] = event
        else:
            self.exceptions[exception['id']].update_from_raw(exception)

    def save_private_info(self, key, value):
        value = str(value)
        if self._extended_properties is None:
            self._extended_properties = {}
        else:
            self._extended_properties = copy.deepcopy(self._extended_properties)
        if 'private' not in self._extended_properties:
            self._extended_properties['private'] = {}
        self._extended_properties['private'][key] = value

    def get_private_info(self, key):
        if self._extended_properties is None:
            return None
        return self._extended_properties.get('private', {}).get(key)

    def _parse_start(self, raw_start):
        if 'date' in raw_start:
            return parse(raw_start['date']).date()
        dt = parse(raw_start['dateTime'])
        time_zone = raw_start.get('timeZone', self.google_calendar.default_timezone)
        return dt.astimezone(gettz(time_zone))

    def _get_start(self):
        return self._parse_start(self._raw['start'])

    def _get_original_start(self):
        return self._parse_start(self._raw['originalStartTime'])

    def _last_occurrence(self):
        instances = self._get_rrule()
        start = self._get_start()
        if instances is None:
            return start

        if instances.count() == 0:
            return None
        last_occurrence = instances[-1]
        if not is_allday(start):
            last_occurrence = last_occurrence.astimezone(start.tzinfo)
        return last_occurrence.date() if is_allday(start) else last_occurrence
    
    def _find_next_occurrence(self, rrule_instances, last_completed):
        non_cancelled_exception_starts = (
            x._get_start() for x in self.exceptions.values() if not x._get_is_cancelled()
        )
        future_exception_starts = (
            start
            for start in non_cancelled_exception_starts
            if start > datetime_as(last_completed, start)
        )
        first_exception_start = min(future_exception_starts, default=None)
        exception_original_starts = {
            x._get_original_start()
            for x in self.exceptions.values()
        }
        last_completed = datetime_as(last_completed, self._get_start())
        for next_regular_occurrence in rrule_instances.xafter(last_completed):
            if (
                first_exception_start is not None and
                first_exception_start < next_regular_occurrence
            ):
                return first_exception_start
            if next_regular_occurrence not in exception_original_starts:
                return next_regular_occurrence
        return first_exception_start

    def next_occurrence(self):
        instances = self._get_rrule()
        start = self._get_start()
        last_completed = self.get_private_info(CALENDAR_LAST_COMPLETED)
        last_completed = (
            parse(last_completed).astimezone(UTC)
            if last_completed is not None
            else datetime.now(UTC)
        )
        if instances is None:
            return start if last_completed < ensure_datetime(start).astimezone(UTC) else None

        next_occurrence = self._find_next_occurrence(instances, last_completed)
        if next_occurrence is None:
            return None
        if not is_allday(start):
            next_occurrence = next_occurrence.astimezone(start.tzinfo)
        return next_occurrence.date() if is_allday(start) else next_occurrence

    def recurrence_string(self):
        rrule = self._get_recurrence()
        if rrule is None:
            return None
        rrule = [x for x in rrule.split('\n') if 'RRULE' in x][0]

        start = self._get_start()
        if not is_allday(start):
            start_time = f'at {start.time().hour:02}:{start.time().minute:02}'
        else:
            start_time = ''

        formatted = format(rrule)
        match = re.search(r'until (.*)Z', formatted)
        if match is not None:
            until_date = parse(match.groups()[0])

            formatted = f'{formatted[:match.span()[0]]}'\
                        f' {start_time} until {until_date.date().isoformat()}'\
                        f'{formatted[match.span()[1]:]}'
            start_time = None
        match = re.search(r'(.*) of every month', formatted)
        if match is not None:
            formatted = f'{formatted[:match.span()[0]]}'\
                        f'every {match.groups()[0]}'\
                        f'{formatted[match.span()[1]:]}'
        formatted = re.sub(r'week on ', '', formatted)
        match = re.search(r'for ([\d]*) times|twice', formatted)
        if match:
            last_instance = self._last_occurrence()
            last_instance = f'{last_instance.year}-{last_instance.month}-{last_instance.day}'
            formatted = f'{formatted[:match.span()[0]]}' \
                        f'{start_time} until {last_instance}' \
                        f'{formatted[match.span()[1]:]}'
            start_time = None
        if start_time is not None:
            formatted += f' {start_time}'
        return formatted

    def html_link(self):
        return self._raw['htmlLink']

    def save(self):
        updated_fields = {}
        if self.summary != self._raw.get('summary'):
            updated_fields['summary'] = self.summary
        if self._extended_properties != self._raw.get('extendedProperties'):
            updated_fields['extendedProperties'] = self._extended_properties
        if updated_fields:
            self.google_calendar.update_event(self._id, updated_fields)
    
    def _get_is_cancelled(self):
        return self._raw['status'] == 'cancelled'

    def __repr__(self):
        if self._get_is_cancelled():
            return f"{self._id}: {self._raw['originalStartTime']} cancelled"
        return f"{self._id}: {self.summary}, {self._get_start()}, {self._raw.get('recurrence')}"
