import os

import redis

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

DEBUG = os.getenv('DEBUG', False)
SLR_LOCAL_ENV = os.environ.get('SLR_LOCAL_ENV')

# APP
APP_URL = os.environ.get('SLR_APP_URL', 'http://localhost:8080')
API_PREFIX = 'api'
APP_PRODUCTION = not SLR_LOCAL_ENV

# DB
SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URI')
SQLALCHEMY_POOL_SIZE = os.getenv('DATABASE_POOL_SIZE', 100)

# We can use signals to track changes to models (e.g Logs with username)
SQLALCHEMY_TRACK_MODIFICATIONS = os.getenv('DATABASE_TRACK_MODIFICATIONS', True)

# CACHE
CACHE_TYPE = os.getenv('SLR_CACHE_TYPE', 'simple')  # RedisCache
CACHE_KEY_PREFIX = 'SLR_'
CACHE_THRESHOLD = os.getenv('SLR_CACHE_THRESHOLD', 4096)
CACHE_REDIS_HOST = os.getenv('SLR_CACHE_REDIS_HOST', 'slr-redis')
CACHE_REDIS_PORT = os.getenv('SLR_CACHE_REDIS_PORT', 6379)

# SESSION
APP_SESSION_SECRET = os.getenv('SLR_APP_SESSION_SECRET', 'SWNUCOVM3Q7OJH3T')
SESSION_KEY_PREFIX = 'SESSION_'
SESSION_COOKIE_NAME = 'slr-session'
SESSION_COOKIE_SECURE = os.getenv('SLR_COOKIE_SECURE', False)
SESSION_PERMANENT = False
SESSION_TYPE = os.getenv('SLR_SESSION_TYPE', 'filesystem')  # redis
SESSION_FILE_DIR = '/tmp/slo-session'
SESSION_REDIS_HOST = os.getenv('SLR_SESSION_REDIS_HOST', '127.0.0.1')
SESSION_REDIS_PORT = os.getenv('SLR_SESSION_REDIS_PORT', 6379)
SESSION_REDIS = redis.Redis(host=SESSION_REDIS_HOST, port=SESSION_REDIS_PORT)

# AUTH & OAUTH2
API_AUTHORIZATION = os.getenv('SLR_API_AUTHORIZATION', '')

OAUTH2_ENABLED = os.getenv('OAUTH2_ENABLED', False) or APP_PRODUCTION
PRESHARED_TOKEN = os.getenv('SLR_PRESHARED_TOKEN')
ACCESS_TOKEN_URL = os.getenv('ACCESS_TOKEN_URL', '')
CREDENTIALS_DIR = os.getenv('CREDENTIALS_DIR', '')
AUTHORIZE_URL = os.getenv('AUTHORIZE_URL', '')

ADMINS = os.getenv('SLR_ADMINS', '').split(',')

# COMMUNITY AUTH
API_AUTHORIZATION_COMMUNITY_URL = os.getenv('SLR_API_AUTHORIZATION_COMMUNITY_URL', '')
API_AUTHORIZATION_COMMUNITY_PREFIX = os.getenv(
    'SLR_API_AUTHORIZATION_COMMUNITY_PREFIX', 'Functions/Communities/'
)

API_DEFAULT_PAGE_SIZE = os.getenv('SLR_API_DEFAULT_PAGE_SIZE', 100)

# THROTTLE
RATELIMIT_DEFAULT = os.getenv('SLR_RATE_LIMIT', '20/second;200/minute')
RATELIMIT_STORAGE_URL = os.getenv('SLR_RATE_LIMIT_STORAGE', 'memory://')
RATELIMIT_HEADERS_ENABLED = True

# ZMON
KAIROSDB_URL = os.getenv('KAIROSDB_URL')
KAIROS_QUERY_LIMIT = os.getenv('KAIROSDB_QUERY_LIMIT', 10000)

# UPDATER / RETENTION
RUN_UPDATER = os.environ.get('SLR_RUN_UPDATER', False)
MAX_QUERY_TIME_SLICE = os.getenv('SLR_MAX_QUERY_TIME_SLICE', 1440)
MAX_RETENTION_DAYS = os.getenv('MAX_RETENTION_DAYS', 100)

# Careful with high concurrency, as we might hit rate limits on ZMON
UPDATER_CONCURRENCY = os.getenv('SLR_UPDATER_CONCURRENCY', 20)
UPDATER_INTERVAL = os.getenv('SLR_UPDATER_INTERVAL', 600)

# OPENTRACING
OPENTRACING_TRACER = os.getenv('OPENTRACING_TRACER')

# LIGHTSTEP
LIGHTSTEP_API_KEY = os.getenv("LIGHTSTEP_API_KEY")
LIGHTSTEP_RESOLUTION_SECONDS = 600
