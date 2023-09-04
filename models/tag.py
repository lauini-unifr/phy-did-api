from db import db

class TagModel(db.Model):
    __tablename__ = "tags"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    topic_id = db.Column(db.Integer, db.ForeignKey("topics.id"), nullable=False)

    topic = db.relationship("TopicModel", back_populates="tags")
    items = db.relationship("ItemModel", back_populates="tags", secondary="item_tags")
    