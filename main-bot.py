import os
from pyrogram import Client, filters
from PIL import Image, ExifTags

# --- Environment Variables থেকে গোপন তথ্য লোড করা ---
# <<<< এই অংশটি পরিবর্তন করা হয়েছে >>>>
API_ID = os.environ.get("API_ID")
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")

# --- সব তথ্য ঠিকমতো পাওয়া গেছে কিনা তা পরীক্ষা করা ---
if not all([API_ID, API_HASH, BOT_TOKEN]):
    print("🔴 ত্রুটি: এক বা একাধিক Environment Variable (API_ID, API_HASH, BOT_TOKEN) সেট করা নেই।")
    exit()

# Initialize the bot client (API_ID কে int তে রূপান্তর করা হয়েছে)
app = Client("exifbot", api_id=int(API_ID), api_hash=API_HASH, bot_token=BOT_TOKEN)
# <<<< পরিবর্তন শেষ >>>>


def dms_to_decimal(dms, ref):
    """
    Convert Degrees, Minutes, Seconds (DMS) to decimal degrees.
    """
    degrees = float(dms[0])
    minutes = float(dms[1])
    seconds = float(dms[2])
    
    decimal = degrees + (minutes / 60.0) + (seconds / 3600.0)
    
    if ref in ['S', 'W']:
        decimal = -decimal
        
    return decimal


def get_exif(file_path):
    """
    Open an image file and extract its EXIF data, including formatted GPS info.
    Returns a tuple: (location_string, general_exif_dict)
    """
    try:
        image = Image.open(file_path)
        exif_data = image._getexif()

        if not exif_data:
            return None, "No EXIF data found."

        exif = {}
        for tag, value in exif_data.items():
            decoded = ExifTags.TAGS.get(tag, tag)
            exif[decoded] = value

        # --- Location Data Processing ---
        location_info = None
        if 'GPSInfo' in exif:
            gps_info_raw = exif['GPSInfo']
            gps_info = {}
            for t, v in gps_info_raw.items():
                decoded_gps = ExifTags.GPSTAGS.get(t, t)
                gps_info[decoded_gps] = v
            
            # Check for essential GPS tags
            if all(k in gps_info for k in ['GPSLatitude', 'GPSLongitude', 'GPSLatitudeRef', 'GPSLongitudeRef']):
                lat_dms = gps_info['GPSLatitude']
                lon_dms = gps_info['GPSLongitude']
                lat_ref = gps_info['GPSLatitudeRef']
                lon_ref = gps_info['GPSLongitudeRef']

                latitude = dms_to_decimal(lat_dms, lat_ref)
                longitude = dms_to_decimal(lon_dms, lon_ref)

                maps_link = f"https://www.google.com/maps?q={latitude},{longitude}"
                
                location_info = (
                    f"📍 **Location Found!**\n\n"
                    f"**Latitude:** `{latitude}`\n"
                    f"**Longitude:** `{longitude}`\n\n"
                    f"🗺️ **View on Google Maps:**\n{maps_link}"
                )
            # Remove GPSInfo from the general dict to avoid redundancy
            del exif['GPSInfo']
            
        return location_info, exif

    except Exception as e:
        return None, f"Error reading EXIF data: {e}"


@app.on_message(filters.command("start"))
def start_command(client, message):
    """
    Respond to the /start command with a welcome message and instructions.
    """
    welcome_text = (
        "**👋 Hello! I'm EXIF Bot.**\n\n"
        "📸 **How to use me:**\n"
        "• Send me an image as a file (not as a photo) to preserve the original EXIF data.\n"
        "• I will extract and display the EXIF details, including any **GPS location** found.\n\n"
        "Send an image document to get started!"
    )
    message.reply_text(welcome_text)


@app.on_message(filters.document)
def document_handler(client, message):
    """
    Process image files sent as documents to extract and display EXIF data.
    """
    if not message.document.mime_type or not message.document.mime_type.startswith("image"):
        message.reply("**❌ Please send an image file (as a document).**")
        return

    # Show a "Processing..." message
    processing_message = message.reply("`Processing image...`")

    # Download the file to a temporary location
    file_path = message.download()
    location_details, general_exif = get_exif(file_path)
    
    # Remove the downloaded file after processing
    os.remove(file_path)
    
    final_reply = ""

    # Add location details at the top if found
    if location_details:
        final_reply += location_details + "\n\n" + ("-"*20) + "\n\n"

    # Format the general EXIF details
    if isinstance(general_exif, dict):
        header = "📸 **General EXIF Details:**\n\n"
        
        # Avoid printing huge byte strings (like MakerNote)
        exif_lines = []
        for key, value in general_exif.items():
            if isinstance(value, bytes) and len(value) > 64:
                value_str = f"({len(value)} bytes of binary data)"
            else:
                value_str = str(value)
            exif_lines.append(f"✨ **{key}:** {value_str}")

        final_reply += header + "\n".join(exif_lines)
    else:
        # If there's an error message from get_exif
        final_reply += f"**❌ {general_exif}**"

    # Edit the "Processing..." message with the final result
    if len(final_reply) > 4096:
        processing_message.edit_text("The EXIF data is too long to display. Sending as a file.")
        # If the message is too long, send it as a text file
        with open("exif_details.txt", "w", encoding="utf-8") as f:
            f.write(final_reply.replace("**", "").replace("`", "")) # Remove markdown for txt file
        message.reply_document("exif_details.txt")
        os.remove("exif_details.txt")
    else:
        # Enable web page preview for the Google Maps link
        processing_message.edit_text(final_reply, disable_web_page_preview=False)


if __name__ == "__main__":
    print("Bot is running...")
    app.run()
