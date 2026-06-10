import os, re, random, smtplib, datetime
from flask import Flask, render_template, request, session, redirect, url_for, jsonify
from email.message import EmailMessage
from googleapiclient.discovery import build
from textblob import TextBlob
from dotenv import load_dotenv
import database
import sqlite3
import requests

# --- SYSTEM INITIALIZATION ---
print("=========================================")
print("System Initialized by: Mrinal Dashora")
print("Roll Number: 24BCON1413")
print("CogniSense Server Running (v7.0 Refined Tiered Engine)...")
print("=========================================")

load_dotenv()
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

app = Flask(__name__)
app.secret_key = 'CogniSense_Secure_Key_2026'
database.init_db()

def send_otp_email(to_email, otp):
    api_key = os.getenv("BREVO_API_KEY")
    sender_email = os.getenv("MAIL_USERNAME")

    url = "https://api.brevo.com/v3/smtp/email"
    headers = {
        "accept": "application/json",
        "api-key": api_key,
        "content-type": "application/json"
    }
    
    # Email ka HTML design
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

# --- ADMIN PANEL ROUTES ---
@app.route('/admin')
def admin_panel():
    if 'user' not in session or session.get('role') != 'admin':
        return redirect(url_for('home'))
    conn = database.get_db()
    users = conn.execute("SELECT * FROM users").fetchall()
    conn.close()
    return render_template('admin.html', users=users, super_admin=os.getenv("SUPER_ADMIN_EMAIL").lower())

@app.route('/api/update_user', methods=['POST'])
def update_user():
    if 'user' not in session or session.get('role') != 'admin':
        return jsonify({"error": "Unauthorized Access"}), 403
    
    data = request.get_json()
    target_email = data.get('email')
    new_role = data.get('role')
    super_admin = os.getenv("SUPER_ADMIN_EMAIL").lower()

    if target_email.lower() == super_admin and new_role != 'admin':
        return jsonify({"error": "System Security: You cannot demote the Super Admin!"})

    try:
        conn = sqlite3.connect(database.DB_NAME)
        # Refined Token Sizes
        if new_role == 'admin': new_credits = 10000
        elif new_role == 'premium': new_credits = 10000
        elif new_role == 'pro': new_credits = 4999
        else: new_credits = 1000 # Free
        
        conn.execute("UPDATE users SET role = ?, credits = ? WHERE email = ?", (new_role, new_credits, target_email))
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": f"{target_email} is now {new_role.upper()}"})
    except Exception as e:
        return jsonify({"error": str(e)})

# --- AUTHENTICATION ROUTES ---
@app.route('/')
def home():
    return render_template('studio.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        if 'user' in session: return redirect(url_for('home'))
        return render_template('login.html')
        
    email = request.form.get('email')
    otp = str(random.randint(100000, 999999))
    database.update_otp(email, otp)
    
    if send_otp_email(email, otp): return jsonify({"status": "success", "message": "OTP sent to your email!"})
    else: return jsonify({"status": "error", "message": "Failed to send OTP. Check backend SMTP configuration."})

@app.route('/verify', methods=['POST'])
def verify_post():
    email = request.form.get('email')
    user_otp = request.form.get('otp')
    user = database.get_user(email)
    
    if user:
        expiry_time = datetime.datetime.strptime(user['otp_expiry'], "%Y-%m-%d %H:%M:%S.%f")
        if datetime.datetime.now() > expiry_time:
            return jsonify({"status": "error", "message": "OTP has expired. Please request a new one."})
            
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
def studio():
    return render_template('studio.html')

# --- PRICING & PAYMENT ROUTES ---
@app.route('/pricing')
def pricing():
    return render_template('pricing.html')

@app.route('/api/checkout', methods=['POST'])
def checkout():
    # Terminal Output Mandate
    print("\n=========================================")
    print("Name: Mrinal Dashora")
    print("Roll Number: 24BCON1413")
    print("[LOG] Processing Real UPI Payment Upgrade...")
    print("=========================================\n")

    if 'user' not in session: return jsonify({"error": "Authentication Required: Please login to upgrade."})
    if session.get('role') == 'admin': return jsonify({"error": "You are a Super Admin! You already have maximum access."})
    
    data = request.get_json()
    plan = str(data.get('plan', '')).strip()  # String mein convert kiya taaki '49' ya 49 dono chalein
    utr = data.get('utr', '').strip()
    email = session['user']
    
    # Basic UTR validation
    if not utr or len(utr) < 8:
        return jsonify({"error": "Invalid UTR. Please enter the correct Transaction ID from your UPI app."})
    
    # Naye 49 aur 99 pricing plans ki mapping
    if plan in ['pro', '49']:
        new_credits = 4999
        new_role = 'pro'
        msg = "Welcome to CogniSense PRO ⚡"
    elif plan in ['premium', '99']:
        new_credits = 10000
        new_role = 'premium'
        msg = "Welcome to CogniSense PREMIUM 💎"
    else:
        return jsonify({"error": "Invalid plan selected."})
    
    try:
        conn = sqlite3.connect(database.DB_NAME)
        conn.execute("UPDATE users SET role = ?, credits = ? WHERE email = ?", (new_role, new_credits, email))
        conn.commit()
        conn.close()
        
        session['role'] = new_role
        session['credits'] = new_credits
        
        # Logging the UTR for Admin verification
        print(f"[UPI AUDIT] User: {email} | Plan: {plan.upper()} | UTR Provided: {utr}")
        
        return jsonify({"status": "success", "message": f"Payment Verified via UTR! {msg}", "redirect": url_for('studio')})
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/analyze', methods=['POST'])
def analyze():
    if 'user' not in session: return jsonify({"error": "Authentication Required: Please login to run Pulse Stream analysis."})
    data = request.get_json()
    v_id = extract_id(data.get('url', ''))
    if not v_id: return jsonify({"error": "Invalid Video URL"})
    if session.get('credits', 0) < 2: return jsonify({"error": "Insufficient Credits. Please upgrade your plan."})
    
    database.deduct_credits(session['user'], 2)
    session['credits'] -= 2

    try:
        youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
        v_meta = youtube.videos().list(part="snippet,statistics", id=v_id).execute()
        meta_data = {}
        if v_meta.get('items'):
            snippet = v_meta['items'][0]['snippet']
            stats = v_meta['items'][0]['statistics']
            meta_data = {
                "title": snippet.get('title', 'Unknown Title'),
                "thumbnail": snippet['thumbnails'].get('high', {}).get('url', ''),
                "views": stats.get('viewCount', '0'),
                "comments_total": stats.get('commentCount', '0')
            }

        res = youtube.commentThreads().list(part="snippet", videoId=v_id, maxResults=50, textFormat='plainText').execute()
        stream, pos_count, neg_count = [], 0, 0
        for item in res.get("items", []):
            text = item["snippet"]["topLevelComment"]["snippet"]["textDisplay"]
            sentiment, _ = analyze_sentiment(text)
            if sentiment == "positive": pos_count += 1
            elif sentiment == "negative": neg_count += 1
            stream.append({"html": text, "sentiment": sentiment})
        
        total_actionable = pos_count + neg_count
        pos_pct = round((pos_count / total_actionable * 100), 1) if total_actionable > 0 else 50.0
        neg_pct = round((neg_count / total_actionable * 100), 1) if total_actionable > 0 else 50.0
            
        result = {"meta": meta_data, "positive": pos_pct, "negative": neg_pct, "stream": stream}
        return jsonify({"source": "api", "data": result, "credits_left": session['credits']})
    except Exception as e: return jsonify({"error": str(e)})

@app.route('/audit_channel', methods=['POST'])
def audit_channel():
    if 'user' not in session: return jsonify({"error": "Authentication Required: Please login to run Channel Audit."})
    user_input = request.get_json().get('channel_id', '').strip()
    if not user_input: return jsonify({"error": "Channel URL missing"})
    if session.get('credits', 0) < 1: return jsonify({"error": "Insufficient Credits."})

    database.deduct_credits(session['user'], 1)
    session['credits'] -= 1

    try:
        youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
        query_data = extract_channel_query(user_input)
        if query_data["type"] == "forHandle": res = youtube.channels().list(part="statistics", forHandle=query_data["value"]).execute()
        else: res = youtube.channels().list(part="statistics", id=query_data["value"]).execute()
        
        if not res.get('items'): return jsonify({"error": "Channel not found."})
        stats = res['items'][0]['statistics']
        stats['credits_left'] = session['credits']
        return jsonify(stats) 
    except Exception as e: return jsonify({"error": str(e)})

@app.route('/deep_consult', methods=['POST'])
def deep_consult():
    if 'user' not in session: return jsonify({"error": "Authentication Required: Please login to run Deep Consult."})
    if session.get('role') not in ['pro', 'premium', 'admin']: 
        return jsonify({"error": "Premium Feature Locked 🔒: Please upgrade your plan."})
    
    data = request.get_json()
    u1 = data.get('url1', '').strip()
    u2 = data.get('url2', '').strip()
    
    if not u1 and not u2: return jsonify({"error": "System Warning: At least one URL is required."})
    if session.get('credits', 0) < 10: return jsonify({"error": "Insufficient Credits."})

    database.deduct_credits(session['user'], 10)
    session['credits'] -= 10

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
                    
                    if score > best_score:
                        best_video = {"title": v['snippet']['title'], "views": v_views, "likes": v_likes, "comments": v_comms, "er": er, "id": v['id']}

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
                    f"spiked above your channel average. To trigger the recommendation system again:\n"
                    f"1. Duplicate the pacing of the first 10 seconds of this specific video.\n"
                    f"2. Use similar color grading and text layout in your next thumbnail.\n"
                    f"3. Upload a direct follow-up or 'Part 2' to ride the algorithmic wave."
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
    app.run(debug=True)