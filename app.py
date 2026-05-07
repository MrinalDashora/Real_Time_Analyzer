import os
from flask import Flask, render_template, request, jsonify
from googleapiclient.discovery import build
from dotenv import load_dotenv
import re

load_dotenv()

app = Flask(__name__)

# Securely get API Key from Environment
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)

def extract_video_id(url):
    pattern = r'(?:v=|\/)([0-9A-Za-z_-]{11}).*'
    match = re.search(pattern, url)
    return match.group(1) if match else None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_metadata', methods=['POST'])
def get_metadata():
    data = request.json
    video_url = data.get('url')
    video_id = extract_video_id(video_url)
    
    if not video_id:
        return jsonify({"error": "Invalid URL"}), 400

    try:
        request_api = youtube.videos().list(part="snippet,statistics", id=video_id)
        response = request_api.execute()
        
        if not response['items']:
            return jsonify({"error": "Video not found"}), 404
            
        stats = response['items'][0]['statistics']
        snippet = response['items'][0]['snippet']
        
        return jsonify({
            "commentCount": stats.get('commentCount', 0),
            "title": snippet.get('title'),
            "thumbnail": snippet['thumbnails']['high']['url']
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/analyze', methods=['POST'])
def analyze():
    data = request.json
    video_url = data.get('url')
    max_results = data.get('max_results', 50)
    video_id = extract_video_id(video_url)

    if not video_id:
        return jsonify({"error": "Invalid YouTube URL"}), 400

    try:
        # Fetch Video Metadata
        video_response = youtube.videos().list(part="snippet", id=video_id).execute()
        title = video_response['items'][0]['snippet']['title']
        thumbnail = video_response['items'][0]['snippet']['thumbnails']['high']['url']

        # Fetch Comments
        comments = []
        next_page_token = None
        
        while len(comments) < max_results:
            request_api = youtube.commentThreads().list(
                part="snippet",
                videoId=video_id,
                maxResults=min(100, max_results - len(comments)),
                pageToken=next_page_token
            )
            response = request_api.execute()

            for item in response['items']:
                comment = item['snippet']['topLevelComment']['snippet']['textDisplay']
                # Simple Sentiment Logic
                pos_words = ['good', 'great', 'awesome', 'amazing', 'love', 'best', 'nice']
                sentiment = 'Positive' if any(word in comment.lower() for word in pos_words) else 'Negative'
                comments.append({'text': comment, 'sentiment': sentiment})

            next_page_token = response.get('nextPageToken')
            if not next_page_token:
                break

        pos_count = sum(1 for c in comments if c.sentiment == 'Positive')
        neg_count = len(comments) - pos_count
        
        return jsonify({
            "title": title,
            "thumbnail": thumbnail,
            "comments": comments,
            "positive_percentage": round((pos_count/len(comments))*100, 1) if comments else 0,
            "negative_percentage": round((neg_count/len(comments))*100, 1) if comments else 0
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)