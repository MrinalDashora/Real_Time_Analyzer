import os
import re
import random
import hashlib
from dotenv import load_dotenv
from collections import Counter # ADDED: Required for finding top keywords

# Flask and HTTP libraries
from flask import Flask, render_template, request, jsonify
from urllib.parse import urlparse, parse_qs
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Load environment variables from .env file
load_dotenv() 

# --- API KEY & FLASK SETUP ---
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

app = Flask(__name__)

# --- SENTIMENT ANALYSIS LEXICON ---
positive_words = {
    'love', 'amazing', 'great', 'excellent', 'best', 'happy', 'fantastic',
    'wonderful', 'beautiful', 'awesome', 'good', 'nice', 'perfect', 'brilliant',
    'pleased', 'delightful', 'joy', 'excited', 'positive', 'superb',
    'incredible', 'outstanding', 'flawless', 'charming', 'magnificent', 'gorgeous',
    'stunning', 'impressive', 'favorable', 'successful', 'thriving', 'effective',
    'spectacular', 'breathtaking', 'phenomenal', 'glowing', 'radiant', 'blessed',
    'champion', 'win', 'adore', 'admire', 'praise', 'inspire', 'motivate',
    'satisfied', 'content', 'grateful', 'thankful', 'eloquent', 'vibrant',
    'uplifting', 'encouraging', 'supportive', 'terrific', 'splendid', 'fabulous',
    'stellar', 'triumphant', 'victory', 'genius', 'masterful', 'innovative'
}
negative_words = {
    'terrible', 'bad', 'hate', 'awful', 'disappointed', 'worst', 'poor',
    'unhelpful', 'mess', 'sad', 'horrible', 'dreadful', 'unhappy', 'frustrating',
    'annoyed', 'useless', 'lousy', 'negative', 'broken', 'fail',
    'disgusting', 'horrendous', 'miserable', 'unpleasant', 'inadequate', 'painful',
    'flawed', 'unfortunate', 'dire', 'abysmal', 'deficient', 'tragic',
    'pathetic', 'ridiculous', 'inferior', 'terrible', 'waste', 'disgust',
    'suffer', 'struggle', 'lost', 'depressing', 'dismal', 'gloomy',
    'insulting', 'offensive', 'aggravating', 'annoying', 'vile', 'nasty',
    'filthy', 'revolting', 'detestable', 'repugnant', 'disastrous', 'catastrophic'
}
explicit_words = {
    'fuck', 'shit', 'bitch', 'asshole', 'damn', 'cunt', 'piss', 'hell',
    'chutiya', 'madarchod', 'behenchod', 'randi', 'bhosadi', 'bhenchod',
    'gaandu', 'lund', 'tatti', 'madar chod'
}
intensifiers = {
    'very', 'really', 'extremely', 'super', 'so', 'incredibly', 'highly', 'utterly', 'truly'
}
negations = {
    'not', 'never', 'no', 'don\'t', 'doesn\'t', 'isn\'t', 'wasn\'t', 'couldn\'t', 'won\'t'
}

# --- HELPER FUNCTIONS ---

def analyze_sentiment(text):
    """Performs sentiment analysis on a given text string, tracking key phrases and neutral words."""
    normalized_text = re.sub(r'[.,\/#!$%\^&\*;:{}=\-_`~()]', '', text.lower())
    words = normalized_text.split()

    positive_points = 0
    negative_points = 0
    neutral_count = 0
    
    positive_phrases = [] 
    negative_phrases = []

    if any(word in explicit_words for word in words):
        return {
            "positive_points": 0, "negative_points": 100, "neutral_points": 0, "is_explicit": True,
            "positive_phrases": [], "negative_phrases": ['Explicit Content Found']
        } 

    for i, word in enumerate(words):
        is_negated = i > 0 and words[i - 1] in negations
        intensity_multiplier = 1.5 if i > 0 and words[i - 1] in intensifiers else 1
        
        # Determine the phrase to save (word or intensifier + word)
        phrase = (words[i-1] + " " + word) if intensity_multiplier > 1 and i > 0 else word

        if word in positive_words:
            if is_negated:
                negative_points += intensity_multiplier
                negative_phrases.append("not " + phrase)
            else:
                positive_points += intensity_multiplier
                positive_phrases.append(phrase)
        elif word in negative_words:
            if is_negated:
                positive_points += intensity_multiplier
                positive_phrases.append("not " + phrase)
            else:
                negative_points += intensity_multiplier
                negative_phrases.append(phrase)
        else:
            neutral_count += 1 # Count neutral words
    
    return {
        "positive_points": positive_points,
        "negative_points": negative_points,
        "neutral_points": neutral_count,
        "is_explicit": False,
        "positive_phrases": positive_phrases,
        "negative_phrases": negative_phrases
    }

def extract_video_id(url):
    """Extracts the 11-character Video ID from various YouTube URL formats."""
    query = urlparse(url).query
    video_id = parse_qs(query).get('v')
    if video_id:
        return video_id[0]
    
    path = urlparse(url).path
    if path and ('youtu.be' in url or 'youtube.com' in url):
        match = re.search(r'([a-zA-Z0-9_-]{11})', path)
        if match:
            return match.group(1)
        
    return None

# --- FLASK ROUTES ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api')
def api():
    try:
        return {"message": "Working!"}
    except Exception as e:
        return str(e), 500


@app.route('/analyze', methods=['POST'])
def analyze():
    # 1. API Key Check
    if not YOUTUBE_API_KEY:
        return jsonify({"error": "YouTube API Key is missing. Please check your .env file.", "error_type": "api_key_error"})

    data = request.get_json()
    url = data.get('url', '')
    comments_to_analyze = []
    MAX_COMMENTS_TO_FETCH = 200

    # 2. Extract Video ID
    video_id = extract_video_id(url)
    if not video_id:
        return jsonify({"error": "Invalid URL or could not extract a YouTube video ID. Please use a valid YouTube link.", "error_type": "invalid_id"})

    try:
        # 3. Initialize the YouTube API Service
        youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
        next_page_token = None
        
        # --- Test for comments status (403 fix) ---
        try:
            # We perform a small check to see if the comment API works
            youtube.commentThreads().list(
                part="id",
                videoId=video_id,
                maxResults=1
            ).execute()
        except HttpError as e:
            if e.resp.status == 403:
                 return jsonify({"sentiment": "Neutral", "positive": 50.0, "negative": 50.0, "comment_count": 0, "positive_keywords": [], "negative_keywords": [], "error": "Comments are disabled or restricted for this video."})
            raise e 
        # --- END TEST ---
        
        # 4. Loop to fetch comments (Paging logic)
        while len(comments_to_analyze) < MAX_COMMENTS_TO_FETCH:
            if len(comments_to_analyze) >= MAX_COMMENTS_TO_FETCH:
                break
                
            request_api = youtube.commentThreads().list(
                part="snippet",
                videoId=video_id,
                maxResults=min(100, MAX_COMMENTS_TO_FETCH - len(comments_to_analyze)), 
                pageToken=next_page_token,
                textFormat="plainText"
            )
            response = request_api.execute()

            # 5. Extract comments and add to list
            for item in response.get("items", []):
                comment_text = item["snippet"]["topLevelComment"]["snippet"]["textDisplay"]
                comments_to_analyze.append(comment_text)

            next_page_token = response.get('nextPageToken')
            if not next_page_token:
                break 

    except HttpError as e:
        # 6. Handle API Errors (Quota, Video Not Found, etc.)
        status = e.resp.status
        if status == 404:
            error_message = "Video not found or is private/deleted."
        elif status == 403:
            error_message = "API Quota exceeded or Access Denied. Check your Google Cloud Console."
        else:
            error_message = f"YouTube API Error (Code: {status}). Could not fetch comments."
            
        return jsonify({"error": error_message, "error_type": "api_error"})
    
    # 7. Sentiment Calculation
    comment_count = len(comments_to_analyze)
    
    if comment_count == 0:
        return jsonify({"sentiment": "Neutral", "positive": 50.0, "negative": 50.0, "comment_count": 0, "positive_keywords": [], "negative_keywords": [], "error": "No comments found on this video."})

    all_results = [analyze_sentiment(comment) for comment in comments_to_analyze]

    # --- AGGREGATE PHRASES (PROOF) ---
    all_positive_phrases = [phrase for r in all_results for phrase in r.get('positive_phrases', [])]
    all_negative_phrases = [phrase for r in all_results for phrase in r.get('negative_phrases', [])]
    
    top_positive_keywords = [item[0] for item in Counter(all_positive_phrases).most_common(5)]
    top_negative_keywords = [item[0] for item in Counter(all_negative_phrases).most_common(5)]
    # --------------------------------

    # Calculate overall score (using Neutral points for accurate percentage)
    total_positive_points = sum(r['positive_points'] for r in all_results)
    total_negative_points = sum(r['negative_points'] for r in all_results)
    total_neutral_points = sum(r['neutral_points'] for r in all_results)
    total_score_for_percentage = total_positive_points + total_negative_points + total_neutral_points

    if any(r["is_explicit"] for r in all_results):
        overall_sentiment = "Negative"
        total_positive = 0.0
        total_negative = 100.0
    elif total_score_for_percentage == 0:
        overall_sentiment = "Neutral"
        total_positive = 50.0
        total_negative = 50.0
    else:
        # Calculate percentages against ALL words for accuracy (Neutrality Damping)
        total_positive = (total_positive_points / total_score_for_percentage) * 100
        total_negative = (total_negative_points / total_score_for_percentage) * 100
        
        # Determine final sentiment category based on net sentiment points (P vs N)
        sentiment_points = total_positive_points + total_negative_points
        
        if sentiment_points == 0:
            overall_sentiment = "Neutral"
        else:
            net_sentiment = (total_positive_points - total_negative_points) / sentiment_points
            
            if net_sentiment > 0.1: 
                overall_sentiment = "Positive"
            elif net_sentiment < -0.1: 
                overall_sentiment = "Negative"
            else:
                overall_sentiment = "Neutral"

    return jsonify({
        "sentiment": overall_sentiment,
        "positive": round(total_positive, 1),
        "negative": round(total_negative, 1),
        "comment_count": comment_count,
        "positive_keywords": top_positive_keywords, # RETURN PROOF
        "negative_keywords": top_negative_keywords  # RETURN PROOF
    })

if __name__ == "__main__":
    # Creates the file structure and saves the HTML
    if not os.path.exists('templates'):
        os.makedirs('templates')
    if not os.path.exists('static'):
        os.makedirs('static')
    
    # Saves the HTML content to the templates folder
    with open('templates/index.html', 'w') as f:
        f.write("""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Real-time CogniSense</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700&display=swap');
        body { font-family: 'Inter', sans-serif; background-color: #0d1117; color: #c9d1d9; }
        .container { max-width: 600px; }
        #resultBox { transition: background-color 0.5s ease-in-out, transform 0.3s ease-in-out; }
        #resultBox:hover { transform: translateY(-5px); }
        .result-positive { background-color: #235532; color: #2ecc71; }
        .result-negative { background-color: #552323; color: #e74c3c; }
        .result-neutral { background-color: #313338; color: #f1c40f; }
        #loadingSpinner { border-top-color: #3498db; -webkit-animation: spinner 1.5s linear infinite; animation: spinner 1.5s linear infinite; }
        @-webkit-keyframes spinner { 0% { -webkit-transform: rotate(0deg); } 100% { -webkit-transform: rotate(360deg); } }
        @keyframes spinner { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        .percentage-bar { transition: width 1s ease-in-out; }
    </style>
    <script src="{{ url_for('static', filename='script.js') }}"></script>
</head>
<body class="flex items-center justify-center min-h-screen p-4">
    <div class="container bg-gray-800 p-8 rounded-xl shadow-lg text-center">
        <h1 class="text-4xl font-bold mb-2 text-white">Real-time YouTube Sentiment Analyzer </h1>
        <p class="text-sm text-gray-400 mb-6">Fetches and analyzes the latest public comments from a YouTube video.</p>

        <div class="mb-4">
            <input type="text" id="urlInput" class="w-full p-3 rounded-lg bg-gray-900 border border-gray-700 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500" placeholder="Paste a YouTube video URL (e.g., youtube.com/watch?v=...)">
        </div>

        <button id="analyzeButton" onclick="analyzeUrl()" class="w-full bg-blue-600 text-white font-bold py-3 px-4 rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2">
            Analyze URL
        </button>

        <div id="loadingMessage" class="hidden text-center mt-4">
            <div id="loadingSpinner" class="w-8 h-8 border-4 border-gray-600 border-solid rounded-full inline-block"></div>
            <p id="loadingText" class="mt-2 text-gray-400">Connecting to server...</p>
        </div>

        <div id="errorBox" class="hidden mt-6 bg-red-800 bg-opacity-30 p-4 rounded-lg border border-red-700 text-red-400">
            <p id="errorMessage" class="font-bold">An error occurred. Please check the server status.</p>
        </div>
        
        <div id="resultBox" class="hidden mt-6 p-6 rounded-xl border border-gray-700 text-center">
            <h2 class="text-2xl font-bold mb-2 text-white">Analysis Result</h2>
            <p id="overallSentiment" class="text-xl font-bold mb-4">Overall Sentiment: </p>
            
            <div class="flex justify-between text-sm font-semibold mb-2">
                <span id="positivePercentage" class="text-green-400"></span>
                <span id="negativePercentage" class="text-red-400"></span>
            </div>
            <div class="w-full h-4 rounded-full bg-gray-600 overflow-hidden mb-4">
                <div id="positiveBar" class="h-full bg-green-500 float-left rounded-full percentage-bar"></div>
                <div id="negativeBar" class="h-full bg-red-500 float-left rounded-full percentage-bar"></div>
            </div>

            <h3 class="text-lg font-bold mt-6 mb-2 text-white">Top Sentiment Keywords (Proof)</h3>
            <div class="grid grid-cols-2 gap-4 text-left">
                <div class="bg-gray-700 p-3 rounded-lg border border-green-500/50">
                    <p class="font-semibold text-green-400 mb-1">Positive Phrases:</p>
                    <ul id="positiveKeywordsList" class="list-disc list-inside text-gray-300 text-sm">
                        </ul>
                </div>
                
                <div class="bg-gray-700 p-3 rounded-lg border border-red-500/50">
                    <p class="font-semibold text-red-400 mb-1">Negative Phrases:</p>
                    <ul id="negativeKeywordsList" class="list-disc list-inside text-gray-300 text-sm">
                        </ul>
                </div>
            </div>
            <p id="commentsAnalyzed" class="text-sm text-gray-400 mt-4"></p>
        </div>
    </div>
</body>
</html>""")

    # Run the Flask application
    app.run(debug=True)