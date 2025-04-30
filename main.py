
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
PORT = int(os.getenv("PORT", 3000))
VOICE = 'alloy'
LOG_EVENT_TYPES = [
    'response.content.done', 'rate_limits.updated', 'response.done',
    'input_audio_buffer.committed', 'input_audio_buffer.speech_stopped',
    'input_audio_buffer.speech_started', 'session.created'
]

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

async def call_openai_api(endpoint, method, headers, data=None, files=None):
    import aiohttp
    url = f"https://api.openai.com{endpoint}"
    
    async with aiohttp.ClientSession() as session:
        if files:
            form = aiohttp.FormData()
            for key, value in files.items():
                if key == 'file':
                    form.add_field('file', value, filename='audio.wav', content_type='audio/wav')
                else:
                    form.add_field(key, str(value))
            async with session.post(url, headers=headers, data=form) as response:
                return await response.json()
        else:
            async with session.post(url, headers=headers, json=data) as response:
                return await response.json()

@app.websocket("/media-stream")
async def media_stream(websocket: WebSocket):
    await websocket.accept()
    print("✅ WebSocket Twilio connecté")

    audio_buffer = b""
    
    async def process_audio_and_respond():
        nonlocal audio_buffer
        if len(audio_buffer) < 32000:  # Wait for more audio data
            return
            
        print(f"🎵 Processing audio buffer of size: {len(audio_buffer)}")
        audio_data = audio_buffer
        audio_buffer = b""
        
        # Convert audio to wav format
        import wave
        import io
        
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(8000)
            wav_file.writeframes(audio_data)
        
        wav_data = wav_buffer.getvalue()

        try:
            headers = {
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json"
            }
            
            # Transcribe audio
            transcription = await call_openai_api(
                '/v1/audio/transcriptions',
                'POST',
                headers,
                files={'file': wav_data, 'model': 'whisper-1', 'language': 'fr'}
            )
            
            user_text = transcription.get('text', '')
            async def process_audio_stream(audio_data):
                try:
                    async with websockets.connect(
                        'wss://api.openai.com/v1/audio/speech',
                        extra_headers={
                            'Authorization': f'Bearer {OPENAI_API_KEY}',
                            'Content-Type': 'audio/wav'
                        }
                    ) as ws:
                        await ws.send(audio_data)
                        async for msg in ws:
                            response = json.loads(msg)
                            if 'audio' in response:
                                await websocket.send_bytes(base64.b64decode(response['audio']))
                except Exception as e:
                    print(f"Error in audio stream: {e}")

            # Process the audio directly
            await process_audio_stream(audio_data)
            print("✅ Audio streaming complete")
        except Exception as e:
            print(f"❌ Error processing audio: {e}")

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
