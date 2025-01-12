"""
Copyright (C) 2020-2023 Kristian Tashkov <kristian.tashkov@gmail.com>

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
from datetime import datetime
from typing import Any, Dict

from dateutil.tz import gettz

from tools_for_todoist.models.google_calendar import GoogleCalendar
from tools_for_todoist.models.todoist import Todoist
from tools_for_todoist.storage import get_storage

NIGHT_OWL_DAY_SWITCH_HOUR = 'night_owl.day_switch_hour'
logger = logging.getLogger(__name__)


class NightOwlEnabler:
    def __init__(self, todoist: Todoist, calendar: GoogleCalendar) -> None:
        self._todoist = todoist
        self._google_calendar = calendar
        self._day_switch_hour = int(get_storage().get_value(NIGHT_OWL_DAY_SWITCH_HOUR, 4))

    def on_todoist_sync(self, sync_result: Dict[str, Any]) -> bool:
        should_sync = False
        for item_id in sync_result['completed']:
            item = self._todoist.get_item_by_id(item_id)
            if (
                item is None
                or item.get_due_string() is None
                or 'every day' not in item.get_due_string()
            ):
                logger.debug(f'NightOwl: Skipping {item} without every day due date')
                continue

            logger.info(f'NightOwl: Completed every day task: {item}')
            now = datetime.now(gettz(self._google_calendar.default_timezone))
            seconds_from_midnight = (now - now.replace(hour=0, minute=0, second=0)).total_seconds()
            if seconds_from_midnight / 3600 > self._day_switch_hour:
                logger.info(f'NightOwl: Completed after day switch hour, skipping: {item}')
                continue

            next_due = item.next_due_date().replace(year=now.year, month=now.month, day=now.day)
            item.set_due(next_date=next_due, due_string=item.get_due_string())
            should_sync |= item.save()
            logger.info(f'NightOwl: Next due date set to {next_due} for {item}')
        return should_sync
