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
from collections import defaultdict

from googleapiclient.discovery import build

from tools_for_todoist.models.event import CalendarEvent
from tools_for_todoist.models.google_auth import GoogleAuth
from tools_for_todoist.storage import get_storage
from tools_for_todoist.utils import retry_flaky_function

logger = logging.getLogger(__name__)

SCOPES = [
    'https://www.googleapis.com/auth/calendar.readonly',
    'https://www.googleapis.com/auth/calendar.events',
]

GOOGLE_CALENDAR_CREDENTIALS = 'google_calendar.credentials'
GOOGLE_CALENDAR_TOKEN = 'google_calendar.token'
GOOGLE_CALENDAR_CALENDAR_ID = 'google_calendar.calendar_id'


class GoogleCalendarSyncResult:
    def __init__(self, raw_results):
        self.raw_results = raw_results
        self.created_events = []
        self.created_events_ids = set()
        self.cancelled_events = []
        self.cancelled_events_ids = set()
        self.updated_events = []
        self.updated_events_ids = set()
        self.merged_event_instances = []


class GoogleCalendar:
    def __init__(self):
        self._recreate_api()
        self._calendar_id = get_storage().get_value(GOOGLE_CALENDAR_CALENDAR_ID)
        self._raw_events = []
        self._events = {}
        self._single_exceptions = defaultdict(list)
        self.sync_token = None
        self.default_timezone = (
            self.api.calendars().get(calendarId=self._calendar_id).execute()['timeZone']
        )

    def _recreate_api(self):
        token = GoogleAuth(
            storage_credentials_key=GOOGLE_CALENDAR_CREDENTIALS,
            storage_token_key=GOOGLE_CALENDAR_TOKEN,
            scopes=SCOPES,
        )
        self.api = build('calendar', 'v3', credentials=token, cache_discovery=False)

    def _process_raw_event(self, raw_event, sync_result):
        if raw_event['status'] == 'cancelled':
            canceled_event = self._events.pop(raw_event['id'], None)
            sync_result.cancelled_events.append(
                canceled_event or CalendarEvent.from_raw(self, raw_event)
            )
            sync_result.cancelled_events_ids.add(raw_event['id'])
        elif raw_event['id'] not in self._events:
            new_event = CalendarEvent.from_raw(self, raw_event)
            self._events[raw_event['id']] = new_event
            sync_result.created_events.append(new_event)
            sync_result.created_events_ids.add(raw_event['id'])

            if raw_event.get('recurringEventId') is not None:
                self._single_exceptions[raw_event['recurringEventId']].append(new_event)
            else:
                single_exceptions = self._single_exceptions.pop(raw_event['id'], [])
                for single_exception in single_exceptions:
                    new_event.update_exception(single_exception.raw())
                    sync_result.merged_event_instances.append(single_exception)
        else:
            event_model = self._events[raw_event['id']]
            old_event_copy = event_model.deep_copy()
            event_model.update_from_raw(raw_event)
            sync_result.updated_events.append((old_event_copy, event_model))
            sync_result.updated_events_ids.add(raw_event['id'])

    def _process_sync(self, sync_result):
        pending_exceptions = []

        for raw_event in self._raw_events:
            recurring_event_id = raw_event.get('recurringEventId')
            if recurring_event_id is not None:
                pending_exceptions.append(raw_event)
            else:
                self._process_raw_event(raw_event, sync_result)

        for raw_event in pending_exceptions:
            recurring_event_id = raw_event.get('recurringEventId')
            if recurring_event_id in sync_result.cancelled_events_ids:
                continue
            if recurring_event_id not in self._events:
                self._process_raw_event(raw_event, sync_result)
                continue

            recurring_event = self._events[recurring_event_id]
            old_event_copy = recurring_event.deep_copy()
            recurring_event.update_exception(raw_event)
            # TODO(daniel): Implement this properly
            if (
                recurring_event_id not in sync_result.updated_events_ids
                and recurring_event_id not in sync_result.created_events_ids
            ):
                sync_result.updated_events.append((old_event_copy, recurring_event))
                sync_result.updated_events_ids.add(recurring_event_id)

    def get_event_by_id(self, event_id):
        return self._events.get(event_id)

    def update_event(self, event_id, update_data):
        self.api.events().patch(
            calendarId=self._calendar_id, eventId=event_id, body=update_data
        ).execute()

    def sync(self):
        request = self.api.events().list(
            calendarId=self._calendar_id,
            syncToken=self.sync_token,
            showDeleted=True,
        )
        response = None

        self._raw_events = []
        while request is not None:
            response = retry_flaky_function(
                lambda: request.execute(),
                'google_calendar_sync',
                on_failure_func=self._recreate_api,
            )
            self._raw_events.extend(response['items'])
            request = self.api.events().list_next(request, response)
        self.sync_token = response['nextSyncToken']

        sync_result = GoogleCalendarSyncResult(self._raw_events)
        self._process_sync(sync_result)
        return sync_result
