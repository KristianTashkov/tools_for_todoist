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
from tools_for_todoist.models.google_calendar import GoogleCalendar
from tools_for_todoist.models.item import TodoistItem
from tools_for_todoist.models.todoist import Todoist

CALENDAR_EVENT_TODOIST_KEY = 'todoist_item_id'


class CalendarToTodoistService:
    def __init__(self, calendar_id, todoist_project):
        self.todoist = Todoist(todoist_project)
        self.google_calendar = GoogleCalendar(calendar_id)

    def step(self):
        sync_result = self.google_calendar.sync()
        created_items = []

        for calendar_event in sync_result['created']:
            todoist_id = calendar_event.get_private_info(CALENDAR_EVENT_TODOIST_KEY)
            if todoist_id is not None and self.todoist.get_item_by_id(int(todoist_id)) is not None:
                continue

            item = TodoistItem(
                self.todoist, calendar_event.summary, self.todoist.active_project_id)
            recurrence_string = calendar_event.get_recurrence_string()
            if recurrence_string:
                item.set_due_by_string(recurrence_string)
            else:
                item.set_next_due_date(calendar_event.get_start_time())
            item.save()
            created_items.append((calendar_event, item))

        for calendar_event in sync_result['cancelled']:
            todoist_id = calendar_event.get_private_info(CALENDAR_EVENT_TODOIST_KEY)
            if todoist_id is not None:
                todoist_item = self.todoist.get_item_by_id(int(todoist_id))
                if todoist_item is not None:
                    self.todoist.delete_item(todoist_item)

        self.todoist.sync()
        for calendar_event, todoist_item in created_items:
            calendar_event.save_private_info(CALENDAR_EVENT_TODOIST_KEY, todoist_item.id)
            #calendar_event.save()

        return sync_result
