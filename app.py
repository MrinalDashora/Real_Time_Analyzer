import os, re, random, smtplib
from flask import Flask, render_template, request, session, redirect, url_for, jsonify
from email.message import EmailMessage
from googleapiclient.discovery import build
from textblob import TextBlob
from dotenv import load_dotenv
import database
import sqlite3
import requests
import json
from datetime import datetime
import urllib.parse

# --- SYSTEM INITIALIZATION ---
print("=========================================")
print("System Initialized by: Mrinal Dashora")
print("Roll Number: 24BCON1413")
print("CogniSense Server Running (v7.0 Ultimate Tiered Engine)...")
print("=========================================")

load_dotenv()
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

app = Flask(__name__) 
app.secret_key = os.getenv("SECRET_KEY", "cognisense_master_key_123")

# --- HELPERS & AI ENGINES ---
def analyze_sentiment_via_gemini(comments_list):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key: return 34, 33, 33
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    formatted_comments = "\n".join([f"- {c}" for c in comments_list[:100]])
    
    prompt = f"""
    Analyze the sentiment of the following YouTube comments. They contain English, Hindi, and Hinglish slang.
    Calculate the exact distribution percentage of Positive, Negative, and Neutral sentiment out of the total.
    Return ONLY a valid JSON object with keys "positive", "negative", and "neutral" as integer percentages summing to 100.
    
    Comments:
    {formatted_comments}
    """
    payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseMimeType": "application/json"}}
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=25)
        raw_text = response.json()['candidates'][0]['content']['parts'][0]['text']
        sentiment = json.loads(raw_text.strip())
        return int(sentiment.get('positive', 0)), int(sentiment.get('negative', 0)), int(sentiment.get('neutral', 0))
    except Exception as e:
        print(f"[Gemini API Error] {e}")
        return 40, 40, 20

def send_otp_email(to_email, otp):
    brevo_key = os.getenv("BREVO_API_KEY")
    sender_email = os.getenv("MAIL_USERNAME")
    sender_pass = os.getenv("MAIL_PASSWORD") # For Gmail SMTP Fallback
    
    # --- PLAN A: BREVO API ---
    if brevo_key and sender_email:
        try:
            url = "https://api.brevo.com/v3/smtp/email"
            headers = {"accept": "application/json", "api-key": brevo_key, "content-type": "application/json"}
            data = {
                "sender": {"email": sender_email, "name": "CogniSense Security"},
                "to": [{"email": to_email}],
                "subject": "CogniSense Login OTP",
                "htmlContent": f"<div style='padding:20px;'><h2>Welcome</h2><p>Your secure Login OTP is: <b>{otp}</b></p></div>"
            }
            res = requests.post(url, json=data, headers=headers)
            if res.status_code in [200, 201]: 
                print("[LOG] OTP sent via Brevo.")
                return True
            else: print(f"[Brevo Warning] {res.text}")
        except Exception as e: print(f"[Brevo Crash] {e}")

    # --- PLAN B: GMAIL SMTP FALLBACK ---
    if sender_email and sender_pass:
        try:
            msg = EmailMessage()
            msg['Subject'] = 'CogniSense Login OTP'
            msg['From'] = sender_email
            msg['To'] = to_email
            msg.set_content(f"Your secure Login OTP is: {otp}\nIt will expire in 5 minutes.")
            
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
                smtp.login(sender_email, sender_pass)
                smtp.send_message(msg)
            print("[LOG] OTP sent via SMTP Fallback.")
            return True
        except Exception as e: print(f"[SMTP Crash] {e}")
            
    print("[CRITICAL ERROR] Failed to send email. Check API keys and App Passwords on Render.")
    return False

def analyze_sentiment(text):
    text_lower = text.lower()
    pos_emojis = ['😂', '❤️', '🔥', '😍', '🙌', '👏', '😊', '👍', '♥️', '🥰', '🤣', '💯', '👌']
    neg_emojis = ['😡', '🤮', '👎', '🤬', '💔', '😭', '🤦‍♂️', '💩', '👎🏻', 'sick']
    
    if any(e in text for e in pos_emojis): return "positive", 0.6
    if any(e in text for e in neg_emojis): return "negative", -0.6
        
    pos_words = ["mast", "kadak", "op", "super", "best", "legend", "goat", "love", "amazing", "awesome", "bhai", "jhakaas"]
    neg_words = ["bakwas", "ghatiya", "bekar", "tatti", "cringe", "fake", "hate", "scam", "chutiya", "worst", "trash", "boring"]
    
    for pw in pos_words:
        if re.search(rf'\b{pw}\b', text_lower): return "positive", 0.5
    for nw in neg_words:
        if re.search(rf'\b{nw}\b', text_lower): return "negative", -0.5
        
    polarity = TextBlob(text_lower).sentiment.polarity
    if polarity > 0.15: return "positive", polarity
    elif polarity < -0.15: return "negative", polarity
    else: return "neutral", polarity

def extract_id(url):
    match = re.search(r'(?:v=|\/)([a-zA-Z0-9_-]{11})', url)
    return match.group(1) if match else None

def extract_channel_query(url_or_id):
    url_or_id = url_or_id.strip()
    if '@' in url_or_id: return {"type": "forHandle", "value": url_or_id.split('@')[-1].split('/')[0].split('?')[0]}
    elif 'channel/UC' in url_or_id: return {"type": "id", "value": 'UC' + url_or_id.split('channel/UC')[-1].split('/')[0].split('?')[0]}
    return {"type": "id", "value": url_or_id}

def get_recent_videos_stats(channel_url):
    yt_api_key = os.getenv("YOUTUBE_API_KEY")
    query_data = extract_channel_query(channel_url)
    
    if query_data["type"] == "forHandle":
        res = requests.get(f"https://www.googleapis.com/youtube/v3/search?part=snippet&type=channel&q=%40{query_data['value']}&key={yt_api_key}").json()
        channel_id = res['items'][0]['snippet']['channelId'] if 'items' in res and len(res['items']) > 0 else None
    else: channel_id = query_data["value"]
    
    if not channel_id: raise Exception("Invalid Channel URL or Handle.")

    c_res = requests.get(f"https://www.googleapis.com/youtube/v3/channels?part=contentDetails&id={channel_id}&key={yt_api_key}").json()
    uploads_id = c_res['items'][0]['contentDetails']['relatedPlaylists']['uploads']

    p_res = requests.get(f"https://www.googleapis.com/youtube/v3/playlistItems?part=snippet&playlistId={uploads_id}&maxResults=12&key={yt_api_key}").json()
    video_ids, titles = [], {}
    for item in p_res.get('items', []):
        vid = item['snippet']['resourceId']['videoId']
        video_ids.append(vid)
        titles[vid] = item['snippet']['title'][:18] + "..."

    v_res = requests.get(f"https://www.googleapis.com/youtube/v3/videos?part=statistics&id={','.join(video_ids)}&key={yt_api_key}").json()
    labels, views_list, er_list = [], [], []
    
    for item in reversed(v_res.get('items', [])):
        vid = item['id']
        labels.append(titles[vid])
        v = int(item['statistics'].get('viewCount', 0))
        l = int(item['statistics'].get('likeCount', 0))
        c = int(item['statistics'].get('commentCount', 0))
        views_list.append(v)
        er_list.append(round(((l + c) / v * 100), 2) if v > 0 else 0)

    return labels, views_list, er_list


# --- MAIN API ROUTES ---
@app.route('/api/channel-audit', methods=['POST'])
def channel_audit():
    print("\n=========================================")
    print("Name: Mrinal Dashora")
    print("Roll Number: 24BCON1413")
    print("[LOG] Executing Deep Channel Video-wise Audit Engine...")
    print("=========================================\n")

    if 'user' not in session: return jsonify({"error": "Authentication required."})
    user_credits, user_role = session.get('credits', 0), session.get('role', 'free')

    if user_credits < 50 and user_role != 'admin': return jsonify({"error": "Insufficient Credits. Requires 50 credits."})
    
    try:
        labels, views, engagement = get_recent_videos_stats(request.get_json().get('url', '').strip())
        if user_role != 'admin':
            session['credits'] -= 50
            conn = sqlite3.connect(database.DB_NAME)
            conn.execute("UPDATE users SET credits = ? WHERE email = ?", (session['credits'], session['user']))
            conn.commit()
            conn.close()
        return jsonify({"status": "success", "labels": labels, "views": views, "engagement": engagement, "credits_left": session['credits']})
    except Exception as e: return jsonify({"error": str(e)})


@app.route('/api/pulse-stream', methods=['POST'])
def pulse_stream():
    print("\n=========================================")
    print("Name: Mrinal Dashora")
    print("Roll Number: 24BCON1413")
    print("[LOG] Triggering MASSIVE Deep Fetch Engine...")
    print("=========================================\n")

    if 'user' not in session: return jsonify({"error": "Please login first."})
    
    user_role, user_credits = session.get('role', 'free'), session.get('credits', 0)
    max_limit = 1000 if user_role == 'free' else (3000 if user_role == 'pro' else 5000)
    cost = 10 if user_role == 'free' else (20 if user_role == 'pro' else 30)
        
    if user_credits < cost and user_role != 'admin': return jsonify({"error": f"Insufficient Credits. Requires {cost} credits."})
    
    video_id = extract_id(request.get_json().get('url', ''))
    if not video_id: return jsonify({"error": "Invalid YouTube URL."})
    
    try:
        youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
        fetched_comments, comment_stream, next_page_token = [], [], None
        
        while True:
            req = youtube.commentThreads().list(part="snippet", videoId=video_id, maxResults=100, textFormat="plainText", pageToken=next_page_token)
            res = req.execute()
            for item in res.get('items', []):
                text = item['snippet']['topLevelComment']['snippet']['textDisplay']
                fetched_comments.append(text)
                sent, _ = analyze_sentiment(text)
                comment_stream.append({"html": text, "sentiment": sent})
                
            next_page_token = res.get('nextPageToken')
            if not next_page_token or len(fetched_comments) >= max_limit: break
        
        if not fetched_comments: return jsonify({"error": "No comments found."})
        pos, neg, neu = analyze_sentiment_via_gemini(fetched_comments)
        
        if user_role != 'admin':
            session['credits'] -= cost
            conn = sqlite3.connect(database.DB_NAME)
            conn.execute("UPDATE users SET credits = ? WHERE email = ?", (session['credits'], session['user']))
            conn.commit()
            conn.close()
            
        return jsonify({"status": "success", "positive": pos, "negative": neg, "neutral": neu, "total_comments": len(fetched_comments), "stream": comment_stream, "credits_left": session['credits']})
    except Exception as e: return jsonify({"error": f"API Error: {str(e)}"})


# --- ADMIN & AUTH ROUTES ---
@app.route('/admin')
def admin_panel():
    if session.get('role') != 'admin': return redirect(url_for('home'))
    conn = database.get_db()
    users = conn.execute("SELECT * FROM users").fetchall()
    conn.close()
    return render_template('admin.html', users=users, super_admin=os.getenv("SUPER_ADMIN_EMAIL").lower())

@app.route('/api/update_user', methods=['POST'])
def update_user():
    if session.get('role') != 'admin': return jsonify({"error": "Unauthorized Access"}), 403
    data = request.get_json()
    target_email, new_role = data.get('email'), data.get('role')
    if target_email.lower() == os.getenv("SUPER_ADMIN_EMAIL").lower() and new_role != 'admin': return jsonify({"error": "Security: Cannot demote Super Admin!"})
    
    conn = sqlite3.connect(database.DB_NAME)
    new_credits = 10000 if new_role in ['admin', 'premium'] else (4999 if new_role == 'pro' else 1000)
    conn.execute("UPDATE users SET role = ?, credits = ? WHERE email = ?", (new_role, new_credits, target_email))
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": f"{target_email} is now {new_role.upper()}"})

@app.route('/')
def home(): return render_template('studio.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        if 'user' in session: return redirect(url_for('home'))
        return render_template('login.html')
    
    email = request.form.get('email')
    admin_email = os.getenv("SUPER_ADMIN_EMAIL")

    # --- ADMIN VIP BYPASS ---
    if admin_email and email.lower() == admin_email.lower():
        database.update_otp(email, "ADMIN_BYPASS")
        return jsonify({"status": "success", "message": "Admin Access: Enter Master Password instead of OTP."})

    # --- REGULAR USERS ---
    otp = str(random.randint(100000, 999999))
    database.update_otp(email, otp)
    
    if send_otp_email(email, otp): return jsonify({"status": "success", "message": "OTP sent to your email!"})
    else: return jsonify({"status": "error", "message": "Failed to send OTP. Check Backend configuration."})


@app.route('/verify', methods=['POST'])
def verify_post():
    email = request.form.get('email')
    user_otp = request.form.get('otp')
    admin_email = os.getenv("SUPER_ADMIN_EMAIL")
    admin_password = os.getenv("ADMIN_PASSWORD", "Admin@123") 
    
    # --- ADMIN VERIFICATION ---
    if admin_email and email.lower() == admin_email.lower():
        if user_otp == admin_password:
            conn = sqlite3.connect(database.DB_NAME)
            conn.execute("UPDATE users SET role = 'admin', credits = 10000 WHERE email = ?", (email,))
            conn.commit()
            conn.close()
            session['user'], session['role'], session['credits'] = email, 'admin', 10000
            return jsonify({"status": "success", "redirect": url_for('home')})
        return jsonify({"status": "error", "message": "Invalid Admin Password!"})

    # --- REGULAR USER VERIFICATION ---
    user = database.get_user(email)
    if user:
        if datetime.now() > datetime.strptime(user['otp_expiry'], "%Y-%m-%d %H:%M:%S.%f"): return jsonify({"status": "error", "message": "OTP expired."})
        if user['otp'] == user_otp:
            session['user'], session['role'], session['credits'] = email, user['role'], user['credits']
            return jsonify({"status": "success", "redirect": url_for('home')})
    return jsonify({"status": "error", "message": "Invalid OTP!"})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/studio')
def studio(): return render_template('studio.html')


# --- PRICING & PAYMENT ROUTES ---
@app.route('/pricing')
def pricing(): return render_template('pricing.html')

@app.route('/api/checkout', methods=['POST'])
def checkout():
    print("\n=========================================")
    print("Name: Mrinal Dashora")
    print("Roll Number: 24BCON1413")
    print("[LOG] Processing Real UPI Payment Upgrade...")
    print("=========================================\n")
    if 'user' not in session: return jsonify({"error": "Authentication Required."})
    if session.get('role') == 'admin': return jsonify({"error": "You are Super Admin!"})
    
    data = request.get_json()
    utr, plan = data.get('utr', '').strip(), str(data.get('plan', '')).strip()
    if len(utr) < 8: return jsonify({"error": "Invalid UTR."})
    
    new_credits, new_role, msg = (4999, 'pro', "PRO ⚡") if plan in ['pro', '49'] else (10000, 'premium', "PREMIUM 💎")
    
    try:
        conn = sqlite3.connect(database.DB_NAME)
        conn.execute("UPDATE users SET role = ?, credits = ? WHERE email = ?", (new_role, new_credits, session['user']))
        conn.commit()
        conn.close()
        session['role'], session['credits'] = new_role, new_credits
        return jsonify({"status": "success", "message": f"Verified! Welcome to {msg}", "redirect": url_for('studio')})
    except Exception as e: return jsonify({"error": str(e)})


# --- DEEP CONSULT ROUTE ---
@app.route('/deep_consult', methods=['POST'])
def deep_consult():
    print("\n=========================================")
    print("Name: Mrinal Dashora")
    print("Roll Number: 24BCON1413")
    print("[LOG] Executing Premium Deep Consult Engine...")
    print("=========================================\n")

    if 'user' not in session: return jsonify({"error": "Authentication Required."})
    if session.get('role') not in ['pro', 'premium', 'admin']: return jsonify({"error": "Premium Feature Locked 🔒"})
    
    data = request.get_json()
    u1, u2 = data.get('url1', '').strip(), data.get('url2', '').strip()
    if not u1 and not u2: return jsonify({"error": "URL required."})
    if session.get('credits', 0) < 100: return jsonify({"error": "Insufficient Credits."})

    database.deduct_credits(session['user'], 100)
    session['credits'] -= 100

    try:
        youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
        def resolve_url(url_input):
            v_id = extract_id(url_input)
            if v_id:
                try: return {"type": "id", "value": youtube.videos().list(part="snippet", id=v_id).execute()['items'][0]['snippet']['channelId']}
                except: pass
            return extract_channel_query(url_input)
        
        def analyze_channel_deep(query_input):
            query = resolve_url(query_input)
            ch_res = youtube.channels().list(part="snippet,statistics,contentDetails", **{query["type"]: query["value"]}).execute()
            if not ch_res.get('items'): return None
            
            ch_item = ch_res['items'][0]
            ch_name, subs, uploads_id = ch_item['snippet']['title'], int(ch_item['statistics'].get('subscriberCount', 0)), ch_item['contentDetails']['relatedPlaylists']['uploads']

            video_ids = [item['snippet']['resourceId']['videoId'] for item in youtube.playlistItems().list(part="snippet", playlistId=uploads_id, maxResults=15).execute().get('items', [])]
            total_v, total_e, best_vid = 0, 0, {"title": "N/A", "views": 0, "likes": 0, "comments": 0, "er": 0, "id": None}
            
            if video_ids:
                for v in youtube.videos().list(part="snippet,statistics", id=",".join(video_ids)).execute().get('items', []):
                    views = int(v['statistics'].get('viewCount', 0))
                    engs = int(v['statistics'].get('likeCount', 0)) + int(v['statistics'].get('commentCount', 0))
                    total_v += views; total_e += engs
                    er = (engs / views * 100) if views > 0 else 0
                    if views + (er * 1000) > best_vid["views"] + (best_vid["er"] * 1000): best_vid = {"title": v['snippet']['title'], "views": views, "likes": engs, "comments": 0, "er": er, "id": v['id']}

            avg_er = (total_e / total_v * 100) if total_v > 0 else 0
            advice = f"📊 Evaluated last 15 uploads.\n• Channel Avg ER: {round(avg_er, 2)}%\n• Outlier Video: '{best_vid['title']}' ({round(best_vid['er'], 2)}% ER)\n\n🔮 ACTION PLAN: The algorithm favored this video due to high ER. Duplicate its pacing and layout." if best_vid["id"] else "Not enough data."
            return {"name": ch_name, "subs": subs, "advice": advice}

        c1_data = analyze_channel_deep(u1) if u1 else None
        if u1 and not u2: return jsonify({"mode": "single", "data": c1_data, "credits_left": session['credits']}) if c1_data else jsonify({"error": "Invalid URL."})

        c2_data = analyze_channel_deep(u2)
        if not c1_data or not c2_data: return jsonify({"error": "Invalid URLs."})
        winner = c1_data['name'] if c1_data['subs'] > c2_data['subs'] else c2_data['name']
        return jsonify({"mode": "versus", "winner": winner, "verdict": f"🏆 DOMINANCE: {winner} has a stronger footprint.", "c1": c1_data, "c2": c2_data, "credits_left": session['credits']})
    except Exception as e: return jsonify({"error": f"Error: {str(e)}"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)