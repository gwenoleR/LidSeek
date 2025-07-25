import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    USER_AGENT = f"{os.getenv('USER_AGENT_NAME')}/{os.getenv('USER_AGENT_VERSION')} ({os.getenv('USER_AGENT_EMAIL')})"
    CACHE_EXPIRATION = 24 * 60 * 60  # 24 heures en secondes
    REDIS_HOST = 'redis'
    REDIS_PORT = 6379
    FLASK_PORT = 8081
    FLASK_HOST = '0.0.0.0'