import os

from flask import request,send_file
from flask.views import MethodView
from flask_smorest import Blueprint, abort
from flask_jwt_extended import jwt_required
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.utils import secure_filename

from db import db
from models import ItemModel
from schemas import ItemSchema, ItemUpdateSchema

import subprocess
import tempfile
from pathlib import Path
import shutil
import os

blp = Blueprint("items", __name__, description="Operations on items")

@blp.route("/item/<int:item_id>")
class Item(MethodView):
    @blp.response(200, ItemSchema)
    def get(self, item_id):
        item = ItemModel.query.get_or_404(item_id)
        return item

    @jwt_required()
    def delete(self, item_id):
        item = ItemModel.query.get_or_404(item_id)
        db.session.delete(item)
        db.session.commit()
        return {"message": "Item deleted"}

    @jwt_required()
    @blp.arguments(ItemUpdateSchema)
    @blp.response(200, ItemSchema)
    def put(self, item_data, item_id):
        item = ItemModel.query.get(item_id)
        if item:
            item.description = item_data["description"]
            item.name = item_data["name"]
            item.file_name = item_data["file_name"]
        else:
            item = ItemModel(id=item_id, **item_data)
        
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
        item = ItemModel(**item_data)

        try:
            db.session.add(item)
            db.session.commit()
        except SQLAlchemyError:
            abort(500, message="An error occurred while inserting the item.")

        return item
    



@blp.route('/upload', methods=['POST'])
def upload_file():
    if "item_id" in request.form:
        item = ItemModel.query.get_or_404(request.form["item_id"])
        if 'file' in request.files:
            file = request.files['file']
            secure_name = secure_filename(file.filename)
            file.save(os.path.join("./upload_dir/attachment", secure_name))
            item.file_name = secure_name

            try:
                db.session.add(item)
                db.session.commit()
            except SQLAlchemyError:
                abort(500, message="An error occurred while inserting the item.")

            return {"message": "File successfully uploaded."}
    
    abort(401, message="No file in request.")



