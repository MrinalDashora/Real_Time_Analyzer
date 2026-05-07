import os
from flask import Flask, render_template, request, jsonify
from googleapiclient.discovery import build
from dotenv import load_dotenv
import re

load_dotenv()

app = Flask(__name__)

# Fetch API Key from Render Environment
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)

def extract_id(url):
    pattern = r'(?:v=|\/)([0-9A-Za-z_-]{11}).*'
    match = re.search(pattern, url)
    return match.group(1) if match else None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_metadata', methods=['POST'])
def get_metadata():
    data = request.json
    vid_id = extract_id(data.get('url'))
    if not vid_id: 
        return jsonify({"error": "Invalid URL"}), 400
    try:
        res = youtube.videos().list(part="statistics", id=vid_id).execute()
        count = res['items'][0]['statistics'].get('commentCount', 0)
        return jsonify({"commentCount": count})
    except: 
        return jsonify({"error": "Fetch failed"}), 500

@app.route('/analyze', methods=['POST'])
def analyze():
    data = request.json
    vid_id = extract_id(data.get('url'))
    limit = int(data.get('max_results', 50))
    
    try:
        comments = []
        token = None
        while len(comments) < limit:
            res = youtube.commentThreads().list(
                part="snippet", videoId=vid_id, 
                maxResults=min(100, limit - len(comments)),
                pageToken=token
            ).execute()

            for item in res['items']:
                txt = item['snippet']['topLevelComment']['snippet']['textDisplay']
                # Improved sentiment check
                pos_list = ['good', 'great', 'love', 'nice', 'best', 'amazing', 'excellent', 'wow']
                sentiment = 'Positive' if any(w in txt.lower() for w in pos_list) else 'Negative'
                comments.append({'text': txt, 'sentiment': sentiment})
            
            token = res.get('nextPageToken')
            if not token: break

        pos = sum(1 for c in comments if c.sentiment == 'Positive')
        total = len(comments)
        p_per = round((pos/total)*100, 1) if total > 0 else 0
        n_per = round(100 - p_per, 1) if total > 0 else 0
        
        return jsonify({"comments": comments, "p_per": p_per, "n_per": n_per})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)