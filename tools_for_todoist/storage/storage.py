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

import json
import logging
import os

import psycopg2

logger = logging.getLogger(__name__)


class KeyValueStorage:
    def __init__(self):
        self.store = {}

    def get_value(self, key, default=None):
        return self.store.get(key, default)

    def set_value(self, key, value):
        self.store[key] = value

    def unset_key(self, key):
        self.store.pop(key, None)

    def close(self):
        pass


class LocalKeyValueStorage(KeyValueStorage):
    def __init__(self, store_path):
        super().__init__()
        self.store_path = store_path
        if os.path.exists(store_path):
            with open(store_path, 'r') as file:
                self.store = json.load(file)

    def set_value(self, key, value):
        super().set_value(key, value)
        self._save_file()

    def unset_key(self, key):
        super().unset_key(key)
        self._save_file()

    def _save_file(self):
        with open(self.store_path, 'w') as file:
            json.dump(self.store, file, indent=2)


class PostgresKeyValueStorage(KeyValueStorage):
    def __init__(self, database_url):
        super().__init__()
        self.connection = psycopg2.connect(database_url)
        initialize_sql = '''
        CREATE TABLE if not exists key_value_store (
            key varchar PRIMARY KEY,
            value json
        )
        '''
        self.cursor = self.connection.cursor()
        self._execute_sql(initialize_sql)

        self._execute_sql('SELECT * from key_value_store')
        for key, value in self.cursor.fetchall():
            self.store[key] = value

    def _execute_sql(self, sql, args=None):
        try:
            self.cursor.execute(sql, args if args is not None else ())
        except Exception as e:
            logger.exception(f'Error while executing: "{sql}" with args: {args}', exc_info=e)
            raise
        finally:
            self.connection.commit()

    def set_value(self, key, value):
        super().set_value(key, value)
        self.store[key] = value
        insert_sql = '''
            INSERT INTO key_value_store (key, value)
            VALUES (%s, %s)
            ON CONFLICT (key) DO UPDATE SET
            value = EXCLUDED.value;
        '''
        self._execute_sql(insert_sql, (key, json.dumps(value)))

    def unset_key(self, key):
        super().unset_key(key)
        delete_sql = '''
            DELETE FROM key_value_store
            WHERE key = %s
        '''
        self._execute_sql(delete_sql, (key,))

    def close(self):
        self.cursor.close()
        self.connection.close()
