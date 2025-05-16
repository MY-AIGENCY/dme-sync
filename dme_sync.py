# file: dme_sync.py
import json, sqlite3, hashlib, requests, datetime as dt

BASE   = "https://dmeacademy.com/wp-json"
TABLES = {"posts": "wp/v2/posts",
          "pages": "wp/v2/pages"}
          # Removing events since it needs special handling: "events": "tribe/events/v1/events"

DB = sqlite3.connect("dme.db")
c  = DB.cursor()
c.execute("""CREATE TABLE IF NOT EXISTS items
             (type TEXT, id INTEGER, hash TEXT,
              raw JSON, updated TEXT,
              PRIMARY KEY(type,id))""")
DB.commit()
# ---------- sync logic ----------

def grab(url):
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": "DME-KB-Sync"})
        r.raise_for_status()
        return r.json()
    except requests.exceptions.HTTPError as e:
        # If we hit a pagination error, just return empty to exit the loop
        if "page=" in url and e.response.status_code in [400, 404]:
            emit(f"[INFO] Reached end of pagination for {url}")
            return []
        # Re-raise other errors
        emit(f"[ERROR] {str(e)}")
        return []
    except Exception as e:
        emit(f"[ERROR] {str(e)}")
        return []

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
    
    try:
        while True:
            data = grab(f"{BASE}/{route}?per_page=100&page={page}")
            if not data:
                break
            
            for rec in data:
                try:
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
                    # Commit after each record to save progress
                    DB.commit()
                except Exception as e:
                    emit(f"[ERROR processing record] {str(e)}")
                    continue
            
            page += 1

        # removals
        c.execute("SELECT id FROM items WHERE type=?", (kind,))
        for (old_id,) in c.fetchall():
            if old_id not in seen:
                emit(f"[REMOVED {kind}] id {old_id}")
                c.execute("DELETE FROM items WHERE type=? AND id=?",
                        (kind, old_id))
        
        # Final commit for any removals
        DB.commit()
    except Exception as e:
        emit(f"[ERROR in sync_one] {str(e)}")
        # Ensure we commit any changes so far
        DB.commit()

# ---------- run all ----------
try:
    for kind, route in TABLES.items():
        emit(f"[INFO] Starting sync for {kind}")
        sync_one(kind, route)
        emit(f"[INFO] Completed sync for {kind}")
    
    emit("[INFO] All syncs completed successfully")
except Exception as e:
    emit(f"[CRITICAL ERROR] {str(e)}")
finally:
    # Always commit at the end
    DB.commit()