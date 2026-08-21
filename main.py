from fastapi import FastAPI, responses
from fastapi.responses import HTMLResponse
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
                return f"{data['movie_results'][0].get('title')} {data['movie_results'][0].get('release_date', '').split('-')[0]}"
        except: return None
    return None

# دالة Scraping ذكية تتجاهل روابط الإعلانات و Yandex
async def scrape_video_url(search_query: str, site_url: str):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = await browser.new_page()
        video_url = None
        
        async def intercept(request):
            nonlocal video_url
            # نبحث عن ملفات الفيديو ونتجاهل المواقع الوسيطة (yandex/ads)
            if (".mp4" in request.url or ".m3u8" in request.url) and "yandex" not in request.url and "ads" not in request.url:
                video_url = request.url

        page.on("request", intercept)
        try:
            await page.goto(f"{site_url}/?s={search_query.replace(' ', '+')}", timeout=15000)
            await page.wait_for_timeout(6000) # انتظار أطول لضمان تحميل الروابط
        except: pass
        finally: await browser.close()
        return video_url

# الواجهة مع زر النسخ
@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <html>
    <body style="background:#0f172a; color:white; text-align:center; padding-top:50px; font-family:sans-serif;">
        <div style="background:#1e293b; padding:30px; border-radius:12px; display:inline-block;">
            <h2>رابط إضافة Stremio</h2>
            <input type="text" id="url" value="https://faselhd-jeti.onrender.com/manifest.json" style="padding:10px; width:300px; border-radius:5px; border:none;">
            <button onclick="copy()" style="padding:10px 20px; background:#38bdf8; border:none; cursor:pointer;">نسخ الرابط</button>
        </div>
        <script>function copy(){navigator.clipboard.writeText(document.getElementById('url').value); alert('تم النسخ!');}</script>
    </body>
    </html>
    """

@app.get("/manifest.json")
def get_manifest():
    return {
        "id": "com.khaled.arabicstreams",
        "version": "1.1.0",
        "name": "Arabic Streams Pro",
        "resources": ["stream"],
        "types": ["movie", "series"],
        "idPrefixes": ["tt"]
    }

@app.get("/stream/{type}/{imdb_id}.json")
async def get_stream(type: str, imdb_id: str):
    search_query = await get_movie_details(imdb_id.split(":")[0])
    if not search_query: return {"streams": []}
    
    streams = []
    # المواقع المدعومة: فاصل، مدينة الأفلام، وأكوام
    for url in ["https://web82118x.faselhdx.buzz", "https://m.filmcity12.com", "https://akwams.org"]:
        video = await scrape_video_url(search_query, url)
        if video:
            streams.append({"name": "Arabic Stream", "title": "تشغيل مباشر", "url": video})
    return {"streams": streams}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
