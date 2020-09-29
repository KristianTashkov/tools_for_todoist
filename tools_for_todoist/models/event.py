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


class CalendarEvent:
    def __init__(self, google_calendar):
        self.google_calendar = google_calendar
        self.exceptions = {}
        self.recurring_event = None
        self._raw = None
        self._id = -1
        self.summary = None
        self._extended_properties = None

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
            self._extended_properties = {
                'private': {}
            }
        else:
            self._extended_properties = copy.deepcopy(self._extended_properties)
        self._extended_properties['private'][key] = value

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
