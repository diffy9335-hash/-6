import os, time, hashlib, hmac, json, logging, threading
from urllib.parse import parse_qsl, urlencode
from urllib.request import urlopen
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from game import db, init, state, act

TOKEN=os.getenv("BOT_TOKEN","")
URL=os.getenv("APP_URL","").rstrip("/")
DEMO=os.getenv("DEMO_MODE")=="1" and not TOKEN
def identity(raw):
    if DEMO and not raw: return 1,"Демо-игрок"
    fields=dict(parse_qsl(raw))
    sig=fields.pop("hash","")
    key=hmac.digest(b"WebAppData",TOKEN.encode(),"sha256")
    payload="\n".join(f"{k}={v}" for k,v in sorted(fields.items()))
    if not TOKEN or not hmac.compare_digest(hmac.digest(key,payload.encode(),"sha256").hex(),sig): raise PermissionError
    if not 0<=time.time()-int(fields["auth_date"])<=86400: raise PermissionError
    u=json.loads(fields["user"])
    return int(u["id"]),u["first_name"]

def telegram(method,params):
    with urlopen("https://api.telegram.org/bot"+TOKEN+"/"+method,urlencode(params).encode(),timeout=40) as r:
        return json.load(r)["result"]
def poll():
    offset=0
    while True:
        try:
            for upd in telegram("getUpdates",dict(offset=offset,timeout=25)):
                m=upd.get("message",{})
                if m.get("chat",{}).get("type")=="private" and m.get("text","").split("@")[0]=="/start":
                    kb={"inline_keyboard":[[{"text":"Открыть VELTON","web_app":{"url":URL}}]]}
                    telegram("sendMessage",dict(chat_id=m["chat"]["id"],text="Твоя карьера в футболе начинается здесь.",reply_markup=json.dumps(kb)))
                offset=upd["update_id"]+1
        except Exception:
            logging.warning("Telegram polling unavailable, retrying")
            time.sleep(5)

class Handler(BaseHTTPRequestHandler):
    def reply(self,code,data,kind="application/json"):
        body=data if isinstance(data,bytes) else json.dumps(data,ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type",kind+"; charset=utf-8")
        self.send_header("Content-Length",str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def do_GET(self):
        if self.path.split("?")[0]=="/": return self.reply(200,Path(__file__).with_name("index.html").read_bytes(),"text/html")
        if self.path=="/health": return self.reply(200,{"ok":True})
        self.reply(404,{})
    def do_POST(self):
        if self.path!="/api": return self.reply(404,{})
        try:
            size=int(self.headers.get("Content-Length",0))
            if not 0<size<=16384: raise ValueError("Некорректный запрос")
            d=json.loads(self.rfile.read(size))
            uid,name=identity(d.get("auth",""))
            with db() as c:
                if d.get("action")!="state": act(c,uid,d)
                data=state(c,uid)
            self.reply(200,dict(data,username=name))
        except PermissionError: self.reply(403,{"error":"Открой приложение кнопкой в Telegram-боте"})
        except (ValueError,KeyError,TypeError,AttributeError) as e: self.reply(400,{"error":str(e)})
if __name__=="__main__":
    init()
    server=ThreadingHTTPServer(("0.0.0.0",3000),Handler)
    if TOKEN and URL.startswith("https://"): threading.Thread(target=poll,daemon=True).start()
    server.serve_forever()
