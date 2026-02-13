import sqlite3
import json
import os
from models.entry import BibEntry


class Database:
    def __init__(self, db_path):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self):
        schema_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'schema.sql')
        with open(schema_path) as f:
            schema = f.read()
        conn = self._get_conn()
        conn.executescript(schema)
        conn.close()

    def get_all_entries(self):
        conn = self._get_conn()
        rows = conn.execute("SELECT * FROM entries ORDER BY created_at DESC").fetchall()
        conn.close()
        return [BibEntry.from_db_row(r) for r in rows]

    def get_entry(self, entry_id):
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM entries WHERE id = ?", (entry_id,)).fetchone()
        conn.close()
        if row:
            return BibEntry.from_db_row(row)
        return None

    def get_entry_by_key(self, citation_key):
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM entries WHERE citation_key = ?", (citation_key,)).fetchone()
        conn.close()
        if row:
            return BibEntry.from_db_row(row)
        return None

    def insert_entry(self, entry: BibEntry) -> int:
        conn = self._get_conn()
        fields = {k: v for k, v in entry.to_dict().items()
                  if k not in ('id', '_extra_fields') and v is not None}
        if 'validation_messages' in fields and isinstance(fields['validation_messages'], list):
            fields['validation_messages'] = json.dumps(fields['validation_messages'])
        columns = ', '.join(fields.keys())
        placeholders = ', '.join(['?'] * len(fields))
        cursor = conn.execute(
            f"INSERT INTO entries ({columns}) VALUES ({placeholders})",
            list(fields.values())
        )
        conn.commit()
        entry_id = cursor.lastrowid
        conn.close()
        return entry_id

    def update_entry(self, entry_id: int, updates: dict) -> bool:
        conn = self._get_conn()
        if 'validation_messages' in updates and isinstance(updates['validation_messages'], list):
            updates['validation_messages'] = json.dumps(updates['validation_messages'])
        updates['updated_at'] = 'CURRENT_TIMESTAMP'
        set_clauses = []
        values = []
        for k, v in updates.items():
            if k == 'updated_at':
                set_clauses.append(f"{k} = CURRENT_TIMESTAMP")
            else:
                set_clauses.append(f"{k} = ?")
                values.append(v)
        values.append(entry_id)
        cursor = conn.execute(
            f"UPDATE entries SET {', '.join(set_clauses)} WHERE id = ?",
            values
        )
        conn.commit()
        changed = cursor.rowcount > 0
        conn.close()
        return changed

    def delete_entry(self, entry_id: int) -> bool:
        conn = self._get_conn()
        cursor = conn.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
        conn.commit()
        changed = cursor.rowcount > 0
        conn.close()
        return changed

    def find_by_doi(self, doi: str):
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM entries WHERE doi = ?", (doi,)).fetchone()
        conn.close()
        if row:
            return BibEntry.from_db_row(row)
        return None

    def find_by_arxiv_id(self, arxiv_id: str):
        conn = self._get_conn()
        # Strip version suffix for matching
        base_id = arxiv_id.split('v')[0] if 'v' in arxiv_id else arxiv_id
        rows = conn.execute("SELECT * FROM entries WHERE arxiv_id LIKE ?", (base_id + '%',)).fetchall()
        conn.close()
        return [BibEntry.from_db_row(r) for r in rows]

    def search_by_title(self, title: str):
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM entries WHERE title LIKE ?",
            (f'%{title}%',)
        ).fetchall()
        conn.close()
        return [BibEntry.from_db_row(r) for r in rows]

    def get_all_for_export(self):
        return self.get_all_entries()
