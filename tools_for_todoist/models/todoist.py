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
import logging

from todoist.api import TodoistAPI

from tools_for_todoist.models.item import TodoistItem
from tools_for_todoist.storage import get_storage

logger = logging.getLogger(__name__)

TODOIST_API_KEY = 'todoist.api_key'
TODOIST_ACTIVE_PROJECT = 'todoist.active_project'


class Todoist:
    def __init__(self):
        storage = get_storage()
        self.api = TodoistAPI(storage.get_value(TODOIST_API_KEY))
        self.api.reset_state()
        self._items = {}
        self._last_completed = None
        self.active_project_id = -1
        self._initial_sync(storage.get_value(TODOIST_ACTIVE_PROJECT))

    def _activity_sync(self, offset=0, limit=100):
        activity_result = self.api.activity.get(
            object_type='item', event_type='completed', parent_project_id=self.active_project_id,
            offset=offset, limit=limit)
        assert 'count' in activity_result and 'events' in activity_result, str(activity_result)
        return activity_result

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
        for item in self.api.items.get_completed(self.active_project_id):
            self._items[item['id']] = TodoistItem.from_raw(self, item)
        activity_result = self._activity_sync(limit=1)
        if activity_result['count']:
            self._last_completed = activity_result['events'][0]['id']

    def _new_completed(self):
        finished_processing = False
        offset = 0
        first_event = None
        new_completed = set()

        while not finished_processing:
            activity_result = self._activity_sync(offset=offset)
            offset += 100
            finished_processing = offset > activity_result['count']
            for event in activity_result['events']:
                if first_event is None:
                    first_event = event['id']
                if event['id'] == self._last_completed:
                    finished_processing = True
                    break
                item_id = event['object_id']
                old_item = self._items.get(item_id)
                if old_item is not None:
                    old_item = TodoistItem.from_raw(self, old_item.raw())
                new_completed.add((old_item, item_id))
        self._last_completed = first_event
        return new_completed

    def _update_items(self, raw_updated_items):
        deleted_items = []
        new_items = []
        updated_items = []
        for item in raw_updated_items:
            if item['is_deleted'] == 1:
                old_item = self._items.pop(item['id'], None)
                if old_item is not None:
                    deleted_items.append(old_item)
            elif item['id'] not in self._items:
                new_item = TodoistItem.from_raw(self, item)
                self._items[new_item.id] = new_item
                new_items.append(new_item)
            else:
                old_item = TodoistItem.from_raw(self, self._items[item['id']].raw())
                item_model = self.get_item_by_id(item['id'])
                item_model.update_from_raw(item)
                updated_items.append((old_item, item_model))
        return {
            'deleted': deleted_items,
            'created': new_items,
            'updated': updated_items,
        }

    def get_item_by_id(self, id):
        return self._items.get(id)

    def add_item(self, item):
        logger.info(f'Adding item| {item}')
        item_raw = self.api.items.add(
            item.content, project_id=item.project_id, priority=item.priority, due=item._due)
        self._items[item_raw['id']] = item
        return item_raw.data

    def update_item(self, item, **kwargs):
        logger.info(f'Updating item| {item} kwargs:{kwargs}')
        self.api.items.update(item.id, **kwargs)

    def delete_item(self, item):
        logger.info(f'Deleting item| {item}')
        self.api.items.delete(item.id)

    def archive_item(self, item):
        logger.info(f'Archiving item| {item}')
        self.api.items.complete(item.id, force_history=True)

    def sync(self):
        new_completed = self._new_completed()
        if len(self.api.queue) > 0:
            result = self.api.commit()
        else:
            result = self.api.sync()
        try:
            for temporary_key, new_id in result.get('temp_id_mapping', {}).items():
                item = self._items.pop(temporary_key)
                item.id = new_id
                self._items[new_id] = item
            active_project_item_updates = [
                x for x in result['items']
                if x['project_id'] == self.active_project_id or x['project_id'] == 0
            ]
            sync_result = self._update_items(active_project_item_updates)
        except Exception as e:
            logger.exception('Todoist Sync Failed| {result}', exc_info=e)
            raise
        sync_result['raw'] = result
        sync_result['completed'] = new_completed
        return sync_result
