from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Dict, Any
from uuid import uuid4

tow_router = APIRouter(prefix="/tow", tags=["Tug Of War"])
templates = Jinja2Templates(directory="templates")

# --- In-Memory Database ---
games: Dict[str, Dict[str, Any]] = {}


# --- Models ---
class CreateGame(BaseModel):
    target_n: int = 20

class JoinGame(BaseModel):
    name: str

# --- UI Routes ---
@tow_router.get("/", response_class=HTMLResponse)
async def get_lobby(request: Request):
    # Pass request separately, and context as a dictionary
    return templates.TemplateResponse(
        request=request,
        name="tow/index.html",
        context={}
    )

@tow_router.get("/host", response_class=HTMLResponse)
async def get_host_ui(request: Request, game_id: str, client_id: str):
    return templates.TemplateResponse(
        request=request,
        name="tow/host.html",
        context={"game_id": game_id, "client_id": client_id}
    )

@tow_router.get("/player", response_class=HTMLResponse)
async def get_player_ui(request: Request, game_id: str, client_id: str):
    return templates.TemplateResponse(
        request=request,
        name="tow/player.html",
        context={"game_id": game_id, "client_id": client_id}
    )

# --- Helper Functions ---
async def broadcast_game(game_id: str):
    if game_id not in games: return  # FIXED: was 'if game_id in games: return'
    game = games[game_id]

    stats = {"A": 0, "B": 0}
    for p in game["players"].values():
        if p["team"] in stats:
            stats[p["team"]] += 1

    payload = {
        "type": "UPDATE",
        "game_id": game_id,
        "counter": game["counter"],
        "target_n": game["target_n"],
        "active": game["active"],
        "winner": game.get("winner"),
        "stats": stats,
        "players": {pid: {"name": p["name"], "team": p["team"]} for pid, p in game["players"].items()}
    }

    for ws in list(game["connections"].values()):  # FIXED: was 'connection'
        try:
            await ws.send_json(payload)
        except:
            pass


async def terminate_game(game_id: str, reason: str):
    if game_id not in games: return
    game = games.pop(game_id)
    for ws in list(game["connections"].values()):
        try:
            await ws.send_json({"type": "TERMINATED", "reason": reason})
            await ws.close()
        except:
            pass


# --- Logic Endpoints ---

@tow_router.post("/create")
async def create_game(data: CreateGame):
    game_id = str(uuid4())[:6].upper()
    host_id = str(uuid4())[:8]
    games[game_id] = {
        "host_id": host_id,
        "target_n": data.target_n,
        "counter": 0,
        "active": False,
        "winner": None,
        "players": {},
        "connections": {}
    }
    return {"game_id": game_id, "host_id": host_id}


@tow_router.post("/{game_id}/join")
async def join_game(game_id: str, player: JoinGame):
    gid = game_id.upper()
    if gid not in games:
        raise HTTPException(status_code=404, detail="Game not found")

    player_id = str(uuid4())[:8]
    # FIXED: key was 'teams', now 'team' to match broadcast
    games[gid]["players"][player_id] = {"name": player.name, "team": "spectator"}
    return {"player_id": player_id, "game_id": gid}


@tow_router.get("/check/{game_id}")
async def check_game(game_id: str):
    gid = game_id.upper()
    return {"exists": gid in games, "game_id": gid if gid in games else None}


@tow_router.websocket("/ws/{game_id}/{client_id}")
async def game_socket(websocket: WebSocket, game_id: str, client_id: str):
    gid = game_id.upper()
    if gid not in games:
        await websocket.close(code=404)
        return

    await websocket.accept()
    game = games[gid]
    game["connections"][client_id] = websocket  # CRITICAL: Store the connection!
    is_host = client_id == game["host_id"]

    try:
        await broadcast_game(gid)
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")
            p_info = game["players"].get(client_id)

            if is_host:
                if msg_type == "START":
                    game.update({"active": True, "counter": 0, "winner": None})
                elif msg_type == "RESET":
                    game.update({"active": False, "counter": 0, "winner": None})
                elif msg_type == "DELETE_GAME":
                    await terminate_game(gid, "Host ended the session.")
                    return

            if msg_type == "PULL" and game["active"] and p_info:
                move = 1 if p_info["team"] == "A" else -1 if p_info["team"] == "B" else 0
                game["counter"] += move
                if abs(game["counter"]) >= game["target_n"]:
                    game["active"] = False
                    game["winner"] = "A" if game["counter"] >= game["target_n"] else "B"

            elif msg_type == "SWITCH_TEAM" and not is_host:
                if not game["active"] and p_info:
                    game["players"][client_id]["team"] = data.get("team", "spectator")

            await broadcast_game(gid)  # Update everyone after any action

    except WebSocketDisconnect:
        if gid in games:
            game["connections"].pop(client_id, None)
            if is_host:
                await terminate_game(gid, "Host connection lost.")
            else:
                await broadcast_game(gid)
