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

from googleapiclient.discovery import build

from tools_for_todoist.models.google_auth import GoogleAuth
from tools_for_todoist.utils import retry_flaky_function

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


class GoogleSheets:
    def __init__(self, credentials_key: str, token_key: str, sheet_id: str):
        self._recreate_api()
        self._credentials_key = credentials_key
        self._token_key = token_key
        self._sheet_id = sheet_id

    def _recreate_api(self):
        token = GoogleAuth(
            storage_credentials_key=self._credentials_key,
            storage_token_key=self._token_key,
            scopes=SCOPES,
        ).do_auth()
        self.api = build("sheets", "v4", credentials=token, cache_discovery=False)

    def get_sheet_values(self, range_name):
        request = (
            self.api.spreadsheets()
            .values()
            .get(
                spreadsheetId=self._sheet_id,
                range=range_name,
            )
        )
        result = retry_flaky_function(
            lambda: request.execute(),
            "get_sheet_values",
            on_failure_func=self._recreate_api,
        )
        return result.get("values", [])

    def write_to_sheet(self, range_name, values):
        request = (
            self.api.spreadsheets()
            .values()
            .update(
                spreadsheetId=self._sheet_id,
                range=range_name,
                valueInputOption="USER_ENTERED",
                body={"values": values},
            )
            .execute()
        )
        retry_flaky_function(
            lambda: request.execute(),
            "write_to_sheet",
            on_failure_func=self._recreate_api,
        )
