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

import psycopg2
import json
import logging
import os

from abc import ABCMeta, abstractmethod

logger = logging.getLogger(__name__)


class KeyValueStorage(metaclass=ABCMeta):
    @abstractmethod
    def get_value(self, key):
        pass

    @abstractmethod
    def set_value(self, key, value):
        pass

    @abstractmethod
    def close(self):
        pass


class LocalKeyValueStorage(KeyValueStorage):
    def __init__(self, store_path):
        self.store_path = store_path
        self.store = {}
        if os.path.exists(store_path):
            with open(store_path, 'r') as file:
                self.store = json.load(file)

    def _save_file(self):
        with open(self.store_path, 'w') as file:
            json.dump(self.store, file, indent=2)

    def get_value(self, key):
        return self.store.get(key)

    def set_value(self, key, value):
        self.store[key] = value
        self._save_file()

    def unset_key(self, key):
        self.store.pop(key, None)
        self._save_file()

    def close(self):
        pass


POSTGRES_SINGLE_VALUE = 'postgres_single_value'


class PostgresKeyValueStorage(KeyValueStorage):
    def __init__(self, database_config):
        self.connection = psycopg2.connect(database_config)
        initialize_sql = '''
        CREATE TABLE if not exists key_value_store (
            key varchar PRIMARY KEY,
            value json
        )
        '''

        self.cursor = self.connection.cursor()
        try:
            self.cursor.execute(initialize_sql)
        except Exception as e:
            logger.exception('Error while initializing database', e)
            raise
        finally:
            self.connection.commit()

    def get_value(self, key):
        try:
            select_sql = '''
                SELECT value from key_value_store
                WHERE key = %s
                LIMIT 1
            '''
            self.cursor.execute(select_sql, (key, ))
            value = self.cursor.fetchone()
            return value[0] if value is not None else None
        except Exception as e:
            logger.exception(f'Error while getting {key}', e)
            raise
        finally:
            self.connection.commit()

    def set_value(self, key, value):
        try:
            insert_sql = '''
                INSERT INTO key_value_store (key, value)
                VALUES (%s, %s)
                ON CONFLICT (key) DO UPDATE SET
                value = EXCLUDED.value;
            '''
            self.cursor.execute(insert_sql, (key, json.dumps(value)))
        except Exception as e:
            logger.exception(f'Error while saving {key} as {value}', e)
            raise
        finally:
            self.connection.commit()

    def unset_value(self, key):
        try:
            delete_sql = '''
                DELETE FROM key_value_store
                WHERE key = %s
            '''
            self.cursor.execute(delete_sql, (key,))
        except Exception as e:
            logger.exception(f'Error while deleting {key}', e)
            raise
        finally:
            self.connection.commit()

    def close(self):
        self.cursor.close()
        self.connection.close()
