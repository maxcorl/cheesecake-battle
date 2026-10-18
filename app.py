"""
Cheesecake Battle - FastAPI Application
Semaine du Cheesecake & Grand Concours Colocations (Nintendo Switch + Mario Kart 8)
"""
import os
import sqlite3
import json
import urllib.request
import urllib.error
import threading
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

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    # Configure flavors: Nature Spéculoos (3.50€) + Option Coulis (+0.30€ -> 3.80€)
    # Dont 0,50€ de caution pour le pot (remboursé si ramené propre)
    cursor.execute("DELETE FROM flavors")
    initial_flavors = [
        ("Pot Nature Spéculoos", "nature_speculoos", "Cheesecake artisanal fait maison par l'asso dans son pot en verre, crème fondante et base croustillante pur Spéculoos. 3,50 € dont 0,50 € de caution pot remboursable.", 3.50, "Pot Classique • 3,50€ (dont 0,50€ caution)", "/static/images/cheesecake_nature_speculoos.jpg", 1),
        ("Pot Nature Spéculoos + Option Coulis", "speculoos_coulis", "Le pot Nature Spéculoos avec un généreux coulis fruité fait maison (+0,30€). 3,80 € dont 0,50 € de caution pot remboursable.", 3.80, "Option Coulis • 3,80€ (dont 0,50€ caution)", "/static/images/cheesecake_nature_speculoos.jpg", 1),
    ]
    cursor.executemany("""
        INSERT INTO flavors (name, slug, description, price, badge, image_url, available)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, initial_flavors)

    conn.commit()
    conn.close()


init_db()


def get_setting(key: str, default: str = "") -> str:
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        conn.close()
        if row and row[0]:
            return row[0].strip()
    except Exception:
        pass
    return default


def set_setting(key: str, value: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO settings (key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
    """, (key, value.strip()))
    conn.commit()
    conn.close()


def get_webhook_url() -> str:
    env_url = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
    if env_url:
        return env_url
    return get_setting("discord_webhook", "")


def trigger_ntfy_notification(topic: str, title: str, message: str, click_url: str = "https://cheesecake-battle.onrender.com/admin"):
    """Envoie une notification push instantanée sur smartphone sans compte ni configuration via ntfy.sh"""
    if not topic:
        topic = "cheesecake-nepal-cs"

    def _send():
        try:
            req = urllib.request.Request(
                f"https://ntfy.sh/{topic}",
                data=message.encode("utf-8"),
                headers={
                    "Title": title.encode("utf-8"),
                    "Tags": "cake,bell",
                    "Click": click_url,
                    "Priority": "high",
                    "User-Agent": "CheesecakeBattle/1.0"
                }
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                pass
        except Exception as e:
            print(f"[ntfy Notification Error]: {e}")

    threading.Thread(target=_send, daemon=True).start()


def trigger_email_notification(subject: str, content: str):
    """Envoie une notification par email via SMTP si configuré"""
    import smtplib
    from email.message import EmailMessage
    import ssl

    to_email = get_setting("notify_email")
    smtp_host = get_setting("smtp_host", "smtp.gmail.com")
    smtp_port_raw = get_setting("smtp_port", "465")
    smtp_port = int(smtp_port_raw) if smtp_port_raw.isdigit() else 465
    smtp_user = get_setting("smtp_user")
    smtp_pass = get_setting("smtp_pass")

    if not to_email or not smtp_user or not smtp_pass:
        return

    def _send():
        try:
            msg = EmailMessage()
            msg["Subject"] = subject
            msg["From"] = smtp_user
            msg["To"] = to_email
            msg.set_content(content)

            context = ssl.create_default_context()
            if smtp_port == 465:
                with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context) as server:
                    server.login(smtp_user, smtp_pass)
                    server.send_message(msg)
            else:
                with smtplib.SMTP(smtp_host, smtp_port) as server:
                    server.starttls(context=context)
                    server.login(smtp_user, smtp_pass)
                    server.send_message(msg)
        except Exception as e:
            print(f"[Email Notification Error]: {e}")

    threading.Thread(target=_send, daemon=True).start()


def trigger_discord_notification(webhook_url: str, title: str, description: str, fields: list, color: int = 0xE05638):
    if not webhook_url or not webhook_url.startswith("http"):
        return

    payload = {
        "username": "Cheesecake Battle 🍰",
        "avatar_url": "https://cheesecake-battle.onrender.com/static/images/logo_nepalasa.png",
        "embeds": [
            {
                "title": title,
                "description": description,
                "color": color,
                "fields": fields,
                "footer": {
                    "text": "Népal Asa • Semaine du Cheesecake"
                },
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
        ]
    }

    def _send():
        try:
            req = urllib.request.Request(
                webhook_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "CheesecakeBattle/1.0"
                }
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                pass
        except Exception as e:
            print(f"[Discord Webhook Notification Error]: {e}")

    threading.Thread(target=_send, daemon=True).start()


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


class NotificationSettingsUpdate(BaseModel):
    secret: str
    ntfy_topic: Optional[str] = "cheesecake-nepal-cs"
    notify_email: Optional[str] = ""
    smtp_host: Optional[str] = "smtp.gmail.com"
    smtp_port: Optional[str] = "465"
    smtp_user: Optional[str] = ""
    smtp_pass: Optional[str] = ""


class WebhookUpdate(BaseModel):
    secret: str
    webhook_url: str


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

    # 1. Alerte Push Smartphone instantanée (ntfy.sh - fonctionne sans aucun compte !)
    ntfy_topic = get_setting("ntfy_topic", "cheesecake-nepal-cs")
    items_summary_txt = "\n".join([f"• {qty}x {name}" for name, qty in sanitized_items.items()])
    ntfy_msg = f"🏠 Coloc: {clean_coloc}\n📍 Lieu: {clean_location}\n⏰ Horaire: {clean_time}\n🍰 Commande:\n{items_summary_txt}\n💰 Total: {round(total_price, 2):.2f}€ ({total_slices} pot{'s' if total_slices > 1 else ''})"
    trigger_ntfy_notification(
        topic=ntfy_topic,
        title=f"🍰 Commande #{order_id} - Coloc {clean_coloc}",
        message=ntfy_msg
    )

    # 2. Notification Email si configurée
    email_body = f"""Bonjour l'équipe Népal Asa !

Une nouvelle commande de Cheesecake vient d'être passée sur le site :

- N° de commande : #{order_id}
- Colocation : {clean_coloc}
- Lieu de livraison : {clean_location}
- Horaire souhaité : {clean_time}
- Détail :
{chr(10).join([f'  • {qty}x {name}' for name, qty in sanitized_items.items()])}
- Montant total : {round(total_price, 2):.2f} € ({total_slices} pot{'s' if total_slices > 1 else ''})

👉 Pour valider la commande et mettre à jour le classement :
https://cheesecake-battle.onrender.com/admin
"""
    trigger_email_notification(
        subject=f"[Cheesecake Battle] 🍰 Commande #{order_id} - Coloc {clean_coloc}",
        content=email_body
    )

    # 3. Discord si configuré (optionnel)
    webhook_url = get_webhook_url()
    if webhook_url:
        items_desc = "\n".join([f"• **{qty}x** {name}" for name, qty in sanitized_items.items()])
        fields = [
            {"name": "🏠 Colocation", "value": clean_coloc, "inline": True},
            {"name": "⏰ Horaire souhaité", "value": clean_time, "inline": True},
            {"name": "📍 Lieu de livraison", "value": clean_location, "inline": False},
            {"name": "🍰 Commande", "value": items_desc, "inline": False},
            {"name": "💰 Montant", "value": f"**{round(total_price, 2):.2f} €** ({total_slices} pot{'s' if total_slices > 1 else ''})", "inline": True},
            {"name": "⚡ Validation", "value": "Rendez-vous sur [l'Espace Admin](https://cheesecake-battle.onrender.com/admin) pour valider.", "inline": True}
        ]
        trigger_discord_notification(
            webhook_url=webhook_url,
            title=f"🍰 Nouvelle Commande #{order_id} !",
            description=f"La coloc **{clean_coloc}** vient de commander des pots de cheesecake !",
            fields=fields,
            color=0xE05638
        )

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
        "discord_webhook": get_webhook_url(),
        "notifications": {
            "ntfy_topic": get_setting("ntfy_topic", "cheesecake-nepal-cs"),
            "notify_email": get_setting("notify_email", ""),
            "smtp_host": get_setting("smtp_host", "smtp.gmail.com"),
            "smtp_port": get_setting("smtp_port", "465"),
            "smtp_user": get_setting("smtp_user", ""),
            "smtp_configured": bool(get_setting("smtp_user") and get_setting("smtp_pass"))
        },
        "stats": {
            "pending_orders": pending_count,
            "validated_revenue": round(revenue, 2),
            "validated_slices": total_validated_slices
        }
    }


@app.post("/api/admin/settings/notifications")
async def admin_save_notifications(data: NotificationSettingsUpdate):
    if data.secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Code secret invalide.")

    if data.ntfy_topic:
        set_setting("ntfy_topic", data.ntfy_topic.strip())
    if data.notify_email is not None:
        set_setting("notify_email", data.notify_email.strip())
    if data.smtp_host is not None:
        set_setting("smtp_host", data.smtp_host.strip())
    if data.smtp_port is not None:
        set_setting("smtp_port", data.smtp_port.strip())
    if data.smtp_user is not None:
        set_setting("smtp_user", data.smtp_user.strip())
    if data.smtp_pass:
        set_setting("smtp_pass", data.smtp_pass.strip())

    topic = get_setting("ntfy_topic", "cheesecake-nepal-cs")
    trigger_ntfy_notification(
        topic=topic,
        title="🎉 Test d'Alerte - Cheesecake Battle",
        message="Le système d'alerte smartphone est bien actif ! Vous recevrez un bip sonore à chaque commande."
    )

    if get_setting("notify_email") and get_setting("smtp_user") and get_setting("smtp_pass"):
        trigger_email_notification(
            subject="[Cheesecake Battle] 🎉 Test de notification Email réussi !",
            content="Bonjour !\n\nLes notifications par email sont bien configurées. Vous recevrez un email à chaque nouvelle commande de colocation !\n\nNépal Asa"
        )

    return {"success": True, "message": "Paramètres de notification enregistrés ! Test envoyé."}


@app.post("/api/admin/settings/webhook")
async def admin_save_webhook(data: WebhookUpdate):
    if data.secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Code secret invalide.")

    clean_url = data.webhook_url.strip()
    set_setting("discord_webhook", clean_url)

    if clean_url:
        fields = [
            {"name": "Statut", "value": "✅ Connecté avec succès !", "inline": True},
            {"name": "Alertes Actives", "value": "Vous recevrez une alerte instantanée ici à chaque nouvelle commande.", "inline": False}
        ]
        trigger_discord_notification(
            webhook_url=clean_url,
            title="🎉 Test de Notification - Cheesecake Battle",
            description="Le webhook Discord est bien relié au site de la Semaine du Cheesecake !",
            fields=fields,
            color=0x2ECC71
        )
        return {"success": True, "message": "Webhook Discord enregistré ! Un message de test a été envoyé sur votre salon."}
    else:
        return {"success": True, "message": "Webhook Discord désactivé."}


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
