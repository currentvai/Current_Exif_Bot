# main.py

import os
from threading import Thread
from flask import Flask
from pyrogram import Client, filters
from PIL import Image, ExifTags

# --- Database Setup (SQLAlchemy) ---
# ডেটাবেসের জন্য নতুন লাইব্রেরি ইম্পোর্ট করা হচ্ছে
from sqlalchemy import create_engine, Column, BigInteger, String
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

# --- Environment Variables ---
# সব এনভায়রনমেন্ট ভ্যারিয়েবল একসাথে লোড করা হচ্ছে
API_ID = os.environ.get("API_ID")
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0)) # আপনার নিজের অ্যাডমিন আইডি এখানে সেট করতে হবে

if not all([API_ID, API_HASH, BOT_TOKEN, DATABASE_URL]):
    print("🔴 ত্রুটি: API_ID, API_HASH, BOT_TOKEN, বা DATABASE_URL সেট করা নেই।")
    exit()

# --- Database Configuration ---
# OnRender-এর 'postgres://' URL-কে SQLAlchemy-এর জন্য 'postgresql://'-তে পরিবর্তন করা হচ্ছে
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ইউজারদের তথ্য রাখার জন্য ডেটাবেস টেবিলের মডেল
class User(Base):
    __tablename__ = "users"
    id = Column(BigInteger, primary_key=True, index=True, unique=True) # User's Telegram ID
    first_name = Column(String)
    last_name = Column(String, nullable=True)
    username = Column(String, nullable=True)

# ডেটাবেসে টেবিলটি তৈরি করা (যদি আগে থেকে না থাকে)
Base.metadata.create_all(bind=engine)

def add_or_update_user(message):
    """ডেটাবেসে নতুন ইউজার যোগ করে বা পুরোনো ইউজারের তথ্য আপডেট করে"""
    db = SessionLocal()
    user_id = message.from_user.id
    try:
        db_user = db.query(User).filter(User.id == user_id).first()
        if not db_user:
            # নতুন ইউজার যোগ করা হচ্ছে
            new_user = User(
                id=user_id,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name,
                username=message.from_user.username
            )
            db.add(new_user)
            db.commit()
            print(f"✅ নতুন ব্যবহারকারী যোগ হয়েছে: {message.from_user.first_name} (ID: {user_id})")
    except Exception as e:
        print(f"❌ ডেটাবেস সংক্রান্ত ত্রুটি: {e}")
    finally:
        db.close()


# --- Flask Web Server (বটকে জীবিত রাখার জন্য) ---
app_flask = Flask('')

@app_flask.route('/')
def home():
    return "I am alive and the EXIF bot is running!"

def run_flask():
    # OnRender-এর দেওয়া PORT ব্যবহার করা হচ্ছে
    port = int(os.environ.get("PORT", 10000))
    app_flask.run(host="0.0.0.0", port=port)


# --- Pyrogram Bot ---
app = Client("exifbot", api_id=int(API_ID), api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- EXIF Helper Functions (এখানে কোনো পরিবর্তন নেই) ---
def dms_to_decimal(dms, ref):
    degrees = float(dms[0])
    minutes = float(dms[1])
    seconds = float(dms[2])
    decimal = degrees + (minutes / 60.0) + (seconds / 3600.0)
    if ref in ['S', 'W']:
        decimal = -decimal
    return decimal

def get_exif(file_path):
    try:
        image = Image.open(file_path)
        exif_data = image._getexif()
        if not exif_data:
            return None, "No EXIF data found."
        exif = {ExifTags.TAGS.get(tag, tag): value for tag, value in exif_data.items()}
        location_info = None
        if 'GPSInfo' in exif:
            gps_info_raw = exif.pop('GPSInfo')
            gps_info = {ExifTags.GPSTAGS.get(t, t): v for t, v in gps_info_raw.items()}
            if all(k in gps_info for k in ['GPSLatitude', 'GPSLongitude', 'GPSLatitudeRef', 'GPSLongitudeRef']):
                lat, lon = dms_to_decimal(gps_info['GPSLatitude'], gps_info['GPSLatitudeRef']), dms_to_decimal(gps_info['GPSLongitude'], gps_info['GPSLongitudeRef'])
                maps_link = f"https://www.google.com/maps?q={lat},{lon}"
                location_info = (f"📍 **Location Found!**\n\n"
                                 f"**Latitude:** `{lat}`\n"
                                 f"**Longitude:** `{lon}`\n\n"
                                 f"🗺️ [View on Google Maps]({maps_link})")
        return location_info, exif
    except Exception as e:
        return None, f"Error reading EXIF data: {e}"


# --- Bot Handlers (এখানে পরিবর্তন করা হয়েছে) ---
@app.on_message(filters.command("start"))
def start_command(client, message):
    add_or_update_user(message) # ডেটাবেসে ইউজার যোগ করা হচ্ছে
    welcome_text = ("**👋 Hello! I'm EXIF Bot.**\n\n"
                    "📸 **How to use me:**\n"
                    "• Send me an image as a **file** (not as a photo) to preserve the original EXIF data.\n"
                    "• I will extract and display the EXIF details, including any **GPS location** found.\n\n"
                    "Send an image document to get started!")
    message.reply_text(welcome_text, disable_web_page_preview=True)

@app.on_message(filters.command("stats") & filters.user(ADMIN_ID))
def stats_command(client, message):
    db = SessionLocal()
    try:
        total_users = db.query(User).count()
        message.reply_text(f"📊 **Bot Statistics**\n\nTotal unique users: `{total_users}`")
    finally:
        db.close()

@app.on_message(filters.document)
def document_handler(client, message):
    add_or_update_user(message) # প্রতিটি ইন্টারেকশনে ইউজারকে ডেটাবেসে চেক/যোগ করা হচ্ছে
    if not message.document.mime_type or not message.document.mime_type.startswith("image"):
        message.reply("**❌ Please send an image file (as a document).**")
        return
    
    processing_message = message.reply("`Processing image...`")
    file_path = message.download()
    location_details, general_exif = get_exif(file_path)
    os.remove(file_path)
    
    final_reply = ""
    if location_details:
        final_reply += location_details + "\n\n" + ("-"*20) + "\n\n"
    
    if isinstance(general_exif, dict):
        header = "📸 **General EXIF Details:**\n\n"
        exif_lines = []
        for key, value in general_exif.items():
            value_str = f"({len(value)} bytes of binary data)" if isinstance(value, bytes) and len(value) > 64 else str(value)
            exif_lines.append(f"✨ **{key}:** `{value_str}`")
        final_reply += header + "\n".join(exif_lines)
    else:
        final_reply += f"**❌ {general_exif}**"
        
    if len(final_reply) > 4096:
        processing_message.edit_text("The EXIF data is too long to display. Sending as a file.")
        with open("exif_details.txt", "w", encoding="utf-8") as f:
            f.write(final_reply.replace("**", "").replace("`", ""))
        message.reply_document("exif_details.txt")
        os.remove("exif_details.txt")
    else:
        processing_message.edit_text(final_reply, disable_web_page_preview=True)


# --- বট এবং ওয়েব সার্ভার একসাথে চালানোর জন্য মূল অংশ ---
if __name__ == "__main__":
    print("Starting the web server in a background thread...")
    flask_thread = Thread(target=run_flask)
    flask_thread.start()
    
    print("EXIF Bot is running...")
    app.run()
