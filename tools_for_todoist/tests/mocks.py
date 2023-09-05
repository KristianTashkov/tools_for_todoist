"""
Copyright (C) 2020-2023 Kristian Tashkov <kristian.tashkov@gmail.com>

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
from contextlib import ExitStack
from typing import Any, Dict, Optional
from unittest import TestCase
from unittest.mock import MagicMock

from tools_for_todoist.models.item import TodoistItem
from tools_for_todoist.storage import set_storage
from tools_for_todoist.storage.storage import KeyValueStorage


class ServicesTestCase(TestCase):
    def setUp(self) -> None:
        self._exit_stack = ExitStack()

        self._todoist_items: Dict[str, TodoistItem] = {}
        self._todoist_mock = MagicMock()
        self._todoist_mock.get_item_by_id.side_effect = lambda item_id: self._todoist_items.get(
            item_id
        )

        self._google_calendar_mock = MagicMock()
        self._google_calendar_mock.default_timezone = 'Europe/Zurich'

        self._storage = KeyValueStorage()
        set_storage(self._storage)

    def tearDown(self) -> None:
        self._exit_stack.close()

    def _create_todoist_item(self, due: Optional[Dict[str, Any]] = None) -> TodoistItem:
        raw_item = {
            'id': 'TEST_ITEM_ID',
            'project_id': 'TEST_PROJECT_ID',
            'content': 'Test item',
            'priority': 1,
            'description': 'Test item description',
            'checked': False,
            'duration': None,
            'labels': [],
            'due': due,
        }
        item = TodoistItem.from_raw(self._todoist_mock, raw_item)
        self._todoist_items[item.id] = item
        return item
