import os
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Request, Query
from fastapi.templating import Jinja2Templates
from typing import Optional
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Dict, Any
from uuid import uuid4
import asyncio

recipe_router = APIRouter(prefix="/recipe", tags=["Recipe Finder"])

# 1. Dynamically calculate the absolute path to your folder structures
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))  # Points to src/
BASE_DIR = os.path.dirname(CURRENT_DIR)                  # Points to project root

# 2. Fix the Templates path for Linux compatibility
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# 3. Build a perfect absolute path to recipes.json 
# Note: If your folder name on your computer is capitalized "Static", change "static" below to "Static"
RECIPE_PATH = os.path.join(BASE_DIR, "static", "recipes.json")

# 4. Open and safe-load your dataset
with open(RECIPE_PATH, "r") as file:
    RECIPES = json.load(file)["recipes"]


# --- The rest of your routes remain exactly the same! ---

@recipe_router.get("/", response_class=HTMLResponse)
async def get_website(request: Request):
    return templates.TemplateResponse(
        request,
        "recipes/recipe.html"
    )

@recipe_router.get("/detail")
def home(request: Request):
    return templates.TemplateResponse(
       request, "recipes/recipes2.html",
       context={"recipe": RECIPES[0]}
    )

# The FastAPI Endpoint
@recipe_router.get("/search")
async def get_recipe(
    item: str = Query(None, title="Ingredient", description="The ingredient to search for")
):
    if not item:
        return {"message": "Please enter an ingredient to search."}

    results = [
        recipe for recipe in RECIPES
        if item.lower() in [i.lower() for i in recipe["ingredients"]]
    ]

    if not results:
        return {"message": f"No recipes found containing '{item}'"}

    return results
