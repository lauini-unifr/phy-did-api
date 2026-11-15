from db import db


class ChapterLabelModel(db.Model):
    __tablename__ = "chapter_labels"
    # Labels are not globally unique: several texts (e.g. copies of a text in
    # different series) may define the same LaTeX label.
    __table_args__ = (db.UniqueConstraint("label", "item_id"),)

    id = db.Column(db.Integer, primary_key=True)
    label = db.Column(db.String(120), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    is_chapter = db.Column(db.Boolean, nullable=False, default=False)
    item_id = db.Column(db.Integer, db.ForeignKey("items.id"), nullable=False)

    item = db.relationship("ItemModel", back_populates="chapter_labels")
