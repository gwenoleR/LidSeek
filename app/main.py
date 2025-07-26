import redis
from flask import Flask, render_template
from config.settings import Config
from database import Database
from services.musicbrainz import MusicBrainzService
from services.download_manager import DownloadManager
from services.downloaders import SlskdDownloader
from services.library import LibraryService
from routes.album_routes import album_routes, init_routes as init_album_routes
from routes.download_routes import download_routes, init_routes as init_download_routes
from routes.library_routes import library_routes, init_routes as init_library_routes

def create_app():
    app = Flask(__name__)
    
    # Initialisation des services
    redis_client = redis.Redis(
        host=Config.REDIS_HOST,
        port=Config.REDIS_PORT,
        decode_responses=True
    )
    
    db = Database()
    musicbrainz_service = MusicBrainzService(
        Config.USER_AGENT,
        redis_client,
        Config.CACHE_EXPIRATION
    )
    
    # Initialisation du DownloadManager avec Slskd
    download_manager = DownloadManager(db)
    slskd_downloader = SlskdDownloader()
    slskd_downloader.configure(
        host_url=Config.SLSKD_HOST,
        api_key=Config.SLSKD_API_KEY,
        url_base=Config.SLSKD_URL_BASE
    )
    slskd_downloader.allowed_filetypes = Config.SLSKD_ALLOWED_FILETYPES
    slskd_downloader.ignored_users = Config.SLSKD_IGNORED_USERS
    slskd_downloader.minimum_match_ratio = Config.SLSKD_MIN_MATCH_RATIO
    
    download_manager.configure_downloader(slskd_downloader)
    download_manager.download_dir = Config.SLSKD_DOWNLOAD_DIR
    
    library_service = LibraryService(db)

    # Enregistrement des routes
    app.register_blueprint(init_album_routes(musicbrainz_service, download_manager))
    app.register_blueprint(init_download_routes(musicbrainz_service, download_manager))
    app.register_blueprint(init_library_routes(library_service))

    @app.route('/')
    def index():
        return render_template('index.html')

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(host=Config.FLASK_HOST, port=Config.FLASK_PORT, debug=True)
