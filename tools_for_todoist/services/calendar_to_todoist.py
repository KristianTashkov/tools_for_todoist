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
import re
from datetime import datetime, timedelta

from dateutil.parser import parse
from dateutil.tz import UTC, gettz

from tools_for_todoist.models.google_calendar import GoogleCalendar
from tools_for_todoist.models.item import TodoistItem
from tools_for_todoist.models.todoist import Todoist
from tools_for_todoist.storage import get_storage
from tools_for_todoist.utils import is_allday

logger = logging.getLogger(__name__)

CALENDAR_EVENT_TODOIST_KEY = 'todoist_item_id'
CALENDAR_EVENT_ID = 'calendar_event_id'
CALENDAR_LAST_COMPLETED = 'last_completed'
CALENDAR_TO_TODOIST_LABEL = 'calendar_to_todoist.label'


def _todoist_id(calendar_event):
    todoist_id = calendar_event.get_private_info(CALENDAR_EVENT_TODOIST_KEY)
    if todoist_id is None:
        return None
    if not re.fullmatch(r'[\d]*', todoist_id):
        return None
    return int(todoist_id)


def _todoist_title(calendar_event):
    title = calendar_event.summary if calendar_event.summary is not None else '(No title)'
    return f'[{title}]({calendar_event.html_link()})'


def _next_occurrence(calendar_event):
    last_completed = parse(calendar_event.get_private_info(CALENDAR_LAST_COMPLETED))
    return calendar_event.next_occurrence(last_completed)


def _update_todoist_item(todoist_item, calendar_event):
    if todoist_item.is_completed():
        return False

    todoist_item.content = _todoist_title(calendar_event)
    todoist_item.set_due(_next_occurrence(calendar_event), calendar_event.recurrence_string())
    return todoist_item.save()


class CalendarToTodoistService:
    def __init__(self):
        self.todoist = Todoist()
        self.google_calendar = GoogleCalendar()
        self.item_to_event = {}

    def _create_todoist_item(self, calendar_event):
        todoist_title = _todoist_title(calendar_event)
        item = TodoistItem(self.todoist, todoist_title, self.todoist.active_project_id)
        label_name = get_storage().get_value(CALENDAR_TO_TODOIST_LABEL)
        if label_name:
            calendar_label_id = self.todoist.get_label_id_by_name(label_name)
            if calendar_label_id is None:
                calendar_label_id = self.todoist.create_label(label_name)
            item.add_label(calendar_label_id)
        item.set_due(_next_occurrence(calendar_event), calendar_event.recurrence_string())
        item.save()
        return item

    def _process_new_event(self, calendar_event):
        todoist_id = _todoist_id(calendar_event)
        todoist_item = None

        if todoist_id is not None:
            self.item_to_event[todoist_id] = calendar_event
            todoist_item = self.todoist.get_item_by_id(todoist_id)

        if calendar_event.get_private_info(CALENDAR_LAST_COMPLETED) is None:
            now = datetime.now(gettz(self.google_calendar.default_timezone))
            default_last_completed = (
                (now.date() - timedelta(1))
                if is_allday(calendar_event.start())
                else now.astimezone(UTC)
            )
            calendar_event.save_private_info(CALENDAR_LAST_COMPLETED, default_last_completed)
            if todoist_item is not None:
                logger.warning(
                    f'Linked Event with missing last completion info '
                    f'{calendar_event} {todoist_item}'
                )
                calendar_event.save()

        if _next_occurrence(calendar_event) is None:
            if todoist_item is None or todoist_item.is_completed():
                return

            self.todoist.archive_item(todoist_item)
            return None

        logger.debug(f'Processing new event| {calendar_event}')
        calendar_id = calendar_event.get_private_info(CALENDAR_EVENT_ID)
        if todoist_item is not None and calendar_id == calendar_event.id():
            _update_todoist_item(todoist_item, calendar_event)
            return None

        item = self._create_todoist_item(calendar_event)
        return calendar_event, item

    def _process_cancelled_event(self, calendar_event):
        logger.debug(f'Canceling event| {calendar_event}')
        todoist_id = _todoist_id(calendar_event)

        if todoist_id is not None:
            todoist_item = self.todoist.get_item_by_id(todoist_id)
            if todoist_item is not None:
                self.todoist.delete_item(todoist_item)

    def _process_updated_event(self, old_calendar_event, calendar_event):
        todoist_id = _todoist_id(calendar_event)

        if todoist_id is None:
            return None
        todoist_item = self.todoist.get_item_by_id(todoist_id)
        if (
            old_calendar_event is not None
            and old_calendar_event.is_declined_by_me()
            and not calendar_event.is_declined_by_me()
        ):
            if todoist_item is not None and todoist_item.is_completed():
                self.todoist.uncomplete_item(todoist_item)

        if _next_occurrence(calendar_event) is None:
            if todoist_item is not None and not todoist_item.is_completed():
                self.todoist.archive_item(todoist_item)
            return None

        logger.debug(f'Updating event| old:{old_calendar_event} new:{calendar_event}')
        if todoist_item is not None:
            _update_todoist_item(todoist_item, calendar_event)
            return None

        item = self._create_todoist_item(calendar_event)
        return calendar_event, item

    def _google_calendar_sync(self):
        sync_result = self.google_calendar.sync()
        new_event_item_links = []

        for calendar_event in sync_result['created']:
            new_event_item_link = self._process_new_event(calendar_event)
            if new_event_item_link is not None:
                new_event_item_links.append(new_event_item_link)

        for calendar_event in sync_result['cancelled']:
            self._process_cancelled_event(calendar_event)

        for old_calendar_event, calendar_event in sync_result['updated']:
            new_event_item_link = self._process_updated_event(old_calendar_event, calendar_event)
            if new_event_item_link is not None:
                new_event_item_links.append(new_event_item_link)

        return sync_result, new_event_item_links

    def _todoist_sync(self):
        should_sync = True
        sync_results = []
        while should_sync:
            sync_result = self.todoist.sync()
            should_sync = False

            for item_id in sync_result['completed']:
                item = self.todoist.get_item_by_id(item_id)
                item_info = item if item is not None else f'Deleted item {item_id}'

                logger.info(f'Completed Item| {item_info}')
                if item is None or item.has_parent():
                    continue

                calendar_event = self.item_to_event.get(item_id)
                if calendar_event is None:
                    logger.warning(f'Link to calendar event missing for {item}')
                    continue

                current_completed = _next_occurrence(calendar_event)
                if current_completed is None:
                    logger.warning(f'Completion for {item} without next viable occurrence')
                    continue

                if not is_allday(current_completed):
                    current_completed = current_completed.astimezone(UTC)

                calendar_event.save_private_info(CALENDAR_LAST_COMPLETED, current_completed)
                calendar_event.save()

                if not item.is_completed():
                    should_sync |= _update_todoist_item(item, calendar_event)
            sync_results.append(sync_result)
        return sync_results

    def sync(self):
        google_calendar_sync_result, new_event_item_links = self._google_calendar_sync()
        todoist_sync_results = self._todoist_sync()

        for calendar_event, todoist_item in new_event_item_links:
            calendar_event.save_private_info(CALENDAR_EVENT_TODOIST_KEY, todoist_item.id)
            calendar_event.save_private_info(CALENDAR_EVENT_ID, calendar_event.id())
            calendar_event.save()
            self.item_to_event[todoist_item.id] = calendar_event

        return {'todoist': todoist_sync_results, 'google_calendar': google_calendar_sync_result}
