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

from dateutil.tz import gettz
from dateutil.parser import parse

from tools_for_todoist.utils import to_todoist_date


class TodoistItem:
    def __init__(self, todoist, content, project_id):
        self.todoist = todoist
        self.content = content or '(No title)'
        self.project_id = project_id

        self.id = -1
        self.priority = 1
        self._due = None
        self._raw = None

    def raw(self):
        return self._raw

    @staticmethod
    def from_raw(todoist, raw):
        item = TodoistItem(todoist, raw['content'], raw['project_id'])
        item.id = raw['id']
        item.update_from_raw(raw)
        return item

    def update_from_raw(self, raw):
        self._raw = copy.deepcopy(raw)
        self.content = self._raw['content']
        self.priority = self._raw['priority']
        self._due = self._raw['due']
        self.project_id = self._raw['project_id']

    def is_recurring(self):
        return self._due is not None and self._due['is_recurring']

    def next_due_date(self):
        if self._due is None or 'date' not in self._due:
            return None
        dt = parse(self._due['date'])
        if 'T' not in self._due['date']:
            return dt.date()
        if self._due.get('timezone'):
            dt = dt.astimezone(gettz(self._due['timezone']))
        return dt

    def get_due_string(self):
        if self._due is None:
            return None
        return self._due.get('string', None)

    def set_due(self, next_date=None, due_string=None):
        if next_date is None and due_string is None:
            self._due = None
            return

        next_date, next_timezone = to_todoist_date(next_date) if next_date else (None, None)
        same_recurrence = (
                (self._due or {}).get('string') == due_string or
                (not self.is_recurring() and due_string is None)
        )
        if (
            self._due is not None and
            self._due.get('date') == next_date and
            self._due.get('timezone') == next_timezone and
            same_recurrence
        ):
            return

        self._due = {}
        if next_date is not None:
            self._due['date'], self._due['timezone'] = next_date, next_timezone
        if due_string is not None:
            self._due['string'] = due_string

    def is_completed(self):
        if self.id == -1:
            return False
        return self._raw.get('in_history', False)

    def has_parent(self):
        return self._raw.get('parent_id') is not None

    def save(self):
        if self.id == -1:
            self._raw = self.todoist.add_item(self)
            self.id = self._raw['id']
            return True

        updated_rows = {}
        if self.content != self._raw['content']:
            updated_rows['content'] = self.content
        if self.priority != self._raw['priority']:
            updated_rows['priority'] = self.priority
        if self._due != self._raw['due']:
            updated_rows['due'] = self._due
        if len(updated_rows) == 0:
            return False
        self.todoist.update_item(self, **updated_rows)
        return True

    def __repr__(self):
        completed_string = 'X' if self.is_completed() else 'O'
        return f'{completed_string} {self.id}: content:{self.content}, '\
               f'due: {self.next_due_date()}, string: {self.get_due_string()}'
