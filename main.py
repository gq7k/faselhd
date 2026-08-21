from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from playwright.async_api import async_playwright
import httpx
import uvicorn
import asyncio
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# دالة مساعدة لتحويل معرّف IMDb إلى اسم العمل وسنة الإصدار باستخدام مفتاحك الخاص
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

# دالة استخراج رابط الفيديو المباشر باستخدام Playwright
async def scrape_video_url(search_query: str, site_url: str):
    async with async_playwright() as p:
        # تشغيل المتصفح في الخلفية 
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
        page = await browser.new_page()
        
        video_url = None

        # اعتراض الطلبات للبحث عن ملفات الفيديو
        async def intercept_request(request):
            nonlocal video_url
            if ".mp4" in request.url or ".m3u8" in request.url:
                if "ads" not in request.url:
                    video_url = request.url

        page.on("request", intercept_request)

        try:
            # الانتقال لموقع البحث
            search_url = f"{site_url}/?s={search_query.replace(' ', '+')}"
            await page.goto(search_url, timeout=15000)
            
            # ننتظر قليلاً حتى تكتمل الطلبات في الشبكة (ممكن تحتاج تعديل بناءً على تصميم الموقع)
            await page.wait_for_timeout(5000)
            
        except Exception as e:
            print(f"Error scraping {site_url}: {e}")
        finally:
            await browser.close()
            
        return video_url

# تعريف الإضافة لـ Stremio
@app.get("/manifest.json")
def get_manifest():
    return {
        "id": "com.khaled.arabicstreams",
        "version": "1.0.0",
        "name": "Arabic Streams Pro",
        "description": "جلب الروابط المباشرة من فاصل إعلاني ومدينة الأفلام",
        "resources": ["stream"],
        "types": ["movie", "series"],
        "idPrefixes": ["tt"],
        "catalogs": []
    }

# نقطة اتصال جلب الروابط
@app.get("/stream/{type}/{imdb_id}.json")
async def get_stream(type: str, imdb_id: str):
    streams = []
    
    # تنظيف الـ ID لأن Stremio أحياناً يرسل رقم الحلقة معه (مثل tt1234567:1:1)
    clean_id = imdb_id.split(":")[0]
    
    # جلب اسم العمل
    search_query = await get_movie_details(clean_id)
    
    if search_query:
        # البحث في فاصل إعلاني
        fasel_url = await scrape_video_url(search_query, "https://web82118x.faselhdx.buzz")
        if fasel_url:
            streams.append({
                "name": "FaselHD",
                "title": "تشغيل مباشر",
                "url": fasel_url
            })
            
        # البحث في مدينة الأفلام
        filmcity_url = await scrape_video_url(search_query, "https://m.filmcity12.com")
        if filmcity_url:
            streams.append({
                "name": "FilmCity",
                "title": "تشغيل مباشر",
                "url": filmcity_url
            })

    return {"streams": streams}

if __name__ == "__main__":
    # الحصول على البورت من السيرفر (Render) أو استخدام 8000 محلياً
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
