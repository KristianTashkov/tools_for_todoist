import os

CREDENTIALS_DIR = os.path.dirname(__file__)

CREDENTIALS_JSON_PATH = os.path.join(CREDENTIALS_DIR, 'google-calendar-credentials.json')
TOKEN_CACHE_PATH = os.path.join(CREDENTIALS_DIR, 'google-calendar-token-cache.pkl')
TODOIST_API_TOKEN_PATH = os.path.join(CREDENTIALS_DIR, 'todoist-api.token')
