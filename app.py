import os
import secrets

from flask import Flask, render_template, request, jsonify
from flask_smorest import Api
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate

from db import db
from sqlalchemy_file.storage import StorageManager
from libcloud.storage.drivers.local import LocalStorageDriver
from blocklist import BLOCKLIST
import models

from ressources.item import blp as ItemBlueprint
from ressources.topic import blp as TopicBlueprint
from ressources.tag import blp as TagBlueprint
from ressources.user import blp as UserBlueprint


def create_app(db_url=None):
    app = Flask(__name__)

    app.config["PROPAGATE_EXCEPTIONS"] = True
    app.config["API_TITLE"] = "Topics REST API"
    app.config["API_VERSION"] = "vi"
    app.config["OPENAPI_VERSION"] = "3.0.3"
    app.config["OPENAPI_URL_PREFIX"] = "/"
    app.config["OPENAPI_SWAGGER_UI_PATH"] = "/swagger-ui"
    app.config["OPENAPI_SWAGGER_UI_URL"] = "https://cdn.jsdelivr.net/npm/swagger-ui-dist/"
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url or os.getenv("DATABASE_URL", "sqlite:///data.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    migrate = Migrate(app,db,render_as_batch=True)

    api = Api(app)

    app.config["JWT_SECRET_KEY"] = "335701585462847755842973221646135403739"
    jwt = JWTManager(app)

    @jwt.token_in_blocklist_loader
    def check_if_token_in_blocklist(jwt_header, jwt_payload):
        return jwt_payload["jti"] in BLOCKLIST

    @jwt.revoked_token_loader
    def revoked_token_callback(jwt_header, jwt_payload):
        return(
            jsonify({"message": "The token has been revoked.", "error": "token_revoked"}), 401,
        )
    
    @jwt.needs_fresh_token_loader
    def token_not_fresh_callback(jwt_header, jwt_payload):
        return(
            jsonify({"message": "The token is not fresh.", "error": "fresh_token_required"}), 401,
        )
    
    
    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return(
            jsonify({"message": "The token has expired.", "error": "token_expired"}), 401,
        )
    
    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        return(
            jsonify({"message": "Signature verification failed.", "error": "invalid_token"}), 401,
        )
    
    @jwt.unauthorized_loader
    def missing_token_callback(error):
        return(
            jsonify({"description": "Request does not contain an access token.", "error": "authorization_required"}), 401,
        )


    api.register_blueprint(ItemBlueprint)
    api.register_blueprint(TopicBlueprint)
    api.register_blueprint(TagBlueprint)
    api.register_blueprint(UserBlueprint)

    # Configure storage
    os.makedirs("./upload_dir/attachment", 0o777, exist_ok=True)
    container = LocalStorageDriver("./upload_dir").get_container("attachment")
    StorageManager.add_storage("default", container)

    app.config['UPLOAD_FOLDER'] = './upload_dir/attachment'


    return app


# @app.route('/')
# def home():
#     return render_template('index.html')




