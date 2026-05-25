from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import random, asyncio, os
from typing import Dict, Any
import json
from openai import AsyncOpenAI

# 1. Fetch your tunnel proxy target
base_url = os.environ.get("OLLAMA_PROXY_URL", "http://localhost:11434/v1")
# 2. Fetch your IP password string from your Render configurations
tunnel_password = os.environ.get("LOCALTUNNEL_PASSWORD", "")

ai_client = AsyncOpenAI(
    base_url=base_url,
    api_key="ollama",  # Required placeholder string
    default_headers={
        "Bypass-Tunnel-Reminder": "true",
        "Authorization": f"Bearer {tunnel_password}" if tunnel_password else ""
    }
)

zone_router = APIRouter(prefix="/zone", tags=["Zone Defense"])

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
templates = Jinja2Templates(directory=os.path.join(base_dir, "templates"))

# --- Configuration ---
ADJACENCY = {
    "A":   ["AB", "AC"],
    "B":   ["AB", "BC"],
    "C":   ["AC", "BC"],
    "AB":  ["A", "B", "ABC"],
    "BC":  ["B", "C", "ABC"],
    "AC":  ["A", "C", "ABC"],
    "ABC": ["AB", "BC", "AC"]
}

MAX_STAY_TIME = 8  # Seconds before sector exhaustion penalty

# --- Game State ---
zone_dots: Dict[str, int] = {z: 0 for z in ADJACENCY}
players:   Dict[str, Any] = {}
state      = {"active": True}
_game_task = None


async def broadcast(data: dict):
    dead = []
    for pid, p in list(players.items()):
        try:
            await p["ws"].send_json(data)
        except Exception:
            dead.append(pid)
    for pid in dead:
        players.pop(pid, None)


async def get_leaderboard():
    return sorted(
        [{"name": p["name"], "score": p["score"], "zone": p["zone"]}
         for p in players.values()],
        key=lambda x: x["score"], reverse=True
    )


async def game_loop():
    tick_count = 0
    while state["active"]:
        await asyncio.sleep(1.0)
        tick_count += 1
        current_time = asyncio.get_event_loop().time()

        if not players:
            continue

        # 1. Spawn threat every 5 ticks
        spawn_msg = None
        if tick_count % 5 == 0:
            spawn_zone = random.choice(list(ADJACENCY.keys()))
            zone_dots[spawn_zone] += 1
            spawn_msg = f"⚠ Threat spawned in {spawn_zone}."

        # 2. Sector exhaustion — check every second
        for pid, p in list(players.items()):
            if "entered_at" not in p:
                p["entered_at"] = current_time
                continue
            if current_time - p["entered_at"] > MAX_STAY_TIME:
                p["score"]     = max(0, p["score"] - 5)
                old_zone       = p["zone"]
                new_zone       = random.choice(ADJACENCY[old_zone])
                p["zone"]      = new_zone
                p["entered_at"] = current_time
                try:
                    await p["ws"].send_json({
                        "type":      "move_reject",
                        "your_zone": new_zone,
                        "msg":       f"⛔ SECTOR EXHAUSTION! Forced out of {old_zone} (-5 pts)"
                    })
                except Exception:
                    pass

        # 3. Punish + broadcast every 5 ticks
        final_msg = spawn_msg
        if tick_count % 5 == 0:
            max_dots = max(zone_dots.values())
            if max_dots > 0:
                hot_zones = [z for z, d in zone_dots.items() if d == max_dots]
                punished  = 0
                for p in players.values():
                    if p["zone"] in hot_zones:
                        p["score"] = max(0, p["score"] - 3)
                        punished  += 1
                if punished > 0:
                    final_msg = f"🔥 {punished} operative(s) hit in {', '.join(hot_zones)}! (-3 pts)"

        # --- 4. TACTICAL AI COGNITION WAVE (Every 20 seconds) ---
        if tick_count % 20 == 0:
            # Using create_task pushes the API processing completely into the background,
            # ensuring that movement registers and dot counts never experience latency.
            asyncio.create_task(fetch_tactical_advice())

        await broadcast({
            "type":        "tick",
            "zones":       zone_dots,
            "msg":         final_msg,
            "leaderboard": await get_leaderboard()
        })


async def fetch_tactical_advice():
    """Reads the current game grid data, prompts the local model, and broadcasts its response."""
    if not players:
        return

    # 1. Map out active operator locations and current points
    active_operators = [
        f"{p['name']} in Sector {p['zone']} (Score: {p['score']})"
        for p in players.values()
    ]

    # 2. Build the live data string for your model context
    prompt = (
        f"--- LIVE GRID METRICS ---\n"
        f"Sector Threat Clusters (Dots): {json.dumps(zone_dots)}\n"
        f"Operative Coordinates: {', '.join(active_operators)}\n\n"
        f"Instructions: You are the central tactical AI core. Provide ONE short, aggressive, "
        f"military sci-fi directive to the operatives based on this layout. "
        f"Keep it under 20 words maximum. Be direct."
    )

    try:
        # Request inference asynchronously so your home loop never stutters
        response = await ai_client.chat.completions.create(
            model="qwen2.5:3b",
            messages=[
                {"role": "system",
                 "content": "You are a tactical military AI overseer inside a sci-fi defense system."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=40,
            timeout=4.0
        )

        ai_message = response.choices[0].message.content.strip()

        # 3. Stream the output globally using your existing chat packet structure
        await broadcast({
            "type": "chat_message",
            "sender": "🤖 COCHISE_AI",
            "msg": ai_message
        })

    except Exception as e:
        print(f"Tactical AI Stream Exception: {e}")


def ensure_game_loop():
    global _game_task
    if _game_task is None or _game_task.done():
        _game_task = asyncio.create_task(game_loop())


# --- Routes ---
@zone_router.get("/", response_class=HTMLResponse)
async def get_ui(request: Request):
    ensure_game_loop()
    return templates.TemplateResponse(
        request=request, name="zone/index.html", context={}
    )


@zone_router.websocket("/ws")
async def zone_socket(ws: WebSocket):
    await ws.accept()
    ensure_game_loop()

    pid = str(random.randint(1000, 9999))

    try:
        data       = await ws.receive_json()
        start_zone = random.choice(list(ADJACENCY.keys()))
        players[pid] = {
            "name":       data.get("name", "Anon"),
            "zone":       start_zone,
            "score":      15,
            "ws":         ws,
            "entered_at": asyncio.get_event_loop().time()
        }

        await ws.send_json({
            "type":        "init",
            "your_zone":   start_zone,
            "zones":       zone_dots,
            "leaderboard": await get_leaderboard()
        })
        await broadcast({
            "type":        "leaderboard",
            "leaderboard": await get_leaderboard(),
            "zones":       zone_dots
        })

        while True:
            cmd = await ws.receive_json()
            p   = players[pid]

            # ── MOVE ──────────────────────────────────────────────────────────
            if cmd["type"] == "move":
                target = cmd.get("target", "")

                # FIX: validate BEFORE touching p["zone"]
                if target not in ADJACENCY:
                    await ws.send_json({
                        "type":      "move_reject",
                        "your_zone": p["zone"],
                        "msg":       f"Unknown zone '{target}'."
                    })
                    continue

                if target == p["zone"]:
                    continue  # already here, no-op

                if target not in ADJACENCY[p["zone"]]:
                    await ws.send_json({
                        "type":      "move_reject",
                        "your_zone": p["zone"],
                        "msg":       f"⛔ {target} is not adjacent to {p['zone']}."
                    })
                    continue

                # Only update state after validation passes
                p["zone"]       = target
                p["entered_at"] = asyncio.get_event_loop().time()
                await ws.send_json({
                    "type":      "move_confirm",
                    "your_zone": target,
                    "msg":       f"Moved to sector {target}."
                })

            # ── PUSH DOT ──────────────────────────────────────────────────────
            elif cmd["type"] == "push_dot":
                frm    = cmd.get("from", p["zone"])
                target = cmd.get("to", "")

                if frm != p["zone"]:
                    await ws.send_json({"type": "push_reject", "msg": "Can only push from your own zone."})
                    continue
                if target not in ADJACENCY.get(frm, []):
                    await ws.send_json({"type": "push_reject", "msg": f"⛔ {target} is not adjacent to {frm}."})
                    continue
                if zone_dots[frm] <= 0:
                    await ws.send_json({"type": "push_reject", "msg": f"No threats in {frm} to push."})
                    continue

                zone_dots[frm]    = max(0, zone_dots[frm] - 1)
                zone_dots[target] += 1
                p["score"]        += 1

            # ── CHAT ──────────────────────────────────────────────────────────
            elif cmd["type"] == "chat":
                chat_msg = cmd.get("msg", "").strip()
                if chat_msg:
                    await broadcast({
                        "type":   "chat_message",
                        "sender": p["name"],
                        "msg":    chat_msg[:100]   # truncate server-side
                    })
                continue  # chat doesn't trigger a zone state broadcast

            # ── STATE BROADCAST (move + push only reach here) ─────────────────
            await broadcast({
                "type":        "update",
                "zones":       zone_dots,
                "leaderboard": await get_leaderboard(),
                "msg":         None
            })

    except WebSocketDisconnect:
        players.pop(pid, None)
        await broadcast({
            "type":        "leaderboard",
            "leaderboard": await get_leaderboard(),
            "zones":       zone_dots,
            "msg":         None
        })
    except Exception:
        players.pop(pid, None)
