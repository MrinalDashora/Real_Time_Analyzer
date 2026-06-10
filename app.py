import os, re, random, smtplib, datetime
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
print("CogniSense Server Running (v7.0 Refined Tiered Engine)...")
print("=========================================")

load_dotenv()
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

app = Flask(__name__) 
app.secret_key = os.getenv("SECRET_KEY", "cognisense_master_key_123")

# --- HELPERS & AI ENGINES ---
def analyze_sentiment_via_gemini(comments_list):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("[ERROR] GEMINI_API_KEY is missing in Render environment!")
        return 34, 33, 33
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    
    formatted_comments = "\n".join([f"- {c}" for c in comments_list])
    
    prompt = f"""
    Analyze the sentiment of the following YouTube comments. They contain English, Hindi, and Hinglish slang (e.g., 'mast', 'bakwas', 'op', 'gajab', 'maza aya').
    Calculate the exact distribution percentage of Positive, Negative, and Neutral sentiment out of the total.
    Return ONLY a valid JSON object with keys "positive", "negative", and "neutral" as integer percentages summing to 100. Do not include markdown codeblocks or triquetra.
    
    Comments:
    {formatted_comments}
    """
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"}
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=25)
        res_data = response.json()
        raw_text = res_data['candidates'][0]['content']['parts'][0]['text']
        
        sentiment = json.loads(raw_text.strip())
        return (
            int(sentiment.get('positive', 0)),
            int(sentiment.get('negative', 0)),
            int(sentiment.get('neutral', 0))
        )
    except Exception as e:
        print(f"[Gemini API Error] {e}. Falling back to default baseline split.")
        return 40, 40, 20

def send_otp_email(to_email, otp):
    api_key = os.getenv("BREVO_API_KEY")
    sender_email = os.getenv("MAIL_USERNAME")

    url = "https://api.brevo.com/v3/smtp/email"
    headers = {
        "accept": "application/json",
        "api-key": api_key,
        "content-type": "application/json"
    }
    
    data = {
        "sender": {"email": sender_email, "name": "CogniSense Security"},
        "to": [{"email": to_email}],
        "subject": "CogniSense Login OTP",
        "htmlContent": f"""
        <div style='font-family: Arial, sans-serif; padding: 20px;'>
            <h2>Welcome to CogniSense</h2>
            <p>Your secure Login OTP is: <b>{otp}</b></p>
            <p>It will expire in 5 minutes. Do not share this with anyone.</p>
        </div>
        """
    }

    try:
        response = requests.post(url, json=data, headers=headers)
        if response.status_code in [200, 201]:
            return True
        else:
            print(f"API Error: {response.text}")
            return False
    except Exception as e:
        print(f"Code Error: {e}")
        return False

def analyze_sentiment(text):
    text_lower = text.lower()
    pos_emojis = ['😂', '❤️', '🔥', '😍', '🙌', '👏', '😊', '👍', '♥️', '🥰', '🤣', '💯', '👌']
    neg_emojis = ['😡', '🤮', '👎', '🤬', '💔', '😭', '🤦‍♂️', '💩', '👎🏻', 'sick']
    
    if any(e in text for e in pos_emojis): return "positive", 0.6
    if any(e in text for e in neg_emojis): return "negative", -0.6
        
    pos_words = ["mast", "kadak", "op", "super", "best", "legend", "goat", "love", "amazing", "awesome", "bhai", "ek number", "jhakaas"]
    neg_words = ["bakwas", "ghatiya", "bekar", "tatti", "cringe", "fake", "hate", "scam", "chutiya", "worst", "gandi", "trash", "boring"]
    
    for ex in ["harsh", "hardik"]:
        text_lower = re.sub(rf'\b{ex}\b', '', text_lower)
        
    for pw in pos_words:
        if re.search(rf'\b{pw}\b', text_lower): return "positive", 0.5
    for nw in neg_words:
        if re.search(rf'\b{nw}\b', text_lower): return "negative", -0.5
        
    analysis = TextBlob(text_lower)
    polarity = analysis.sentiment.polarity
    
    if polarity > 0.15: return "positive", polarity
    elif polarity < -0.15: return "negative", polarity
    else: return "neutral", polarity

def extract_id(url):
    match = re.search(r'(?:v=|\/)([a-zA-Z0-9_-]{11})', url)
    return match.group(1) if match else None

def extract_channel_query(url_or_id):
    url_or_id = url_or_id.strip()
    if '@' in url_or_id:
        handle = url_or_id.split('@')[-1].split('/')[0].split('?')[0]
        return {"type": "forHandle", "value": handle}
    elif 'channel/UC' in url_or_id:
        cid = 'UC' + url_or_id.split('channel/UC')[-1].split('/')[0].split('?')[0]
        return {"type": "id", "value": cid}
    else:
        return {"type": "id", "value": url_or_id}

# --- NEW CHANNEL AUDIT MATH ENGINE ---
def get_channel_monthly_stats(channel_url):
    yt_api_key = os.getenv("YOUTUBE_API_KEY")
    if not yt_api_key:
        raise Exception("YOUTUBE_API_KEY is missing in Render environment.")

    channel_id = None
    query_data = extract_channel_query(channel_url)
    
    if query_data["type"] == "forHandle":
        search_url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&type=channel&q=%40{query_data['value']}&key={yt_api_key}"
        res = requests.get(search_url).json()
        if 'items' in res and len(res['items']) > 0:
            channel_id = res['items'][0]['snippet']['channelId']
    else:
        channel_id = query_data["value"]
    
    if not channel_id: raise Exception("Invalid Channel URL or Handle.")

    channel_url = f"https://www.googleapis.com/youtube/v3/channels?part=contentDetails&id={channel_id}&key={yt_api_key}"
    c_res = requests.get(channel_url).json()
    if not c_res.get('items'): raise Exception("Channel details not found.")
    uploads_playlist_id = c_res['items'][0]['contentDetails']['relatedPlaylists']['uploads']

    playlist_url = f"https://www.googleapis.com/youtube/v3/playlistItems?part=snippet&playlistId={uploads_playlist_id}&maxResults=50&key={yt_api_key}"
    p_res = requests.get(playlist_url).json()
    
    video_ids = []
    published_dates = {}
    for item in p_res.get('items', []):
        vid = item['snippet']['resourceId']['videoId']
        video_ids.append(vid)
        published_dates[vid] = item['snippet']['publishedAt']

    if not video_ids: raise Exception("No videos found on this channel.")

    vids_joined = ",".join(video_ids)
    stats_url = f"https://www.googleapis.com/youtube/v3/videos?part=statistics&id={vids_joined}&key={yt_api_key}"
    v_res = requests.get(stats_url).json()

    monthly_data = {}
    for item in v_res.get('items', []):
        vid = item['id']
        date_str = published_dates[vid]
        month_key = datetime.strptime(date_str[:10], "%Y-%m-%d").strftime("%b %Y")
        
        views = int(item['statistics'].get('viewCount', 0))
        likes = int(item['statistics'].get('likeCount', 0))
        comments = int(item['statistics'].get('commentCount', 0))
        
        if month_key not in monthly_data:
            monthly_data[month_key] = {"views": 0, "engagements": 0}
            
        monthly_data[month_key]["views"] += views
        monthly_data[month_key]["engagements"] += (likes + comments)

    sorted_months = sorted(monthly_data.keys(), key=lambda x: datetime.strptime(x, "%b %Y"))
    
    labels, views_list, engagement_rate_list = [], [], []
    for m in sorted_months:
        labels.append(m)
        v = monthly_data[m]["views"]
        e = monthly_data[m]["engagements"]
        views_list.append(v)
        rate = round((e / v * 100), 2) if v > 0 else 0
        engagement_rate_list.append(rate)

    return labels, views_list, engagement_rate_list


# --- MAIN API ROUTES ---
@app.route('/api/channel-audit', methods=['POST'])
def channel_audit():
    print("\n=========================================")
    print("Name: Mrinal Dashora")
    print("Roll Number: 24BCON1413")
    print("[LOG] Executing Deep Channel Math & Audit Engine...")
    print("=========================================\n")

    if 'user' not in session: return jsonify({"error": "Authentication required. Please login."})
    
    user_credits = session.get('credits', 0)
    user_role = session.get('role', 'free')
    credit_cost = 50

    if user_credits < credit_cost and user_role != 'admin':
        return jsonify({"error": f"Insufficient Credits. This Deep Audit requires {credit_cost} credits."})
        
    data = request.get_json()
    channel_url = data.get('url', '').strip()

    if not channel_url: return jsonify({"error": "Please provide a valid YouTube channel URL."})

    try:
        labels, views, engagement = get_channel_monthly_stats(channel_url)
        
        if user_role != 'admin':
            new_credits = user_credits - credit_cost
            session['credits'] = new_credits
            conn = sqlite3.connect(database.DB_NAME)
            conn.execute("UPDATE users SET credits = ? WHERE email = ?", (new_credits, session['user']))
            conn.commit()
            conn.close()

        return jsonify({
            "status": "success",
            "labels": labels,
            "views": views,
            "engagement": engagement,
            "credits_left": session.get('credits')
        })
    except Exception as e:
        print(f"[Audit Error] {str(e)}")
        return jsonify({"error": str(e)})


@app.route('/api/pulse-stream', methods=['POST'])
def pulse_stream():
    print("\n=========================================")
    print("Name: Mrinal Dashora")
    print("Roll Number: 24BCON1413")
    print("[LOG] Triggering Gemini 1.5 Flash Tiered Batching Engine...")
    print("=========================================\n")

    if 'user' not in session: return jsonify({"error": "Please login first."})
    
    user_role = session.get('role', 'free')
    user_credits = session.get('credits', 0)
    
    if user_role == 'free':
        comment_limit, credit_cost = 100, 10
    elif user_role == 'pro':
        comment_limit, credit_cost = 500, 20
    else:
        comment_limit, credit_cost = 1000, 30
        
    if user_credits < credit_cost and user_role != 'admin':
        return jsonify({"error": f"Insufficient Credits. Requires {credit_cost} credits."})
        
    data = request.get_json()
    video_url = data.get('url', '')
    video_id = extract_id(video_url)
    
    if not video_id: return jsonify({"error": "Invalid YouTube URL."})
    
    try:
        youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
        req = youtube.commentThreads().list(part="snippet", videoId=video_id, maxResults=comment_limit, textFormat="plainText")
        res = req.execute()
        
        fetched_comments = [item['snippet']['topLevelComment']['snippet']['textDisplay'] for item in res.get('items', [])]
        
        if not fetched_comments: return jsonify({"error": "No comments found or API disabled."})
        
        pos, neg, neu = analyze_sentiment_via_gemini(fetched_comments)
        
        if user_role != 'admin':
            new_credits = user_credits - credit_cost
            session['credits'] = new_credits
            conn = sqlite3.connect(database.DB_NAME)
            conn.execute("UPDATE users SET credits = ? WHERE email = ?", (new_credits, session['user']))
            conn.commit()
            conn.close()
            
        return jsonify({
            "status": "success",
            "positive": pos,
            "negative": neg,
            "neutral": neu,
            "total_comments": len(fetched_comments),
            "credits_left": session.get('credits')
        })
    except Exception as e:
        return jsonify({"error": f"API Error: {str(e)}"})


# --- ADMIN & AUTH ROUTES ---
@app.route('/admin')
def admin_panel():
    if 'user' not in session or session.get('role') != 'admin': return redirect(url_for('home'))
    conn = database.get_db()
    users = conn.execute("SELECT * FROM users").fetchall()
    conn.close()
    return render_template('admin.html', users=users, super_admin=os.getenv("SUPER_ADMIN_EMAIL").lower())

@app.route('/api/update_user', methods=['POST'])
def update_user():
    if 'user' not in session or session.get('role') != 'admin': return jsonify({"error": "Unauthorized Access"}), 403
    data = request.get_json()
    target_email = data.get('email')
    new_role = data.get('role')
    super_admin = os.getenv("SUPER_ADMIN_EMAIL").lower()
    if target_email.lower() == super_admin and new_role != 'admin': return jsonify({"error": "System Security: You cannot demote the Super Admin!"})
    try:
        conn = sqlite3.connect(database.DB_NAME)
        if new_role == 'admin': new_credits = 10000
        elif new_role == 'premium': new_credits = 10000
        elif new_role == 'pro': new_credits = 4999
        else: new_credits = 1000 
        conn.execute("UPDATE users SET role = ?, credits = ? WHERE email = ?", (new_role, new_credits, target_email))
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": f"{target_email} is now {new_role.upper()}"})
    except Exception as e: return jsonify({"error": str(e)})

@app.route('/')
def home(): return render_template('studio.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        if 'user' in session: return redirect(url_for('home'))
        return render_template('login.html')
    email = request.form.get('email')
    otp = str(random.randint(100000, 999999))
    database.update_otp(email, otp)
    if send_otp_email(email, otp): return jsonify({"status": "success", "message": "OTP sent to your email!"})
    else: return jsonify({"status": "error", "message": "Failed to send OTP."})

@app.route('/verify', methods=['POST'])
def verify_post():
    email = request.form.get('email')
    user_otp = request.form.get('otp')
    user = database.get_user(email)
    if user:
        # YAHAN FIX KIYA HAI: datetime.datetime ko sirf datetime kar diya
        expiry_time = datetime.strptime(user['otp_expiry'], "%Y-%m-%d %H:%M:%S.%f")
        if datetime.now() > expiry_time: return jsonify({"status": "error", "message": "OTP expired."})
        
        if user['otp'] == user_otp:
            admin_email = os.getenv("SUPER_ADMIN_EMAIL")
            if admin_email and email.lower() == admin_email.lower() and user['role'] != 'admin':
                conn = sqlite3.connect(database.DB_NAME)
                conn.execute("UPDATE users SET role = 'admin', credits = 10000 WHERE email = ?", (email,))
                conn.commit()
                conn.close()
                user = database.get_user(email)
            session['user'] = email
            session['role'] = user['role']
            session['credits'] = user['credits']
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
    plan = str(data.get('plan', '')).strip()
    utr = data.get('utr', '').strip()
    email = session['user']
    
    if not utr or len(utr) < 8: return jsonify({"error": "Invalid UTR."})
    
    if plan in ['pro', '49']: new_credits, new_role, msg = 4999, 'pro', "Welcome to PRO ⚡"
    elif plan in ['premium', '99']: new_credits, new_role, msg = 10000, 'premium', "Welcome to PREMIUM 💎"
    else: return jsonify({"error": "Invalid plan."})
    
    try:
        conn = sqlite3.connect(database.DB_NAME)
        conn.execute("UPDATE users SET role = ?, credits = ? WHERE email = ?", (new_role, new_credits, email))
        conn.commit()
        conn.close()
        session['role'], session['credits'] = new_role, new_credits
        return jsonify({"status": "success", "message": f"Payment Verified! {msg}", "redirect": url_for('studio')})
    except Exception as e: return jsonify({"error": str(e)})


# --- DEEP CONSULT ROUTE ---
@app.route('/deep_consult', methods=['POST'])
def deep_consult():
    if 'user' not in session: return jsonify({"error": "Authentication Required."})
    if session.get('role') not in ['pro', 'premium', 'admin']: return jsonify({"error": "Premium Feature Locked 🔒"})
    
    data = request.get_json()
    u1 = data.get('url1', '').strip()
    u2 = data.get('url2', '').strip()
    
    if not u1 and not u2: return jsonify({"error": "At least one URL required."})
    if session.get('credits', 0) < 100: return jsonify({"error": "Insufficient Credits."})

    database.deduct_credits(session['user'], 100)
    session['credits'] -= 100

    try:
        youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
        def resolve_url(url_input):
            v_id = extract_id(url_input)
            if v_id:
                try:
                    v_res = youtube.videos().list(part="snippet", id=v_id).execute()
                    if v_res.get('items'): return {"type": "id", "value": v_res['items'][0]['snippet']['channelId']}
                except: pass
            return extract_channel_query(url_input)
        
        def analyze_channel_deep(query_input):
            query = resolve_url(query_input)
            if query["type"] == "forHandle": ch_res = youtube.channels().list(part="snippet,statistics,contentDetails", forHandle=query["value"]).execute()
            else: ch_res = youtube.channels().list(part="snippet,statistics,contentDetails", id=query["value"]).execute()
            
            if not ch_res.get('items'): return None
            ch_item = ch_res['items'][0]
            ch_name = ch_item['snippet']['title']
            subs = int(ch_item['statistics'].get('subscriberCount', 0))
            uploads_id = ch_item['contentDetails']['relatedPlaylists']['uploads']

            pl_res = youtube.playlistItems().list(part="snippet", playlistId=uploads_id, maxResults=15).execute()
            video_ids = [item['snippet']['resourceId']['videoId'] for item in pl_res.get('items', [])]
            
            total_recent_views, total_recent_engagements = 0, 0
            best_video = {"title": "N/A", "views": 0, "likes": 0, "comments": 0, "er": 0, "id": None}
            
            if video_ids:
                vid_res = youtube.videos().list(part="snippet,statistics", id=",".join(video_ids)).execute()
                for v in vid_res.get('items', []):
                    v_views = int(v['statistics'].get('viewCount', 0))
                    v_likes = int(v['statistics'].get('likeCount', 0))
                    v_comms = int(v['statistics'].get('commentCount', 0))
                    
                    total_recent_views += v_views
                    engagements = v_likes + v_comms
                    total_recent_engagements += engagements
                    er = (engagements / v_views * 100) if v_views > 0 else 0
                    
                    score = v_views + (er * 1000)
                    best_score = best_video["views"] + (best_video["er"] * 1000)
                    
                    if score > best_score: best_video = {"title": v['snippet']['title'], "views": v_views, "likes": v_likes, "comments": v_comms, "er": er, "id": v['id']}

            channel_avg_er = (total_recent_engagements / total_recent_views * 100) if total_recent_views > 0 else 0
            
            if best_video["id"]:
                advice = (
                    f"📊 DATA EXTRACT: Evaluated the last {len(video_ids)} uploads.\n"
                    f"• Channel Average Engagement Rate: {round(channel_avg_er, 2)}%\n"
                    f"• Outlier Video: '{best_video['title']}'\n"
                    f"• Outlier Performance: {best_video['views']} Views, {best_video['likes']} Likes, {best_video['comments']} Comments.\n"
                    f"• Outlier Engagement Rate: {round(best_video['er'], 2)}%\n\n"
                    f"🔮 AI PREDICTION & ACTION PLAN:\n"
                    f"The algorithm heavily favored this video because its engagement rate ({round(best_video['er'], 2)}%) "
                    f"spiked above your channel average. Duplicate pacing and visual style to trigger recommendations."
                )
            else: advice = "Not enough recent data to calculate precise engagement metrics."
            return {"name": ch_name, "subs": subs, "advice": advice}

        if u1 and not u2:
            c1_data = analyze_channel_deep(u1)
            if not c1_data: return jsonify({"error": "Invalid URL."})
            return jsonify({"mode": "single", "data": c1_data, "credits_left": session['credits']})

        if u1 and u2:
            c1_data = analyze_channel_deep(u1)
            c2_data = analyze_channel_deep(u2)
            if not c1_data or not c2_data: return jsonify({"error": "Invalid URLs."})
            winner = c1_data['name'] if c1_data['subs'] > c2_data['subs'] else c2_data['name']
            verdict = f"🏆 ALGORITHMIC DOMINANCE: {winner} has a stronger overall footprint."
            return jsonify({"mode": "versus", "winner": winner, "verdict": verdict, "c1": c1_data, "c2": c2_data, "credits_left": session['credits']})
    except Exception as e: return jsonify({"error": "Processing Error: " + str(e)})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)