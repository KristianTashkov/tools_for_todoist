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

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone

from requests import Session

from tools_for_todoist.models.item import TodoistItem
from tools_for_todoist.storage import get_storage
from tools_for_todoist.utils import retry_flaky_function

logger = logging.getLogger(__name__)

TODOIST_API_KEY = 'todoist.api_key'
SYNC_API_URL = 'https://api.todoist.com/api/v1/sync'
ACTIVITIES_API_URL = 'https://api.todoist.com/api/v1/activities'
COMPLETED_API_URL = 'https://api.todoist.com/api/v1/tasks/completed/by_completion_date'


class SyncError(Exception):
    pass


class Todoist:
    def __init__(self):
        self._recreate_api()
        self._sync_token = '*'
        self._command_queue = []
        self._items = {}
        self._projects = {}
        self._last_completed = None
        self._initial_sync()

    def _recreate_api(self):
        token = get_storage().get_value(TODOIST_API_KEY)
        self._session = Session()
        self._session.headers['Authorization'] = f'Bearer {token}'

    def _do_sync(self, resource_types=None, commands=None):
        data = {'sync_token': self._sync_token}
        if resource_types is not None:
            data['resource_types'] = json.dumps(resource_types)
        if commands is not None:
            data['commands'] = json.dumps(commands)
        response = self._session.post(SYNC_API_URL, data=data)
        response.raise_for_status()
        result = response.json()

        if commands and 'sync_status' in result:
            for cmd_uuid, status in result['sync_status'].items():
                if isinstance(status, dict) and 'error' in status:
                    raise SyncError(f'Command {cmd_uuid} failed: {status["error"]}')

        if 'sync_token' in result:
            self._sync_token = result['sync_token']
        return result

    def _add_command(self, command_type, args, temp_id=None):
        command = {
            'type': command_type,
            'uuid': str(uuid.uuid4()),
            'args': args,
        }
        if temp_id is not None:
            command['temp_id'] = temp_id
        self._command_queue.append(command)

    def _activity_sync(self, cursor=None, limit=50):
        def activity_get_func():
            params = {
                'object_event_types': json.dumps(['item:completed']),
                'limit': limit,
            }
            if cursor is not None:
                params['cursor'] = cursor
            response = self._session.get(ACTIVITIES_API_URL, params=params)
            response.raise_for_status()
            return response.json()

        return retry_flaky_function(
            activity_get_func,
            'todoist_activity_get',
            validate_result_func=lambda x: x and 'results' in x,
            on_failure_func=self._recreate_api,
        )

    def _update_projects(self, sync_result):
        for project in sync_result.get('projects', []):
            self._projects[project['id']] = project

    def _fetch_completed_items(self, project_id, cursor=None, limit=200):
        now = datetime.now(timezone.utc)
        params = {
            'project_id': project_id,
            'since': (now - timedelta(days=89)).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'until': now.strftime('%Y-%m-%dT%H:%M:%SZ'),
            'limit': limit,
        }
        if cursor is not None:
            params['cursor'] = cursor
        response = self._session.get(COMPLETED_API_URL, params=params)
        response.raise_for_status()
        return response.json()

    def _initial_sync(self):
        def do_initial_sync():
            return self._do_sync(resource_types=['all'])

        self._initial_result = retry_flaky_function(
            do_initial_sync,
            'todoist_initial_sync',
            on_failure_func=self._recreate_api,
            validate_result_func=lambda x: x and 'projects' in x and 'items' in x,
        )
        for item in self._initial_result['items']:
            self._items[item['id']] = TodoistItem.from_raw(self, item)
        self._update_projects(self._initial_result)
        for project_id in self._projects.keys():
            # TODO(kris): Improve this completed logic or deprecate
            result = self._fetch_completed_items(project_id)
            for item in result.get('items', []):
                self._items[item['id']] = TodoistItem.from_raw(self, item)
            while result.get('next_cursor'):
                result = self._fetch_completed_items(project_id, cursor=result['next_cursor'])
                for item in result.get('items', []):
                    self._items[item['id']] = TodoistItem.from_raw(self, item)
        activity_result = self._activity_sync(limit=1)
        if activity_result['results']:
            self._last_completed = activity_result['results'][0]['id']
        self.owner_id = self._initial_result['user']['id']

    def _new_completed(self):
        finished_processing = False
        cursor = None
        first_event = None
        new_completed = set()

        while not finished_processing:
            activity_result = self._activity_sync(cursor=cursor)
            results = activity_result['results']
            next_cursor = activity_result.get('next_cursor')
            finished_processing = next_cursor is None
            cursor = next_cursor
            for event in results:
                if first_event is None:
                    first_event = event['id']
                if event['id'] == self._last_completed:
                    finished_processing = True
                    break

                new_completed.add((event.get('initiator_id'), event['object_id']))
        self._last_completed = first_event
        return new_completed

    def _update_items(self, raw_updated_items):
        deleted_items = []
        new_items = []
        updated_items = []
        for item in raw_updated_items:
            if item.get('is_deleted'):
                old_item = self._items.pop(item['id'], None)
                if old_item is not None:
                    deleted_items.append(old_item)
            elif item['id'] not in self._items:
                if 'content' not in item:
                    continue
                new_item = TodoistItem.from_raw(self, item)
                self._items[new_item.id] = new_item
                new_items.append(new_item)
            else:
                item_model = self.get_item_by_id(item['id'])
                existing_raw = item_model.raw()
                old_item = (
                    TodoistItem.from_raw(self, existing_raw)
                    if existing_raw and 'content' in existing_raw
                    else None
                )
                merged_raw = {**(existing_raw or {}), **item}
                item_model.update_from_raw(merged_raw)
                if old_item is not None:
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
        temp_id = str(uuid.uuid4())
        self._add_command('label_add', {'name': name}, temp_id=temp_id)
        result = self._commit()
        return result.get('temp_id_mapping', {}).get(temp_id, temp_id)

    def add_item(self, item):
        logger.info(f'Adding item| {item}')
        temp_id = str(uuid.uuid4())
        args = {
            'content': item.content,
            'project_id': item.project_id,
            'priority': item.priority,
            'labels': list(item.labels()),
            'description': item.description,
        }
        if item._due is not None:
            args['due'] = item._due
        if item._duration is not None:
            args['duration'] = item._duration
        self._add_command('item_add', args, temp_id=temp_id)
        self._items[temp_id] = item
        return {'id': temp_id}

    def update_item(self, item, **kwargs):
        logger.info(f'Updating item| {item}')
        kwargs['id'] = item.id
        self._add_command('item_update', kwargs)

    def delete_item(self, item):
        logger.info(f'Deleting item| {item}')
        self._add_command('item_delete', {'id': item.id})

    def archive_item(self, item):
        logger.info(f'Archiving item| {item}')
        self._add_command('item_complete', {'id': item.id})

    def uncomplete_item(self, item):
        logger.info(f'Uncompleting item| {item}')
        self._add_command('item_uncomplete', {'id': item.id})

    def _commit(self):
        commands = self._command_queue.copy()
        self._command_queue.clear()
        return self._do_sync(commands=commands)

    def sync(self):
        commands = self._command_queue.copy()
        self._command_queue.clear()

        def api_sync():
            if commands:
                return self._do_sync(resource_types=['all'], commands=commands)
            return self._do_sync(resource_types=['all'])

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
