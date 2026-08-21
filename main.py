from fastapi import FastAPI, responses
from fastapi.middleware.cors import CORSMiddleware
from playwright.async_api import async_playwright
import httpx
import uvicorn
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# دالة TMDB
async def get_movie_details(imdb_id: str):
    tmdb_api_key = "5660a3878cc2c5dcf067bb286f5b7bea"
    url = f"https://api.themoviedb.org/3/find/{imdb_id}?api_key={tmdb_api_key}&external_source=imdb_id"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url)
            data = response.json()
            if data.get("movie_results") and len(data["movie_results"]) > 0:
                title = data["movie_results"][0].get("title")
                year = data["movie_results"][0].get("release_date", "").split("-")[0]
                return f"{title} {year}"
        except: return None
    return None

# دالة Scraping
async def scrape_video_url(search_query: str, site_url: str):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = await browser.new_page()
        video_url = None
        async def intercept(request):
            nonlocal video_url
            if (".mp4" in request.url or ".m3u8" in request.url) and "ads" not in request.url:
                video_url = request.url
        page.on("request", intercept)
        try:
            await page.goto(f"{site_url}/?s={search_query.replace(' ', '+')}", timeout=15000)
            await page.wait_for_timeout(5000)
        except: pass
        finally: await browser.close()
        return video_url

# تغيير جذري: عند الدخول للرابط الرئيسي، يتم تحويلك للملف الصحيح
@app.get("/")
def home():
    return responses.RedirectResponse(url="/manifest.json")

@app.get("/manifest.json")
def get_manifest():
    return {
        "id": "com.khaled.arabicstreams",
        "version": "1.0.0",
        "name": "Arabic Streams Pro",
        "description": "جلب الروابط المباشرة",
        "resources": ["stream"],
        "types": ["movie", "series"],
        "idPrefixes": ["tt"]
    }

@app.get("/stream/{type}/{imdb_id}.json")
async def get_stream(type: str, imdb_id: str):
    search_query = await get_movie_details(imdb_id.split(":")[0])
    if not search_query: return {"streams": []}
    
    streams = []
    # تجربة المواقع
    for url in ["https://web82118x.faselhdx.buzz", "https://m.filmcity12.com"]:
        video = await scrape_video_url(search_query, url)
        if video:
            streams.append({"name": "Arabic Stream", "title": "تشغيل مباشر", "url": video})
    return {"streams": streams}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
