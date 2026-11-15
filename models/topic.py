from db import db

class TopicModel(db.Model):
    __tablename__ = "topics"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    items = db.relationship("ItemModel", back_populates="topic", lazy="dynamic", cascade="all, delete",
                            order_by="(ItemModel.sort_order, ItemModel.name)")
    tags = db.relationship("TagModel", back_populates="topic", lazy="dynamic")