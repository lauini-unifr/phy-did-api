import os
import app

from flask import request,send_file
from flask.views import MethodView
from flask_smorest import Blueprint, abort
from flask_jwt_extended import jwt_required
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.utils import secure_filename

from db import db
from models import ItemModel
from schemas import ItemSchema, ItemUpdateSchema

## TODO remove to own class
from pylatex import Document
from pylatex.utils import NoEscape
from pdflatex import PDFLaTeX
from latexcompiler import LC

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


def compile(path):
    feedback = LC.compile_document(tex_engine = 'lualatex',
                        bib_engine = 'biber', # Value is not necessary
                        no_bib = True, path=path, # Provide the full path to the file!
                        folder_name = '.aux_files')
    print(feedback)

def copy_files(src, trg):
    files=os.listdir(src)
 
    # iterating over all the files in
    # the source directory
    for fname in files:
        
        # copying the files to the
        # destination directory
        shutil.copy2(os.path.join(src,fname), trg)

@blp.route('/download/<int:item_id>', methods=['GET'])
def download_files(item_id):

    item = ItemModel.query.get_or_404(item_id)
    if item.file_name:
        tmpdirname = tempfile.mkdtemp(prefix="pre_",suffix="_suf")

        src = "C:/Users/Nils/Desktop/Scripts/Uni Freiburg/RestApiFlask/upload_dir/attachment/Skript_Klima"
        src_pic = "C:/Users/Nils/Desktop/Scripts/Uni Freiburg/RestApiFlask/upload_dir/attachment/Bilder"
        os.makedirs(tmpdirname + '\Bilder')
        copy_files(src, tmpdirname)
        copy_files(src_pic, tmpdirname + '\Bilder')

        output = subprocess.call(["pdflatex", "-output-directory", tmpdirname, "-jobname", 'file', item.file_name])

        path = Path(tmpdirname + "/file.pdf").resolve()

        

        #compile(path)

        #try:
        #with open(path, 'r') as file:
        #     tex= file.read()

        # doc = Document('basic')
        # doc.append(NoEscape(tex))
        # doc.generate_pdf(clean_tex=False)
        #except:
        # abort(500, message="An error occurred while compiling the pdf.")

        return send_file(path, as_attachment=True)

    
    abort(401, message="No file in request.")

