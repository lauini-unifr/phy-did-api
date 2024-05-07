import os
import secrets

from flask import Flask, render_template, request, redirect, jsonify, send_file
from flask_smorest import Api, abort
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from flask_executor import Executor
from flask_cors import CORS

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
import logging

from ressources.item import blp as ItemBlueprint
from ressources.topic import blp as TopicBlueprint
from ressources.tag import blp as TagBlueprint
from ressources.user import blp as UserBlueprint

CHAPTER_VARS = { ### "label" : "item_id" 
    "chap_Klima1": ["1", "Solarkonstante und Paleoklima"],
    "chap_Klima3": ["2", "Klimamodelle"],
    "chap_SI": ["3", "SI-Einheiten"],
    "chap_Kalender": ["4", "Kalendersysteme"], ### not in use
    "chap_Zeitgleichung": ["5", "Die Zeitgleichung"],
    "chap_Uhren": ["6", "Zeitmessung"],
    "chap_Gezeiten": ["7", "Die Gezeiten - Ebbe und Flut"],
    "eq_Schwerpunkt": ["7", "8 Kap. Die Gezeiten - Ebbe und Flut"],
    "tab_Tide": ["7", "1 Kap. Die Gezeiten - Ebbe und Flut"],
    "chap_Gezeiten2": ["8", r"Gezeiten und Tagesl\"ange"],
    "sec_EMWW": ["8", r"Gezeiten und Tagesl\"ange"],
    "chap_Nachthimmel": ["9", "Der Nachthimmel"],
    "chap_Kosm_Entfernung": ["10", "Die Kosmische Entfernungsleiter"],
    "chap_Landkarte": ["11", "Landkarten und der metrische Tensor"],
    "chap_QuBit": ["12", "Das QuBit"],
    "chap_Interferometer": ["13", "Interferometer"],
    "chap_BB84": ["14", "BB84 - Quantenkryptographie"],
    "chap_Quantenradierer": ["15", "Quantenradierer"],
    "chap_Grundlagen": ["16", "Grundlagen der SRT"],
    "eq_vadd": ["16", "21 des Kapitels Grundlagen der SRT"],
    "chap_Philosophie": ["17", "Philosphischer Hintergrund der SRT"],
    "chap_SpezRel": ["17", "Philosphischer Hintergrund der SRT"],
    "sec_Synch": ["17", "3 des Kapitels Philosphischer Hintergrund der SRT"],
    "chap_SRT-Effekte": ["18", "SRT – Effekte"],
    "chap_Zwilling": ["19", "Das Zwillingsparadoxon"],
    "SRT_Beschleunigung": ["20", "Beschleunigte Systeme und das Rindler-Universum"],
    "chap_Entanglement": ["21", r"Verschr\"ankung"],
    "chap_EPR": ["22", "EPR-Bell-CHSH"]
}



def create_app(db_url=None):
    app = Flask(__name__)

    CORS(app)

    app.config["PROPAGATE_EXCEPTIONS"] = True
    app.config["API_TITLE"] = "Topics REST API"
    app.config["API_VERSION"] = "vi"
    app.config["OPENAPI_VERSION"] = "3.0.3"
    app.config["OPENAPI_URL_PREFIX"] = "/"
    app.config["OPENAPI_SWAGGER_UI_PATH"] = "/swagger-ui"
    app.config["OPENAPI_SWAGGER_UI_URL"] = "https://cdn.jsdelivr.net/npm/swagger-ui-dist/"
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url or os.getenv("DATABASE_URL", "sqlite:///data.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Logging
    logging.basicConfig(filename='app.log', level=logging.INFO)
    app.logger.addHandler(logging.StreamHandler())

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


    def generate_pdf(item_ids):
        if item_ids:
            try:
                texdoc = []  # a list of string representing the latex document in python
                begin = r'\documentclass[german,10pt]{book}      \input{preambel.tex}         \begin{document}  \setcounter{chapter}{0}'
                texdoc.append(begin)

                tmpdirname = tempfile.mkdtemp(prefix="pre_",suffix="_suf")
                os.makedirs(tmpdirname + '/Bilder')

                # Deckblatt
                copy_files("upload_dir/attachment/Deckblatt/Bilder", tmpdirname + '/Bilder')
                with open("upload_dir/attachment/Deckblatt/deckblatt_clean.tex") as f_in:
                    for line in f_in:
                        texdoc.append(line)

                # Table of contents
                table_of_contents = r'{\let\cleardoublepage\clearpage\tableofcontents}'
                texdoc.append(table_of_contents)

                for item_id in item_ids:
                    item = ItemModel.query.get_or_404(int(item_id))
                    if item.file_name:

                        if item.topic.name == "Klimaphysik":
                            topic_folder_name = "Skript_Klima"
                        elif item.topic.name == "Klassische Systeme":
                            topic_folder_name = "Skript_klass"
                        elif item.topic.name == "Quantenphysik":
                            topic_folder_name = "Skript_QM"
                        elif item.topic.name == "Relativitätstheorie":
                            topic_folder_name = "Skript_SRT"    
                        elif item.topic.name == "Thermodynamik":
                            topic_folder_name = "Skript_Thermo"  

                        src = "upload_dir/attachment/" + topic_folder_name + "/" + item.name + "/" + item.file_name
                        with open(src) as f_in:
                            for line in f_in:
                                if '\documentclass[german,10pt]' not in line and '\end{document}' not in line:
                                    if 'ref' in line:
                                        hit = False
                                        for chapter, index in CHAPTER_VARS.items():
                                            if chapter in line and index[0] not in item_ids:
                                                hit = True
                                                newline = line.replace('ref','href')
                                                newline = newline.replace(chapter+'}','https://physikdidaktik.uni-freiburg.de/kurztexte/}{'+index[1]+'}')
                                                texdoc.append(newline)
                                        if not hit:
                                            texdoc.append(line)
                                    else:
                                        texdoc.append(line)

                        src_pic = "upload_dir/attachment/Bilder"
                        
                        #copy_files(src, tmpdirname)
                        copy_files("upload_dir/attachment/Preambel", tmpdirname)
                        copy_files(src_pic, tmpdirname + '/Bilder')

                        if item.name in ["Klass_03_Zeitgleichung",
                                        "Klass_05_Uhren",
                                        "Klass_08_Nachthimmel",
                                        "Klass_10_Landkarten",
                                        "QM_01_QuBit",
                                        "SRT_03_Kette",
                                        "Thermo_01_Prozess",
                                        "Thermo_03_Entropie"]:
                            copy_files("upload_dir/attachment/" + topic_folder_name + "/Bilder", tmpdirname + '/Bilder') 
                    
                texdoc.append('\printindex\n\end{document}')

                # write back the new document
                with open(os.path.join(tmpdirname, 'final.tex')  , 'w') as f_out:
                    for i in range(len(texdoc)):
                        f_out.write(texdoc[i])


                output = subprocess.call(["pdflatex", "-output-directory", tmpdirname, "-jobname", 'file', 'final.tex'])
                output = subprocess.call(["pdflatex", "-output-directory", tmpdirname, "-jobname", 'file', 'final.tex'])

                path = Path(tmpdirname + "/file.pdf").resolve()
            except Exception as e:
                    app.logger.error(f"Fehler in some_route: {str(e)}")
                    abort(500, message="An error occurred while compiling the pdf.")

            return path
                    
            #except:
            # abort(500, message="An error occurred while compiling the pdf.")

        
        else:
            abort(401, message="No ids in request.")
    

    @app.route('/download/<item_ids_as_str>', methods=['GET'])
    def download_files(item_ids_as_str):
        item_ids = item_ids_as_str.split("+")
        
        executor.submit_stored('pdf_ready', generate_pdf, item_ids)

        time.sleep(5)

        return redirect("/get-pdf")


        #abort(401, message="No file in request.")


    @app.route('/get-pdf')
    def get_result():
        while not executor.futures.done('pdf_ready'):
            time.sleep(5)
        future = executor.futures.pop('pdf_ready')
        response = send_file(future.result(), as_attachment=True, mimetype="application/pdf")
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response


    if __name__ == "__main__":
        app.run(host='0.0.0.0')

    return app
