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
from datetime import datetime
from unittest.mock import patch

from tools_for_todoist.services.night_owl_enabler import NIGHT_OWL_DAY_SWITCH_HOUR, NightOwlEnabler
from tools_for_todoist.tests.mocks import ServicesTestCase


class NightOwlEnablerTests(ServicesTestCase):
    def setUp(self):
        super().setUp()
        self._storage.set_value(NIGHT_OWL_DAY_SWITCH_HOUR, 2)

    def _set_current_time(self, day: int, hour: int) -> None:
        datetime_mock = self._exit_stack.enter_context(
            patch(
                'tools_for_todoist.services.night_owl_enabler.datetime',
            )
        )
        datetime_mock.now.return_value = datetime(year=2020, month=1, day=day, hour=hour)

    def test_empty_completed(self) -> None:
        self._create_todoist_item(
            due={
                'date': '2020-01-10T23:00:00',
                'string': 'every day at 23:00',
            }
        )
        night_owl_enabler = NightOwlEnabler(self._todoist_mock, self._google_calendar_mock)

        night_owl_enabler.on_todoist_sync({'completed': []})
        self.assertFalse(self._todoist_mock.update_item.called)

    def test_completed_before_midnight(self) -> None:
        test_item = self._create_todoist_item(
            due={
                'date': '2020-01-10T23:00:00',
                'string': 'every day at 23:00',
            }
        )
        night_owl_enabler = NightOwlEnabler(self._todoist_mock, self._google_calendar_mock)

        self._set_current_time(day=10, hour=23)
        night_owl_enabler.on_todoist_sync({'completed': [test_item.id]})
        self._todoist_mock.update_item.assert_not_called()

    def test_completed_before_midnight_date_only(self) -> None:
        test_item = self._create_todoist_item(
            due={
                'date': '2020-01-10',
                'string': 'every day',
            }
        )
        night_owl_enabler = NightOwlEnabler(self._todoist_mock, self._google_calendar_mock)

        self._set_current_time(day=10, hour=23)
        night_owl_enabler.on_todoist_sync({'completed': [test_item.id]})
        self._todoist_mock.update_item.assert_not_called()

    def test_completed_non_recurring(self) -> None:
        test_item = self._create_todoist_item()
        night_owl_enabler = NightOwlEnabler(self._todoist_mock, self._google_calendar_mock)

        self._set_current_time(day=11, hour=1)
        night_owl_enabler.on_todoist_sync({'completed': [test_item.id]})
        self._todoist_mock.update_item.assert_not_called()

    def test_completed_non_every_day(self) -> None:
        test_item = self._create_todoist_item(
            due={
                'date': '2020-01-10T23:00:00',
                'string': 'every 23 hour at 23:00',
            }
        )
        night_owl_enabler = NightOwlEnabler(self._todoist_mock, self._google_calendar_mock)

        self._set_current_time(day=11, hour=1)
        night_owl_enabler.on_todoist_sync({'completed': [test_item.id]})
        self._todoist_mock.update_item.assert_not_called()

    def test_completed_after_midnight(self) -> None:
        test_item = self._create_todoist_item(
            due={
                'date': '2020-01-10T23:00:00',
                'string': 'every day at 23:00',
            }
        )
        night_owl_enabler = NightOwlEnabler(self._todoist_mock, self._google_calendar_mock)

        self._set_current_time(day=11, hour=1)
        night_owl_enabler.on_todoist_sync({'completed': [test_item.id]})
        self._todoist_mock.update_item.assert_called_once_with(
            test_item,
            due={
                'date': '2020-01-11T23:00:00',
                'string': 'every day at 23:00',
                'timezone': None,
            },
        )

    def test_completed_after_midnight_date_only(self) -> None:
        test_item = self._create_todoist_item(
            due={
                'date': '2020-01-10',
                'string': 'every day',
            }
        )
        night_owl_enabler = NightOwlEnabler(self._todoist_mock, self._google_calendar_mock)

        self._set_current_time(day=11, hour=1)
        night_owl_enabler.on_todoist_sync({'completed': [test_item.id]})
        self._todoist_mock.update_item.assert_called_once_with(
            test_item,
            due={
                'date': '2020-01-11',
                'string': 'every day',
                'timezone': None,
            },
        )

    def test_completed_after_midnight_date_overdue(self) -> None:
        test_item = self._create_todoist_item(
            due={
                'date': '2020-01-10',
                'string': 'every day',
            }
        )
        night_owl_enabler = NightOwlEnabler(self._todoist_mock, self._google_calendar_mock)

        self._set_current_time(day=14, hour=1)
        night_owl_enabler.on_todoist_sync({'completed': [test_item.id]})
        self._todoist_mock.update_item.assert_called_once_with(
            test_item,
            due={
                'date': '2020-01-14',
                'string': 'every day',
                'timezone': None,
            },
        )

    def test_completed_after_midnight_overdue(self) -> None:
        test_item = self._create_todoist_item(
            due={
                'date': '2020-01-10T23:00:00',
                'string': 'every day at 23:00',
            }
        )
        night_owl_enabler = NightOwlEnabler(self._todoist_mock, self._google_calendar_mock)

        self._set_current_time(day=15, hour=1)
        night_owl_enabler.on_todoist_sync({'completed': [test_item.id]})
        self._todoist_mock.update_item.assert_called_once_with(
            test_item,
            due={
                'date': '2020-01-15T23:00:00',
                'string': 'every day at 23:00',
                'timezone': None,
            },
        )

    def test_completed_after_midnight_timezone(self) -> None:
        test_item = self._create_todoist_item(
            due={
                'date': '2020-01-10T20:00:00Z',
                'timezone': 'Europe/Sofia',
                'string': 'every day at 23:00',
            }
        )
        night_owl_enabler = NightOwlEnabler(self._todoist_mock, self._google_calendar_mock)

        self._set_current_time(day=11, hour=1)
        night_owl_enabler.on_todoist_sync({'completed': [test_item.id]})
        self._todoist_mock.update_item.assert_called_once_with(
            test_item,
            due={
                'date': '2020-01-11T20:00:00Z',
                'string': 'every day at 23:00',
                'timezone': 'Europe/Sofia',
            },
        )
