import os
import pickle
import warnings

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

CREDENTIALS_JSON_PATH = 'credentials.json'
TOKEN_CACHE_PATH = 'token_cache.pkl'


def _save_credentials(token):
    if TOKEN_CACHE_PATH is None:
        warnings.warn('TOKEN_CACHE_PATH is not set in settings.py')
        return
    with open(TOKEN_CACHE_PATH, 'wb') as token_io:
        pickle.dump(token, token_io)
    

def _do_auth():
    if TOKEN_CACHE_PATH is not None and os.path.exists(TOKEN_CACHE_PATH):
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


class CalendarAPI:
    def __init__(self):
        token  = _do_auth()
        self._calendar_service = build('calendar', 'v3', credentials=token)

    def iterate_events(self, calendar_id, **kwargs):
        request = self._calendar_service.events().list(calendarId=calendar_id, **kwargs)
        while request is not None:
            response = request.execute()
            for item in response['items']:
                yield item
            request = self._calendar_service.events().list_next(request, response)
