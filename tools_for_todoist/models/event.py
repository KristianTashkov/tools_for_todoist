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


class CalendarEvent:
    def __init__(self):
        self._raw = None
        self.id = -1
        self.exceptions = {}
        self.recurring_event = None

    @staticmethod
    def from_raw(raw):
        event = CalendarEvent()
        event._id = raw['id']
        event.update_from_raw(raw)
        return event

    def update_from_raw(self, raw):
        self._raw = raw

    def update_exception(self, exception):
        if exception['id'] not in self.exceptions:
            event = CalendarEvent.from_raw(exception)
            event.recurring_event = self
            self.exceptions[exception['id']] = event
        else:
            self.exceptions[exception['id']].update_from_raw(exception)

    def __repr__(self):
        if self._raw['status'] == 'cancelled':
            return f"{self.id}: {self._raw['originalStartTime']} cancelled"
        return f"{self.id}: {self._raw.get('summary')}, {self._raw['start']} - {self._raw['end']} "\
               f"exceptions: {self.exceptions}"
