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
import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from tools_for_todoist.models.event import CalendarEvent
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


def _save_credentials(token):
    get_storage().set_value(GOOGLE_CALENDAR_TOKEN, json.loads(token.to_json()))


def _do_auth():
    storage = get_storage()
    token_json = storage.get_value(GOOGLE_CALENDAR_TOKEN)
    if token_json is not None:
        token = Credentials.from_authorized_user_info(token_json)
        if token.valid:
            return token
        if token.expired and token.refresh_token:
            token.refresh(Request())
            _save_credentials(token)
            return token
    flow = InstalledAppFlow.from_client_config(
        storage.get_value(GOOGLE_CALENDAR_CREDENTIALS), SCOPES
    )
    token = flow.run_local_server(port=int(os.environ.get('PORT', 0)))
    _save_credentials(token)
    return token


class GoogleCalendar:
    def __init__(self):
        self._recreate_api()
        self._calendar_id = get_storage().get_value(GOOGLE_CALENDAR_CALENDAR_ID)
        self._raw_events = []
        self._events = {}
        self.sync_token = None
        self.default_timezone = (
            self.api.calendars().get(calendarId=self._calendar_id).execute()['timeZone']
        )

    def _recreate_api(self):
        token = _do_auth()
        self.api = build('calendar', 'v3', credentials=token, cache_discovery=False)

    def _process_sync(self):
        created_events = []
        created_events_ids = set()
        cancelled_events = []
        updated_events = []
        updated_events_ids = set()
        pending_exceptions = []
        cancelled_events_ids = set()

        for event in self._raw_events:
            recurring_event_id = event.get('recurringEventId')
            if recurring_event_id is not None:
                pending_exceptions.append(event)
            elif event['status'] == 'cancelled':
                canceled_event = self._events.pop(event['id'], None)
                if canceled_event is not None:
                    cancelled_events.append(canceled_event)
                cancelled_events_ids.add(event['id'])
            elif event['id'] not in self._events:
                new_event = CalendarEvent.from_raw(self, event)
                self._events[event['id']] = new_event
                created_events.append(new_event)
                created_events_ids.add(event['id'])
            else:
                event_model = self._events[event['id']]
                old_event_copy = CalendarEvent.from_raw(self, event_model.raw())
                event_model.update_from_raw(event)
                updated_events.append((old_event_copy, event_model))
                updated_events_ids.add(event['id'])

        for event in pending_exceptions:
            recurring_event_id = event.get('recurringEventId')
            if recurring_event_id in cancelled_events_ids:
                continue
            if recurring_event_id not in self._events:
                logger.warning(
                    f'Skipping recurring event exception for missing event: '
                    f'{event.get("summary")} {event.get("status")} {event.get("originalStartTime")}'
                )
                continue
            recurring_event = self._events[recurring_event_id]
            recurring_event.update_exception(event)
            # TODO(daniel): Implement this properly
            if (
                recurring_event_id not in updated_events_ids
                and recurring_event_id not in created_events_ids
            ):
                updated_events.append((None, recurring_event))
                updated_events_ids.add(recurring_event_id)

        return {
            'created': created_events,
            'cancelled': cancelled_events,
            'updated': updated_events,
            'exceptions': pending_exceptions,
        }

    def get_event_by_id(self, event_id):
        return self._events.get(event_id)

    def update_event(self, event_id, update_data):
        self.api.events().patch(
            calendarId=self._calendar_id, eventId=event_id, body=update_data
        ).execute()

    def sync(self):
        request = self.api.events().list(calendarId=self._calendar_id, syncToken=self.sync_token)
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
        sync_result = self._process_sync()
        sync_result['raw_events'] = self._raw_events
        return sync_result
