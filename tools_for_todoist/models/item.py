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


class TodoistItem:
    def __init__(self, todoist, content, project_id):
        self.todoist = todoist
        self.content = content
        self.project_id = project_id

        self.id = -1
        self.priority = 1
        self._raw = None

    @staticmethod
    def from_raw(todoist, raw):
        item = TodoistItem(todoist, raw['content'], raw['project_id'])
        item.id = raw['id']
        item.update_from_raw(raw)
        return item

    def update_from_raw(self, raw):
        self._raw = raw
        self.priority = raw['priority']
        self.content = raw['content']
        self.project_id = raw['project_id']

    def save(self):
        if self.id == -1:
            self._raw = self.todoist.add_item(self)
            self.id = self._raw['id']
            return self._raw

        updated_rows = {}
        if self.content != self._raw['content']:
            updated_rows['content'] = self.content
        if self.priority != self._raw['priority']:
            updated_rows['priority'] = self.priority
        return self.todoist.update_item(self, **updated_rows)

    def __repr__(self):
        return f'{self.id}: content:{self.content}, priority: {self.priority}'
