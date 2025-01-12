import logging
import re
from datetime import datetime
from typing import Any

from dateutil.tz import gettz

from tools_for_todoist.models.google_sheets import GoogleSheets
from tools_for_todoist.models.todoist import Todoist
from tools_for_todoist.storage import get_storage

INCENTIVE_GOOGLE_SHEETS_CREDENTIALS = "incentive.google_sheets.credentials"
INCENTIVE_GOOGLE_SHEETS_TOKEN = "incentive.google_sheets.token"
INCENTIVE_GOOGLE_SHEETS_SHEET_ID = "incentive.google_sheets.sheet_id"
INCENTIVE_LABEL_NAME_REGEX = "incentive.label_name_regex"

logger = logging.getLogger(__name__)


class IncentivePoints:
    def __init__(self, todoist: Todoist, timezone: str) -> None:
        self._todoist = todoist
        self._google_sheets = GoogleSheets(
            credentials_key=INCENTIVE_GOOGLE_SHEETS_CREDENTIALS,
            token_key=INCENTIVE_GOOGLE_SHEETS_TOKEN,
            sheet_id=get_storage().get_value(INCENTIVE_GOOGLE_SHEETS_SHEET_ID),
        )
        self._points_matcher_re = re.compile(get_storage().get_value(INCENTIVE_LABEL_NAME_REGEX))
        self._timezone = timezone

    def _points_from_labels(self, labels: list[str]) -> int:
        for label in labels:
            match = self._points_matcher_re.match(label)
            if match is not None:
                return int(match.group(1))
        return 0

    def on_todoist_sync(self, sync_result: dict[str, Any]) -> bool:
        for initiator_id, item_id in sync_result["completed"]:
            item = self._todoist.get_item_by_id(item_id)
            points = self._points_from_labels(item.labels())
            if points == 0:
                logger.debug(f"IncentivePoints: Skipping {item} without incentive label")
                continue
            if initiator_id is not None and initiator_id != self._todoist.owner_id:
                logger.debug(f"IncentivePoints: Skipping {item} completed by another user")
                continue

            logger.info(f"IncentivePoints: Adding {points} points for: {item}")
            existing_rows_count = len(self._google_sheets.get_sheet_values("A:A"))
            now = datetime.now(gettz(self._timezone))
            description = item.content
            if item.has_parent():
                description = f"{item.parent().content}: {description}"
            self._google_sheets.write_to_sheet(
                f"A{existing_rows_count + 1}:C{existing_rows_count + 1}",
                [[now.isoformat(), description, points]],
            )
        return False
