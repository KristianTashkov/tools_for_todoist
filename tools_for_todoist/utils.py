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
from datetime import date as dt_date
from datetime import datetime as dt_datetime
from time import sleep

from dateutil.tz import UTC

logger = logging.getLogger(__name__)


def is_allday(dt):
    return isinstance(dt, dt_date) and not isinstance(dt, dt_datetime)


def ensure_datetime(dt):
    if not is_allday(dt):
        return dt
    return dt_datetime.combine(dt, dt_datetime.min.time())


def datetime_as(dt, compare_dt):
    dt = ensure_datetime(dt)
    if is_allday(compare_dt):
        return dt.date()
    if compare_dt.tzinfo is not None:
        return dt.astimezone(UTC)
    assert dt.tzinfo is None
    return dt


def to_todoist_date(dt):
    if is_allday(dt):
        return str(dt), None

    if dt.tzinfo is None:
        return dt.isoformat(), None

    timezone = re.search(r'.*/(.*/.*)', dt.tzinfo._filename)[1]
    return dt.astimezone(UTC).isoformat().replace('+00:00', 'Z'), timezone


def retry_flaky_function(
    func, name, validate_result_func=None, on_failure_func=None, critical_errors=None
):
    for attempt in range(1, 6):
        try:
            result = func()
            if validate_result_func is not None and not validate_result_func(result):
                raise ValueError(f'Flaky function result was invalid: "{result}"')
            return result
        except Exception as e:
            if critical_errors is not None and type(e) in critical_errors:
                raise
            if on_failure_func is not None:
                on_failure_func()
            if attempt == 5:
                logger.exception(f'Failed to execute flaky function {name}', exc_info=e)
                raise
            plural_failure = 's' if attempt > 1 else ''
            logger.warning(
                f'Retrying flaky function {name} soon. {attempt} failure{plural_failure} so far.'
            )
            sleep(10 * (attempt - 1))
