import os
import re
import random
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify
from googleapiclient.discovery import build
from words import positive_words, negative_words, explicit_words, intensifiers, negations

load_dotenv() 
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

app = Flask(__name__)
active_otps = {}

# --- ARCHITECT: MRINAL DASHORA | 24BCON1413 ---

def analyze_and_highlight(text):
    if not text: return None
    words = text.split()
    p_pts, n_pts = 0, 0
    highlighted_words = []
    is_explicit = any(re.sub(r'\W+', '', w.lower()) in explicit_words for w in words)

    for i, word in enumerate(words):
        clean = re.sub(r'\W+', '', word.lower())
        is_negated = i > 0 and words[i-1].lower() in negations
        weight = 2.0 if i > 0 and words[i-1].lower() in intensifiers else 1.0
        
        display = word
        if clean in positive_words:
            if is_negated: n_pts += weight; display = f'<b class="text-rose-600 underline">{word}</b>'
            else: p_pts += weight; display = f'<b class="text-blue-600 underline">{word}</b>'
        elif clean in negative_words:
            if is_negated: p_pts += weight; display = f'<b class="text-blue-600 underline">{word}</b>'
            else: n_pts += weight; display = f'<b class="text-rose-600 underline">{word}</b>'
        highlighted_words.append(display)

    return {"p": p_pts, "n": n_pts, "html": " ".join(highlighted_words), "explicit": is_explicit}

def extract_id(url):
    from urllib.parse import urlparse, parse_qs
    v_id = parse_qs(urlparse(url).query).get('v')
    if v_id: return v_id[0]
    match = re.search(r'([a-zA-Z0-9_-]{11})', urlparse(url).path)
    return match.group(1) if match else None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/request_otp', methods=['POST'])
def request_otp():
    data = request.get_json()
    email = data.get('email', '')
    if not re.match(r'^[a-zA-Z0-9._%+-]+@gmail\.com$', email):
        return jsonify({"error": "Invalid Gmail format."})
    otp = str(random.randint(1000, 9999))
    active_otps[email] = otp
    return jsonify({"success": True, "code": otp})

@app.route('/get_meta', methods=['POST'])
def get_meta():
    data = request.get_json()
    v_id = extract_id(data.get('url', ''))
    if not v_id: return jsonify({"error": "Invalid URL"})
    youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
    v_resp = youtube.videos().list(part="snippet,statistics", id=v_id).execute()
    item = v_resp['items'][0]
    return jsonify({
        "title": item['snippet']['title'],
        "thumb": item['snippet']['thumbnails']['high']['url'],
        "total": int(item['statistics'].get('commentCount', 0))
    })

@app.route('/analyze', methods=['POST'])
def analyze():
    data = request.get_json()
    v_id, limit = extract_id(data.get('url', '')), int(data.get('limit', 100))
    youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
    comments_data, next_token = [], None
    while len(comments_data) < limit:
        res = youtube.commentThreads().list(part="snippet", videoId=v_id, maxResults=100, pageToken=next_token).execute()
        for item in res.get("items", []):
            snippet = item["snippet"]["topLevelComment"]["snippet"]
            comments_data.append({"author": snippet["authorDisplayName"], "avatar": snippet["authorProfileImageUrl"], "text": snippet["textDisplay"]})
        next_token = res.get('nextPageToken')
        if not next_token: break

    stream, tp, tn = [], 0, 0
    for c in comments_data:
        analysis = analyze_and_highlight(c["text"])
        if not analysis: continue
        tp += analysis["p"]; tn += analysis["n"]
        stream.append({"author": c["author"], "avatar": c["avatar"], "html": analysis["html"], "explicit": analysis["explicit"], "is_neg": analysis["n"] > analysis["p"]})
    
    weight = tp + tn
    return jsonify({
        "positive": round((tp/weight*100), 1) if weight > 0 else 50,
        "negative": round((tn/weight*100), 1) if weight > 0 else 50,
        "stream": stream
    })

if __name__ == "__main__":
    app.run(debug=True)