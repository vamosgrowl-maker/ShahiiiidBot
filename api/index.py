import os
import requests
import urllib.parse
import re
import cloudscraper
import textwrap
from bs4 import BeautifulSoup
from flask import Flask, request
from io import BytesIO

# مكتبات معالجة الصور والنصوص العربية
from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display

app = Flask(__name__)

# ==========================================
# ⚙️ 1. الإعدادات ومفاتيح الوصول
# ==========================================
PAGE_ACCESS_TOKEN = "EAAbKSDqX63sBRCwuKN25lpbQBJtbA6a008dbN6mNvY3OAh0tj0D3frABilRPkk2jOAToy9qBQEVvZAXYn6yJf0snCpgikQbFgxotyJYgqDGkZBuGxPtYsnOfaV8lmre1JTsdAdZAzNq53B8LC4Rh2mNU59X1F1VefEZBTtIEqJFNOgPNGZBBF6MMEO4ZBx6WVEoNe5nwZDZD"
VERIFY_TOKEN = "ismail dev"
FB_API_URL = "https://graph.facebook.com/v25.0/me/messages"

# 🔑 مفاتيح API
JSONBIN_API_KEY = "$2a$10$8JmDvmx5Ik8.LJu5C7rmmOIDxWpjAgDBZRIaHBCL7eZ9KMk3jwV6y"
JSONBIN_BIN_ID = "69c1725dc3097a1dd55122d5"
JSONBIN_URL = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}"

IMGBB_API_KEY = "128aec5bcb2bf6b1bdf2c0738980f0c7"
processed_mids = set()

# ==========================================
# 🎨 دالة توليد ورفع صورة التفاصيل (التحديث الجديد)
# ==========================================
FONT_URL = "https://raw.githubusercontent.com/google/fonts/main/ofl/cairo/Cairo-Bold.ttf"
FONT_PATH = "/tmp/Cairo-Bold.ttf"

def get_font(size):
    if not os.path.exists(FONT_PATH):
        try:
            r = requests.get(FONT_URL)
            with open(FONT_PATH, 'wb') as f:
                f.write(r.content)
        except:
            return ImageFont.load_default()
    return ImageFont.truetype(FONT_PATH, size)

def generate_and_upload_movie_card(title, type_val, cats, story, poster_url, total_episodes):
    # 1. إنشاء الخلفية
    bg = Image.new('RGB', (800, 500), color=(15, 23, 42)) # لون سينمائي
    draw = ImageDraw.Draw(bg)
    font_title = get_font(28)
    font_text = get_font(22)

    # 2. وضع البوستر على اليمين
    try:
        p_res = requests.get(poster_url)
        poster = Image.open(BytesIO(p_res.content)).convert("RGB")
        poster = poster.resize((240, 360))
        bg.paste(poster, (520, 70))
    except: pass

    # 3. معالجة اللغة العربية
    def fix_ar(text):
        return get_display(arabic_reshaper.reshape(str(text)))

    # 4. كتابة النصوص على اليسار (محاذاة لليمين)
    draw.text((490, 70), fix_ar(f"الإسم : {title}"), font=font_title, fill="white", anchor="rt")
    draw.text((490, 120), fix_ar(f"النوع : {type_val}"), font=font_title, fill="#38bdf8", anchor="rt")
    draw.text((490, 170), fix_ar(f"التصنيفات : {cats}"), font=font_title, fill="#10b981", anchor="rt")
    draw.text((490, 220), fix_ar(f"عدد الفصول : {total_episodes}"), font=font_title, fill="#fbbf24", anchor="rt")
    draw.text((490, 270), fix_ar("القصة :"), font=font_title, fill="#f472b6", anchor="rt")

    # تقسيم القصة لأسطر
    reshaped_story = arabic_reshaper.reshape(story)
    lines = textwrap.wrap(reshaped_story, width=40)
    y_text = 320
    for line in lines[:4]: # نأخذ 4 أسطر كحد أقصى لكي لا تخرج عن الصورة
        draw.text((490, y_text), get_display(line), font=font_text, fill="#cbd5e1", anchor="rt")
        y_text += 35

    # 5. حفظ الصورة ورفعها لـ ImgBB
    img_io = BytesIO()
    bg.save(img_io, 'JPEG', quality=90)
    img_io.seek(0)
    
    try:
        res = requests.post(
            "https://api.imgbb.com/1/upload",
            data={"key": IMGBB_API_KEY},
            files={"image": img_io.getvalue()}
        )
        return res.json()["data"]["url"]
    except Exception as e:
        print("ImgBB Error:", e)
        return None

# ==========================================
# 🕸️ دالة استخراج رابط التحميل المباشر
# ==========================================
def get_akwam_direct_link(episode_page_url):
    scraper = cloudscraper.create_scraper()
    try:
        res = scraper.get(episode_page_url, timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        go_link = None
        for a in soup.find_all('a', href=True):
            if 'go.ak.sv/link' in a['href']:
                go_link = a['href']
                break
        if not go_link: return None
        res_final = scraper.get(go_link, timeout=15)
        match = re.search(r'https://ak\.sv/download/[^\s"\'<>]+', res_final.text)
        return match.group(0) if match else go_link
    except:
        return None

# ==========================================
# 🧠 إدارة قاعدة البيانات ورسائل فيسبوك
# ==========================================
def load_db():
    try:
        res = requests.get(JSONBIN_URL, headers={"X-Master-Key": JSONBIN_API_KEY}, timeout=5)
        if res.status_code == 200:
            return res.json().get('record', {"users": {}})
    except: pass
    return {"users": {}}

def save_db(data):
    try: 
        requests.put(JSONBIN_URL, json=data, headers={"Content-Type": "application/json", "X-Master-Key": JSONBIN_API_KEY}, timeout=5)
    except: pass

def send_fb_message(rid, txt):
    if len(txt) > 1900:
        parts = [txt[i:i+1900] for i in range(0, len(txt), 1900)]
        for part in parts:
            requests.post(f"{FB_API_URL}?access_token={PAGE_ACCESS_TOKEN}", json={"recipient": {"id": rid}, "message": {"text": part}})
    else:
        requests.post(f"{FB_API_URL}?access_token={PAGE_ACCESS_TOKEN}", json={"recipient": {"id": rid}, "message": {"text": txt}})

def send_fb_photo(rid, txt, photo_url):
    data = {
        "recipient": {"id": rid},
        "message": {
            "attachment": {"type": "image", "payload": {"url": photo_url, "is_reusable": True}}
        }
    }
    requests.post(f"{FB_API_URL}?access_token={PAGE_ACCESS_TOKEN}", json=data)
    if txt: send_fb_message(rid, txt)

def send_welcome(sid):
    msg = "👋 مرحبا بك في بوت Shahiiiid Bot .\n"
    msg += "🤖 يوفر لكم البوت كمية كبيرة من الأفلام والمسلسلات بمجرد كتابة اسمه.\n"
    msg += "👨‍💻 تابع حساب المطور من هنا :\n\n"
    msg += "https://www.facebook.com/M.oulay.I.smail.B.drk\n\n"
    msg += "🔗 رابط صفحة Maghrib-Ai لبرمجة وتطوير البوتات :\n\n"
    msg += "https://www.facebook.com/profile.php?id=61579427890346\n\n"
    msg += "🔗 رابط موقعنا الرسمي :\n\n"
    msg += "https://maghrib-ai-official-company.vercel.app/\n\n"
    msg += "🖊️ أرسل إسم الفيلم / المسلسل للبحث :"
    send_fb_message(sid, msg)

# ==========================================
# 🚀 نقطة الاستقبال (Webhook)
# ==========================================
@app.route('/', methods=['GET'])
def index(): return "🎬 Shahiiiid Bot is active!", 200

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        return request.args.get("hub.challenge", ""), 200 if request.args.get("hub.verify_token") == VERIFY_TOKEN else 403

    data = request.get_json()
    if data and data.get('object') == 'page':
        db = load_db()
        users_db = db.get("users", {})
        db_changed = False

        for entry in data.get('entry', []):
            for event in entry.get('messaging', []):
                if 'sender' not in event: continue
                sid = str(event['sender']['id'])
                message_data = event.get('message', {})
                mid = message_data.get('mid')
                if not message_data.get('text') or message_data.get('is_echo') or (mid and mid in processed_mids): 
                    continue
                if mid: processed_mids.add(mid)
                
                text = message_data.get('text', '').strip()
                if sid not in users_db:
                    users_db[sid] = {"step": "idle"}
                    db_changed = True
                    send_welcome(sid)
                    save_db(db)
                    continue

                user_state = users_db[sid]
                current_step = user_state.get("step", "idle")

                if text.lower() in ["/start", "رجوع", "بحث جديد"]:
                    user_state["step"] = "idle"
                    user_state.pop("search_results", None)
                    user_state.pop("episodes_data", None)
                    db_changed = True
                    send_welcome(sid)
                    save_db(db)
                    continue

                if current_step == "idle":
                    send_fb_message(sid, "⏳ جاري البحث...")
                    query_formatted = text.replace(" ", "+")
                    search_url = f"https://obito-mr-apis.vercel.app/api/search/akwam?name={query_formatted}"
                    try:
                        res = requests.get(search_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
                        data = res.json()
                        if data.get("success") and data.get("total", 0) > 0:
                            preview = data.get("preview", [])
                            user_state["search_results"] = preview
                            user_state["step"] = "selecting_result"
                            db_changed = True
                            
                            msg1 = f"▫️ محتوى البحث : {text}\n🔎 مجموع نتائج البحث : {data.get('total')}"
                            send_fb_message(sid, msg1)
                            
                            msg2 = "🖊️ أدخل رقم النتيجة التي تظن أنها تطابق محتوى بحثك :\n================\n"
                            for i, item in enumerate(preview, 1):
                                msg2 += f"{i}- {item.get('title', 'بدون عنوان')}\n================\n"
                            send_fb_message(sid, msg2)
                        else:
                            send_fb_message(sid, "❌ لم يتم العثور على أية نتائج. جرب اسماً آخر.")
                    except:
                        send_fb_message(sid, "❌ حدث خطأ في خادم البحث. يرجى المحاولة بعد قليل.")

                elif current_step == "selecting_result":
                    if text.isdigit():
                        index = int(text) - 1
                        results = user_state.get("search_results", [])
                        if 0 <= index < len(results):
                            selected_link = results[index].get("link")
                            poster_url = results[index].get("image", "") # جلب صورة البوستر من البحث
                            
                            send_fb_message(sid, "⏳ جاري تصميم بطاقة التفاصيل الفنية، يرجى الانتظار قليلاً...")
                            
                            details_url = f"https://obito-mr-apis.vercel.app/api/search/akwam_episode?url={selected_link}"
                            try:
                                res = requests.get(details_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=20)
                                details = res.json()
                                
                                if details.get("success"):
                                    cats = details.get("categories", [])
                                    cats_str = "، ".join(cats) if cats else "غير محدد"
                                    
                                    # توليد الصورة الاحترافية
                                    uploaded_img_url = generate_and_upload_movie_card(
                                        title=details.get('title', ''),
                                        type_val=details.get('type', 'غير معروف'),
                                        cats=cats_str,
                                        story=details.get('story', 'لا توجد قصة متاحة.'),
                                        poster_url=poster_url,
                                        total_episodes=details.get('totalEpisodes', '1')
                                    )
                                    
                                    if uploaded_img_url:
                                        send_fb_photo(sid, "🖊️ أدخل رقم 1️⃣ لرؤية الفصول المتوفرة.", uploaded_img_url)
                                    else:
                                        # في حال فشل رفع الصورة، نرسل التفاصيل كنص عادي كما كان في السابق
                                        fallback_msg = f"📧 الإسم : {details.get('title', '')}\n👾 النوع : {details.get('type', 'غير معروف')}\n🧱 التصنيفات : {cats_str}\n📄 القصة :\n================\n▫️ {details.get('story', '')}\n================\n🎫 عدد الفصول : {details.get('totalEpisodes', '1')}\n\n🖊️ أدخل رقم 1️⃣ لرؤية الفصول المتوفرة."
                                        send_fb_message(sid, fallback_msg)
                                    
                                    user_state["episodes_data"] = details.get("episodes", [])
                                    user_state["step"] = "viewing_episodes"
                                    db_changed = True
                                else:
                                    send_fb_message(sid, "❌ تعذر جلب تفاصيل هذا العمل.")
                            except Exception as e:
                                import traceback
                                error_msg = traceback.format_exc()
                                send_fb_message(sid, f"❌ حدث خطأ تقني في الكود:\n{str(e)}\n\nتفاصيل للمطور:\n{error_msg[:600]}")
                        else:
                            send_fb_message(sid, "❌ الرقم غير صحيح، يرجى اختيار رقم من القائمة أعلاه.")
                    else:
                        send_fb_message(sid, "⚠️ يرجى إرسال رقم النتيجة فقط (مثال: 1 أو 2).")

                elif current_step == "viewing_episodes":
                    if text in ["1", "1️⃣"]:
                        episodes = user_state.get("episodes_data", [])
                        if not episodes:
                            send_fb_message(sid, "❌ لا توجد فصول متوفرة حالياً لهذا العمل.")
                            user_state["step"] = "idle"
                            db_changed = True
                        else:
                            send_fb_message(sid, "⏳ جاري إرسال الفصول، يرجى الانتظار قليلاً...")
                            for ep in episodes[:25]:
                                ep_msg = f"📧 العنوان : {ep.get('title', '')}\n📆 التاريخ : {ep.get('date', 'غير معروف')}\n🏷️ الفصل : {ep.get('episodeNumber', '')}"
                                thumbnail = ep.get("thumbnail")
                                if thumbnail: send_fb_photo(sid, ep_msg, thumbnail)
                                else: send_fb_message(sid, ep_msg)
                            if len(episodes) > 25: send_fb_message(sid, "⚠️ تم عرض أول 25 فصلاً فقط لتجنب الضغط.")
                            send_fb_message(sid, "🖊️ أدخل رقم الفصل لتحميله 💾 .")
                            user_state["step"] = "download_episode"
                            db_changed = True
                    else:
                        send_fb_message(sid, "⚠️ يرجى إدخال الرقم 1 لعرض الفصول، أو 'رجوع' للبحث من جديد.")

                elif current_step == "download_episode":
                    if text.isdigit():
                        episodes = user_state.get("episodes_data", [])
                        selected_ep = next((ep for ep in episodes if str(ep.get("episodeNumber", "")) == text), None)
                        
                        if selected_ep:
                            send_fb_message(sid, "⏳ جاري استخراج الرابط المباشر، يرجى الانتظار (قد يستغرق بضع ثوانٍ)...")
                            direct_link = get_akwam_direct_link(selected_ep.get("link"))
                            
                            if direct_link:
                                msg = f"📥 الرابط المباشر جاهز للتحميل :\n\n{direct_link}\n\n🎬 نتمنى لكم فرجة ممتعة!"
                                send_fb_message(sid, msg)
                            else:
                                send_fb_message(sid, "❌ عذراً، لم نتمكن من تخطي حماية السيرفر لاستخراج الرابط لهذا الفصل.")
                            
                            user_state["step"] = "idle"
                            db_changed = True
                            send_fb_message(sid, "\nأرسل اسم فيلم أو مسلسل للبحث من جديد 🎬")
                        else:
                            send_fb_message(sid, "❌ رقم الفصل غير صحيح أو غير متوفر في القائمة المعروضة.")
                    else:
                        send_fb_message(sid, "⚠️ يرجى إدخال رقم الفصل الذي تريد تحميله.")

        if db_changed:
            save_db(db)
            
    return "OK", 200

if __name__ == '__main__': 
    app.run(port=5000)
