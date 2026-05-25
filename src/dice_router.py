from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import random, asyncio, json, os
from typing import Dict, Any
import time  # Add this import

dice_router = APIRouter(prefix="/dice", tags=["Dice Tag Royale"])

# Path logic for your templates
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
templates = Jinja2Templates(directory=os.path.join(base_dir, "templates"))

# --- Global State (Scoped to this router) ---
players: Dict[str, Any] = {}  # pid -> {name, tag, score, shield_active, ws}
state = {
    "turns": 0,
    "voting_active": False
}

# --- Update Global State ---
state = {
    "turns": 0,
    "voting_active": False,
    "start_time": None,
    "match_duration": 120, # 2 Minutes in seconds
    "game_over": False
}
# Add this list near your other global variables
DICE_COLORS = ["#0891b2", "#9333ea", "#e11d48", "#16a34a", "#ea580c", "#ca8a04"]

async def broadcast(data):
    # If the game is won, use the locked end_time
    if state.get("end_time"):
        data["elapsed"] = round(state["end_time"] - state["start_time"], 1)
    elif state["start_time"]:
        data["elapsed"] = round(time.time() - state["start_time"], 1)

    if state["start_time"] and not state["game_over"]:
        elapsed = time.time() - state["start_time"]
        remaining = max(0, state["match_duration"] - elapsed)
        data["remaining"] = round(remaining, 1)

        # Auto-end game if time hits zero
        if remaining <= 0:
            state["game_over"] = True
            await broadcast({"type": "game_over", "msg": "⌛ TIME IS UP!"})

    for p in list(players.values()):
        try:
            await p['ws'].send_json(data)
        except:
            pass

async def get_leaderboard():
    sorted_list = sorted(players.values(), key=lambda p: p['score'], reverse=True)
    return [{
        "name": p['name'],
        "score": p['score'],
        "tag": p['tag'],
        "shield_active": p.get('shield_active', False)
    } for p in sorted_list[:3]]

async def sabotage_countdown():
    """Handles the 10s window without blocking the home loop."""
    await asyncio.sleep(10)
    state["voting_active"] = False
    await broadcast({
        "type": "voting_ended",
        "leaderboard": await get_leaderboard(),
        "msg": "Sabotage ended! Dice back in play."
    })


# --- Routes ---

@dice_router.get("/", response_class=HTMLResponse)
async def get_dice_ui(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="dice/index.html",
        context={}
    )


@dice_router.websocket("/ws")
async def dice_socket(ws: WebSocket):
    await ws.accept()
    pid = str(random.randint(1000, 9999))

    try:
        # --- PLAYER JOIN ---
        data = await ws.receive_json()
        # Assign a random color from the list
        player_color = random.choice(DICE_COLORS)

        players[pid] = {
            "name": data["name"],
            "tag": int(data["tag"]),
            "score": 0,
            "color": player_color,  # Store the color here
            "shield_active": False,
            "ws": ws
        }
        # Send the assigned color back to the player immediately
        await ws.send_json({"type": "init", "color": player_color})

        await broadcast({"type": "msg", "text": f"⚔️ {players[pid]['name']} joined the fray!"})

        while True:
            msg = await ws.receive_json()
            roller = players[pid]

            # --- 1. REPAIR LOGIC (Roll during Sabotage) ---
            if msg["type"] == "roll" and state["voting_active"]:
                if not roller.get("shield_active"):
                    roller["shield_active"] = True
                    event_text = f"🛡️ {roller['name']} REPAIRED their shield!"
                else:
                    roller["score"] += 1
                    event_text = f"⚡ {roller['name']} is reinforcing! (+1)"

                await broadcast({
                    "type": "msg",
                    "text": event_text,
                    "leaderboard": await get_leaderboard()
                })
                continue  # Skip normal dice roll logic

            # --- 2. PREVENT SELF-SABOTAGE ---
            if msg["type"] == "vote_down" and state["voting_active"]:
                target_player = next((p for p in players.values() if p["name"] == msg["target"]), None)
                if target_player and target_player == roller:  # Simplified check
                    await ws.send_json({"type": "msg", "text": "❌ You can't sabotage yourself!"})
                    continue

            # --- ROLL PHASE ---
            if msg["type"] == "roll" and not state["voting_active"]:
                # Start the clock on the very first roll
                if state["start_time"] is None:
                    state["start_time"] = time.time()
                    state["end_time"] = None
                    state["game_over"] = False

                state["turns"] += 1
                roll_val = random.randint(1, 6)


                # Basic Scoring Logic
                if roll_val == roller["tag"]:
                    # Use max(0, ...) to ensure score never goes below zero
                    roller["score"] = max(0, roller["score"] - 1)
                    event_text = f"Ouch! {roller['name']} rolled their own number ({roll_val})!"
                else:
                    target = next((p for p in players.values() if p["tag"] == roll_val), None)
                    if target:
                        target["score"] += 1
                        event_text = f"🎲 {roller['name']} rolled {roll_val}. {target['name']} +1 point!"
                    else:
                        event_text = f"🎲 {roller['name']} rolled {roll_val}. No target found."

                # WIN CONDITION: First to 15 points wins
                if roller["score"] >= 15:
                    state["end_time"] = time.time()
                    event_text = f"🏆 {roller['name']} REACHED THE LIMIT AND WINS!"

                # RARE EVENT: Sabotage / Voting Phase
                # Triggers every 5 turns if a 6 is rolled
                rare_event = (state["turns"] % 3 == 0 and roll_val == 6 and not state.get("end_time"))

                if rare_event:
                    state["voting_active"] = True
                    lb = await get_leaderboard()
                    # Give the King (#1 on leaderboard) a shield
                    for p in players.values():
                        p["shield_active"] = (len(lb) > 0 and p["name"] == lb[0]["name"])

                # Send results to everyone
                await broadcast({
                    "type": "roll_result",
                    "roll": roll_val,
                    "msg": event_text,
                    "active_color": roller["color"],  # Pass the roller's color
                    "voting_active": state["voting_active"],
                    "leaderboard": await get_leaderboard()
                })
                # Handle Sabotage Countdown
                if rare_event:
                    # START TIMER IN BACKGROUND (Don't use await here!)
                    asyncio.create_task(sabotage_countdown())

            # --- SABOTAGE ACTIONS ---
            elif msg["type"] == "vote_down" and state["voting_active"]:
                target_player = next((p for p in players.values() if p["name"] == msg["target"]), None)
                if target_player:
                    if target_player.get("shield_active"):
                        # Breaking a shield doesn't reduce score, just removes protection
                        target_player["shield_active"] = False
                        await broadcast({"type": "msg", "text": f"🛡️ {target_player['name']}'s Shield BROKE!"})
                    else:
                        # Direct hit reduces score by 2
                        target_player["score"] = max(0, target_player["score"] - 2)
                        await broadcast({"type": "msg", "text": f"💥 {target_player['name']} sabotaged -2 pts!"})

                await broadcast({"type": "leaderboard_update", "leaderboard": await get_leaderboard()})

    except WebSocketDisconnect:
        players.pop(pid, None)
        # Reset game if no one is left
        if not players:
            state["start_time"] = None
            state["end_time"] = None
            state["turns"] = 0
            state["voting_active"] = False

    except WebSocketDisconnect:
        players.pop(pid, None)
