from fastapi import Request, APIRouter
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

# --- Setup templates ---
templates = Jinja2Templates(directory="templates")
portfolio_router = APIRouter(prefix="", tags=["Game", "Adventure", "Have Fun"])

@portfolio_router.get("/", response_class=HTMLResponse)
async def show_portfolio(request: Request):
    return templates.TemplateResponse(request=request, name="home/index.html", context={})