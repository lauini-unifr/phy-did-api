import os

TOPIC_FOLDER_NAMES = {
    "Klimaphysik": "Skript_Klima",
    "Klassische Systeme": "Skript_klass",
    "Quantenphysik": "Skript_QM",
    "Thermodynamik": "Skript_Thermo",
    "QBus": "Skript_QBus",
}


def get_topic_folder_name(topic_name, item_name):
    """Map a topic (and, for Relativitätstheorie, the item name) to the
    on-disk folder its LaTeX sources live in under upload_dir/attachment/.
    Returns None if the topic has no known folder mapping."""
    if topic_name == "Relativitätstheorie":
        return "Skript_ART" if "ART" in item_name else "Skript_SRT"
    return TOPIC_FOLDER_NAMES.get(topic_name)


def is_known_topic_name(topic_name):
    """Whether a topic name has a folder mapping at all (regardless of item name)."""
    return topic_name == "Relativitätstheorie" or topic_name in TOPIC_FOLDER_NAMES


def remove_item_attachment(item):
    """Delete an item's on-disk attachment, if any, and its now-empty item
    folder. Safe to call on items without a known folder mapping or without
    an attachment at all."""
    if not item.file_name:
        return
    folder = get_topic_folder_name(item.topic.name, item.name)
    if not folder:
        return
    item_dir = os.path.join("./upload_dir/attachment", folder, item.name)
    file_path = os.path.join(item_dir, item.file_name)
    if os.path.exists(file_path):
        os.remove(file_path)
    try:
        os.rmdir(item_dir)
    except OSError:
        pass
