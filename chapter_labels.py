import re

from db import db
from models import ChapterLabelModel

KURZTEXTE_URL = "https://physikdidaktik.uni-freiburg.de/kurztexte/"

CHAPTER_RE = re.compile(r"\\chapter\{([^}]*)\}")
LABEL_RE = re.compile(r"\\label\{([^}]*)\}")
REF_RE = re.compile(r"\\(?:page)?ref\{([^}]*)\}")
HYPERREF_RE = re.compile(r"\\hyperref\[([^\]]*)\]")


LATEX_REPLACEMENTS = [
    (r'\"a', "ä"), (r'\"o', "ö"), (r'\"u', "ü"), (r'\"A', "Ä"), (r'\"O', "Ö"), (r'\"U', "Ü"),
    (r'\"{a}', "ä"), (r'\"{o}', "ö"), (r'\"{u}', "ü"), (r'\"{A}', "Ä"), (r'\"{O}', "Ö"), (r'\"{U}', "Ü"),
    (r"\glqq", "„"), (r"\grqq", "“"), ("---", "—"), ("--", "–"), ("~", " "),
]


def latex_to_text(title):
    """Turn a LaTeX chapter title into plain display text."""
    text = re.sub(r"\\\\(\[[^\]]*\])?", " – ", title)  # forced line breaks
    text = re.sub(r"\\ss(\{\}|\s)?", "ß", text)
    for latex, plain in LATEX_REPLACEMENTS:
        text = text.replace(latex, plain)
    text = re.sub(r"\\[a-zA-Z]+\*?", "", text)  # drop remaining commands, keep their arguments
    text = text.replace("{", "").replace("}", "").replace("\\", "")
    text = re.sub(r"\s*–\s*–\s*", " – ", text)
    return re.sub(r"\s+", " ", text).strip()


def extract_chapter_title_and_labels(path):
    """Return the chapter title and all labels defined in a .tex file.
    The first label after \\chapter{} is treated as the chapter's own label."""
    title = None
    chapter_label = None
    labels = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.lstrip().startswith("%"):
                continue
            if title is None:
                match = CHAPTER_RE.search(line)
                if match:
                    title = match.group(1)
            for label in LABEL_RE.findall(line):
                if title is not None and chapter_label is None:
                    chapter_label = label
                if label not in labels:
                    labels.append(label)
    return title, chapter_label, labels


def sync_chapter_labels(item, path):
    """Rebuild the item's label entries from its .tex file. Caller commits."""
    title, chapter_label, labels = extract_chapter_title_and_labels(path)
    ChapterLabelModel.query.filter_by(item_id=item.id).delete()
    if title is None:
        return
    if not item.display_title:
        item.display_title = latex_to_text(title)
    for label in labels:
        db.session.add(ChapterLabelModel(
            label=label,
            title=title,
            is_chapter=(label == chapter_label),
            item_id=item.id,
        ))
    db.session.flush()


def load_label_lookup():
    """label -> {"item_ids": set of str ids defining it, "text": link text}."""
    lookup = {}
    for row in ChapterLabelModel.query.order_by(ChapterLabelModel.item_id).all():
        entry = lookup.setdefault(row.label, {"item_ids": set(), "text": None})
        entry["item_ids"].add(str(row.item_id))
        if entry["text"] is None:
            entry["text"] = row.title if row.is_chapter else "im Kapitel " + row.title
    return lookup


def rewrite_external_refs(line, lookup, item_ids):
    """Turn refs to labels whose chapter is not part of this compilation into
    links to the website; refs to included or unknown labels stay untouched."""
    selected = set(item_ids)

    def is_external(label):
        entry = lookup.get(label)
        return entry is not None and not (entry["item_ids"] & selected)

    def replace_ref(match):
        label = match.group(1)
        if not is_external(label):
            return match.group(0)
        return "\\href{" + KURZTEXTE_URL + "}{" + lookup[label]["text"] + "}"

    def replace_hyperref(match):
        if not is_external(match.group(1)):
            return match.group(0)
        return "\\href{" + KURZTEXTE_URL + "}"

    line = HYPERREF_RE.sub(replace_hyperref, line)
    return REF_RE.sub(replace_ref, line)
