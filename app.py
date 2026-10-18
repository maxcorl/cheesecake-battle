"""
Cheesecake Battle - FastAPI Application
Semaine du Cheesecake & Grand Concours Colocations (Nintendo Switch + Mario Kart 8)
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

app = FastAPI(title="Semaine du Cheesecake Battle")

app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    os.makedirs(os.path.join(BASE_DIR, "data"), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS colocations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        score INTEGER DEFAULT 0,
        address TEXT,
        created_at TEXT
    )
    """)

    cursor.execute("""
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

    cursor.execute("""
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

    # Configure flavors: Nature Spéculoos (2.50€) + Option Coulis (+0.30€ -> 2.80€)
    # Dont 0,50€ de caution pour le pot (remboursé si ramené propre)
    cursor.execute("DELETE FROM flavors")
    initial_flavors = [
        ("Pot Nature Spéculoos", "nature_speculoos", "Cheesecake artisanal fait maison par l'asso dans son pot en verre, crème fondante et base croustillante pur Spéculoos. 2,50 € (dont 0,50 € de caution pot remboursable).", 2.50, "Pot Classique • 2,50€ (dont 0,50€ caution)", "/static/images/cheesecake_nature_speculoos.jpg", 1),
        ("Pot Nature Spéculoos + Option Coulis", "speculoos_coulis", "Le pot Nature Spéculoos avec un généreux coulis fruité fait maison (+0,30€). 2,80 € (dont 0,50 € de caution pot remboursable).", 2.80, "Option Coulis • 2,80€ (dont 0,50€ caution)", "/static/images/cheesecake_nature_speculoos.jpg", 1),
    ]
    cursor.executemany("""
        INSERT INTO flavors (name, slug, description, price, badge, image_url, available)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, initial_flavors)

    conn.commit()
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
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM flavors WHERE available = 1")
    flavors = cursor.fetchall()

    cursor.execute("SELECT * FROM colocations ORDER BY score DESC, name ASC")
    colocations = cursor.fetchall()

    cursor.execute("SELECT SUM(score) FROM colocations")
    total_slices_sold = cursor.fetchone()[0] or 0

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
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, score, address FROM colocations ORDER BY score DESC, name ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/colocations-names")
async def get_colocation_names():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM colocations ORDER BY name ASC")
    names = [row[0] for row in cursor.fetchall()]
    conn.close()
    return names


@app.get("/api/flavors")
async def get_flavors():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM flavors WHERE available = 1")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.post("/api/orders")
async def create_order(order: OrderCreate):
    clean_coloc = order.coloc_name.strip()
    clean_location = order.delivery_location.strip()
    clean_time = order.delivery_time.strip()
    if not clean_coloc or not clean_location or not clean_time:
        raise HTTPException(status_code=400, detail="Veuillez remplir les 3 champs (Colocation, Lieu de livraison, Horaire).")

    # Calculate total slices and total price based on flavors in DB
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT name, price FROM flavors")
    price_map = {row["name"]: row["price"] for row in cursor.fetchall()}

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
        conn.close()
        raise HTTPException(status_code=400, detail="Veuillez sélectionner au moins une part de cheesecake.")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        INSERT INTO orders (
            coloc_name, buyer_name, phone, room_or_address,
            items_json, total_slices, total_price, payment_method,
            status, notes, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
    """, (
        clean_coloc,
        clean_coloc,
        "",
        clean_location,
        json.dumps(sanitized_items, ensure_ascii=False),
        total_slices,
        round(total_price, 2),
        "",
        clean_time,
        now
    ))
    order_id = cursor.lastrowid

    # If the colocation does not exist yet in the colocations table, register it with score 0
    cursor.execute("SELECT id FROM colocations WHERE LOWER(name) = LOWER(?)", (clean_coloc,))
    existing_coloc = cursor.fetchone()
    if not existing_coloc:
        cursor.execute("INSERT INTO colocations (name, score, address, created_at) VALUES (?, 0, ?, ?)",
                       (clean_coloc, clean_location, now))

    conn.commit()
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

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM orders ORDER BY id DESC")
    orders = [dict(r) for r in cursor.fetchall()]

    cursor.execute("SELECT * FROM colocations ORDER BY score DESC, name ASC")
    colocs = [dict(r) for r in cursor.fetchall()]

    cursor.execute("SELECT COUNT(*) FROM orders WHERE status = 'pending'")
    pending_count = cursor.fetchone()[0]

    cursor.execute("SELECT SUM(total_slices) FROM orders WHERE status = 'approved'")
    total_validated_slices = cursor.fetchone()[0] or 0

    # Compteur d'argent asso : 2,00 € par cheesecake validé
    revenue = total_validated_slices * 2.0

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

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
    order = cursor.fetchone()
    if not order:
        conn.close()
        raise HTTPException(status_code=404, detail="Commande introuvable.")

    current_status = order["status"]
    coloc_name = order["coloc_name"]
    slices = order["total_slices"]

    if current_status == "approved":
        conn.close()
        return {"success": True, "message": "Cette commande est déjà validée."}

    # Update order status
    cursor.execute("UPDATE orders SET status = 'approved' WHERE id = ?", (order_id,))

    # Update or insert coloc score
    cursor.execute("SELECT id, score FROM colocations WHERE LOWER(name) = LOWER(?)", (coloc_name,))
    coloc_row = cursor.fetchone()
    if coloc_row:
        new_score = coloc_row["score"] + slices
        cursor.execute("UPDATE colocations SET score = ? WHERE id = ?", (new_score, coloc_row["id"]))
    else:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("INSERT INTO colocations (name, score, address, created_at) VALUES (?, ?, ?, ?)",
                       (coloc_name, slices, order["room_or_address"] or "", now))

    conn.commit()
    conn.close()

    return {"success": True, "message": f"Commande #{order_id} validée ! +{slices} parts ajoutées à la coloc '{coloc_name}'."}


@app.post("/api/admin/orders/{order_id}/reject")
async def admin_reject_order(order_id: int, secret: str = Form(...)):
    if secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Code secret invalide.")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
    order = cursor.fetchone()
    if not order:
        conn.close()
        raise HTTPException(status_code=404, detail="Commande introuvable.")

    # If it was previously approved, decrement score
    if order["status"] == "approved":
        cursor.execute("SELECT id, score FROM colocations WHERE LOWER(name) = LOWER(?)", (order["coloc_name"],))
        coloc = cursor.fetchone()
        if coloc:
            new_score = max(0, coloc["score"] - order["total_slices"])
            cursor.execute("UPDATE colocations SET score = ? WHERE id = ?", (new_score, coloc["id"]))

    cursor.execute("UPDATE orders SET status = 'rejected' WHERE id = ?", (order_id,))
    conn.commit()
    conn.close()

    return {"success": True, "message": f"Commande #{order_id} marquée comme refusée/annulée."}


@app.post("/api/admin/colocations/score")
async def admin_update_coloc_score(coloc_id: int = Form(...), new_score: int = Form(...), secret: str = Form(...)):
    if secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Code secret invalide.")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE colocations SET score = ? WHERE id = ?", (max(0, new_score), coloc_id))
    conn.commit()
    conn.close()

    return {"success": True, "message": "Score mis à jour avec succès."}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
