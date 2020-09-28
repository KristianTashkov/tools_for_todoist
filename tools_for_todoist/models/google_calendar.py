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

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from tools_for_todoist.credentials import CREDENTIALS_JSON_PATH, TOKEN_CACHE_PATH
from tools_for_todoist.models.event import CalendarEvent

SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']


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
    token = flow.run_local_server(port=0)
    _save_credentials(token)
    return token


class GoogleCalendar:
    def __init__(self, calendar_id):
        token = _do_auth()
        self._calendar_id = calendar_id
        self.api = build('calendar', 'v3', credentials=token)
        self._raw_events = []
        self.events = []
        self.sync_token = None
        self._initial_sync()

    def _initial_sync(self):
        self._sync()
        for event in self._raw_events:
            self.events.append(CalendarEvent.from_raw(event))

    def _sync(self):
        request = self.api.events().list(
            calendarId=self._calendar_id, maxResults=1, singleEvents=True,
            syncToken=self.sync_token
        )
        self._raw_events = []
        while request is not None:
            response = request.execute()
            self._raw_events.extend(response['items'])
            request = self.api.events().list_next(request, response)
        self.sync_token = response['nextSyncToken']
