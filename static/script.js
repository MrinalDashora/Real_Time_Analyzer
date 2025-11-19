document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('urlInput').addEventListener('keyup', (event) => {
        if (event.key === 'Enter') {
            analyzeUrl();
        }
    });
});

async function analyzeUrl() {
    const urlInput = document.getElementById('urlInput').value.trim();
    const analyzeButton = document.getElementById('analyzeButton');
    const loadingMessage = document.getElementById('loadingMessage');
    const resultBox = document.getElementById('resultBox');
    const errorBox = document.getElementById('errorBox');
    const loadingText = document.getElementById('loadingText');

    resultBox.classList.add('hidden');
    errorBox.classList.add('hidden');
    loadingMessage.classList.remove('hidden');
    
    analyzeButton.disabled = true;

    const urlPattern = /^(http|https):\/\/[^ "]+$/;
    if (!urlInput) {
        showError("Please enter a URL to analyze.");
        return;
    }
    if (!urlPattern.test(urlInput)) {
        showError("Invalid URL format. Please enter a full URL starting with http:// or https://.");
        return;
    }

    try {
        loadingText.textContent = "Sending URL to server...";

        const response = await fetch('/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: urlInput })
        });

        if (!response.ok) {
            throw new Error(`Server returned status: ${response.status}`);
        }

        loadingText.textContent = "Analyzing comments...";

        const result = await response.json();

        loadingMessage.classList.add('hidden');
        analyzeButton.disabled = false;

        if (result.error) {
            showError(result.error);
        } else {
            const sentiment = result.sentiment;
            const positive = result.positive;
            const negative = result.negative;
            const commentCount = result.comment_count;
            const positiveKeywords = result.positive_keywords; 
            const negativeKeywords = result.negative_keywords; 

            const sentimentText = document.getElementById('overallSentiment');
            const positivePercentage = document.getElementById('positivePercentage');
            const negativePercentage = document.getElementById('negativePercentage');
            const positiveBar = document.getElementById('positiveBar');
            const negativeBar = document.getElementById('negativeBar');
            const commentsAnalyzed = document.getElementById('commentsAnalyzed');

            sentimentText.textContent = `Overall Sentiment: ${sentiment}`;
            positivePercentage.textContent = `Positive: ${positive}%`;
            negativePercentage.textContent = `Negative: ${negative}%`;
            commentsAnalyzed.textContent = `Analyzed ${commentCount} comments.`;

            positiveBar.style.width = `${positive}%`;
            negativeBar.style.width = `${negative}%`;

            positiveBar.style.float = 'left';
            negativeBar.style.float = 'right';

            // Populate Keyword Lists (Proof Section)
            const posList = document.getElementById('positiveKeywordsList');
            const negList = document.getElementById('negativeKeywordsList');

            posList.innerHTML = positiveKeywords.map(word => `<li>${word}</li>`).join('') || '<li>None found</li>';
            negList.innerHTML = negativeKeywords.map(word => `<li>${word}</li>`).join('') || '<li>None found</li>';

            if (sentiment === 'Positive') {
                resultBox.className = 'mt-6 p-6 rounded-xl border border-gray-700 text-center result-positive';
            } else if (sentiment === 'Negative') {
                resultBox.className = 'mt-6 p-6 rounded-xl border border-gray-700 text-center result-negative';
            } else {
                resultBox.className = 'mt-6 p-6 rounded-xl border border-gray-700 text-center result-neutral';
            }
            resultBox.classList.remove('hidden');
        }

    } catch (error) {
        loadingMessage.classList.add('hidden');
        analyzeButton.disabled = false;
        console.error("Fetch error:", error);
        showError("A connection error occurred. Ensure the Flask server is running and the URL is correct.");
    }
}

function showError(message) {
    const errorBox = document.getElementById('errorBox');
    const errorMessage = document.getElementById('errorMessage');
    const analyzeButton = document.getElementById('analyzeButton');
    const loadingMessage = document.getElementById('loadingMessage');
    const resultBox = document.getElementById('resultBox');

    loadingMessage.classList.add('hidden');
    resultBox.classList.add('hidden');
    analyzeButton.disabled = false;
    
    errorMessage.textContent = message;
    errorBox.classList.remove('hidden');
}