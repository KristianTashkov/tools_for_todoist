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
import re

from tools_for_todoist.models.google_calendar import GoogleCalendar
from tools_for_todoist.models.item import TodoistItem
from tools_for_todoist.models.todoist import Todoist
from datetime import datetime
from dateutil.tz import UTC

CALENDAR_EVENT_TODOIST_KEY = 'todoist_item_id'
CALENDAR_EVENT_ID = 'calendar_event_id'


class CalendarToTodoistService:
    def __init__(self, calendar_id, todoist_project):
        self.todoist = Todoist(todoist_project)
        self.google_calendar = GoogleCalendar(calendar_id)

    def step(self):
        sync_result = self.google_calendar.sync()
        created_items = []

        for calendar_event in sync_result['created']:
            print('Processing new event|', calendar_event)
            last_occurrence = calendar_event.get_last_occurrence()
            if last_occurrence is None or last_occurrence < datetime.now(UTC):
                todoist_id = calendar_event.get_private_info(CALENDAR_EVENT_TODOIST_KEY)
                if todoist_id is None:
                    continue

                todoist_item = self.todoist.get_item_by_id(int(todoist_id))
                if todoist_item is None:
                    continue

                self.todoist.delete_item(todoist_item)
                continue

            todoist_id = calendar_event.get_private_info(CALENDAR_EVENT_TODOIST_KEY)
            calendar_id = calendar_event.get_private_info(CALENDAR_EVENT_ID)
            if (
                    todoist_id is not None and
                    re.fullmatch(r'[\d]*', todoist_id) is not None and
                    self.todoist.get_item_by_id(int(todoist_id)) is not None and
                    calendar_id == calendar_event.id()
            ):
                continue

            item = TodoistItem(
                self.todoist, calendar_event.summary, self.todoist.active_project_id)
            recurrence_string = calendar_event.get_recurrence_string()
            next_occurrence = calendar_event.get_next_occurrence().isoformat()
            next_occurrence = re.search(
                r'(.*T\d\d:\d\d:\d\d)\+(.*)', next_occurrence).groups()[0]
            item.set_due(next_occurrence, recurrence_string)
            item.save()
            created_items.append((calendar_event, item))

        for calendar_event in sync_result['cancelled']:
            print('Canceling event|', calendar_event)
            todoist_id = calendar_event.get_private_info(CALENDAR_EVENT_TODOIST_KEY)
            if todoist_id is not None:
                todoist_item = self.todoist.get_item_by_id(int(todoist_id))
                if todoist_item is not None:
                    self.todoist.delete_item(todoist_item)

        self.todoist.sync()
        for calendar_event, todoist_item in created_items:
            calendar_event.save_private_info(CALENDAR_EVENT_TODOIST_KEY, todoist_item.id)
            calendar_event.save_private_info(CALENDAR_EVENT_ID, calendar_event.id())
            calendar_event.save()

        return sync_result
