"""
Cheesecake Battle - FastAPI Application
Semaine du Cheesecake & Grand Concours Colocations (Nintendo Switch + Mario Kart 8)
Compatible SQLite (local) et PostgreSQL (Render Cloud)
"""
import os
import sqlite3
import json
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, Request, HTTPException, Form, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "cheesecakes.db")
ADMIN_SECRET = os.environ.get("ADMIN_SECRET", "NEPAL2026")
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

app = FastAPI(title="Semaine du Cheesecake Battle")

app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))


class Database:
    @staticmethod
    def get_conn():
        if DATABASE_URL:
            import psycopg2
            url = DATABASE_URL
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql://", 1)
            return psycopg2.connect(url)
        else:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            return conn

    @staticmethod
    def execute(conn, sql: str, params: tuple = (), return_id: bool = False):
        if DATABASE_URL:
            import psycopg2.extras
            pg_sql = sql.replace("?", "%s")
            if return_id:
                pg_sql += " RETURNING id"
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(pg_sql, params)
                if return_id:
                    row = cur.fetchone()
                    return row["id"] if row else None
                return None
        else:
            cur = conn.cursor()
            cur.execute(sql, params)
            if return_id:
                return cur.lastrowid
            return None

    @staticmethod
    def fetch_all(conn, sql: str, params: tuple = ()):
        if DATABASE_URL:
            import psycopg2.extras
            pg_sql = sql.replace("?", "%s")
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(pg_sql, params)
                return cur.fetchall()
        else:
            cur = conn.cursor()
            cur.execute(sql, params)
            return cur.fetchall()

    @staticmethod
    def fetch_one(conn, sql: str, params: tuple = ()):
        if DATABASE_URL:
            import psycopg2.extras
            pg_sql = sql.replace("?", "%s")
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(pg_sql, params)
                return cur.fetchone()
        else:
            cur = conn.cursor()
            cur.execute(sql, params)
            return cur.fetchone()


def init_db():
    conn = Database.get_conn()
    try:
        if DATABASE_URL:
            import psycopg2.extras
            with conn.cursor() as cur:
                cur.execute("""
                CREATE TABLE IF NOT EXISTS colocations (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) UNIQUE NOT NULL,
                    score INTEGER DEFAULT 0,
                    address TEXT,
                    created_at TEXT
                );
                CREATE TABLE IF NOT EXISTS flavors (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    slug VARCHAR(255) UNIQUE NOT NULL,
                    description TEXT,
                    price REAL NOT NULL,
                    badge TEXT,
                    image_url TEXT,
                    available BOOLEAN DEFAULT TRUE
                );
                CREATE TABLE IF NOT EXISTS orders (
                    id SERIAL PRIMARY KEY,
                    coloc_name VARCHAR(255) NOT NULL,
                    buyer_name VARCHAR(255) NOT NULL,
                    phone TEXT NOT NULL,
                    room_or_address TEXT,
                    items_json TEXT NOT NULL,
                    total_slices INTEGER NOT NULL,
                    total_price REAL NOT NULL,
                    payment_method VARCHAR(50) DEFAULT 'Lydia',
                    status VARCHAR(50) DEFAULT 'pending',
                    notes TEXT,
                    created_at TEXT
                );
                """)
                cur.execute("DELETE FROM flavors")
                initial_flavors = [
                    ("Pot Nature Spéculoos", "nature_speculoos", "Cheesecake artisanal fait maison par l'asso dans son pot en verre, crème fondante et base croustillante pur Spéculoos. 2,50 € (dont 0,50 € de caution pot remboursable).", 2.50, "Pot Classique • 2,50€ (dont 0,50€ caution)", "/static/images/cheesecake_nature_speculoos.jpg", True),
                    ("Pot Nature Spéculoos + Option Coulis", "speculoos_coulis", "Le pot Nature Spéculoos avec un généreux coulis fruité fait maison (+0,30€). 2,80 € (dont 0,50 € de caution pot remboursable).", 2.80, "Option Coulis • 2,80€ (dont 0,50€ caution)", "/static/images/cheesecake_nature_speculoos.jpg", True),
                ]
                cur.executemany("""
                    INSERT INTO flavors (name, slug, description, price, badge, image_url, available)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, initial_flavors)
                # Cleanup duplicate order 10 if present
                cur.execute("DELETE FROM orders WHERE id = 10 AND coloc_name = '4B508'")
            conn.commit()
        else:
            os.makedirs(os.path.join(BASE_DIR, "data"), exist_ok=True)
            cur = conn.cursor()
            cur.execute("""
            CREATE TABLE IF NOT EXISTS colocations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                score INTEGER DEFAULT 0,
                address TEXT,
                created_at TEXT
            )
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS flavors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                slug TEXT UNIQUE NOT NULL,
                description TEXT,
                price REAL NOT NULL,
                badge TEXT,
                image_url TEXT,
                available BOOLEAN DEFAULT 1
            )
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                coloc_name TEXT NOT NULL,
                buyer_name TEXT NOT NULL,
                phone TEXT NOT NULL,
                room_or_address TEXT,
                items_json TEXT NOT NULL,
                total_slices INTEGER NOT NULL,
                total_price REAL NOT NULL,
                payment_method TEXT DEFAULT 'Lydia',
                status TEXT DEFAULT 'pending',
                notes TEXT,
                created_at TEXT
            )
            """)
            cur.execute("DELETE FROM flavors")
            initial_flavors = [
                ("Pot Nature Spéculoos", "nature_speculoos", "Cheesecake artisanal fait maison par l'asso dans son pot en verre, crème fondante et base croustillante pur Spéculoos. 2,50 € (dont 0,50 € de caution pot remboursable).", 2.50, "Pot Classique • 2,50€ (dont 0,50€ caution)", "/static/images/cheesecake_nature_speculoos.jpg", 1),
                ("Pot Nature Spéculoos + Option Coulis", "speculoos_coulis", "Le pot Nature Spéculoos avec un généreux coulis fruité fait maison (+0,30€). 2,80 € (dont 0,50 € de caution pot remboursable).", 2.80, "Option Coulis • 2,80€ (dont 0,50€ caution)", "/static/images/cheesecake_nature_speculoos.jpg", 1),
            ]
            cur.executemany("""
                INSERT INTO flavors (name, slug, description, price, badge, image_url, available)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, initial_flavors)
            conn.commit()
    finally:
        conn.close()


init_db()


class OrderCreate(BaseModel):
    coloc_name: str
    delivery_location: str
    delivery_time: str
    items: dict  # flavor_name -> quantity
    buyer_name: Optional[str] = ""
    phone: Optional[str] = ""
    room_or_address: Optional[str] = ""
    payment_method: Optional[str] = ""
    notes: Optional[str] = ""


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    conn = Database.get_conn()
    try:
        flavors = [dict(r) for r in Database.fetch_all(conn, "SELECT * FROM flavors WHERE available = TRUE")]
        colocations = [dict(r) for r in Database.fetch_all(conn, "SELECT * FROM colocations ORDER BY score DESC, name ASC")]
        sum_row = Database.fetch_one(conn, "SELECT COALESCE(SUM(score), 0) as total FROM colocations")
        total_slices_sold = int(sum_row["total"]) if sum_row and sum_row["total"] else 0
    finally:
        conn.close()

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "flavors": flavors,
            "colocations": colocations,
            "total_slices_sold": total_slices_sold
        }
    )


@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={}
    )


@app.get("/api/leaderboard")
async def get_leaderboard():
    conn = Database.get_conn()
    try:
        rows = Database.fetch_all(conn, "SELECT id, name, score, address FROM colocations ORDER BY score DESC, name ASC")
        return [dict(r) for r in rows]
    finally:
        conn.close()


@app.get("/api/colocations-names")
async def get_colocation_names():
    conn = Database.get_conn()
    try:
        rows = Database.fetch_all(conn, "SELECT name FROM colocations ORDER BY name ASC")
        return [r["name"] for r in rows]
    finally:
        conn.close()


@app.get("/api/flavors")
async def get_flavors():
    conn = Database.get_conn()
    try:
        rows = Database.fetch_all(conn, "SELECT * FROM flavors WHERE available = TRUE")
        return [dict(r) for r in rows]
    finally:
        conn.close()


@app.post("/api/orders")
async def create_order(order: OrderCreate):
    clean_coloc = order.coloc_name.strip()
    clean_location = order.delivery_location.strip()
    clean_time = order.delivery_time.strip()
    clean_phone = (order.phone or "").strip()
    if not clean_coloc or not clean_location or not clean_time or not clean_phone:
        raise HTTPException(status_code=400, detail="Veuillez remplir tous les champs (Colocation, Téléphone, Lieu de livraison, Horaire).")

    conn = Database.get_conn()
    try:
        flavor_rows = Database.fetch_all(conn, "SELECT name, price FROM flavors")
        price_map = {row["name"]: row["price"] for row in flavor_rows}

        total_slices = 0
        total_price = 0.0
        sanitized_items = {}

        for flavor_name, qty in order.items.items():
            try:
                qty_int = int(qty)
            except ValueError:
                continue
            if qty_int > 0:
                unit_price = price_map.get(flavor_name, 2.50)
                sanitized_items[flavor_name] = qty_int
                total_slices += qty_int
                total_price += unit_price * qty_int

        if total_slices <= 0:
            raise HTTPException(status_code=400, detail="Veuillez sélectionner au moins un pot de cheesecake.")

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        order_id = Database.execute(
            conn,
            """
            INSERT INTO orders (
                coloc_name, buyer_name, phone, room_or_address,
                items_json, total_slices, total_price, payment_method,
                status, notes, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
            """,
            (
                clean_coloc,
                clean_coloc,
                clean_phone,
                clean_location,
                json.dumps(sanitized_items, ensure_ascii=False),
                total_slices,
                round(total_price, 2),
                "",
                clean_time,
                now
            ),
            return_id=True
        )

        existing_coloc = Database.fetch_one(conn, "SELECT id FROM colocations WHERE LOWER(name) = LOWER(?)", (clean_coloc,))
        if not existing_coloc:
            Database.execute(conn, "INSERT INTO colocations (name, score, address, created_at) VALUES (?, 0, ?, ?)",
                             (clean_coloc, clean_location, now))

        conn.commit()
    finally:
        conn.close()

    return {
        "success": True,
        "order_id": order_id,
        "message": f"Commande #{order_id} enregistrée avec succès ! Elle sera comptabilisée dans le classement dès validation par l'équipe."
    }


@app.get("/api/admin/orders")
async def admin_get_orders(secret: str):
    if secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Code secret administrateur invalide.")

    conn = Database.get_conn()
    try:
        orders = [dict(r) for r in Database.fetch_all(conn, "SELECT * FROM orders ORDER BY id DESC")]
        colocs = [dict(r) for r in Database.fetch_all(conn, "SELECT * FROM colocations ORDER BY score DESC, name ASC")]
        pending_row = Database.fetch_one(conn, "SELECT COUNT(*) as count FROM orders WHERE status = 'pending'")
        pending_count = int(pending_row["count"]) if pending_row and pending_row["count"] else 0
        slices_row = Database.fetch_one(conn, "SELECT COALESCE(SUM(total_slices), 0) as sum_slices FROM orders WHERE status = 'approved'")
        total_validated_slices = int(slices_row["sum_slices"]) if slices_row and slices_row["sum_slices"] else 0
        revenue = total_validated_slices * 2.0
    finally:
        conn.close()

    return {
        "orders": orders,
        "colocations": colocs,
        "stats": {
            "pending_orders": pending_count,
            "validated_revenue": round(revenue, 2),
            "validated_slices": total_validated_slices
        }
    }


@app.post("/api/admin/orders/{order_id}/validate")
async def admin_validate_order(order_id: int, secret: str = Form(...)):
    if secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Code secret invalide.")

    conn = Database.get_conn()
    try:
        order = Database.fetch_one(conn, "SELECT * FROM orders WHERE id = ?", (order_id,))
        if not order:
            raise HTTPException(status_code=404, detail="Commande introuvable.")

        current_status = order["status"]
        coloc_name = order["coloc_name"]
        slices = order["total_slices"]

        if current_status == "approved":
            return {"success": True, "message": "Cette commande est déjà validée."}

        Database.execute(conn, "UPDATE orders SET status = 'approved' WHERE id = ?", (order_id,))

        coloc_row = Database.fetch_one(conn, "SELECT id, score FROM colocations WHERE LOWER(name) = LOWER(?)", (coloc_name,))
        if coloc_row:
            new_score = coloc_row["score"] + slices
            Database.execute(conn, "UPDATE colocations SET score = ? WHERE id = ?", (new_score, coloc_row["id"]))
        else:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            Database.execute(conn, "INSERT INTO colocations (name, score, address, created_at) VALUES (?, ?, ?, ?)",
                             (coloc_name, slices, order["room_or_address"] or "", now))

        conn.commit()
        return {"success": True, "message": f"Commande #{order_id} validée ! +{slices} parts ajoutées à la coloc '{coloc_name}'."}
    finally:
        conn.close()


@app.post("/api/admin/orders/{order_id}/reject")
async def admin_reject_order(order_id: int, secret: str = Form(...)):
    if secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Code secret invalide.")

    conn = Database.get_conn()
    try:
        order = Database.fetch_one(conn, "SELECT * FROM orders WHERE id = ?", (order_id,))
        if not order:
            raise HTTPException(status_code=404, detail="Commande introuvable.")

        if order["status"] == "approved":
            coloc = Database.fetch_one(conn, "SELECT id, score FROM colocations WHERE LOWER(name) = LOWER(?)", (order["coloc_name"],))
            if coloc:
                new_score = max(0, coloc["score"] - order["total_slices"])
                Database.execute(conn, "UPDATE colocations SET score = ? WHERE id = ?", (new_score, coloc["id"]))

        Database.execute(conn, "UPDATE orders SET status = 'rejected' WHERE id = ?", (order_id,))
        conn.commit()
        return {"success": True, "message": f"Commande #{order_id} marquée comme refusée/annulée."}
    finally:
        conn.close()


@app.post("/api/admin/colocations/score")
async def admin_update_coloc_score(coloc_id: int = Form(...), new_score: int = Form(...), secret: str = Form(...)):
    if secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Code secret invalide.")

    conn = Database.get_conn()
    try:
        Database.execute(conn, "UPDATE colocations SET score = ? WHERE id = ?", (max(0, new_score), coloc_id))
        conn.commit()
        return {"success": True, "message": "Score mis à jour avec succès."}
    finally:
        conn.close()


@app.post("/api/admin/orders/{order_id}/delete")
async def admin_delete_order(order_id: int, secret: str = Form(...), adjust_coloc: str = Form("false")):
    if secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Code secret invalide.")

    should_adjust = adjust_coloc.lower() in ("true", "1", "yes")

    conn = Database.get_conn()
    try:
        order = Database.fetch_one(conn, "SELECT * FROM orders WHERE id = ?", (order_id,))
        if not order:
            raise HTTPException(status_code=404, detail="Commande introuvable.")

        if should_adjust and order["status"] == "approved":
            coloc = Database.fetch_one(conn, "SELECT id, score FROM colocations WHERE LOWER(name) = LOWER(?)", (order["coloc_name"],))
            if coloc:
                new_score = max(0, coloc["score"] - order["total_slices"])
                Database.execute(conn, "UPDATE colocations SET score = ? WHERE id = ?", (new_score, coloc["id"]))

        Database.execute(conn, "DELETE FROM orders WHERE id = ?", (order_id,))
        conn.commit()
        return {"success": True, "message": f"Commande #{order_id} supprimée définitivement."}
    finally:
        conn.close()


@app.post("/api/admin/sync-scores")
async def admin_sync_scores(secret: str = Form(...)):
    if secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Code secret invalide.")

    conn = Database.get_conn()
    try:
        # Reset all coloc scores based on currently approved orders
        Database.execute(conn, "UPDATE colocations SET score = 0")
        approved_sums = Database.fetch_all(conn, """
            SELECT coloc_name, SUM(total_slices) as sum_slices
            FROM orders
            WHERE status = 'approved'
            GROUP BY coloc_name
        """)
        for row in approved_sums:
            Database.execute(conn, "UPDATE colocations SET score = ? WHERE LOWER(name) = LOWER(?)",
                             (row["sum_slices"], row["coloc_name"]))
        conn.commit()
        return {"success": True, "message": "Tous les scores ont été synchronisés avec les commandes validées !"}
    finally:
        conn.close()



if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
