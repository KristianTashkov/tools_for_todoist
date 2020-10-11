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
import argparse
import json
import subprocess

from tools_for_todoist.models.google_calendar import (
    GOOGLE_CALENDAR_TOKEN, GOOGLE_CALENDAR_CREDENTIALS, GOOGLE_CALENDAR_CALENDAR_ID, GoogleCalendar)
from tools_for_todoist.models.todoist import (
    TODOIST_API_KEY, TODOIST_ACTIVE_PROJECT, Todoist)
from tools_for_todoist.storage import (
    get_storage, PostgresKeyValueStorage, LocalKeyValueStorage, DEFAULT_STORAGE)


def _get_heroku_postgres_link():
    try:
        return subprocess.check_output(['heroku', 'config:get', 'DATABASE_URL']).decode().strip()
    except Exception as e:
        print(e)
        return None


parser = argparse.ArgumentParser(description='Configure the application.')
parser.add_argument('--copy_local', action='store_true',
                    help='Copy local store to remote postgres store')
parser.add_argument('--local_file_store', type=str, default=DEFAULT_STORAGE,
                    help='Local filepath to local key value storage')
parser.add_argument('--database_url', type=str, default=_get_heroku_postgres_link(),
                    help='Postgres url to remote database to copy local data to')


def manual_flow():
    storage = get_storage()
    print('Enter Todoist API key:')
    todoist_key = input()
    storage.set_value(TODOIST_API_KEY, todoist_key)
    print('Enter Todoist project name in which events to be synced:')
    todoist_project = input()
    storage.set_value(TODOIST_ACTIVE_PROJECT, todoist_project)
    print('Attempting to sync Todoist...')
    Todoist()
    print('Todoist synced successfully!')

    print('Enter Google Calendar credentials:')
    google_calendar_credentials = input()
    storage.set_value(GOOGLE_CALENDAR_CREDENTIALS, json.loads(google_calendar_credentials))
    print('Enter Google Calendar token (leave empty for local setup):')
    google_calendar_token = input()
    if google_calendar_token:
        storage.set_value(GOOGLE_CALENDAR_TOKEN, json.loads(google_calendar_token))
    print('Enter Google Calendar ID to sync:')
    google_calendar_calendar_id = input()
    storage.set_value(GOOGLE_CALENDAR_CALENDAR_ID, google_calendar_calendar_id)
    print('Attempting to sync Google Calendar...')
    google_calendar = GoogleCalendar()
    google_calendar.sync()

    print('Setup Successful!')


def copy_local_flow(local_file_store, destination_database_url):
    local_storage = LocalKeyValueStorage(local_file_store)
    remote_storage = PostgresKeyValueStorage(destination_database_url)
    for key in list(remote_storage.store.keys()):
        remote_storage.unset_key(key)
    for key, value in local_storage.store.items():
        remote_storage.set_value(key, value)


if __name__ == '__main__':
    args = parser.parse_args()
    if args.copy_local:
        assert args.database_url is not None
        copy_local_flow(args.local_file_store, args.database_url)
    else:
        manual_flow()
