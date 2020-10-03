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
import time
import os

from tools_for_todoist.credentials import (
    CREDENTIALS_JSON_PATH, TODOIST_API_TOKEN_PATH, TOKEN_CACHE_PATH
)
from tools_for_todoist.services.calendar_to_todoist import CalendarToTodoistService

if not os.path.exists(CREDENTIALS_JSON_PATH):
    with open(CREDENTIALS_JSON_PATH, 'w') as file:
        file.write(os.environ.get('GOOGLE_CALENDAR_CREDENTIALS'))

if not os.path.exists(TODOIST_API_TOKEN_PATH):
    with open(TODOIST_API_TOKEN_PATH, 'w') as file:
        file.write(os.environ.get('TODOIST_API_KEY'))

if not os.path.exists(TOKEN_CACHE_PATH):
    with open(TOKEN_CACHE_PATH, 'w') as file:
        file.write(os.environ.get('GOOGLE_CALENDAR_TOKEN'))

todoist_project = os.environ.get('TODOIST_PROJECT_NAME')
calendar_id = os.environ.get('GOOGLE_CALENDAR_ID')
sync_service = CalendarToTodoistService(calendar_id, todoist_project)

while True:
    result = sync_service.step()
    if result['updated'] or result['exceptions']:
        for event in result['updated']:
            print('RAW|Updated|', event)
        for event in result['exceptions']:
            print('RAW|Event Instance|', event)

    time.sleep(10)
