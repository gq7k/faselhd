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

# دالة لتحويل معرّف IMDb إلى اسم العمل وسنة الإصدار
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
            elif data.get("tv_results") and len(data["tv_results"]) > 0:
                title = data["tv_results"][0].get("name")
                return f"{title}"
        except Exception as e:
            print(f"Error fetching TMDB data: {e}")
            
    return None

# دالة استخراج رابط الفيديو المباشر مع تجنب Yandex والإعلانات
async def scrape_video_url(search_query: str, site_url: str):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
        page = await browser.new_page()
        
        video_url = None

        async def intercept_request(request):
            nonlocal video_url
            if (".mp4" in request.url or ".m3u8" in request.url):
                if "ads" not in request.url and "yandex" not in request.url:
                    video_url = request.url

        page.on("request", intercept_request)

        try:
            search_url = f"{site_url}/?s={search_query.replace(' ', '+')}"
            await page.goto(search_url, timeout=15000)
            await page.wait_for_timeout(6000)
        except Exception as e:
            print(f"Error scraping {site_url}: {e}")
        finally:
            await browser.close()
            
        return video_url

# الصفحة الرئيسية: تعرض واجهة جميلة مع رابط الإضافة وزر نسخ مباشر!
@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>Arabic Streams Addon</title>
        <style>
            body { font-family: Tahoma, sans-serif; background: #0f172a; color: #fff; text-align: center; padding-top: 50px; }
            .container { background: #1e293b; padding: 30px; border-radius: 12px; display: inline-block; box-shadow: 0 4px 20px rgba(0,0,0,0.5); width: 80%; max-width: 600px; }
            input { width: 80%; padding: 12px; font-size: 16px; border-radius: 6px; border: none; text-align: center; background: #0f172a; color: #38bdf8; margin: 15px 0; }
            button { background: #38bdf8; color: #0f172a; border: none; padding: 12px 25px; font-size: 16px; font-weight: bold; border-radius: 6px; cursor: pointer; transition: 0.3s; }
            button:hover { background: #0ea5e9; }
            .success { color: #4ade80; margin-top: 10px; display: none; }
        </style>
    </head>
    <body>
        <div class="container">
            <h2>إضافة Stremio - فاصل، مدينة الأفلام، وأكوام</h2>
            <p>انسخ رابط الإضافة أدناه والصقه في تطبيق Stremio:</p>
            <input type="text" id="addonUrl" readonly>
            <br>
            <button onclick="copyUrl()">نسخ الرابط</button>
            <p id="msg" class="success">تم النسخ بنجاح! 🚀</p>
        </div>

        <script>
            const fullUrl = window.location.origin + "/manifest.json";
            document.getElementById('addonUrl').value = fullUrl;

            function copyUrl() {
                const copyText = document.getElementById("addonUrl");
                copyText.select();
                document.execCommand("copy");
                const msg = document.getElementById("msg");
                msg.style.display = "block";
                setTimeout(() => { msg.style.display = "none"; }, 3000);
            }
        </script>
    </body>
    </html>
    """

# تعريف الإضافة لـ Stremio
@app.get("/manifest.json")
def get_manifest():
    return {
        "id": "com.khaled.arabicstreams",
        "version": "1.1.0",
        "name": "Arabic Streams Pro",
        "description": "جلب الروابط المباشرة من فاصل إعلاني، مدينة الأفلام، وأكوام",
        "resources": ["stream"],
        "types": ["movie", "series"],
        "idPrefixes": ["tt"],
        "catalogs": []
    }

# نقطة اتصال جلب الروابط
@app.get("/stream/{type}/{imdb_id}.json")
async def get_stream(type: str, imdb_id: str):
    streams = []
    clean_id = imdb_id.split(":")[0]
    search_query = await get_movie_details(clean_id)
    
    if search_query:
        # البحث في المواقع الثلاثة
        sites = [
            ("FaselHD", "https://web82118x.faselhdx.buzz"),
            ("FilmCity", "https://m.filmcity12.com"),
            ("Akwam", "https://akwams.org")
        ]
        
        for name, site_url in sites:
            video_url = await scrape_video_url(search_query, site_url)
            if video_url:
                streams.append({"name": name, "title": "تشغيل مباشر", "url": video_url})

    return {"streams": streams}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
