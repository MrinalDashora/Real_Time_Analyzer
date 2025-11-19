document.addEventListener('DOMContentLoaded', () => {
    // Event listener for the Enter key on the input field
    document.getElementById('urlInput').addEventListener('keyup', (event) => {
        if (event.key === 'Enter') {
            analyzeUrl();
        }
    });
});

/**
 * Initiates the sentiment analysis by fetching data from the Flask backend.
 */
async function analyzeUrl() {
    const urlInput = document.getElementById('urlInput').value.trim();
    const analyzeButton = document.getElementById('analyzeButton');
    const loadingMessage = document.getElementById('loadingMessage');
    const resultBox = document.getElementById('resultBox');
    const errorBox = document.getElementById('errorBox');
    const loadingText = document.getElementById('loadingText');

    // Hide previous results and errors
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

        // Step 1: Send the request to the Flask backend
        const response = await fetch('/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: urlInput })
        });

        if (!response.ok) {
            throw new Error(`Server returned status: ${response.status}`);
        }

        loadingText.textContent = "Analyzing comments...";

        // Step 2: Parse the JSON result
        const result = await response.json();

        loadingMessage.classList.add('hidden');
        analyzeButton.disabled = false;

        // Step 3: Handle Errors returned in the JSON payload
        if (result.error) {
            showError(result.error);
        } else {
            // Step 4: Destructure and display results
            const sentiment = result.sentiment;
            const positive = result.positive;
            const negative = result.negative;
            const commentCount = result.comment_count;
            const positiveKeywords = result.positive_keywords; // NEW
            const negativeKeywords = result.negative_keywords; // NEW

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

            // Animate the percentage bars
            positiveBar.style.width = `${positive}%`;
            negativeBar.style.width = `${negative}%`;

            // Correct bar layout for separation
            positiveBar.style.float = 'left';
            negativeBar.style.float = 'right';

            // Populate Keyword Lists (Proof Section)
            const posList = document.getElementById('positiveKeywordsList');
            const negList = document.getElementById('negativeKeywordsList');

            posList.innerHTML = positiveKeywords.map(word => `<li>${word}</li>`).join('') || '<li>None found</li>';
            negList.innerHTML = negativeKeywords.map(word => `<li>${word}</li>`).join('') || '<li>None found</li>';

            // Set box color based on sentiment
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

/**
 * Handles the display of error messages.
 */
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