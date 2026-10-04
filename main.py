import os,hmac,hashlib,json,time,urllib.parse,uuid
from pathlib import Path
from fastapi import FastAPI,HTTPException,Header,UploadFile,File
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv
from .db import db,init_db,get_settings,set_setting
load_dotenv(); init_db()
BASE=Path(__file__).resolve().parent.parent; FRONT=BASE/"frontend"; UP=BASE/"uploads"; UP.mkdir(exist_ok=True)
TOKEN=os.getenv("BOT_TOKEN",""); ADM={int(x) for x in os.getenv("ADMIN_IDS","").split(",") if x.strip().isdigit()}
app=FastAPI(title="Chicken Money")
def verify(s):
    if not s or not TOKEN: raise HTTPException(401,"Telegram auth sozlanmagan.")
    d=dict(urllib.parse.parse_qsl(s,keep_blank_values=True)); rh=d.pop("hash",None)
    if not rh: raise HTTPException(401,"Hash topilmadi.")
    if time.time()-int(d.get("auth_date","0"))>86400: raise HTTPException(401,"Sessiya eskirgan.")
    check="\n".join(f"{k}={d[k]}" for k in sorted(d)); secret=hmac.new(b"WebAppData",TOKEN.encode(),hashlib.sha256).digest()
    if not hmac.compare_digest(hmac.new(secret,check.encode(),hashlib.sha256).hexdigest(),rh): raise HTTPException(401,"Telegram signature noto‘g‘ri.")
    u=json.loads(d.get("user","{}"))
    if not u.get("id"): raise HTTPException(401,"User topilmadi.")
    return u
def user(init):
    u=verify(init)
    with db() as c:
        r=c.execute("SELECT * FROM users WHERE telegram_id=?",(u["id"],)).fetchone()
        if not r:
            c.execute("INSERT INTO users(telegram_id,username,first_name,referral_code) VALUES(?,?,?,?)",(u["id"],u.get("username"),u.get("first_name",""),str(u["id"])))
        else:c.execute("UPDATE users SET username=?,first_name=? WHERE telegram_id=?",(u.get("username"),u.get("first_name",""),u["id"]))
        r=c.execute("SELECT * FROM users WHERE telegram_id=?",(u["id"],)).fetchone()
    if r["banned"]: raise HTTPException(403,"Akkaunt bloklangan.")
    return u,r
def admin(init):
    u,r=user(init)
    if u["id"] not in ADM: raise HTTPException(403,"Admin huquqi kerak.")
    return u,r
class Amount(BaseModel): amount_uzs:float
class Withdraw(BaseModel): amount_uzs:float; wallet:str
class Setting(BaseModel): key:str; value:str
class Decision(BaseModel): note:str=""
class Chicken(BaseModel): name:str; price:float; lifetime_days:int; eggs_per_hour:float; feed_per_hour:float; multiplier:float=1
@app.get("/")
def home(): return FileResponse(FRONT/"index.html")
@app.get("/api/me")
def me(x_telegram_init_data:str=Header(default="")):
    u,r=user(x_telegram_init_data); s=get_settings()
    with db() as c: ch=[dict(x) for x in c.execute("SELECT c.*,ct.name,ct.price,ct.lifetime_days,ct.eggs_per_hour,ct.feed_per_hour,ct.multiplier FROM chickens c JOIN chicken_types ct ON ct.id=c.chicken_type_id WHERE c.user_id=? AND c.active=1",(r["id"],))]
    return {"telegram":u,"user":dict(r),"chickens":ch,"is_admin":u["id"] in ADM,"settings":s}
@app.post("/api/eggs/sell")
def sell(x_telegram_init_data:str=Header(default="")):
    _,r=user(x_telegram_init_data); s=get_settings(); p=float(s["egg_price_uzs"])
    with db() as c:
        r=c.execute("SELECT * FROM users WHERE id=?",(r["id"],)).fetchone(); e=float(r["eggs"])
        if e<=0: raise HTTPException(400,"Sotiladigan tuxum yo‘q.")
        a=e*p;c.execute("UPDATE users SET eggs=0,balance=balance+? WHERE id=?",(a,r["id"]));c.execute("INSERT INTO transactions(user_id,type,amount,note) VALUES(?,?,?,?)",(r["id"],"egg_sale",a,f"{e:g} eggs"))
    return {"ok":True,"sold_eggs":e,"credited_uzs":a}
@app.post("/api/deposits")
def deposit(x:Amount,x_telegram_init_data:str=Header(default="")):
    _,r=user(x_telegram_init_data);s=get_settings();a=float(x.amount_uzs)
    if not float(s["min_deposit_uzs"])<=a<=float(s["max_deposit_uzs"]): raise HTTPException(400,"Depozit limiti noto‘g‘ri.")
    with db() as c:
        cur=c.execute("INSERT INTO deposits(user_id,amount_uzs,asset,network,wallet) VALUES(?,?,?,?,?)",(r["id"],a,s["deposit_asset"],s["deposit_network"],s["deposit_wallet"]))
    return {"id":cur.lastrowid,"status":"pending","amount":a,"wallet":s["deposit_wallet"],"asset":s["deposit_asset"],"network":s["deposit_network"]}
@app.post("/api/deposits/{did}/screenshot")
async def screenshot(did:int,file:UploadFile=File(...),x_telegram_init_data:str=Header(default="")):
    _,r=user(x_telegram_init_data)
    with db() as c: d=c.execute("SELECT * FROM deposits WHERE id=? AND user_id=?",(did,r["id"])).fetchone()
    if not d: raise HTTPException(404,"Deposit topilmadi.")
    ext=Path(file.filename or "").suffix.lower()
    if ext not in {".jpg",".jpeg",".png",".webp"}: raise HTTPException(400,"Rasm formati noto‘g‘ri.")
    data=await file.read()
    if len(data)>8*1024*1024: raise HTTPException(400,"Rasm 8 MB dan katta.")
    name=f"deposit_{did}_{uuid.uuid4().hex}{ext}";(UP/name).write_bytes(data)
    with db() as c:c.execute("UPDATE deposits SET screenshot_path=? WHERE id=?",(name,did))
    return {"ok":True,"filename":name}
@app.post("/api/withdrawals")
def withdrawal(x:Withdraw,x_telegram_init_data:str=Header(default="")):
    _,r=user(x_telegram_init_data);s=get_settings();a=float(x.amount_uzs);w=x.wallet.strip()
    if not float(s["min_withdraw_uzs"])<=a<=float(s["max_withdraw_uzs"]): raise HTTPException(400,"Withdrawal limiti noto‘g‘ri.")
    fee=a*float(s["withdraw_commission_pct"])/100;p=a-fee
    with db() as c:
        r=c.execute("SELECT * FROM users WHERE id=?",(r["id"],)).fetchone()
        if r["balance"]<a: raise HTTPException(400,"Balans yetarli emas.")
        c.execute("UPDATE users SET balance=balance-? WHERE id=?",(a,r["id"]))
        c.execute("INSERT INTO withdrawals(user_id,amount_uzs,commission_pct,commission_uzs,payout_uzs,asset,network,wallet) VALUES(?,?,?,?,?,?,?,?)",(r["id"],a,s["withdraw_commission_pct"],fee,p,s["deposit_asset"],s["deposit_network"],w))
    return {"ok":True,"amount":a,"commission":fee,"payout":p}
@app.get("/api/chickens")
def chickens():
    with db() as c:return [dict(x) for x in c.execute("SELECT * FROM chicken_types WHERE active=1 ORDER BY price")]
@app.post("/api/chickens/{cid}/buy")
def buy(cid:int,x_telegram_init_data:str=Header(default="")):
    _,r=user(x_telegram_init_data)
    with db() as c:
        ch=c.execute("SELECT * FROM chicken_types WHERE id=? AND active=1",(cid,)).fetchone();r=c.execute("SELECT * FROM users WHERE id=?",(r["id"],)).fetchone()
        if not ch: raise HTTPException(404,"Tovuq topilmadi.")
        if r["balance"]<ch["price"]: raise HTTPException(400,"Balans yetarli emas.")
        c.execute("UPDATE users SET balance=balance-? WHERE id=?",(ch["price"],r["id"]));c.execute("INSERT INTO chickens(user_id,chicken_type_id) VALUES(?,?)",(r["id"],cid))
    return {"ok":True}
@app.get("/api/admin/settings")
def a_settings(x_telegram_init_data:str=Header(default="")): admin(x_telegram_init_data);return get_settings()
@app.post("/api/admin/settings")
def a_setting(x:Setting,x_telegram_init_data:str=Header(default="")):
    u,_=admin(x_telegram_init_data);allowed={"egg_price_uzs","min_deposit_uzs","max_deposit_uzs","min_withdraw_uzs","max_withdraw_uzs","withdraw_commission_pct","deposit_wallet","deposit_asset","deposit_network","daily_bonus_uzs","referral_pct","egg_storage_limit"}
    if x.key not in allowed: raise HTTPException(400,"Setting ruxsat etilmagan.")
    set_setting(x.key,x.value)
    with db() as c:c.execute("INSERT INTO admin_logs(admin_telegram_id,action,target,details) VALUES(?,?,?,?)",(u["id"],"setting_update",x.key,x.value))
    return {"ok":True}
@app.get("/api/admin/chickens")
def a_chickens(x_telegram_init_data:str=Header(default="")):
    admin(x_telegram_init_data)
    with db() as c:return [dict(x) for x in c.execute("SELECT * FROM chicken_types ORDER BY id DESC")]
@app.post("/api/admin/chickens")
def a_chicken(x:Chicken,x_telegram_init_data:str=Header(default="")):
    u,_=admin(x_telegram_init_data)
    with db() as c:
        cur=c.execute("INSERT INTO chicken_types(name,price,lifetime_days,eggs_per_hour,feed_per_hour,multiplier) VALUES(?,?,?,?,?,?)",(x.name,x.price,x.lifetime_days,x.eggs_per_hour,x.feed_per_hour,x.multiplier));c.execute("INSERT INTO admin_logs(admin_telegram_id,action,target,details) VALUES(?,?,?,?)",(u["id"],"chicken_create",str(cur.lastrowid),x.name))
    return {"ok":True,"id":cur.lastrowid}
@app.get("/api/admin/deposits")
def a_deposits(x_telegram_init_data:str=Header(default="")):
    admin(x_telegram_init_data)
    with db() as c:return [dict(x) for x in c.execute("SELECT d.*,u.telegram_id,u.username,u.first_name FROM deposits d JOIN users u ON u.id=d.user_id ORDER BY d.id DESC LIMIT 200")]
@app.post("/api/admin/deposits/{did}/approve")
def approve(did:int,x:Decision,x_telegram_init_data:str=Header(default="")):
    u,_=admin(x_telegram_init_data)
    with db() as c:
        d=c.execute("SELECT * FROM deposits WHERE id=?",(did,)).fetchone()
        if not d or d["status"]!="pending": raise HTTPException(400,"Deposit mavjud emas yoki ko‘rilgan.")
        c.execute("UPDATE deposits SET status='approved',admin_note=?,reviewed_at=CURRENT_TIMESTAMP WHERE id=?",(x.note,did));c.execute("UPDATE users SET balance=balance+? WHERE id=?",(d["amount_uzs"],d["user_id"]));c.execute("INSERT INTO transactions(user_id,type,amount,note) VALUES(?,?,?,?)",(d["user_id"],"deposit",d["amount_uzs"],f"Deposit #{did}"));c.execute("INSERT INTO admin_logs(admin_telegram_id,action,target,details) VALUES(?,?,?,?)",(u["id"],"deposit_approve",str(did),x.note))
    return {"ok":True}
@app.post("/api/admin/deposits/{did}/reject")
def reject(did:int,x:Decision,x_telegram_init_data:str=Header(default="")):
    u,_=admin(x_telegram_init_data)
    with db() as c:
        d=c.execute("SELECT * FROM deposits WHERE id=?",(did,)).fetchone()
        if not d or d["status"]!="pending": raise HTTPException(400,"Deposit mavjud emas yoki ko‘rilgan.")
        c.execute("UPDATE deposits SET status='rejected',admin_note=?,reviewed_at=CURRENT_TIMESTAMP WHERE id=?",(x.note,did));c.execute("INSERT INTO admin_logs(admin_telegram_id,action,target,details) VALUES(?,?,?,?)",(u["id"],"deposit_reject",str(did),x.note))
    return {"ok":True}
@app.get("/api/admin/withdrawals")
def a_withdrawals(x_telegram_init_data:str=Header(default="")):
    admin(x_telegram_init_data)
    with db() as c:return [dict(x) for x in c.execute("SELECT w.*,u.telegram_id,u.username,u.first_name FROM withdrawals w JOIN users u ON u.id=w.user_id ORDER BY w.id DESC LIMIT 200")]
@app.post("/api/admin/withdrawals/{wid}/approve")
def aw_approve(wid:int,x:Decision,x_telegram_init_data:str=Header(default="")):
    u,_=admin(x_telegram_init_data)
    with db() as c:
        w=c.execute("SELECT * FROM withdrawals WHERE id=?",(wid,)).fetchone()
        if not w or w["status"]!="pending": raise HTTPException(400,"Withdrawal mavjud emas yoki ko‘rilgan.")
        c.execute("UPDATE withdrawals SET status='approved',admin_note=?,reviewed_at=CURRENT_TIMESTAMP WHERE id=?",(x.note,wid));c.execute("INSERT INTO admin_logs(admin_telegram_id,action,target,details) VALUES(?,?,?,?)",(u["id"],"withdraw_approve",str(wid),x.note))
    return {"ok":True}
@app.post("/api/admin/withdrawals/{wid}/reject")
def aw_reject(wid:int,x:Decision,x_telegram_init_data:str=Header(default="")):
    u,_=admin(x_telegram_init_data)
    with db() as c:
        w=c.execute("SELECT * FROM withdrawals WHERE id=?",(wid,)).fetchone()
        if not w or w["status"]!="pending": raise HTTPException(400,"Withdrawal mavjud emas yoki ko‘rilgan.")
        c.execute("UPDATE users SET balance=balance+? WHERE id=?",(w["amount_uzs"],w["user_id"]));c.execute("UPDATE withdrawals SET status='rejected',admin_note=?,reviewed_at=CURRENT_TIMESTAMP WHERE id=?",(x.note,wid));c.execute("INSERT INTO transactions(user_id,type,amount,note) VALUES(?,?,?,?)",(w["user_id"],"withdrawal_refund",w["amount_uzs"],f"Withdrawal #{wid} rejected"));c.execute("INSERT INTO admin_logs(admin_telegram_id,action,target,details) VALUES(?,?,?,?)",(u["id"],"withdraw_reject",str(wid),x.note))
    return {"ok":True}
app.mount("/assets",StaticFiles(directory=FRONT),name="assets");app.mount("/uploads",StaticFiles(directory=UP),name="uploads")
