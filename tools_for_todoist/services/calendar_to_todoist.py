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

CALENDAR_EVENT_TODOIST_KEY = 'todoist_item_id'
CALENDAR_EVENT_ID = 'calendar_event_id'


def _todoist_id(calendar_event):
    todoist_id = calendar_event.get_private_info(CALENDAR_EVENT_TODOIST_KEY)
    if todoist_id is None:
        return None
    if not re.fullmatch(r'[\d]*', todoist_id):
        return None
    return int(todoist_id)


def _todoist_title(calendar_event):
    return f'[{calendar_event.summary}]({calendar_event.html_link()})'


class CalendarToTodoistService:
    def __init__(self, calendar_id, todoist_project):
        self.todoist = Todoist(todoist_project)
        self.google_calendar = GoogleCalendar(calendar_id)

    def _update_todoist_item(self, todoist_item, calendar_event):
        todoist_item.content = _todoist_title(calendar_event)
        todoist_item.save()

    def _process_new_event(self, calendar_event):
        print('Processing new event|', calendar_event)
        todoist_id = _todoist_id(calendar_event)
        next_occurence = calendar_event.next_occurrence()
        if next_occurence is None:
            if todoist_id is None:
                return

            todoist_item = self.todoist.get_item_by_id(int(todoist_id))
            if todoist_item is None:
                return

            self.todoist.delete_item(todoist_item)
            return

        calendar_id = calendar_event.get_private_info(CALENDAR_EVENT_ID)
        if (
                todoist_id is not None and
                self.todoist.get_item_by_id(todoist_id) is not None and
                calendar_id == calendar_event.id()
        ):
            self._update_todoist_item(self.todoist.get_item_by_id(todoist_id), calendar_event)
            return

        todoist_title = _todoist_title(calendar_event)
        item = TodoistItem(
            self.todoist, todoist_title, self.todoist.active_project_id)
        item.set_due(
            next_occurence,
            calendar_event.recurrence_string())
        item.save()
        return calendar_event, item

    def _process_cancelled_event(self, calendar_event):
        print('Canceling event|', calendar_event)
        todoist_id = _todoist_id(calendar_event)

        if todoist_id is not None:
            todoist_item = self.todoist.get_item_by_id(todoist_id)
            if todoist_item is not None:
                self.todoist.delete_item(todoist_item)

    def _google_calendar_sync(self):
        sync_result = self.google_calendar.sync()
        new_event_item_links = []

        for calendar_event in sync_result['created']:
            new_event_item_link = self._process_new_event(calendar_event)
            if new_event_item_link is not None:
                new_event_item_links.append(new_event_item_link)

        for calendar_event in sync_result['cancelled']:
            self._process_cancelled_event(calendar_event)
        return sync_result, new_event_item_links

    def _todoist_sync(self):
        sync_result = self.todoist.sync()
        for item_id in sync_result['completed']:
            item = self.todoist.get_item_by_id(item_id)
            print('Completed Item|', item if item is not None else f'Deleted item {item_id}')
        return sync_result

    def sync(self):
        google_calendar_sync_result, new_event_item_links = self._google_calendar_sync()
        todoist_sync_result = self._todoist_sync()

        for calendar_event, todoist_item in new_event_item_links:
            calendar_event.save_private_info(CALENDAR_EVENT_TODOIST_KEY, todoist_item.id)
            calendar_event.save_private_info(CALENDAR_EVENT_ID, calendar_event.id())
            calendar_event.save()

        return {
            'todoist': todoist_sync_result,
            'google_calendar': google_calendar_sync_result
        }
