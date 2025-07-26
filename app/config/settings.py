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
    
    # Configuration Slskd
    SLSKD_HOST = os.getenv('SLSKD_HOST', 'http://localhost:5030')
    SLSKD_API_KEY = os.getenv('SLSKD_API_KEY', '')
    SLSKD_URL_BASE = os.getenv('SLSKD_URL_BASE', '/')
    SLSKD_DOWNLOAD_DIR = os.getenv('SLSKD_DOWNLOAD_DIR', '/downloads')
    SLSKD_ALLOWED_FILETYPES = os.getenv('SLSKD_ALLOWED_FILETYPES', 'mp3,flac').split(',')
    SLSKD_IGNORED_USERS = os.getenv('SLSKD_IGNORED_USERS', '').split(',')
    SLSKD_MIN_MATCH_RATIO = float(os.getenv('SLSKD_MIN_MATCH_RATIO', '0.5'))