
import os
import json
import base64
import asyncio
import websockets
from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.websockets import WebSocketDisconnect
from twilio.twiml.voice_response import VoiceResponse, Connect, Stream
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PORT = int(os.getenv("PORT", 3000))  # Replit uses port 3000

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY is not set in the .env file")

app = FastAPI()

SYSTEM_MESSAGE = (
    "Vous êtes un agent immobilier AI joyeux et serviable spécialisé dans la location d'appartements cosy et abordables."
)

@app.get("/", response_class=JSONResponse)
async def index_page():
    return {"message": "Twilio Media Stream Server is running!"}

@app.api_route("/incoming-call", methods=["GET", "POST"])
async def handle_incoming_call(request: Request):
    print("✅ Twilio vient d'appeler /incoming-call")
    host = request.url.hostname or request.client.host
    response = VoiceResponse()
    connect = Connect()
    connect.stream(url=f"wss://{host}/media-stream")
    response.append(connect)
    return HTMLResponse(content=str(response), media_type="application/xml")

@app.websocket("/media-stream")
async def media_stream(websocket: WebSocket):
    await websocket.accept()
    print("✅ WebSocket Twilio connecté")

    try:
        while True:
            message = await websocket.receive_text()
            data = json.loads(message)

            if data.get("event") == "start":
                print(f"🚀 Stream démarré – callSid = {data['start']['callSid']}")
            elif data.get("event") == "media":
                payload = data["media"]["payload"]
                audio_bytes = base64.b64decode(payload)
                # Here we should make an HTTP POST request to OpenAI's API
                # using aiohttp or httpx for the actual implementation
                print(f"🔊 Audio reçu – {len(audio_bytes)} octets")
            elif data.get("event") == "stop":
                print("🛑 Stream terminé")
                break
    except WebSocketDisconnect:
        print("❌ WebSocket Twilio déconnecté")
    except Exception as e:
        print(f"❌ Erreur dans la WebSocket : {e}")
    finally:
        await websocket.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=PORT)
