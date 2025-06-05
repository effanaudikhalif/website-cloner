from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from typing import List
import uvicorn
import httpx
from bs4 import BeautifulSoup
from scraper import WebsiteContext, scrape_website

# Create FastAPI instance
app = FastAPI(
    title="Orchids Challenge API",
    description="A starter FastAPI template for the Orchids Challenge backend",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models


class Item(BaseModel):
    id: int
    name: str
    description: str = None


class ItemCreate(BaseModel):
    name: str
    description: str = None

class URLSubmit(BaseModel):
    url: HttpUrl

# In-memory storage for demo purposes
items_db: List[Item] = [
    Item(id=1, name="Sample Item", description="This is a sample item"),
    Item(id=2, name="Another Item", description="This is another sample item")
]

# Root endpoint


@app.get("/")
async def root():
    return {"message": "Hello from FastAPI backend!", "status": "running"}

# Health check endpoint


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "orchids-challenge-api"}

@app.post("/submit-url")
async def submit_url(payload: URLSubmit):
    """Fetch the given URL and return the page title if reachable."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(str(payload.url), timeout=10)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=400, detail=f"Failed to retrieve URL: {exc}") from exc

    soup = BeautifulSoup(response.text, "html.parser")
    title = soup.title.string.strip() if soup.title else ""
    return {"url": payload.url, "title": title}
    
@app.post("/scrape-context", response_model=WebsiteContext)
async def scrape_context(payload: URLSubmit):
    try:
        return await scrape_website(str(payload.url))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scraping failed: {e}")

# Get all items

@app.get("/items", response_model=List[Item])
async def get_items():
    return items_db

# Get item by ID


@app.get("/items/{item_id}", response_model=Item)
async def get_item(item_id: int):
    for item in items_db:
        if item.id == item_id:
            return item
    return {"error": "Item not found"}

# Create new item


@app.post("/items", response_model=Item)
async def create_item(item: ItemCreate):
    new_id = max([item.id for item in items_db], default=0) + 1
    new_item = Item(id=new_id, **item.dict())
    items_db.append(new_item)
    return new_item

# Update item


@app.put("/items/{item_id}", response_model=Item)
async def update_item(item_id: int, item: ItemCreate):
    for i, existing_item in enumerate(items_db):
        if existing_item.id == item_id:
            updated_item = Item(id=item_id, **item.dict())
            items_db[i] = updated_item
            return updated_item
    return {"error": "Item not found"}

# Delete item


@app.delete("/items/{item_id}")
async def delete_item(item_id: int):
    for i, item in enumerate(items_db):
        if item.id == item_id:
            deleted_item = items_db.pop(i)
            return {"message": f"Item {item_id} deleted successfully", "deleted_item": deleted_item}
    return {"error": "Item not found"}


def main():
    """Run the application"""
    uvicorn.run(
        "hello:app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )


if __name__ == "__main__":
    main()
