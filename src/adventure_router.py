from fastapi import Request, APIRouter
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse
from fastapi.templating import Jinja2Templates

# --- Setup templates ---
templates = Jinja2Templates(directory="templates")
adventure_router = APIRouter(prefix="/adventure", tags=["Game", "Adventure", "Have Fun"])

@adventure_router.get("/", response_class=HTMLResponse)
async def template_demo(request: Request):
    return templates.TemplateResponse(
        "quest.html", {"request": request, "path": f"{adventure_router.prefix}/notes"}
    )

@adventure_router.get("/notes", response_class=PlainTextResponse)
async def notes(request: Request):
    response  = "Hello adventure, this is a plain text response!\n"
    response += f"Go to {adventure_router.prefix}/notes/&lt;any number&gt to find the missing notes\n"
    return response

@adventure_router.get("/notes/{note_number}", response_class=PlainTextResponse)
async def notes_number(request: Request, note_number: int):
    if note_number==7:
        response  = "Hello adventure, You find the hidden notes!\n"
        response += "The notes say, find the J guy at /j!\n"
        return response
    response  = "Hello adventure, there are nothing here!\n"
    response += f"Try again go to {adventure_router.prefix}/notes/&lt;any number&gt to find the missing notes\n"
    response += "Hint: it is between 1~10\n"
    return response

@adventure_router.get("/j", response_class=JSONResponse)
async def j_guy(request: Request):
    return {
        "name": "This is JSON",
        "structure": "It is similar to python dictionary",
        "Where to go next": f"{adventure_router.prefix}/welcome/{name}"
    }

@adventure_router.get("/welcome/{name}", response_class=PlainTextResponse)
async def welcome(request: Request, name: str, title: str = "warrior"):
    response  = f"Welcome to the game {name}!\n"
    response += f"We are blessed to have the brave might {title}\n"
    return response


# # YOUR TASK IS TO ADD 5 NEW ROUTE AS HOMEWORK
# @adventure_router.get("/????")
# @adventure_router.get("/????")
# @adventure_router.get("/????")
# @adventure_router.get("/????")
# @adventure_router.get("/????")


@adventure_router.get("/begin", response_class=PlainTextResponse)
async def begin(request: Request, name: str, title: str = "warrior"):
    response  = f"The adventure is about to begin.\n"
    return response


@adventure_router.get("/about", response_class=PlainTextResponse)
async def about(request: Request):
    response = "This is a simple adventure game built with FastAPI!\n"
    return response


@adventure_router.get("/level/{level_number}", response_class=PlainTextResponse)
async def level(request: Request, level_number: int):
    response = f"You have reached level {level_number}! Prepare for battle!\n"
    return response


@adventure_router.get("/boss", response_class=PlainTextResponse)
async def boss(request: Request):
    response = "A mighty boss appears! Are you ready to fight?\n"
    return response


@adventure_router.get("/goodbye/{name}", response_class=PlainTextResponse)
async def goodbye(request: Request, name: str):
    response =  f"Farewell {name}, until the next adventure!\n"
    return response







