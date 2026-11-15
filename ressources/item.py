import os

from flask import request,send_file
from flask.views import MethodView
from flask_smorest import Blueprint, abort
from flask_jwt_extended import jwt_required
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.utils import secure_filename

from db import db
from models import ItemModel, TopicModel
from schemas import ItemSchema, ItemUpdateSchema
from topic_folders import get_topic_folder_name, remove_item_attachment
from chapter_labels import sync_chapter_labels
from latex_build import ATTACHMENT_DIR, precheck_chapter

import tempfile
from pathlib import Path
import shutil
import os

blp = Blueprint("items", __name__, description="Operations on items")


def _next_sort_order(topic_id):
    """Place new items after the existing ones of their topic."""
    current = db.session.query(db.func.max(ItemModel.sort_order)).filter(ItemModel.topic_id == topic_id).scalar()
    return (current or 0) + 10

@blp.route("/item/<int:item_id>")
class Item(MethodView):
    @blp.response(200, ItemSchema)
    def get(self, item_id):
        item = ItemModel.query.get_or_404(item_id)
        return item

    @jwt_required()
    def delete(self, item_id):
        item = ItemModel.query.get_or_404(item_id)
        remove_item_attachment(item)
        db.session.delete(item)
        db.session.commit()
        return {"message": "Item deleted"}

    @jwt_required()
    @blp.arguments(ItemUpdateSchema)
    @blp.response(200, ItemSchema)
    def put(self, item_data, item_id):
        item = ItemModel.query.get_or_404(item_id)

        new_name = item_data.get("name", item.name)
        new_topic_id = item_data.get("topic_id", item.topic_id)
        new_topic = item.topic if new_topic_id == item.topic_id else TopicModel.query.get_or_404(new_topic_id)

        if item.file_name and (new_name != item.name or new_topic_id != item.topic_id):
            old_folder = get_topic_folder_name(item.topic.name, item.name)
            new_folder = get_topic_folder_name(new_topic.name, new_name)
            if not new_folder:
                abort(400, message=f"Kein Ordner-Mapping für Thema '{new_topic.name}' bekannt.")

            if old_folder:
                old_dir = os.path.join("./upload_dir/attachment", old_folder, item.name)
                old_path = os.path.join(old_dir, item.file_name)
                if os.path.exists(old_path):
                    new_dir = os.path.join("./upload_dir/attachment", new_folder, new_name)
                    os.makedirs(new_dir, exist_ok=True)
                    shutil.move(old_path, os.path.join(new_dir, item.file_name))
                    try:
                        os.rmdir(old_dir)
                    except OSError:
                        pass

        item.name = new_name
        item.description = item_data.get("description", item.description)
        item.file_name = item_data.get("file_name", item.file_name)
        item.display_title = item_data.get("display_title", item.display_title) or None
        if new_topic_id != item.topic_id and "sort_order" not in item_data:
            item.sort_order = _next_sort_order(new_topic_id)
        item.sort_order = item_data.get("sort_order", item.sort_order)
        item.topic_id = new_topic_id

        db.session.add(item)
        db.session.commit()

        return item

@blp.route("/item")
class ItemList(MethodView):
    @blp.response(200, ItemSchema(many=True))
    def get(self):
        return ItemModel.query.all()
    
    @jwt_required(fresh=True)
    @blp.arguments(ItemSchema)
    @blp.response(201, ItemSchema)
    def post(self, item_data):
        item_data.setdefault("sort_order", _next_sort_order(item_data["topic_id"]))
        if not item_data.get("display_title"):
            item_data["display_title"] = None
        item = ItemModel(**item_data)

        try:
            db.session.add(item)
            db.session.commit()
        except SQLAlchemyError:
            abort(500, message="An error occurred while inserting the item.")

        return item
    



@blp.route('/upload', methods=['POST'])
@jwt_required()
def upload_file():
    """Upload or replace an item's .tex file. The file is compiled on its own
    first; it only replaces the current file if that check passes."""
    if "item_id" not in request.form or 'file' not in request.files:
        abort(400, message="No file in request.")

    item = ItemModel.query.get_or_404(request.form["item_id"])
    topic_folder_name = get_topic_folder_name(item.topic.name, item.name)
    if not topic_folder_name:
        abort(400, message=f"Kein Ordner-Mapping für Thema '{item.topic.name}' bekannt.")

    file = request.files['file']
    secure_name = secure_filename(file.filename)
    if not secure_name.lower().endswith(".tex"):
        abort(400, message="Es können nur .tex-Dateien als Kurztext hochgeladen werden.")

    other = ItemModel.query.filter(ItemModel.file_name == secure_name, ItemModel.id != item.id).first()
    if other:
        abort(409, message=f"Der Dateiname '{secure_name}' wird bereits vom Kurztext '{other.name}' verwendet.")

    staging_dir = tempfile.mkdtemp(prefix="upload_")
    try:
        staged_path = os.path.join(staging_dir, secure_name)
        file.save(staged_path)

        errors = precheck_chapter(staged_path, item.name, topic_folder_name)
        if errors:
            abort(422, message="Die Datei lässt sich nicht kompilieren und wurde nicht übernommen:\n" + "\n".join(errors),
                  errors={"latex": errors})

        item_dir = os.path.join(ATTACHMENT_DIR, topic_folder_name, item.name)
        os.makedirs(item_dir, exist_ok=True)
        file_path = os.path.join(item_dir, secure_name)
        old_file_name = item.file_name
        shutil.move(staged_path, file_path)
        if old_file_name and old_file_name != secure_name:
            old_path = os.path.join(item_dir, old_file_name)
            if os.path.exists(old_path):
                os.remove(old_path)
    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)

    item.file_name = secure_name
    try:
        db.session.add(item)
        sync_chapter_labels(item, file_path)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        abort(500, message="An error occurred while inserting the item.")

    replaced = old_file_name is not None
    return {"message": "Datei erfolgreich aktualisiert." if replaced else "Datei erfolgreich hochgeladen."}


ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "eps", "pdf", "svg"}


def _has_allowed_image_extension(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


@blp.route('/upload/image', methods=['POST'])
@jwt_required()
def upload_images():
    files = [f for f in request.files.getlist("images") if f.filename]
    if not files:
        abort(400, message="No images in request.")

    for file in files:
        if not _has_allowed_image_extension(file.filename):
            abort(400, message=f"Dateityp von '{file.filename}' wird nicht unterstützt.")

    bilder_dir = "./upload_dir/attachment/Bilder"
    os.makedirs(bilder_dir, exist_ok=True)

    saved_files = []
    for file in files:
        secure_name = secure_filename(file.filename)
        file.save(os.path.join(bilder_dir, secure_name))
        saved_files.append(secure_name)

    return {"message": f"{len(saved_files)} Bild(er) erfolgreich hochgeladen.", "files": saved_files}
