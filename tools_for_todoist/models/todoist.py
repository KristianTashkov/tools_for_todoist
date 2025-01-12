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
from contextlib import ExitStack
from tempfile import TemporaryDirectory
from typing import Optional

from requests import Session
from todoist.api import SyncError, TodoistAPI

from tools_for_todoist.models.item import TodoistItem
from tools_for_todoist.storage import get_storage
from tools_for_todoist.utils import retry_flaky_function

logger = logging.getLogger(__name__)

TODOIST_API_KEY = 'todoist.api_key'


class Todoist:
    def __init__(self):
        self._exit_stack: Optional[ExitStack] = None
        self._recreate_api()
        self.api.reset_state()
        self._items = {}
        self._projects = {}
        self._last_completed = None
        self._initial_sync()

    def _recreate_api(self):
        if self._exit_stack is not None:
            self._exit_stack.close()
        self._exit_stack = ExitStack()
        token = get_storage().get_value(TODOIST_API_KEY)
        headered_session = Session()
        headered_session.headers['Authorization'] = f'Bearer {token}'

        new_temp_dir = self._exit_stack.enter_context(TemporaryDirectory())
        self.api = TodoistAPI(token, session=headered_session, api_version='v9', cache=new_temp_dir)

    def _activity_sync(self, offset=0, limit=100):
        def activity_get_func():
            return self.api.activity.get(
                object_type='item',
                event_type='completed',
                offset=offset,
                limit=limit,
            )

        return retry_flaky_function(
            activity_get_func,
            'todoist_activity_get',
            validate_result_func=lambda x: x and 'count' in x and 'events' in x,
            on_failure_func=self._recreate_api,
        )

    def _update_projects(self, sync_result):
        for project in sync_result['projects']:
            self._projects[project['id']] = project

    def _initial_sync(self):
        self._initial_result = retry_flaky_function(
            self.api.sync,
            'todoist_initial_sync',
            on_failure_func=self._recreate_api,
            validate_result_func=lambda x: x and 'projects' in x and 'items' in x,
        )
        for item in self._initial_result['items']:
            self._items[item['id']] = TodoistItem.from_raw(self, item)
        self._update_projects(self._initial_result)
        for project_id in self._projects.keys():
            # TODO(kris): Improve this completed logic or deprecate
            for item in self.api.items.get_completed(project_id, limit=200):
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
                new_completed.add(event['object_id'])
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
        return {'deleted': deleted_items, 'created': new_items, 'updated': updated_items}

    def get_item_by_id(self, item_id: str) -> TodoistItem:
        return self._items.get(item_id)

    def get_project_by_name(self, name):
        for project in self._projects.values():
            if project['name'] == name:
                return project
        return None

    def create_label(self, name):
        logger.info(f'Creating label| {name}')
        return self.api.labels.add(name)['id']

    def add_item(self, item):
        logger.info(f'Adding item| {item}')
        item_raw = self.api.items.add(
            item.content,
            project_id=item.project_id,
            priority=item.priority,
            due=item._due,
            labels=list(item.labels()),
        )
        self._items[item_raw['id']] = item
        return item_raw.data

    def update_item(self, item, **kwargs):
        logger.info(f'Updating item| {item}')
        self.api.items.update(item.id, **kwargs)

    def delete_item(self, item):
        logger.info(f'Deleting item| {item}')
        self.api.items.delete(item.id)

    def archive_item(self, item):
        logger.info(f'Archiving item| {item}')
        self.api.items.complete(item.id)

    def uncomplete_item(self, item):
        logger.info(f'Uncompleting item| {item}')
        self.api.items.uncomplete(item.id)

    def sync(self):
        api_queue = self.api.queue

        def api_sync():
            if len(api_queue) > 0:
                self.api.queue = api_queue.copy()
                return self.api.commit()
            return self.api.sync()

        result = retry_flaky_function(
            api_sync,
            'todoist_api_sync',
            on_failure_func=self._recreate_api,
            validate_result_func=lambda x: x and 'items' in x,
            critical_errors=[SyncError],
        )
        try:
            for temporary_key, new_id in result.get('temp_id_mapping', {}).items():
                item = self._items.pop(temporary_key, None)
                if item:
                    item.id = new_id
                    self._items[new_id] = item
            item_updates = [x for x in result['items']]
            self._update_projects(result)
            sync_result = self._update_items(item_updates)
        except Exception as e:
            logger.exception(f'Todoist Sync Failed| {result}', exc_info=e)
            raise
        sync_result['raw'] = result
        sync_result['completed'] = self._new_completed()
        return sync_result
