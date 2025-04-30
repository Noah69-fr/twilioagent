
import os
import json
import base64
import asyncio
import aiohttp
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
    response.say("Bonjour! Je suis votre agent immobilier virtuel. Comment puis-je vous aider aujourd'hui?", language="fr-FR")
    connect = Connect()
    connect.stream(url=f"wss://{host}/media-stream")
    response.append(connect)
    return HTMLResponse(content=str(response), media_type="application/xml")

@app.websocket("/media-stream")
async def media_stream(websocket: WebSocket):
    await websocket.accept()
    print("✅ WebSocket Twilio connecté")

    audio_buffer = b""
    
    async def process_audio_and_respond():
        nonlocal audio_buffer
        if len(audio_buffer) < 4000:  # Wait for enough audio data
            return
            
        # Convert audio to file-like object
        audio_data = audio_buffer
        audio_buffer = b""  # Reset buffer
        
        # Transcribe with Whisper API
        async with aiohttp.ClientSession() as session:
            # First, transcribe the audio
            headers = {
                "Authorization": f"Bearer {OPENAI_API_KEY}"
            }
            data = aiohttp.FormData()
            data.add_field('file', audio_data, filename='audio.wav', content_type='audio/wav')
            data.add_field('model', 'whisper-1')
            data.add_field('language', 'fr')
            
            async with session.post('https://api.openai.com/v1/audio/transcriptions', headers=headers, data=data) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    user_text = result.get('text', '')
                    print(f"🎤 Transcription: {user_text}")
                    
                    if user_text.strip():
                        # Get AI response
                        chat_data = {
                            "model": "gpt-3.5-turbo",
                            "messages": [
                                {"role": "system", "content": SYSTEM_MESSAGE},
                                {"role": "user", "content": user_text}
                            ]
                        }
                        
                        async with session.post('https://api.openai.com/v1/chat/completions', headers=headers, json=chat_data) as chat_resp:
                            if chat_resp.status == 200:
                                chat_result = await chat_resp.json()
                                ai_response = chat_result['choices'][0]['message']['content']
                                print(f"🤖 Réponse: {ai_response}")
                                
                                # Send response back to user
                                response = VoiceResponse()
                                response.say(ai_response, language="fr-FR")
                                await websocket.send_text(str(response))

    try:
        while True:
            message = await websocket.receive_text()
            data = json.loads(message)

            if data.get("event") == "start":
                print(f"🚀 Stream démarré – callSid = {data['start']['callSid']}")
            elif data.get("event") == "media":
                payload = data["media"]["payload"]
                audio_bytes = base64.b64decode(payload)
                audio_buffer += audio_bytes
                await process_audio_and_respond()
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
