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
import os

from tools_for_todoist.storage.storage import LocalKeyValueStorage, PostgresKeyValueStorage

DEFAULT_STORAGE = os.path.join(os.path.dirname(__file__), 'store.json')
_storage = None


def get_storage():
    global _storage
    if _storage is not None:
        return _storage

    database_config = os.environ.get('DATABASE_URL', None)
    if database_config is not None:
        _storage = PostgresKeyValueStorage(database_config)
    else:
        _storage = LocalKeyValueStorage(os.environ.get('FILE_STORE', DEFAULT_STORAGE))

    return _storage


def reinitialize_storage():
    global _storage
    if _storage is not None:
        _storage.close()
        _storage = None
    return get_storage()
