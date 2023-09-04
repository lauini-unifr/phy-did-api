from db import db

class TopicModel(db.Model):
    __tablename__ = "topics"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    items = db.relationship("ItemModel", back_populates="topic", lazy="dynamic", cascade="all, delete")
    tags = db.relationship("TagModel", back_populates="topic", lazy="dynamic")