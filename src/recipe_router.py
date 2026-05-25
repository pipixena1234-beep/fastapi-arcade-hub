from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Request, Query
from fastapi.templating import Jinja2Templates
from typing import Optional
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Dict, Any
from uuid import uuid4
import asyncio
import json

recipe_router = APIRouter(prefix="/recipe", tags=["Recipe Finder"])
templates = Jinja2Templates(directory="templates")

with open("static/recipes.json", "r") as file:
    RECIPES = json.load(file)["recipes"]

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
    # 'item' is the Query Parameter the user sends from the website
    item: str = Query(None, title="Ingredient", description="The ingredient to search for")
):
    if not item:
        return {"message": "Please enter an ingredient to search."}

    # Filter recipes: check if the input string exists in the ingredients list
    results = [
        recipe for recipe in RECIPES
        if item.lower() in [i.lower() for i in recipe["ingredients"]]
    ]

    if not results:
        return {"message": f"No recipes found containing '{item}'"}

    return results

# To run: uvicorn home:app --reload