import random
import sqlite3
import os
from pathlib import Path

ROLES = {
    "Игрок": [("Пробить по воротам", "Голы", .45), ("Отдать голевой пас", "Ассисты", .6)],
    "Тренер": [("Сыграть в прессинг", "Победы", .55), ("Удержать ничью", "Ничьи", .82)],
    "Судья": [("Оценить контакт", "Верные решения", 1), ("Проверить офсайд", "Верные решения", 1)],
    "Агент": [("Обсудить трансфер", "Трансферы", .45), ("Продлить контракт", "Продления", .75)],
    "Свой клуб": [("Развивать академию", "Воспитанники", .7), ("Искать партнёра", "Спонсоры", .5)]
}
AWARDS = dict(zip(ROLES, ["Точный удар", "Первая победа", "По правилам", "Первая сделка", "Свой фундамент"]))
def db():
    path = Path(os.getenv("DB_PATH","data/velton.sqlite"))
    path.parent.mkdir(parents=True,exist_ok=True)
    con = sqlite3.connect(path,timeout=10)
    con.row_factory = sqlite3.Row
    return con

def init():
    with db() as c:
        c.executescript("""CREATE TABLE IF NOT EXISTS careers(uid INTEGER,slot INTEGER CHECK(slot BETWEEN 1 AND 5),role TEXT,name TEXT,turn INTEGER DEFAULT 0,points INTEGER DEFAULT 0,stats TEXT DEFAULT '{}',log TEXT DEFAULT '', PRIMARY KEY(uid,slot));
        CREATE TABLE IF NOT EXISTS awards(uid INTEGER,title TEXT,PRIMARY KEY(uid,title));""")

import json
def state(c, uid):
    return dict(careers=[dict(r,stats=json.loads(r["stats"])) for r in c.execute("SELECT * FROM careers WHERE uid=? ORDER BY slot",(uid,))],
                awards=[r[0] for r in c.execute("SELECT title FROM awards WHERE uid=? ORDER BY title",(uid,))], roles={k:[v[0] for v in a] for k,a in ROLES.items()}, trophies=AWARDS)

def act(c, uid, d):
    slot=d.get("slot")
    if type(slot)!=int or not 1<=slot<=5: raise ValueError("Выбери слот от 1 до 5")
    c.execute("BEGIN IMMEDIATE")
    row=c.execute("SELECT * FROM careers WHERE uid=? AND slot=?",(uid,slot)).fetchone()
    if d.get("action")=="create":
        name=str(d.get("name","")).strip()
        role=d.get("role")
        if row or role not in ROLES or not 1<=len(name)<=40: raise ValueError("Проверь свободный слот, роль и название")
        c.execute("INSERT INTO careers(uid,slot,role,name) VALUES(?,?,?,?)",(uid,slot,role,name))
        return
    if not row or d.get("turn")!=row["turn"]: raise ValueError("Карьера изменилась. Обнови страницу")
    idx=d.get("choice")
    if d.get("action")!="play" or type(idx)!=int or idx not in (0,1): raise ValueError("Выбери действие")
    role=row["role"]
    label,stat,chance=ROLES[role][idx]
    ok=random.random()<chance
    if role=="Судья":
        ok=idx==row["turn"]%2
        log=("Решение верное" if ok else "Инспектор отметил ошибку")
    else:
        log=label+" · "+("Успех" if ok else "Попытка не удалась")
    stats=json.loads(row["stats"])
    if ok:
        stats[stat]=stats.get(stat,0)+1
        if idx==0 or role in ("Агент","Судья","Свой клуб"):
            c.execute("INSERT OR IGNORE INTO awards VALUES(?,?)",(uid,AWARDS[role]))
    c.execute("UPDATE careers SET turn=turn+1,points=points+?,stats=?,log=? WHERE uid=? AND slot=?",(3 if ok else 0,json.dumps(stats),log,uid,slot))
