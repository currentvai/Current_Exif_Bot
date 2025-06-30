import os
from pyrogram import Client, filters
from PIL import Image, ExifTags
from flask import Flask
from threading import Thread

# --- Flask Web Server Setup (বটকে জীবিত রাখার জন্য) ---
app_flask = Flask('')

@app_flask.route('/')
def home():
    return "I am alive and the EXIF bot is running!"

def run_flask():
    # Render সাধারণত 10000 পোর্ট ব্যবহার করতে পছন্দ করে
    app_flask.run(host="0.0.0.0", port=10000)

# --- Pyrogram Bot Setup (আপনার মূল বট) ---
API_ID = os.environ.get("API_ID")
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")

if not all([API_ID, API_HASH, BOT_TOKEN]):
    print("🔴 ত্রুটি: এক বা একাধিক Environment Variable সেট করা নেই।")
    exit()

app = Client("exifbot", api_id=int(API_ID), api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- আপনার বটের বাকি ফাংশনগুলো এখানে অপরিবর্তিত থাকবে ---

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
        exif = {}
        for tag, value in exif_data.items():
            decoded = ExifTags.TAGS.get(tag, tag)
            exif[decoded] = value
        location_info = None
        if 'GPSInfo' in exif:
            gps_info_raw = exif['GPSInfo']
            gps_info = {}
            for t, v in gps_info_raw.items():
                decoded_gps = ExifTags.GPSTAGS.get(t, t)
                gps_info[decoded_gps] = v
            if all(k in gps_info for k in ['GPSLatitude', 'GPSLongitude', 'GPSLatitudeRef', 'GPSLongitudeRef']):
                lat_dms, lon_dms = gps_info['GPSLatitude'], gps_info['GPSLongitude']
                lat_ref, lon_ref = gps_info['GPSLatitudeRef'], gps_info['GPSLongitudeRef']
                latitude, longitude = dms_to_decimal(lat_dms, lat_ref), dms_to_decimal(lon_dms, lon_ref)
                maps_link = f"https://www.google.com/maps?q={latitude},{longitude}"
                location_info = (f"📍 **Location Found!**\n\n"
                                 f"**Latitude:** `{latitude}`\n"
                                 f"**Longitude:** `{longitude}`\n\n"
                                 f"🗺️ **View on Google Maps:**\n{maps_link}")
            del exif['GPSInfo']
        return location_info, exif
    except Exception as e:
        return None, f"Error reading EXIF data: {e}"

@app.on_message(filters.command("start"))
def start_command(client, message):
    welcome_text = ("**👋 Hello! I'm EXIF Bot.**\n\n"
                    "📸 **How to use me:**\n"
                    "• Send me an image as a file (not as a photo) to preserve the original EXIF data.\n"
                    "• I will extract and display the EXIF details, including any **GPS location** found.\n\n"
                    "Send an image document to get started!")
    message.reply_text(welcome_text)

@app.on_message(filters.document)
def document_handler(client, message):
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
            exif_lines.append(f"✨ **{key}:** {value_str}")
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
        processing_message.edit_text(final_reply, disable_web_page_preview=False)


# --- বট এবং ওয়েব সার্ভার একসাথে চালানোর জন্য মূল অংশ ---
if __name__ == "__main__":
    print("Starting the web server in a background thread...")
    # ওয়েব সার্ভারটিকে একটি আলাদা থ্রেডে চালানো হচ্ছে
    flask_thread = Thread(target=run_flask)
    flask_thread.start()
    
    # এবার মূল বটটি চালানো হচ্ছে
    print("EXIF Bot is running...")
    app.run()
