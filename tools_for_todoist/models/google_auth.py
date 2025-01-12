import json
import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from tools_for_todoist.storage import get_storage


class GoogleAuth:
    def __init__(
        self, storage_credentials_key: str, storage_token_key: str, scopes: list[str]
    ) -> None:
        self._storage_credentials_key = storage_credentials_key
        self._storage_token_key = storage_token_key
        self._scopes = scopes

    def _save_credentials(self, token):
        get_storage().set_value(self._storage_token_key, json.loads(token.to_json()))

    def do_auth(self):
        storage = get_storage()
        token_json = storage.get_value(self._storage_token_key)
        if token_json is not None:
            token = Credentials.from_authorized_user_info(token_json)
            if token.valid:
                return token
            if token.expired and token.refresh_token:
                token.refresh(Request())
                self._save_credentials(token)
                return token
        flow = InstalledAppFlow.from_client_config(
            storage.get_value(self._storage_credentials_key), self._scopes
        )
        token = flow.run_local_server(port=int(os.environ.get("PORT", 0)))
        self._save_credentials(token)
        return token
