import sqlite3
import os
import json
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'reavaliacao.db')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            name     TEXT UNIQUE NOT NULL,
            role     TEXT NOT NULL DEFAULT 'servidor',
            password TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS assets (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            planilha         TEXT NOT NULL,
            row_index        INTEGER NOT NULL,
            natureza_despesa TEXT,
            material         TEXT,
            nrp              TEXT,
            tipo             TEXT,
            marca            TEXT,
            modelo           TEXT,
            data_tombamento  TEXT,
            valor_contabil   REAL,
            valor_atual      REAL
        );

        CREATE TABLE IF NOT EXISTS assignments (
            asset_id    INTEGER PRIMARY KEY REFERENCES assets(id),
            user_id     INTEGER NOT NULL REFERENCES users(id),
            assigned_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS reviews (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id        INTEGER UNIQUE REFERENCES assets(id),
            valor_mercado   REAL NOT NULL,
            screenshot_path TEXT,
            user_id         INTEGER REFERENCES users(id),
            updated_at      TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            action         TEXT NOT NULL,
            asset_id       INTEGER,
            admin_id       INTEGER NOT NULL,
            target_user_id INTEGER,
            justificativa  TEXT,
            created_at     TEXT NOT NULL
        );
    """)
    conn.commit()
    # Migração: adiciona colunas novas se ainda não existirem
    for col, defn in [('prices', 'TEXT'), ('screenshot_paths', 'TEXT'), ('observacao', 'TEXT')]:
        try:
            conn.execute(f'ALTER TABLE reviews ADD COLUMN {col} {defn}')
            conn.commit()
        except Exception:
            pass
    conn.close()


def _row_to_dict(row):
    return dict(row) if row else None


# ── Users ──────────────────────────────────────────────────────────────────

def create_user(name, password_hash, role='servidor'):
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (name, role, password) VALUES (?, ?, ?)",
            (name, role, password_hash)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def update_user_password(user_id, password_hash):
    conn = get_db()
    conn.execute("UPDATE users SET password = ? WHERE id = ?", (password_hash, user_id))
    conn.commit()
    conn.close()


def get_user_by_name(name):
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE name = ?", (name,)).fetchone()
    conn.close()
    return _row_to_dict(row)


def get_user_by_id(user_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return _row_to_dict(row)


def get_all_users():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM users WHERE role = 'servidor' ORDER BY name"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Assets ─────────────────────────────────────────────────────────────────

def count_assets():
    conn = get_db()
    n = conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
    conn.close()
    return n


def get_asset(asset_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM assets WHERE id = ?", (asset_id,)).fetchone()
    conn.close()
    return _row_to_dict(row)


def get_distinct_planilhas():
    conn = get_db()
    rows = conn.execute(
        "SELECT DISTINCT planilha FROM assets ORDER BY planilha"
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


def get_unassigned_count_by_planilha():
    conn = get_db()
    rows = conn.execute("""
        SELECT a.planilha, COUNT(*) as total
        FROM assets a
        LEFT JOIN assignments asg ON a.id = asg.asset_id
        WHERE asg.asset_id IS NULL
        GROUP BY a.planilha
        ORDER BY a.planilha
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_unassigned_total():
    conn = get_db()
    n = conn.execute("""
        SELECT COUNT(*) FROM assets a
        LEFT JOIN assignments asg ON a.id = asg.asset_id
        WHERE asg.asset_id IS NULL
    """).fetchone()[0]
    conn.close()
    return n


# ── Assignments ────────────────────────────────────────────────────────────

def assign_by_planilha(planilha, user_id):
    now = datetime.utcnow().isoformat()
    conn = get_db()
    conn.execute("""
        INSERT OR IGNORE INTO assignments (asset_id, user_id, assigned_at)
        SELECT a.id, ?, ?
        FROM assets a
        LEFT JOIN assignments asg ON a.id = asg.asset_id
        WHERE a.planilha = ? AND asg.asset_id IS NULL
    """, (user_id, now, planilha))
    count = conn.execute("SELECT changes()").fetchone()[0]
    conn.commit()
    conn.close()
    return count


def assign_by_quantity(n, user_id):
    now = datetime.utcnow().isoformat()
    conn = get_db()
    rows = conn.execute("""
        SELECT a.id FROM assets a
        LEFT JOIN assignments asg ON a.id = asg.asset_id
        WHERE asg.asset_id IS NULL
        ORDER BY a.planilha, a.row_index
        LIMIT ?
    """, (n,)).fetchall()
    ids = [r[0] for r in rows]
    if ids:
        conn.executemany(
            "INSERT OR IGNORE INTO assignments (asset_id, user_id, assigned_at) VALUES (?, ?, ?)",
            [(aid, user_id, now) for aid in ids]
        )
        conn.commit()
    conn.close()
    return len(ids)


def reassign_pending(from_user_id, to_user_id):
    """Move bens não avaliados de um servidor para outro."""
    now = datetime.utcnow().isoformat()
    conn = get_db()
    conn.execute("""
        UPDATE assignments SET user_id = ?, assigned_at = ?
        WHERE user_id = ?
          AND asset_id NOT IN (SELECT asset_id FROM reviews)
    """, (to_user_id, now, from_user_id))
    count = conn.execute("SELECT changes()").fetchone()[0]
    conn.commit()
    conn.close()
    return count


def get_assets_for_user(user_id):
    conn = get_db()
    rows = conn.execute("""
        SELECT a.*, r.valor_mercado, r.screenshot_path, r.observacao, r.updated_at AS reviewed_at
        FROM assets a
        JOIN assignments asg ON a.id = asg.asset_id
        LEFT JOIN reviews r ON a.id = r.asset_id
        WHERE asg.user_id = ?
        ORDER BY a.planilha, a.row_index
    """, (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_next_pending_asset(user_id):
    conn = get_db()
    row = conn.execute("""
        SELECT a.*
        FROM assets a
        JOIN assignments asg ON a.id = asg.asset_id
        LEFT JOIN reviews r ON a.id = r.asset_id
        WHERE asg.user_id = ? AND r.id IS NULL
        ORDER BY a.planilha, a.row_index
        LIMIT 1
    """, (user_id,)).fetchone()
    conn.close()
    return _row_to_dict(row)


def get_adjacent_asset_ids(user_id, current_asset_id):
    """Retorna (prev_id, next_id, posição_1based, total) para o asset atual."""
    conn = get_db()
    rows = conn.execute("""
        SELECT a.id
        FROM assets a
        JOIN assignments asg ON a.id = asg.asset_id
        WHERE asg.user_id = ?
        ORDER BY a.planilha, a.row_index
    """, (user_id,)).fetchall()
    conn.close()
    ids = [r[0] for r in rows]
    if current_asset_id not in ids:
        return None, None, None, len(ids)
    idx = ids.index(current_asset_id)
    prev_id = ids[idx - 1] if idx > 0 else None
    next_id = ids[idx + 1] if idx < len(ids) - 1 else None
    return prev_id, next_id, idx + 1, len(ids)


# ── Reviews ────────────────────────────────────────────────────────────────

def save_review(asset_id, user_id, valor_mercado, screenshot_path=None,
                prices=None, screenshot_paths=None, observacao=None):
    now = datetime.utcnow().isoformat()
    prices_json = json.dumps(prices) if prices else None
    paths_json  = json.dumps(screenshot_paths) if screenshot_paths else None
    conn = get_db()
    conn.execute("""
        INSERT INTO reviews
            (asset_id, user_id, valor_mercado, screenshot_path, prices, screenshot_paths, observacao, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(asset_id) DO UPDATE SET
            valor_mercado    = excluded.valor_mercado,
            screenshot_path  = excluded.screenshot_path,
            prices           = excluded.prices,
            screenshot_paths = excluded.screenshot_paths,
            observacao       = excluded.observacao,
            user_id          = excluded.user_id,
            updated_at       = excluded.updated_at
    """, (asset_id, user_id, valor_mercado, screenshot_path, prices_json, paths_json, observacao, now))

    fields = conn.execute(
        "SELECT material, marca, modelo, tipo FROM assets WHERE id = ?", (asset_id,)
    ).fetchone()
    if fields and fields['material'] and fields['marca'] and fields['modelo']:
        conn.execute("""
            INSERT OR IGNORE INTO reviews
                (asset_id, user_id, valor_mercado, screenshot_path, prices, screenshot_paths, observacao, updated_at)
            SELECT a.id, ?, ?, ?, ?, ?, ?, ?
            FROM assets a
            WHERE a.material = ? AND a.marca = ? AND a.modelo = ?
              AND COALESCE(a.tipo, '') = COALESCE(?, '')
              AND a.id != ?
        """, (user_id, valor_mercado, screenshot_path, prices_json, paths_json, observacao, now,
              fields['material'], fields['marca'], fields['modelo'], fields['tipo'], asset_id))

    conn.commit()
    conn.close()


def get_group_size(asset_id):
    conn = get_db()
    fields = conn.execute(
        "SELECT material, marca, modelo, tipo FROM assets WHERE id = ?", (asset_id,)
    ).fetchone()
    if not fields or not fields['material'] or not fields['marca'] or not fields['modelo']:
        conn.close()
        return 1
    row = conn.execute("""
        SELECT COUNT(*) as cnt FROM assets
        WHERE material = ? AND marca = ? AND modelo = ?
          AND COALESCE(tipo, '') = COALESCE(?, '')
    """, (fields['material'], fields['marca'], fields['modelo'], fields['tipo'])).fetchone()
    conn.close()
    return row['cnt'] if row else 1


def get_review(asset_id):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM reviews WHERE asset_id = ?", (asset_id,)
    ).fetchone()
    conn.close()
    d = _row_to_dict(row)
    if not d:
        return d
    d['prices'] = json.loads(d['prices']) if d.get('prices') else []
    raw_paths = d.get('screenshot_paths')
    if raw_paths:
        d['screenshot_paths'] = json.loads(raw_paths)
    elif d.get('screenshot_path'):
        d['screenshot_paths'] = [d['screenshot_path']]
    else:
        d['screenshot_paths'] = []
    return d


def delete_review(asset_id, user_id):
    """Remove a avaliação deste bem e de todos os do mesmo grupo (mesmo tipo) atribuídos ao mesmo servidor."""
    conn = get_db()
    fields = conn.execute(
        "SELECT material, marca, modelo, tipo FROM assets WHERE id = ?", (asset_id,)
    ).fetchone()
    if fields and fields['material'] and fields['marca'] and fields['modelo']:
        conn.execute("""
            DELETE FROM reviews
            WHERE asset_id IN (
                SELECT a.id FROM assets a
                JOIN assignments asg ON a.id = asg.asset_id
                WHERE a.material = ? AND a.marca = ? AND a.modelo = ?
                  AND COALESCE(a.tipo, '') = COALESCE(?, '')
                  AND asg.user_id = ?
            )
        """, (fields['material'], fields['marca'], fields['modelo'], fields['tipo'], user_id))
    else:
        conn.execute("DELETE FROM reviews WHERE asset_id = ?", (asset_id,))
    conn.commit()
    conn.close()


def delete_user(user_id):
    """Remove o servidor: preserva reviews (user_id → NULL), libera assignments, apaga o user."""
    conn = get_db()
    conn.execute("UPDATE reviews SET user_id = NULL WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM assignments WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()


def admin_delete_review(asset_id, admin_id, target_user_id, justificativa):
    """Admin remove uma avaliação específica (sem cascata de grupo) e registra no audit_log."""
    now = datetime.utcnow().isoformat()
    conn = get_db()
    conn.execute("DELETE FROM reviews WHERE asset_id = ?", (asset_id,))
    conn.execute("""
        INSERT INTO audit_log (action, asset_id, admin_id, target_user_id, justificativa, created_at)
        VALUES ('undo_review', ?, ?, ?, ?, ?)
    """, (asset_id, admin_id, target_user_id, justificativa, now))
    conn.commit()
    conn.close()


def get_unique_count_by_planilha():
    """Grupos únicos por planilha. Chave: tipo + material + marca + modelo (assets incompletos contam 1 cada)."""
    conn = get_db()
    rows = conn.execute("""
        SELECT planilha, COUNT(DISTINCT
            CASE WHEN material IS NOT NULL AND marca IS NOT NULL AND modelo IS NOT NULL
                 THEN COALESCE(tipo, '') || '~~' || material || '~~' || marca || '~~' || modelo
                 ELSE CAST(id AS TEXT)
            END) AS unicos
        FROM assets
        GROUP BY planilha
        ORDER BY planilha
    """).fetchall()
    conn.close()
    return {r['planilha']: r['unicos'] for r in rows}


def get_unique_unassigned_by_planilha():
    """Grupos únicos não distribuídos por planilha."""
    conn = get_db()
    rows = conn.execute("""
        SELECT a.planilha, COUNT(DISTINCT
            CASE WHEN a.material IS NOT NULL AND a.marca IS NOT NULL AND a.modelo IS NOT NULL
                 THEN COALESCE(a.tipo, '') || '~~' || a.material || '~~' || a.marca || '~~' || a.modelo
                 ELSE CAST(a.id AS TEXT)
            END) AS unicos
        FROM assets a
        LEFT JOIN assignments asg ON a.id = asg.asset_id
        WHERE asg.asset_id IS NULL
        GROUP BY a.planilha
        ORDER BY a.planilha
    """).fetchall()
    conn.close()
    return {r['planilha']: r['unicos'] for r in rows}


# ── Progress ───────────────────────────────────────────────────────────────

def get_global_progress():
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
    principais = conn.execute("SELECT COUNT(*) FROM assets WHERE tipo IS NULL").fetchone()[0]
    reviewed = conn.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
    unassigned = conn.execute("""
        SELECT COUNT(*) FROM assets a
        LEFT JOIN assignments asg ON a.id = asg.asset_id
        WHERE asg.asset_id IS NULL
    """).fetchone()[0]
    conn.close()
    return {"total": total, "principais": principais, "reviewed": reviewed, "unassigned": unassigned}


def get_user_progress(user_id):
    conn = get_db()
    total = conn.execute(
        "SELECT COUNT(*) FROM assignments WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    reviewed = conn.execute("""
        SELECT COUNT(*) FROM reviews r
        JOIN assignments asg ON r.asset_id = asg.asset_id
        WHERE asg.user_id = ?
    """, (user_id,)).fetchone()[0]
    conn.close()
    return {"total": total, "reviewed": reviewed}


def get_all_users_progress():
    conn = get_db()
    rows = conn.execute("""
        SELECT u.id, u.name,
               COUNT(asg.asset_id)  AS total,
               COUNT(r.id)          AS reviewed
        FROM users u
        LEFT JOIN assignments asg ON u.id = asg.user_id
        LEFT JOIN reviews r ON asg.asset_id = r.asset_id
        WHERE u.role = 'servidor'
        GROUP BY u.id
        ORDER BY u.name
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_progress_by_planilha():
    conn = get_db()
    rows = conn.execute("""
        SELECT a.planilha,
               COUNT(a.id) AS total,
               SUM(CASE WHEN a.tipo IS NULL THEN 1 ELSE 0 END) AS principais,
               SUM(CASE WHEN a.tipo IS NOT NULL THEN 1 ELSE 0 END) AS agregacoes,
               COUNT(r.id) AS reviewed
        FROM assets a
        LEFT JOIN reviews r ON a.id = r.asset_id
        GROUP BY a.planilha
        ORDER BY a.planilha
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]
