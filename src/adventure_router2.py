from fastapi import Request, APIRouter
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import os

# --- Setup templates ---
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
templates = Jinja2Templates(directory=os.path.join(base_dir, "templates"))

adventure_router2 = APIRouter(prefix="/rubric", tags=["Game", "Adventure", "Jason"])


@adventure_router2.get("/", response_class=HTMLResponse)
async def template_demo(request: Request):
    return templates.TemplateResponse(
        request=request, name="rubric/index.html", context={}
    )
@adventure_router2.get("/notes", response_class=PlainTextResponse)
async def notes(request: Request):
    response = "Hello adventurer, this is a plain text respone!"
    response = "Go to /notes/<any number> to find the missing notes"
    return response

@adventure_router2.get("/notes/{note_number}", response_class = PlainTextResponse)
async def notes_number(request: Request, note_number:int):
    if note_number==7:
        response = "Hello adventurer, you found the hidden note!"
        response += "The note says: find the J guy at /j"
        return response
    response = "Hello adventurer, there is nothing here!"
    response += "Try again go to /notes/<any number> to find the missing"
    response += "Hint: The number is more than 1 \n"
    return response

@adventure_router2.get("/j", response_class=JSONResponse)
async def j_guy(request: Request):
    return {
        "name": "This is JSON",
        "structure": "It is similar to python dictionary",
        "where to go next?": "Find Justin the fat wizard. Go to /justin/<secret password> to speak to him."
    }

@adventure_router2.get("/justin/{justin_pass}", response_class = PlainTextResponse)
async def justins_pass(request: Request, justin_pass:str):
    if justins_pass=="lienge_luvr":
        response = "Congratulations! Here is the key to unlock the door of the hub."
        response += "Go to /hub/<book number> and continue on your adventure!"
        return response
    response = "Nice try adventurer, but the password is wrong!"
    response += "I'll give you another shot, go to /justin/<secret password> to try again."
    response += "Hint: The password has something to do with a girl I like!"
    return response


@adventure_router2.get("/hub/{book_num}", response_class=PlainTextResponse)
async def hub_book(request: Request, book_num: int):
    # CHANGED: Check 'book_num' (the path parameter) instead of 'hub_book' (the function name)
    if book_num == 69:
        response = "Well done kiddo, you have found the book. In it is the path to meet the riddle-master.\n"
        response += "I have keys but no locks. I have space but no room. You can enter, but you can't go outside. What am I?\n"
        response += "Go to /riddler/<riddle answer> to test your thinking skills!"
        return response

    response = "Nice try adventurer, but that's the wrong book!\n"
    response += "I'll give you another shot, go to /hub/<book number> to try again.\n"
    response += "Hint: The book number is between 1-100. Muahahaha."
    return response



