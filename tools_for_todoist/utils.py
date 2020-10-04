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
import re

from dateutil.tz import UTC
from datetime import date as dt_date, datetime as dt_datetime


def is_allday(dt):
    return isinstance(dt, dt_date) and not isinstance(dt, dt_datetime)


def ensure_datetime(dt):
    if not is_allday(dt):
        return dt
    return dt_datetime.combine(dt, dt_datetime.min.time()).astimezone(UTC)


def to_todoist_date(dt):
    if is_allday(dt):
        return str(dt), None

    if dt.tzinfo is None:
        return dt.isoformat(), None

    timezone = re.search(r'.*/(.*/.*)', dt.tzinfo._filename).groups()[0]
    return dt.astimezone(UTC).isoformat().replace('+00:00', 'Z'), timezone
