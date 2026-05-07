import os
import re
from flask import Flask, render_template, request, jsonify
from googleapiclient.discovery import build
from dotenv import load_dotenv

# Initialize environment and Flask
load_dotenv()
app = Flask(__name__)

# System Configuration
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)

def extract_video_id(url):
    """
    Extracts the unique 11-character YouTube video ID using regex.
    Supports standard, shortened, and mobile URLs.
    """
    regex_patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
        r'(?:be\/)([0-9A-Za-z_-]{11}).*'
    ]
    for pattern in regex_patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

@app.route('/')
def home():
    """Renders the main dashboard."""
    return render_template('index.html')

@app.route('/get_metadata', methods=['POST'])
def get_metadata():
    """
    Fetches video statistics instantly when a URL is pasted.
    Used for the real-time auto-fill feature.
    """
    payload = request.json
    video_url = payload.get('url')
    video_id = extract_video_id(video_url)
    
    if not video_id:
        return jsonify({"error": "Invalid Video Link"}), 400

    try:
        # Requesting statistics for comment count
        api_request = youtube.videos().list(
            part="statistics,snippet",
            id=video_id
        )
        api_response = api_request.execute()
        
        if not api_response['items']:
            return jsonify({"error": "Video Not Found"}), 404
            
        stats = api_response['items'][0]['statistics']
        snippet = api_response['items'][0]['snippet']
        
        return jsonify({
            "commentCount": stats.get('commentCount', 0),
            "title": snippet.get('title'),
            "thumbnail": snippet['thumbnails']['high']['url']
        })
    except Exception as error:
        return jsonify({"error": str(error)}), 500

@app.route('/analyze', methods=['POST'])
def analyze_sentiment():
    """
    The core analytical engine. Fetches comments, runs NLP logic, 
    and returns precise percentage ratios.
    """
    payload = request.json
    video_url = payload.get('url')
    requested_limit = int(payload.get('max_results', 50))
    video_id = extract_video_id(video_url)

    if not video_id:
        return jsonify({"error": "System requires a valid URL to proceed"}), 400

    try:
        comment_dataset = []
        next_token = None
        
        # Paginated fetching to respect YouTube API limits
        while len(comment_dataset) < requested_limit:
            api_request = youtube.commentThreads().list(
                part="snippet",
                videoId=video_id,
                maxResults=min(100, requested_limit - len(comment_dataset)),
                pageToken=next_token,
                textFormat="plainText"
            )
            api_response = api_request.execute()

            for item in api_response['items']:
                raw_text = item['snippet']['topLevelComment']['snippet']['textDisplay']
                
                # NLP Sentiment Logic
                positive_keywords = [
                    'good', 'great', 'amazing', 'love', 'best', 'wow', 'excellent', 
                    'brilliant', 'nice', 'awesome', 'informative', 'helpful', 'thanks'
                ]
                
                # Check for positive hits in lowercase text
                is_positive = any(word in raw_text.lower() for word in positive_keywords)
                sentiment_label = 'Positive' if is_positive else 'Negative'
                
                comment_dataset.append({
                    'text': raw_text,
                    'sentiment': sentiment_label
                })

            next_token = api_response.get('nextPageToken')
            if not next_token:
                break

        # Calculating exact mathematical ratios
        positive_hits = sum(1 for entry in comment_dataset if entry.sentiment == 'Positive')
        total_analyzed = len(comment_dataset)
        
        if total_analyzed > 0:
            pos_ratio = round((positive_hits / total_analyzed) * 100, 1)
            neg_ratio = round(100 - pos_ratio, 1)
        else:
            pos_ratio, neg_ratio = 0, 0
        
        return jsonify({
            "comments": comment_dataset,
            "positive_percentage": pos_ratio,
            "negative_percentage": neg_ratio,
            "total_count": total_analyzed
        })

    except Exception as error:
        return jsonify({"error": str(error)}), 500

if __name__ == '__main__':
    # Running on local port 5000 for development
    app.run(debug=True)