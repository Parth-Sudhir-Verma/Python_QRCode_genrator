from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import qrcode
import io
import base64
from pymongo import MongoClient
from bson.objectid import ObjectId
import requests

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# MongoDB Atlas connection
client = MongoClient("mongodb+srv://parthverma022005_db_user:vs21jZBWTQbHhFrV@qr.q70qhyg.mongodb.net/?retryWrites=true&w=majority&appName=QR")
db = client["QR"]
users_collection = db["users"]

def get_ngrok_url():
    """Fetch active ngrok public URL if available"""
    try:
        resp = requests.get("http://127.0.0.1:4040/api/tunnels")
        tunnels = resp.json()["tunnels"]
        for tunnel in tunnels:
            if tunnel["proto"] == "https":  # always prefer https
                return tunnel["public_url"]
    except Exception:
        return None
    return None

@app.get("/", response_class=HTMLResponse)
async def show_form(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/register", response_class=HTMLResponse)
async def register_user(request: Request, name: str = Form(...), email: str = Form(...)):
    # Save user in DB
    user = {"name": name, "email": email}
    result = users_collection.insert_one(user)
    user_id = str(result.inserted_id)

    # Always get ngrok URL dynamically
    ngrok_url = get_ngrok_url()
    if ngrok_url:
        verify_url = f"{ngrok_url}/verify/{user_id}"
    else:
        # fallback if ngrok not running
        verify_url = f"http://127.0.0.1:8000/verify/{user_id}"

    # Generate QR code
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(verify_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qr_base64 = base64.b64encode(buf.getvalue()).decode()

    # Update DB with QR code + URL
    users_collection.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"qr_code": qr_base64, "verify_url": verify_url}}
    )

    return HTMLResponse(f"""
        <h2>User Registered Successfully!</h2>
        <p>Name: {name}</p>
        <p>Email: {email}</p>
        <p>QR Code:</p>
        <img src="data:image/png;base64,{qr_base64}" alt="QR Code"><br><br>
        <p>Or open directly: <a href="{verify_url}" target="_blank">{verify_url}</a></p>
        <p><a href="/">Register Another User</a></p>
    """)

@app.get("/verify/{user_id}", response_class=HTMLResponse)
async def verify_user(user_id: str):
    user = users_collection.find_one({"_id": ObjectId(user_id)})
    if user:
        qr_code = user.get("qr_code", None)
        verify_url = user.get("verify_url", f"/verify/{user_id}")
        qr_img_html = f'<img src="data:image/png;base64,{qr_code}" alt="QR Code">' if qr_code else ""

        return HTMLResponse(f"""
            <h2>User Info</h2>
            <p>Name: {user['name']}</p>
            <p>Email: {user['email']}</p>
            <p>QR Code:</p>
            {qr_img_html}
            <br><br>
            <p>Direct Link: <a href="{verify_url}" target="_blank">{verify_url}</a></p>
        """)
    return HTMLResponse("<h2>User not found</h2>") 