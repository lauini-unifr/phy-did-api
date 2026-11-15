from db import db

class ItemModel(db.Model):
    __tablename__ = "items"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=False, nullable=False)
    description = db.Column(db.String)
    file_name = db.Column(db.String, unique=True)
    display_title = db.Column(db.String(255))
    sort_order = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    topic_id = db.Column(db.Integer, db.ForeignKey("topics.id"), unique=False, nullable=False)
    topic = db.relationship("TopicModel", back_populates="items")
    tags = db.relationship("TagModel", back_populates="items", secondary="item_tags")
    chapter_labels = db.relationship("ChapterLabelModel", back_populates="item", cascade="all, delete-orphan")
    