<script>
    async function connectVideo() {
        const urlInput = document.getElementById('videoUrl');
        const url = urlInput.value.trim();
        const btn = document.querySelector('button');

        if (!url) {
            alert("System Warning: URL missing.");
            return;
        }

        // UI Feedback
        btn.innerText = "Processing...";
        btn.disabled = true;

        try {
            console.log("Fetching analysis for:", url); // Debug: Check URL in console
            
            const response = await fetch('/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: url })
            });

            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            
            const result = await response.json();
            
            if (result.error) throw new Error(result.error);
            
            // UI Update: DOM Elements ko update karte waqt check karo
            const data = result.data;
            
            const posEl = document.querySelector('.text-2xl.font-black.text-blue-600');
            const negEl = document.querySelector('.text-2xl.font-black.text-rose-600');
            
            if (posEl && negEl) {
                posEl.innerText = data.positive + "%";
                negEl.innerText = data.negative + "%";
            }

            // Stream rendering with check
            const streamDiv = document.querySelector('#view-pulse .text-xs');
            if (streamDiv) {
                streamDiv.innerHTML = data.stream.map(c => `
                    <div class="mb-4 p-4 rounded-xl border border-slate-100 bg-white text-left">
                        <p class="text-xs ${c.sentiment === 'negative' ? 'text-rose-600' : 'text-slate-700'}">${c.html}</p>
                    </div>
                `).join('');
            }

            console.log("Analysis success:", data);
        } catch (e) {
            console.error("Critical System Failure:", e);
            alert("Fatal Exception: Check console for trace.");
        } finally {
            btn.innerText = "Connect";
            btn.disabled = false;
        }
    }
</script>