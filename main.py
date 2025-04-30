from flask import Flask, request
from flask_sock import Sock
import json
import base64

app = Flask(_name_)
sock = Sock(app)

@app.route("/incoming-call", methods=["GET", "POST"])
def incoming_call():
    host = request.host
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="wss://{host}/media-stream" />
    </Connect>
</Response>"""

@sock.route("/media-stream")
def media_stream(ws):
    while True:
        data = ws.receive()
        if not data:
            break
        try:
            event = json.loads(data)
            if event["event"] == "start":
                print("🚀 Appel démarré")
            elif event["event"] == "media":
                audio = base64.b64decode(event["media"]["payload"])
                print(f"🔊 Audio reçu – {len(audio)} octets")
            elif event["event"] == "stop":
                print("🛑 Appel terminé")
                break
        except:
            print("⚠ Message non JSON")

app.run(host='0.0.0.0', port=3000)