import os
import secrets

from flask import Flask, render_template, request, redirect, jsonify, send_file
from flask_smorest import Api
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from flask_executor import Executor

from db import db
from sqlalchemy_file.storage import StorageManager
from libcloud.storage.drivers.local import LocalStorageDriver
from blocklist import BLOCKLIST

from models import ItemModel

import subprocess
import tempfile
from pathlib import Path
import shutil
import os
import time

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

    executor = Executor(app)

    @app.route('/')
    def home():
        return render_template('index.html')

    def copy_files(src, trg):
        files=os.listdir(src)

        # iterating over all the files in
        # the source directory
        for fname in files:
            
            # copying the files to the
            # destination directory
            shutil.copy2(os.path.join(src,fname), trg)

    def generate_pdf(item_id):
        item = ItemModel.query.get_or_404(item_id)
        if item.file_name:
            tmpdirname = tempfile.mkdtemp(prefix="pre_",suffix="_suf")

            if item.topic.name == "Klimaphysik":
                topic_folder_name = "Skript_Klima"
            elif item.topic.name == "Klassische Systeme":
                topic_folder_name = "Skript_klass"
            elif item.topic.name == "Quantenphysik":
                topic_folder_name = "Skript_QM"
            elif item.topic.name == "Relativitätstheorie":
                topic_folder_name = "Skript_SRT"    

            src = "upload_dir/attachment/" + topic_folder_name + "/" + item.name
            src_pic = "upload_dir/attachment/Bilder"
            os.makedirs(tmpdirname + '/Bilder')
            copy_files(src, tmpdirname)
            copy_files("upload_dir/attachment/Preambel", tmpdirname)
            copy_files(src_pic, tmpdirname + '/Bilder')

            if item.name in ["Klass_03_Zeitgleichung",
                                "Klass_05_Uhren",
                                "Klass_08_Nachthimmel",
                                "Klass_10_Landkarten",
                                "QM_01_QuBit",
                                "SRT_03_Kette"]:
                copy_files("upload_dir/attachment/" + topic_folder_name + "/Bilder", tmpdirname + '/Bilder')


        output = subprocess.run(["pdflatex", "-output-directory", tmpdirname, "-jobname", 'file', item.file_name])
        output = subprocess.run(["pdflatex", "-output-directory", tmpdirname, "-jobname", 'file', item.file_name])

        path = Path(tmpdirname + "/file.pdf").resolve()

        return path

    @app.route('/download', methods=['GET'])
    def download_files():
        item_id = 1

        
         

        executor.submit_stored('pdf_ready', generate_pdf, item_id)

    
        #except:
        # abort(500, message="An error occurred while compiling the pdf.")


            # output = subprocess.run(["pdflatex", "-output-directory", tmpdirname, "-jobname", 'file', item.file_name])
            # output = subprocess.run(["pdflatex", "-output-directory", tmpdirname, "-jobname", 'file', item.file_name])

            # path = Path(tmpdirname + "/file.pdf").resolve()

            
            #except:
            # abort(500, message="An error occurred while compiling the pdf.")
        time.sleep(5)

        return redirect("/get-pdf")


        #abort(401, message="No file in request.")


    @app.route('/get-pdf')
    def get_result():
        while not executor.futures.done('pdf_ready'):
            time.sleep(5)
        future = executor.futures.pop('pdf_ready')
        return send_file(future.result(), as_attachment=True, mimetype="application/pdf")


    if __name__ == "__main__":
        app.run(host='0.0.0.0')

    return app
