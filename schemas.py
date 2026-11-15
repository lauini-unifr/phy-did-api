from marshmallow import Schema, fields

class PlainItemSchema(Schema):
    id = fields.Int(dump_only=True)
    name = fields.Str(required=True)
    description = fields.Str()
    file_name = fields.Str()
    display_title = fields.Str(allow_none=True)
    sort_order = fields.Int()


class PlainTopicSchema(Schema):
    id = fields.Int(dump_only=True)
    name = fields.Str(required=True)
    sort_order = fields.Int()


class PlainTagSchema(Schema):
    id = fields.Int(dump_only=True)
    name = fields.Str()


class ItemUpdateSchema(Schema):
    name = fields.Str()
    description = fields.Str()
    file_name = fields.Str()
    topic_id = fields.Int()
    display_title = fields.Str(allow_none=True)
    sort_order = fields.Int()


class TopicUpdateSchema(Schema):
    name = fields.Str()
    sort_order = fields.Int()


class ItemSchema(PlainItemSchema):
    topic_id = fields.Int(required=True, load_only=True)
    topic = fields.Nested(PlainTopicSchema(), dump_only=True)
    tags = fields.List(fields.Nested(PlainTagSchema()), dump_only=True)


class TopicSchema(PlainTopicSchema):
    items = fields.List(fields.Nested(PlainItemSchema()), dump_only=True)
    tags = fields.List(fields.Nested(PlainTagSchema()), dump_only=True)

class TagSchema(PlainTagSchema):
    topic_id = fields.Int(load_only=True)
    topic = fields.Nested(PlainTopicSchema(), dump_only=True)
    items = fields.List(fields.Nested(PlainItemSchema()), dump_only=True)


class TagAndItemSchema(Schema):
    message = fields.Str()
    item = fields.Nested(ItemSchema)
    tag = fields.Nested(TagSchema)


class UserSchema(Schema):
    id = fields.Int(dump_only=True)
    username = fields.Str(required=True)
    password = fields.Str(required=True, load_only=True)
    is_approved = fields.Bool(dump_only=True)


class PendingUserSchema(Schema):
    id = fields.Int(dump_only=True)
    username = fields.Str(dump_only=True)