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
from uuid import uuid4

from tools_for_todoist.models.event import CalendarEvent


class MockGoogleCalendar:
    def __init__(self):
        self.default_timezone = 'Europe/Zurich'

    def update_event(self, event_id, update_data):
        pass


class EventBuilder:
    def __init__(self, google_calendar=None):
        self.google_calendar = google_calendar or MockGoogleCalendar()
        self._raw = {
            'id': uuid4(),
            'summary': None,
            'start': {'date': '1970-01-01'},
            'status': 'confirmed',
        }

    def create_event(self):
        return CalendarEvent.from_raw(self.google_calendar, self._raw)

    def set_id(self, event_id):
        self._raw['id'] = event_id
        return self

    def set_title(self, title):
        self._raw['summary'] = title
        return self

    def set_info(self, key, value, domain='private'):
        if 'extendedProperties' not in self._raw:
            self._raw['extendedProperties'] = {}
        if domain not in self._raw['extendedProperties']:
            self._raw['extendedProperties'][domain] = {}
        self._raw['extendedProperties'][domain][key] = value
        return self

    def _set_date(self, type, date, datetime, timezone):
        assert date is not None or datetime is not None
        if date:
            self._raw[type] = {'date': date}
        else:
            self._raw[type] = {'dateTime': datetime}
            if timezone:
                self._raw[type]['timeZone'] = timezone

    def set_start_date(self, date=None, datetime=None, timezone=None):
        self._set_date('start', date, datetime, timezone)
        return self

    def set_end_date(self, date=None, datetime=None, timezone=None):
        self._set_date('end', date, datetime, timezone)
        return self

    def set_original_start_date(self, date=None, datetime=None, timezone=None):
        self._set_date('originalStartTime', date, datetime, timezone)
        return self
