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
from topic_folders import get_topic_folder_name

from models import ItemModel

import tempfile
from pathlib import Path
import os
import time
import io
import logging
import uuid

from werkzeug.exceptions import HTTPException

from ressources.item import blp as ItemBlueprint
from ressources.topic import blp as TopicBlueprint
from ressources.tag import blp as TagBlueprint
from ressources.user import blp as UserBlueprint
from chapter_labels import load_label_lookup, rewrite_external_refs, sync_chapter_labels
from latex_build import (ATTACHMENT_DIR, BEGIN_DOCUMENT, BUILD_TIMEOUT, LatexError, build_pdf,
                         copy_dir_files, copy_item_assets, is_wrapper_line, read_tex)

PDF_JOB_MAX_WAIT = 2 * BUILD_TIMEOUT + 60

# deckblatt_clean.tex names Thomas Filk with his title; that line is kept for
# his texts and replaced by the actual author(s) otherwise.
COVER_AUTHOR_MARKER = "Professor Dr. Thomas Filk"
DEFAULT_AUTHOR = "Thomas Filk"


def cover_author_line(authors):
    """Replacement for the cover page author line, or None to keep it."""
    authors = sorted({a for a in authors if a})
    if not authors or authors == [DEFAULT_AUTHOR]:
        return None
    if len(authors) == 1:
        joined = authors[0]
    else:
        joined = ", ".join(authors[:-1]) + " und " + authors[-1]
    return "\\textbf{" + joined + "}\n"



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
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    file_handler = logging.FileHandler('app.log')
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)
    app.logger.setLevel(logging.INFO)

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

    @app.cli.command("sync-chapter-labels")
    def sync_chapter_labels_command():
        """Rebuild chapter_labels from every item's .tex file on disk."""
        synced = 0
        for item in ItemModel.query.order_by(ItemModel.id).all():
            if not item.file_name or not item.file_name.lower().endswith(".tex"):
                continue
            folder = get_topic_folder_name(item.topic.name, item.name)
            if not folder:
                print(f"  Übersprungen (kein Ordner-Mapping): {item.name}")
                continue
            path = os.path.join("./upload_dir/attachment", folder, item.name, item.file_name)
            if not os.path.exists(path):
                print(f"  Übersprungen (Datei fehlt): {path}")
                continue
            sync_chapter_labels(item, path)
            synced += 1
        db.session.commit()
        print(f"Labels für {synced} Texte synchronisiert.")

    def generate_pdf(item_ids):
        label_lookup = load_label_lookup()
        chapter_info = {}
        multiple_authors = False
        chapter_starts = []

        texdoc = [BEGIN_DOCUMENT + "\n"]
        tmpdirname = tempfile.mkdtemp(prefix="pre_", suffix="_suf")
        os.makedirs(os.path.join(tmpdirname, "Bilder"))

        def chapter_source(item):
            topic_folder_name = get_topic_folder_name(item.topic.name, item.name)
            if not topic_folder_name:
                raise ValueError(f"No folder mapping known for topic '{item.topic.name}'.")
            return topic_folder_name, os.path.join(ATTACHMENT_DIR, topic_folder_name, item.name, item.file_name)

        if len(item_ids) > 1:
            # Pre-scan every chapter's title/author so the cover page and
            # table of contents can be adapted if more than one author is involved.
            for item_id in item_ids:
                item = ItemModel.query.get_or_404(int(item_id))
                if not item.file_name:
                    continue
                _, src = chapter_source(item)
                title, author = None, None
                with io.StringIO(read_tex(src)) as f_in:
                    for line in f_in:
                        if "\\chapter{" in line and title is None:
                            title = line.split("{")[1].split("}")[0]
                        if "\\info{" in line and author is None:
                            author = line.split("{")[1].split("}")[0]
                chapter_info[item_id] = {"title": title, "author": author}

            authors = [info["author"] for info in chapter_info.values()]
            multiple_authors = len({a for a in authors if a}) > 1
            author_line = cover_author_line(authors)

            # Deckblatt
            copy_dir_files(os.path.join(ATTACHMENT_DIR, "Deckblatt", "Bilder"), os.path.join(tmpdirname, "Bilder"))
            with io.StringIO(read_tex(os.path.join(ATTACHMENT_DIR, "Deckblatt", "deckblatt_clean.tex"))) as f_in:
                for line in f_in:
                    if author_line and COVER_AUTHOR_MARKER in line:
                        texdoc.append(author_line)
                    else:
                        texdoc.append(line)

            # Table of contents
            texdoc.append(r'{\let\cleardoublepage\clearpage\tableofcontents}')

        for item_id in item_ids:
            item = ItemModel.query.get_or_404(int(item_id))
            if not item.file_name:
                continue
            topic_folder_name, src = chapter_source(item)

            if len(item_ids) == 1:
                date = False
                author = None
                with io.StringIO(read_tex(src)) as f_in:
                    for line in f_in:
                        if "\\chapter{" in line:
                            title = line.split("{")[1].split("}")[0]
                        if "\\info{" in line:
                            date = line.split("}{")[1].split("}")[0]
                            author = author or line.split("{")[1].split("}")[0]
                author_line = cover_author_line([author])

                # Deckblatt
                copy_dir_files(os.path.join(ATTACHMENT_DIR, "Deckblatt", "Bilder"), os.path.join(tmpdirname, "Bilder"))
                with io.StringIO(read_tex(os.path.join(ATTACHMENT_DIR, "Deckblatt", "deckblatt_clean.tex"))) as f_in:
                    for line in f_in:
                        if "today" in line and date:
                            texdoc.append(date)
                        elif "Kapitel" in line:
                            texdoc.append(r"\textbf{"+title+r"} \\")
                        elif author_line and COVER_AUTHOR_MARKER in line:
                            texdoc.append(author_line)
                        else:
                            texdoc.append(line)

                # Table of contents
                texdoc.append(r'{\let\cleardoublepage\clearpage\tableofcontents}')

            chapter_starts.append(("".join(texdoc).count("\n") + 1, item.name))
            with io.StringIO(read_tex(src)) as f_in:
                for line in f_in:
                    if is_wrapper_line(line):
                        continue
                    chapter_author = chapter_info.get(item_id, {}).get("author") if multiple_authors else None
                    if chapter_author and "\\chapter{" in line:
                        chapter_title = chapter_info[item_id]["title"] or line.split("{")[1].split("}")[0]
                        texdoc.append("\\chapter[" + chapter_title + " - " + chapter_author + "]{" + chapter_title + "}\n")
                    elif 'ref' in line:
                        texdoc.append(rewrite_external_refs(line, label_lookup, item_ids))
                    else:
                        texdoc.append(line)

            copy_item_assets(tmpdirname, item.name, topic_folder_name)

        texdoc.append("\n\\printindex\n\\end{document}\n")
        with open(os.path.join(tmpdirname, 'final.tex'), 'w', encoding='utf-8') as f_out:
            f_out.write("".join(texdoc))

        pdf_path, errors = build_pdf(tmpdirname, chapter_starts)
        if errors:
            app.logger.warning(f"PDF für {item_ids} mit LaTeX-Fehlern erzeugt: {errors}")
        return Path(pdf_path).resolve()

    def run_pdf_job(item_ids):
        # Runs in the executor thread; turn every failure into a clean HTTP error
        # so the waiting /get-pdf request always gets an answer.
        try:
            return generate_pdf(item_ids)
        except LatexError as e:
            app.logger.error(f"LaTeX-Fehler beim PDF-Export {item_ids}: {e.errors}")
            message = "PDF konnte nicht erzeugt werden:\n" + "\n".join(e.errors)
        except HTTPException:
            raise
        except Exception as e:
            app.logger.exception(f"Fehler beim PDF-Export {item_ids}: {e}")
            message = "Beim Erzeugen des PDFs ist ein Fehler aufgetreten."
        abort(500, message=message)

    @app.route('/download/<item_ids_as_str>', methods=['GET'])
    def download_files(item_ids_as_str):
        item_ids = [i for i in item_ids_as_str.split("+") if i]
        if not item_ids:
            abort(400, message="No ids in request.")
        job_id = uuid.uuid4().hex
        executor.submit_stored(job_id, run_pdf_job, item_ids)
        return redirect(f"/get-pdf/{job_id}")

    @app.route('/get-pdf/<job_id>')
    def get_result(job_id):
        # FutureCollection.done() returns None for unknown keys (`in` checks values, not keys).
        if executor.futures.done(job_id) is None:
            abort(404, message="Unknown or expired PDF job.")
        deadline = time.monotonic() + PDF_JOB_MAX_WAIT
        try:
            while not executor.futures.done(job_id):
                if time.monotonic() > deadline:
                    abort(504, message="Die PDF-Erzeugung hat zu lange gedauert.")
                time.sleep(0.5)
            pdf_path = executor.futures.result(job_id)
        finally:
            executor.futures.pop(job_id)
        response = send_file(pdf_path, as_attachment=True, mimetype="application/pdf")
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response


    if __name__ == "__main__":
        app.run(host='0.0.0.0')

    return app
