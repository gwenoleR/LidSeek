import redis
from flask import Flask, render_template
from config.settings import Config
from database import Database
from services.musicbrainz import MusicBrainzService
from services.download_manager import DownloadManager
from routes.album_routes import album_routes, init_routes as init_album_routes
from routes.download_routes import download_routes, init_routes as init_download_routes

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
    download_manager = DownloadManager(db)

    # Enregistrement des routes
    app.register_blueprint(init_album_routes(musicbrainz_service, download_manager))
    app.register_blueprint(init_download_routes(musicbrainz_service, download_manager))

    @app.route('/')
    def index():
        return render_template('index.html')

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(host=Config.FLASK_HOST, port=Config.FLASK_PORT, debug=True)
