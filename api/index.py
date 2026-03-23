import os
import requests
import urllib.parse
from flask import Flask, request

app = Flask(__name__)

# ==========================================
# ⚙️ 1. الإعدادات ومفاتيح الوصول
# ==========================================
PAGE_ACCESS_TOKEN = "EAAbKSDqX63sBRCwuKN25lpbQBJtbA6a008dbN6mNvY3OAh0tj0D3frABilRPkk2jOAToy9qBQEVvZAXYn6yJf0snCpgikQbFgxotyJYgqDGkZBuGxPtYsnOfaV8lmre1JTsdAdZAzNq53B8LC4Rh2mNU59X1F1VefEZBTtIEqJFNOgPNGZBBF6MMEO4ZBx6WVEoNe5nwZDZD"
VERIFY_TOKEN = "ismail dev"
FB_API_URL = "https://graph.facebook.com/v25.0/me/messages"

# ⚠️ ملاحظة: استخدم نفس مفاتيح JSONBin السابقة لحفظ تقدم المستخدمين
JSONBIN_API_KEY = "$2a$10$8JmDvmx5Ik8.LJu5C7rmmOIDxWpjAgDBZRIaHBCL7eZ9KMk3jwV6y"
JSONBIN_BIN_ID = "69c11690aa77b81da90e7786" # يفضل إنشاء Bin جديد لهذا البوت ووضع الـ ID هنا
JSONBIN_URL = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}"

processed_mids = set()

# ==========================================
# 🧠 2. إدارة قاعدة البيانات
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

# ==========================================
# ✉️ 3. دوال إرسال رسائل فيسبوك
# ==========================================
def send_fb_message(rid, txt):
    # تقسيم الرسالة إذا كانت طويلة جداً
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
            "attachment": {
                "type": "image",
                "payload": {"url": photo_url, "is_reusable": True}
            }
        }
    }
    requests.post(f"{FB_API_URL}?access_token={PAGE_ACCESS_TOKEN}", json=data)
    if txt:
        send_fb_message(rid, txt)

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
# 🚀 4. نقطة الاستقبال (Webhook)
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
                if mid: 
                    processed_mids.add(mid)
                
                text = message_data.get('text', '').strip()
                
                if sid not in users_db:
                    users_db[sid] = {"step": "idle"}
                    db_changed = True
                    send_welcome(sid)
                    save_db(db)
                    continue

                user_state = users_db[sid]
                current_step = user_state.get("step", "idle")

                # --- إعادة تعيين البوت ---
                if text.lower() in ["/start", "رجوع", "بحث جديد"]:
                    user_state["step"] = "idle"
                    user_state.pop("search_results", None)
                    user_state.pop("episodes_data", None)
                    db_changed = True
                    send_welcome(sid)
                    save_db(db)
                    continue

                # ==========================================
                # 🔍 الخطوة 1: البحث عن فيلم/مسلسل
                # ==========================================
                if current_step == "idle":
                    send_fb_message(sid, "⏳ جاري البحث...")
                    
                    # استبدال المسافات بعلامة +
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
                            
                            # الرسالة الأولى (إحصائيات البحث)
                            msg1 = f"▫️ محتوى البحث : {text}\n"
                            msg1 += f"🔎 مجموع نتائج البحث : {data.get('total')}"
                            send_fb_message(sid, msg1)
                            
                            # الرسالة الثانية (القائمة المرقمة)
                            msg2 = "🖊️ أدخل رقم النتيجة التي تظن أنها تطابق محتوى بحثك :\n"
                            msg2 += "================\n"
                            for i, item in enumerate(preview, 1):
                                msg2 += f"{i}- {item.get('title', 'بدون عنوان')}\n"
                                msg2 += "================\n"
                            
                            send_fb_message(sid, msg2)
                        else:
                            send_fb_message(sid, "❌ لم يتم العثور على أية نتائج. جرب اسماً آخر.")
                    except:
                        send_fb_message(sid, "❌ حدث خطأ في خادم البحث. يرجى المحاولة بعد قليل.")

                # ==========================================
                # 📑 الخطوة 2: اختيار النتيجة وعرض التفاصيل
                # ==========================================
                elif current_step == "selecting_result":
                    if text.isdigit():
                        index = int(text) - 1
                        results = user_state.get("search_results", [])
                        
                        if 0 <= index < len(results):
                            selected_link = results[index].get("link")
                            send_fb_message(sid, "⏳ جاري جلب التفاصيل...")
                            
                            details_url = f"https://obito-mr-apis.vercel.app/api/search/akwam_episode?url={selected_link}"
                            try:
                                res = requests.get(details_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=20)
                                details = res.json()
                                
                                if details.get("success"):
                                    # تنظيف وتنسيق التصنيفات
                                    cats = details.get("categories", [])
                                    cats_str = "، ".join(cats) if cats else "غير محدد"
                                    
                                    # إعداد رسالة التفاصيل
                                    msg = f"📧 الإسم : {details.get('title', '')}\n"
                                    msg += f"👾 النوع : {details.get('type', 'غير معروف')}\n"
                                    msg += f"🧱 التصنيفات : {cats_str}\n"
                                    msg += f"📄 القصة :\n"
                                    msg += "================\n"
                                    msg += f"▫️ {details.get('story', 'لا توجد قصة متاحة.')}\n"
                                    msg += "================\n"
                                    msg += f"🎫 عدد الفصول : {details.get('totalEpisodes', '1')}\n\n"
                                    msg += "🖊️ أدخل رقم 1️⃣ لرؤية الفصول المتوفرة."
                                    
                                    send_fb_message(sid, msg)
                                    
                                    # حفظ الحلقات للمرحلة القادمة
                                    user_state["episodes_data"] = details.get("episodes", [])
                                    user_state["step"] = "viewing_episodes"
                                    db_changed = True
                                else:
                                    send_fb_message(sid, "❌ تعذر جلب تفاصيل هذا العمل.")
                            except:
                                send_fb_message(sid, "❌ حدث خطأ أثناء جلب التفاصيل.")
                        else:
                            send_fb_message(sid, "❌ الرقم غير صحيح، يرجى اختيار رقم من القائمة أعلاه.")
                    else:
                        send_fb_message(sid, "⚠️ يرجى إرسال رقم النتيجة فقط (مثال: 1 أو 2).")

                # ==========================================
                # 📺 الخطوة 3: عرض الحلقات
                # ==========================================
                elif current_step == "viewing_episodes":
                    if text in ["1", "1️⃣"]:
                        episodes = user_state.get("episodes_data", [])
                        
                        if not episodes:
                            send_fb_message(sid, "❌ لا توجد فصول متوفرة حالياً لهذا العمل.")
                            user_state["step"] = "idle"
                            db_changed = True
                        else:
                            send_fb_message(sid, "⏳ جاري إرسال الفصول، يرجى الانتظار قليلاً...")
                            
                            # إرسال الحلقات (مع تجنب حظر ماسنجر إذا كانت كثيرة، نأخذ أول 25 كحد أقصى)
                            for ep in episodes[:25]:
                                ep_msg = f"📧 العنوان : {ep.get('title', '')}\n"
                                ep_msg += f"📆 التاريخ : {ep.get('date', 'غير معروف')}\n"
                                ep_msg += f"🏷️ الفصل : {ep.get('episodeNumber', '')}"
                                
                                thumbnail = ep.get("thumbnail")
                                if thumbnail:
                                    send_fb_photo(sid, ep_msg, thumbnail)
                                else:
                                    send_fb_message(sid, ep_msg)
                            
                            if len(episodes) > 25:
                                send_fb_message(sid, "⚠️ تم عرض أول 25 فصلاً فقط لتجنب الضغط.")

                            # الرسالة الختامية
                            send_fb_message(sid, "🖊️ أدخل رقم الفصل لتحميله 💾 .")
                            user_state["step"] = "download_episode"
                            db_changed = True
                    else:
                        send_fb_message(sid, "⚠️ يرجى إدخال الرقم 1 لعرض الفصول، أو 'رجوع' للبحث من جديد.")

                # ==========================================
                # 📥 الخطوة 4: التحميل (قيد التطوير)
                # ==========================================
                elif current_step == "download_episode":
                    if text.isdigit():
                        msg = "🔜 هذه الميزة غير متوفرة حاليا.\n"
                        msg += "سنعمل قصارى جهدنا لتوفيرها لكم قريبا..."
                        send_fb_message(sid, msg)
                        
                        # إعادة المستخدم للبداية
                        user_state["step"] = "idle"
                        db_changed = True
                        send_fb_message(sid, "\nأرسل اسم فيلم أو مسلسل للبحث من جديد 🎬")
                    else:
                        send_fb_message(sid, "⚠️ يرجى إدخال رقم الفصل الذي تريد تحميله.")

        if db_changed:
            save_db(db)
            
    return "OK", 200

if __name__ == '__main__': 
    app.run(port=5000)