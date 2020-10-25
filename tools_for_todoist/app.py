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

from tools_for_todoist.services.calendar_to_todoist import CalendarToTodoistService


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
    sync_service = CalendarToTodoistService()
    logger.info('Started syncing service.')

    while True:
        result = sync_service.sync()
        for todoist_sync_result in result['todoist']:
            for item in todoist_sync_result['created']:
                logger.info(f'RAW|Created Item| {item}')
            for item in todoist_sync_result['deleted']:
                logger.info(f'RAW|Deleted Item| {item}')

        time.sleep(10)


def main():
    logger = setup_logger(os.environ.get('LOGGING_LEVEL', logging.DEBUG))
    while True:
        try:
            run_sync_service(logger)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as e:
            logger.exception('Restarting app after exception!', exc_info=e)


if __name__ == '__main__':
    main()
