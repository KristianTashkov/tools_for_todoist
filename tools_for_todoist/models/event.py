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
from dateutil.rrule import rrulestr
from datetime import datetime
from dateutil.tz import UTC


class CalendarEvent:
    def __init__(self, google_calendar):
        self.google_calendar = google_calendar
        self.exceptions = {}
        self.recurring_event = None
        self._raw = None
        self._id = -1
        self.summary = None
        self._extended_properties = None

    def _get_rrule(self):
        recurrence = self._raw.get('recurrence')
        if recurrence is None:
            return None
        return [x for x in recurrence if 'RRULE' in x][0]

    @staticmethod
    def from_raw(google_calendar, raw):
        event = CalendarEvent(google_calendar)
        event._id = raw['id']
        event.update_from_raw(raw)
        return event

    def update_from_raw(self, raw):
        self._raw = raw
        extended_properties = raw.get('extendedProperties')
        if extended_properties is not None:
            self._extended_properties = extended_properties
        self.summary = raw.get('summary')

    def update_exception(self, exception):
        if exception['id'] not in self.exceptions:
            event = CalendarEvent.from_raw(self.google_calendar, exception)
            event.recurring_event = self
            self.exceptions[exception['id']] = event
        else:
            self.exceptions[exception['id']].update_from_raw(exception)

    def save_private_info(self, key, value):
        if self._extended_properties is None:
            self._extended_properties = {}
        else:
            self._extended_properties = copy.deepcopy(self._extended_properties)
        if 'private' not in self._extended_properties:
            self._extended_properties['private'] = {key: value}
        else:
            self._extended_properties['private'][key] = value

    def get_private_info(self, key):
        if self._extended_properties is None:
            return None
        return self._extended_properties.get('private', {}).get(key)

    def get_start_datetime(self):
        if 'dateTime' in self._raw['start']:
            match = re.search(r'(.*T\d\d:\d\d:\d\d)\+(.*)', self._raw['start']['dateTime'])
            return match.groups()[0]
        else:
            return self._raw['start']['date']

    def get_start_date(self):
        if 'date' in self._raw['start']:
            return self._raw['start']['date']
        return self._raw['start']['dateTime'].split('T')[0]

    def get_last_occurrence(self):
        start_date = datetime.fromisoformat(self.get_start_datetime()).astimezone(UTC)
        rrule = self._get_rrule()
        if rrule is None:
            return start_date

        instances = rrulestr(rrule, dtstart=start_date)
        return instances[-1]

    def get_next_occurrence(self):
        start_date = datetime.fromisoformat(self.get_start_datetime()).astimezone(UTC)
        rrule = self._get_rrule()
        if rrule is None:
            return start_date.astimezone()

        instances = rrulestr(rrule, dtstart=start_date)
        for event in instances:
            if event > datetime.now(UTC):
                return event.astimezone()

    def get_recurrence_string(self):
        rrule = self._get_rrule()
        if rrule is None:
            return None

        match = re.search(r'(.*)T(\d\d:\d\d)', self.get_start_datetime())
        if match:
            start_time = f"at {match.groups()[1]}"
        else:
            start_time = None

        formatted = format(rrule)
        match = re.search(r'until (\d{4})(\d{2})(\d{2})T\d*Z', formatted)
        if match is not None:
            end_date = '-'.join(match.groups()[::-1])
            formatted = f'{formatted[:match.span()[0]]}'\
                        f' {start_time} until {end_date}'\
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
            last_instance = str(self.get_last_occurrence()).rpartition(' ')[0]
            formatted = f'{formatted[:match.span()[0]]}' \
                        f'{start_time} until {last_instance}' \
                        f'{formatted[match.span()[1]:]}'
            start_time = None
        if start_time is not None:
            formatted += f' {start_time}'
        return formatted

    def save(self):
        updated_fields = {}
        if self.summary != self._raw.get('summary'):
            updated_fields['summary'] = self.summary
        if self._extended_properties != self._raw.get('extendedProperties'):
            updated_fields['extendedProperties'] = self._extended_properties
        if updated_fields:
            self.google_calendar.update_event(self._id, updated_fields)

    def __repr__(self):
        if self._raw['status'] == 'cancelled':
            return f"{self._id}: {self._raw['originalStartTime']} cancelled"
        return f"{self._id}: {self.summary}, {self._raw['start']} - {self._raw['end']} "\
               f"exceptions: {self.exceptions}"
