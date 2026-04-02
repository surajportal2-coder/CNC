from flask import Flask, render_template, request, jsonify
from instagrapi import Client
import threading
import time
import random
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = "sujal_final"

state = {"running": False, "sent": 0, "logs": [], "start_time": None}
cfg = {
    "sessionid": "",
    "messages": [],
    "group_name": "",
    "delay": 25,        # Messages ke beech
    "cycle": 35,        # Har kitne messages ke baad NC + Break
    "break_sec": 40,    # Cycle ke baad break
    "group_delay": 5    # Ek GC se dusre GC mein delay
}

def log(msg):
    entry = f"[{time.strftime('%H:%M:%S')}] {msg}"
    state["logs"].append(entry)
    if len(state["logs"]) > 500:
        state["logs"] = state["logs"][-500:]

def bomber():
    cl = Client()
    cl.delay_range = [8, 30]
    
    try:
        cl.login_by_sessionid(cfg["sessionid"])
        log("✅ LOGIN SUCCESS")
    except Exception as e:
        log(f"❌ LOGIN FAILED → {str(e)[:80]}")
        return

    sent_in_cycle = 0
    while state["running"]:
        try:
            # Fetch all groups
            threads = cl.direct_threads(amount=100)
            groups = [t for t in threads if getattr(t, "is_group", False)]
            
            if not groups:
                log("⚠ No groups found, retrying in 30s...")
                time.sleep(30)
                continue

            log(f"🔄 Found {len(groups)} groups - Starting rotation")

            for thread in groups:
                if not state["running"]: 
                    break
                
                gid = thread.id
                title = thread.thread_title or "Unknown Group"

                # Send Message
                msg = random.choice(cfg["messages"])
                try:
                    cl.direct_send(msg, thread_ids=[gid])
                    sent_in_cycle += 1
                    state["sent"] += 1
                    log(f"📨 SENT to → {title}")
                except Exception as e:
                    log(f"⚠ FAILED in {title} → {str(e)[:50]}")   # Fail hone par bhi continue

                # Group Switch Delay
                time.sleep(cfg["group_delay"] + random.uniform(1, 3))

            # Name Change + Break after full cycle
            if sent_in_cycle >= cfg["cycle"] and cfg["group_name"]:
                new_name = f"{cfg['group_name']} → {datetime.now().strftime('%I:%M:%S %p')}"
                for thread in groups:
                    try:
                        cl.direct_thread_change_title(thread.id, new_name)
                        log(f"💠 NAME CHANGE → {new_name}")
                    except:
                        pass
                log(f"⏳ BREAK {cfg['break_sec']} SECONDS")
                time.sleep(cfg["break_sec"])
                sent_in_cycle = 0

            time.sleep(cfg["delay"])

        except Exception as e:
            log(f"⚠ Loop Error: {str(e)[:60]}")
            time.sleep(20)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/start", methods=["POST"])
def start():
    global state
    state["running"] = False
    time.sleep(0.5)

    state = {"running": True, "sent": 0, "logs": ["🚀 BOT STARTED"], "start_time": time.time()}

    cfg["sessionid"] = request.form.get("sessionid", "").strip()
    
    # Single full message (pura textarea ek hi message)
    raw_text = request.form["messages"].strip()
    cfg["messages"] = [raw_text] if raw_text else []

    cfg["group_name"] = request.form.get("group_name", "").strip()
    cfg["delay"] = float(request.form.get("delay", "25"))
    cfg["cycle"] = int(request.form.get("cycle", "35"))
    cfg["break_sec"] = int(request.form.get("break_sec", "40"))
    cfg["group_delay"] = int(request.form.get("group_delay", "5"))

    threading.Thread(target=bomber, daemon=True).start()
    log("BOT STARTED - Rotating through all groups")
    return jsonify({"ok": True})

@app.route("/stop", methods=["POST"])
def stop():
    state["running"] = False
    log("⛔ STOPPED BY USER")
    return jsonify({"ok": True})

@app.route("/status")
def status():
    uptime = "00:00:00"
    if state.get("start_time"):
        t = int(time.time() - state["start_time"])
        h, r = divmod(t, 3600)
        m, s = divmod(r, 60)
        uptime = f"{h:02d}:{m:02d}:{s:02d}"
    return jsonify({
        "running": state["running"],
        "sent": state["sent"],
        "uptime": uptime,
        "logs": state["logs"][-100:]
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
