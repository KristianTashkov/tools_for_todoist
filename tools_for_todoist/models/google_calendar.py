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


import os
import pickle
import datetime

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from tools_for_todoist.credentials import CREDENTIALS_JSON_PATH, TOKEN_CACHE_PATH
from tools_for_todoist.models.event import CalendarEvent

SCOPES = [
    'https://www.googleapis.com/auth/calendar.readonly',
    'https://www.googleapis.com/auth/calendar.events'
]


def _save_credentials(token):
    with open(TOKEN_CACHE_PATH, 'wb') as token_io:
        pickle.dump(token, token_io)
    

def _do_auth():
    if os.path.exists(TOKEN_CACHE_PATH):
        with open(TOKEN_CACHE_PATH, 'rb') as token_io:
            token = pickle.load(token_io)
        if token.valid:
            return token
        if token.expired and token.refresh_token:
            token.refresh(Request())
            _save_credentials(token)
            return token
    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_JSON_PATH, SCOPES)
    host = os.environ.get('HOST') or 'localhost'
    token = flow.run_local_server(host=host, port=0)
    _save_credentials(token)
    return token


class GoogleCalendar:
    def __init__(self, calendar_id):
        token = _do_auth()
        self._calendar_id = calendar_id
        self.api = build('calendar', 'v3', credentials=token)
        self._raw_events = []
        self._events = {}
        self.sync_token = None

    def _process_sync(self):
        created_events = []
        cancelled_events = []
        cancelled_events_ids = set()

        pending_exceptions = []
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
            else:
                self._events[event['id']].update_from_raw(event)

        for event in pending_exceptions:
            recurring_event_id = event.get('recurringEventId')
            if recurring_event_id in cancelled_events_ids:
                continue
            if recurring_event_id not in self._events:
                print(
                    "Skipping recurring event exception because recurring event is missing: ",
                    recurring_event_id)
                continue
            self._events[recurring_event_id].update_exception(event)

        return {
            'created': created_events,
            'cancelled': cancelled_events
        }

    def get_event_by_id(self, event_id):
        return self._events.get(event_id)

    def update_event(self, event_id, update_data):
        self.api.events().patch(
            calendarId=self._calendar_id, eventId=event_id, body=update_data).execute()

    def sync(self):
        extra_params = {}
        if self.sync_token is None:
            now = datetime.datetime.utcnow().isoformat() + 'Z'
            extra_params['timeMin'] = now
        request = self.api.events().list(
            calendarId=self._calendar_id, syncToken=self.sync_token, **extra_params)

        self._raw_events = []
        while request is not None:
            response = request.execute()
            self._raw_events.extend(response['items'])
            request = self.api.events().list_next(request, response)
        self.sync_token = response['nextSyncToken']
        return self._process_sync()

