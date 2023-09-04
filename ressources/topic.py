import uuid
from flask import request
from flask.views import MethodView
from flask_smorest import Blueprint, abort

from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from db import db
from models import TopicModel
from schemas import TopicSchema, TopicUpdateSchema

blp = Blueprint("topics", __name__, description="Operations on topics")

@blp.route("/topic/<int:topic_id>")
class Topic(MethodView):
    @blp.response(200, TopicSchema)
    def get(self, topic_id):
        topic = TopicModel.query.get_or_404(topic_id)
        return topic

    def delete(self, topic_id):
        topic = TopicModel.query.get_or_404(topic_id)
        db.session.delete(topic)
        db.session.commit()
        return {"message": "Topic deleted"}

    @blp.arguments(TopicUpdateSchema)
    @blp.response(200, TopicSchema)
    def put(self, topic_data, topic_id):
        topic = TopicModel.query.get(topic_id)
        if topic:
            topic.name = topic_data["name"]
        else:
            topic = TopicModel(id=topic_id, **topic_data)
        
        db.session.add(topic)
        db.session.commit()
        return topic
        

@blp.route("/topic")
class TopicList(MethodView):
    @blp.response(200, TopicSchema(many=True))
    def get(self):
        return TopicModel.query.all()
    
    @blp.arguments(TopicSchema)
    @blp.response(201, TopicSchema)
    def post(self, topic_data):
        topic = TopicModel(**topic_data)
        try:
            db.session.add(topic)
            db.session.commit()
        except IntegrityError:
            abort(400, message="A topic with that name already exists.")
        except SQLAlchemyError:
            abort(500, message="An error occured creating the topic.")

        return topic