from fastapi import FastAPI
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
                title = data["movie_results"][0].get('title')
                year = data["movie_results"][0].get('release_date', '').split('-')[0]
                return f"{title} {year}"
        except: 
            return None
    return None

# دالة Scraping مع دعم أكوام وتجنب Yandex
async def scrape_video_url(search_query: str, site_url: str):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = await browser.new_page()
        video_url = None
        
        async def intercept(request):
            nonlocal video_url
            if (".mp4" in request.url or ".m3u8" in request.url) and "yandex" not in request.url and "ads" not in request.url:
                video_url = request.url

        page.on("request", intercept)
        try:
            await page.goto(f"{site_url}/?s={search_query.replace(' ', '+')}", timeout=15000)
            await page.wait_for_timeout(6000)
        except: 
            pass
        finally: 
            await browser.close()
        return video_url

# الواجهة الرئيسية مع زر النسخ والتوليد التلقائي
@app.get("/", response_class=HTMLResponse)
def home():
    html_content = """
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>Arabic Streams Addon</title>
        <style>
            body { font-family: Tahoma, sans-serif; background: #0f172a; color: #fff; text-align: center; padding-top: 60px; }
            .box { background: #1e293b; padding: 40px; border-radius: 12px; display: inline-block; box-shadow: 0 4px 20px rgba(0,0,0,0.5); width: 85%; max-width: 550px; }
            input { width: 85%; padding: 12px; font-size: 15px; border-radius: 6px; border: none; text-align: center; background: #0f172a; color: #38bdf8; margin: 20px 0; }
            button { background: #38bdf8; color: #0f172a; border: none; padding: 12px 25px; font-size: 16px; font-weight: bold; border-radius: 6px; cursor: pointer; transition: 0.3s; }
            button:hover { background: #0ea5e9; }
            .msg { color: #4ade80; margin-top: 15px; display: none; font-weight: bold; }
        </style>
    </head>
    <body>
        <div class="box">
            <h2>إضافة Stremio - فاصل، مدينة الأفلام، وأكوام</h2>
            <p>انسخ رابط الإضافة أدناه والصقه في تطبيق Stremio:</p>
            <input type="text" id="addonUrl" readonly>
            <br>
            <button onclick="copyText()">نسخ الرابط</button>
            <div id="successMsg" class="msg">تم نسخ الرابط بنجاح! 🚀</div>
        </div>

        <script>
            // توليد رابط الـ manifest تلقائياً حسب دومين السيرفر الحالي
            document.getElementById('addonUrl').value = window.location.origin + "/manifest.json";

            function copyText() {
                var copyInput = document.getElementById("addonUrl");
                copyInput.select();
                copyInput.setSelectionRange(0, 99999);
                navigator.clipboard.writeText(copyInput.value);
                
                var msg = document.getElementById("successMsg");
                msg.style.display = "block";
                setTimeout(function() {
                    msg.style.display = "none";
                }, 3000);
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/manifest.json")
def get_manifest():
    return {
        "id": "com.khaled.arabicstreams",
        "version": "1.2.0",
        "name": "Arabic Streams Pro",
        "description": "جلب الروابط المباشرة من فاصل إعلاني، مدينة الأفلام، وأكوام",
        "resources": ["stream"],
        "types": ["movie", "series"],
        "idPrefixes": ["tt"]
    }

@app.get("/stream/{type}/{imdb_id}.json")
async def get_stream(type: str, imdb_id: str):
    search_query = await get_movie_details(imdb_id.split(":")[0])
    if not search_query: 
        return {"streams": []}
    
    streams = []
    # البحث في المواقع الثلاثة (فاصل، مدينة الأفلام، وأكوام)
    sites = [
        ("FaselHD", "https://web82118x.faselhdx.buzz"),
        ("FilmCity", "https://m.filmcity12.com"),
        ("Akwam", "https://akwams.org")
    ]
    
    for name, site_url in sites:
        video = await scrape_video_url(search_query, site_url)
        if video:
            streams.append({"name": name, "title": "تشغيل مباشر", "url": video})
            
    return {"streams": streams}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
