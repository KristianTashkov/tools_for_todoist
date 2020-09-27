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
from todoist.api import TodoistAPI

from tools_for_todoist.credentials import TODOIST_API_TOKEN_PATH
from tools_for_todoist.models.item import TodoistItem


class Todoist:
    def __init__(self, active_project_name):
        with open(TODOIST_API_TOKEN_PATH) as file:
            token = file.readline().strip()
        self.api = TodoistAPI(token)
        self.api.reset_state()
        self._items = {}
        self._initial_sync(active_project_name)

    def _initial_sync(self, active_project_name):
        self._initial_result = self.api.sync()
        self.active_project_id = [
            x for x in self._initial_result['projects']
            if x['name'] == active_project_name
        ][0]['id']
        for item in self._initial_result['items']:
            if item['project_id'] != self.active_project_id:
                continue
            self._items[item['id']] = TodoistItem.from_raw(self, item)

    def _safety_filter_item(self, item):
        if item['type'] == 'item_add':
            return item['args']['project_id'] == self.active_project_id
        if item['type'] == 'item_update':
            return self._items[item['args']['id']].project_id == self.active_project_id
        return False

    def get_item_by_id(self, id):
        return self._items.get(id)

    def add_item(self, item):
        item_raw = self.api.items.add(
            item.content, project_id=item.project_id, priority=item.priority)
        self._items[item_raw['id']] = item
        return item_raw

    def update_item(self, item, **kwargs):
        self.api.items.update(item.id, **kwargs)

    def commit(self):
        filtered_items = []
        for item in self.api.queue:
            if not self._safety_filter_item(item):
                print("Filtered:", item)
                continue
            filtered_items.append(item)
        self.api.queue = filtered_items
        result = self.api.commit()
        for temporary_key in result['temp_id_mapping']:
            item = self._items.pop(temporary_key)
            item.id = result['temp_id_mapping'][temporary_key]
            self._items[item.id] = item
        return result

