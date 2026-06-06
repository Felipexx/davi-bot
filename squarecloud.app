DISPLAY_NAME=Davi Bot
DESCRIPTION=Bot do WhatsApp do Davi (FastAPI + Gemini)
MAIN=app.py
START=uvicorn app:app --host 0.0.0.0 --port 80
MEMORY=512
VERSION=recommended
AUTORESTART=true
SUBDOMAIN=davi-bot
