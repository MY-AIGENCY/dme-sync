# file: dme_sync.py
import json, sqlite3, hashlib, requests, datetime as dt

BASE   = "https://dmeacademy.com/wp-json"
TABLES = {"posts": "wp/v2/posts",
          "pages": "wp/v2/pages",
          "events": "tribe/events/v1/events"}

DB = sqlite3.connect("dme.db")
c  = DB.cursor()
c.execute("""CREATE TABLE IF NOT EXISTS items
             (type TEXT, id INTEGER, hash TEXT,
              raw JSON, updated TEXT,
              PRIMARY KEY(type,id))""")
DB.commit()
# ---------- sync logic ----------

def grab(url):
    r = requests.get(url, timeout=15, headers={"User-Agent": "DME-KB-Sync"})
    r.raise_for_status()
    return r.json()

def digest(obj):  # produce a stable content hash
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True).encode()
    ).hexdigest()

def emit(msg):
    # for now just print; swap in Slack/Discord webhook later
    print(msg)

def sync_one(kind, route):
    page = 1
    seen = set()
    while True:
        data = grab(f"{BASE}/{route}?per_page=100&page={page}")
        if not data:
            break
        for rec in data:
            hid  = rec["id"]
            hsh  = digest(rec)
            seen.add(hid)

            c.execute("SELECT hash FROM items WHERE type=? AND id=?",
                      (kind, hid))
            row = c.fetchone()

            if not row:                         # — new item —
                emit(f"[NEW {kind}] {rec.get('title',{}).get('rendered','')}")
                c.execute("""INSERT OR REPLACE INTO items
                             VALUES (?,?,?,?,?)""",
                          (kind, hid, hsh, json.dumps(rec),
                           dt.date.today().isoformat()))
            elif row[0] != hsh:                 # — changed item —
                emit(f"[UPDATED {kind}] id {hid}")
                c.execute("""UPDATE items SET hash=?, raw=?, updated=?
                             WHERE type=? AND id=?""",
                          (hsh, json.dumps(rec),
                           dt.date.today().isoformat(), kind, hid))
        page += 1

    # removals
    c.execute("SELECT id FROM items WHERE type=?", (kind,))
    for (old_id,) in c.fetchall():
        if old_id not in seen:
            emit(f"[REMOVED {kind}] id {old_id}")
            c.execute("DELETE FROM items WHERE type=? AND id=?",
                      (kind, old_id))

# ---------- run all ----------

for kind, route in TABLES.items():
    sync_one(kind, route)

DB.commit()