from fastapi import FastAPI
from src.adventure_router import adventure_router
from src.adventure_router2 import adventure_router2
from fastapi.staticfiles import StaticFiles
from src.tow_router import tow_router
from src.recipe_router import recipe_router
from src.portfolio_router import portfolio_router
from src.dice_router import dice_router
from src.zone_router import zone_router
from fastapi.middleware.cors import CORSMiddleware


# ... (your app = FastAPI() line)
app = FastAPI(title="FastAPI Full Demo with Pydantic and Users UI")

# --- Mount Static files ---
app.mount("/Static", StaticFiles(directory="Static"), name="Static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ... (then your app.include_router lines)
app.include_router(adventure_router)
app.include_router(tow_router)
app.include_router(recipe_router)
app.include_router(portfolio_router)
app.include_router(dice_router)
app.include_router(zone_router)
app.include_router(adventure_router2)

# --- Run Uvi corn ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8080, reload=True)