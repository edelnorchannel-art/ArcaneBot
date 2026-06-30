from dotenv import load_dotenv
import os

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBDAV_URL = os.getenv("WEBDAV_URL")
WEBDAV_LOGIN = os.getenv("WEBDAV_LOGIN")
WEBDAV_PASSWORD = os.getenv("WEBDAV_PASSWORD")
CORPORATE_CHAT_ID = os.getenv("CORPORATE_CHAT_ID")