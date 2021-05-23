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
import logging

from dateutil.parser import parse
from dateutil.tz import gettz

from tools_for_todoist.utils import to_todoist_date

logger = logging.getLogger(__name__)


class TodoistItem:
    def __init__(self, todoist, content, project_id):
        self.todoist = todoist
        self.content = content or '(No title)'
        self.description = ''
        self.project_id = project_id

        self.id = -1
        self.priority = 1
        self._due = None
        self._raw = None
        self._in_history = False
        self._labels = set()

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
        self.description = self._raw['description']
        self.priority = self._raw['priority']
        self._due = self._raw['due']
        self._in_history = self._raw['in_history']
        self.project_id = self._raw['project_id']
        self._labels = set(int(x) for x in self._raw['labels'])

    def is_recurring(self):
        return self._due is not None and self._due.get('is_recurring')

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
        same_recurrence = (self._due or {}).get('string') == due_string or (
            not self.is_recurring() and due_string is None
        )
        if (
            self._due is not None
            and self._due.get('date') == next_date
            and self._due.get('timezone') == next_timezone
            and same_recurrence
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
        return self._in_history

    def has_parent(self):
        return self._raw.get('parent_id') is not None

    def labels(self):
        return self._labels

    def add_label(self, label):
        label_id = self.todoist.get_label_id_by_name(label)
        if label_id is None:
            label_id = self.todoist.create_label(label)
        self._labels.add(label_id)

    def remove_label(self, label):
        label_id = self.todoist.get_label_id_by_name(label)
        self._labels.discard(label_id)

    def uncomplete(self):
        self._in_history = False
        self.todoist.uncomplete_item(self)

    def archive(self):
        self._in_history = True
        self.todoist.archive_item(self)

    def save(self):
        if self.id == -1:
            self._raw = self.todoist.add_item(self)
            self.id = self._raw['id']
            return True

        updated_rows = {}
        if self.content != self._raw['content']:
            logger.debug(
                f'{self.id}: updating content: "{self._raw["content"]}" to "{self.content}"'
            )
            updated_rows['content'] = self.content
        if self.description != self._raw['description']:
            logger.debug(
                f'{self.id}: updating description: '
                f'"{self._raw["description"]}" to "{self.description}"'
            )
            updated_rows['description'] = self.description
        if self.priority != self._raw['priority']:
            logger.debug(
                f'{self.id}: updating priority: {self._raw["priority"]} to {self.priority}'
            )
            updated_rows['priority'] = self.priority
        if self._due != self._raw['due']:
            logger.debug(f'{self.id}: updating due: {self._raw["due"]} to {self._due}')
            updated_rows['due'] = self._due
        if self._labels != set(self._raw['labels']):
            old_labels = [self.todoist.get_label_name_by_id(x) for x in self._raw["labels"]]
            new_labels = [self.todoist.get_label_name_by_id(x) for x in self._labels]
            logger.debug(f'{self.id}: updating labels: {old_labels} to {new_labels}')
            updated_rows['labels'] = list(self._labels)
        if len(updated_rows) == 0:
            return False
        self.todoist.update_item(self, **updated_rows)
        return True

    def __repr__(self):
        completed_string = 'X' if self.is_completed() else 'O'
        return (
            f'{completed_string} {self.id}: content:{self.content}, '
            f'due: {self.next_due_date()}, string: {self.get_due_string()}'
        )
