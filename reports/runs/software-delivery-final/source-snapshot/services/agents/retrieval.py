"""Versioned, permission-filtered SQLite FTS5 retrieval, without remote embeddings."""
import hashlib
import json
import re
import sqlite3
from datetime import date
from pathlib import Path

PACK_PATH = Path(__file__).with_name("knowledge.json")
REQUIRED_META = {"id", "authority", "jurisdiction", "pathway", "effective_date", "version", "expires_at", "language", "access_scope", "section", "source", "text"}
INJECTION = re.compile(r"ignore (all |previous |prior )?instructions|system prompt|execute (shell|code)|reveal (the )?(key|secret)|override (policy|safety)|<\|system", re.I)


class PolicyReviewRequired(Exception):
    pass


def pack_hash():
    return hashlib.sha256(PACK_PATH.read_bytes()).hexdigest()


def retrieve(query, pathway="colorectal-fit", language="en", scope="staff", documents=None, today=None, limit=3):
    raw = json.loads(PACK_PATH.read_text())["documents"] if documents is None else documents
    today = today or date.today().isoformat()
    permitted = []
    versions = {}
    # Filter scope/pathway/language BEFORE inspecting or indexing text.
    for doc in raw:
        if doc.get("pathway") != pathway or doc.get("language") != language:
            continue
        if doc.get("access_scope") not in ({"public", "staff"} if scope == "staff" else {"public"}):
            continue
        if REQUIRED_META - doc.keys():
            raise PolicyReviewRequired("Policy metadata is incomplete; assigned policy review is required.")
        if doc["effective_date"] > today or doc["expires_at"] < today:
            raise PolicyReviewRequired("The applicable policy is not effective or has expired.")
        if INJECTION.search(doc["text"]):
            raise PolicyReviewRequired("Untrusted document instructions detected; policy review is required.")
        key = (doc["authority"], doc["section"])
        if key in versions and versions[key] != (doc["version"], doc["text"]):
            raise PolicyReviewRequired("Conflicting applicable policy sections require human review.")
        versions[key] = (doc["version"], doc["text"])
        permitted.append(doc)
    if not permitted:
        raise PolicyReviewRequired("No permitted, current policy supports this pathway and language.")
    db = sqlite3.connect(":memory:")
    try:
        db.execute("CREATE VIRTUAL TABLE knowledge USING fts5(doc_id UNINDEXED, section, text)")
        db.executemany("INSERT INTO knowledge VALUES (?,?,?)", [(d["id"], d["section"], d["text"]) for d in permitted])
        terms = re.findall(r"[\w\u0600-\u06ff]+", query, re.UNICODE)[:24]
        match = " OR ".join('"' + t.replace('"', '') + '"' for t in terms)
        ranked = db.execute("SELECT doc_id,bm25(knowledge) FROM knowledge WHERE knowledge MATCH ? ORDER BY bm25(knowledge) LIMIT ?", (match or '"followup"', limit)).fetchall()
        ids = [r[0] for r in ranked]
        if not ids:
            raise PolicyReviewRequired("No retrieved section supports this request; human review is required.")
        return [{**next(d for d in permitted if d["id"] == did), "citation": did + "#" + next(d for d in permitted if d["id"] == did)["section"]} for did in ids]
    finally:
        db.close()
