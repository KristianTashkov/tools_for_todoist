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
import os
import time

import requests

from tools_for_todoist.models.google_calendar import GoogleCalendar
from tools_for_todoist.models.todoist import Todoist
from tools_for_todoist.services.calendar_to_todoist import CalendarToTodoistService
from tools_for_todoist.services.night_owl_enabler import NightOwlEnabler
from tools_for_todoist.storage import KeyValueStorage, set_storage
from tools_for_todoist.storage.storage import LocalKeyValueStorage, PostgresKeyValueStorage

DEFAULT_STORAGE = os.path.join(os.path.dirname(__file__), 'storage', 'store.json')


def setup_storage() -> KeyValueStorage:
    database_config = os.environ.get('DATABASE_URL', None)
    if database_config is not None:
        storage = PostgresKeyValueStorage(database_config)
    else:
        storage = LocalKeyValueStorage(os.environ.get('FILE_STORE', DEFAULT_STORAGE))
    set_storage(storage)
    return storage


def setup_logger(logging_level=logging.DEBUG):
    logger = logging.getLogger()
    logger.handlers.clear()
    stream_handler = logging.StreamHandler()
    formatter = logging.Formatter('[%(levelname)s] %(name)s: %(message)s')
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    logger = logging.getLogger('tools_for_todoist')
    logger.setLevel(logging_level)
    return logger


def run_sync_service(logger):
    todoist = Todoist()
    google_calendar = GoogleCalendar()
    calendar_service = CalendarToTodoistService(todoist, google_calendar)
    night_owl_enabler = NightOwlEnabler(todoist, google_calendar)
    logger.info('Started syncing service.')

    while True:
        calendar_sync_result = google_calendar.sync()
        calendar_service.on_calendar_sync(calendar_sync_result)

        should_keep_syncing = True
        while should_keep_syncing:
            todoist_sync_result = todoist.sync()
            should_keep_syncing = False
            should_keep_syncing |= calendar_service.on_todoist_sync(todoist_sync_result)
            should_keep_syncing |= night_owl_enabler.on_todoist_sync(todoist_sync_result)
        time.sleep(10)


def _send_slack_message(storage: KeyValueStorage, message: str) -> None:
    slack_webhook_url = storage.get_value('logging.slack_webhook_url')
    if slack_webhook_url is None:
        return
    payload = {'text': message, 'username': 'tools_for_todoist'}
    requests.post(slack_webhook_url, json=payload)


STABLE_RUNNING_THRESHOLD = 300
MAX_RESTART_DELAY = 300


def main():
    storage = setup_storage()
    logger = setup_logger(os.environ.get('LOGGING_LEVEL', logging.DEBUG))
    restart_delay = 0
    while True:
        start_time = time.monotonic()
        try:
            run_sync_service(logger)
        except Exception as e:
            elapsed = time.monotonic() - start_time
            if elapsed >= STABLE_RUNNING_THRESHOLD:
                restart_delay = 0
            _send_slack_message(storage, f'TFT server restarting: {e}')
            logger.exception(
                f'Restarting app after exception! Delay {restart_delay}s.',
                exc_info=e,
            )
            time.sleep(restart_delay)
            restart_delay = min(max(restart_delay * 2, 1), MAX_RESTART_DELAY)


if __name__ == '__main__':
    main()
