/**
 * CogniSense Neural Engine v2.0
 * Developer: Mrinal Dashora | Roll No: 24BCON1413
 */

async function analyzeUrl() {
    const url = document.getElementById('urlInput').value.trim();
    if(!url) return alert("System Warning: Please provide a valid YouTube URL Uplink.");
    
    const btn = document.getElementById('analyzeButton');
    const idle = document.getElementById('idleState');
    const load = document.getElementById('loadingMessage');
    const res = document.getElementById('resultBox');
    
    // UI Phase Transition
    res.classList.add('hidden');
    idle.classList.add('hidden');
    load.classList.remove('hidden');
    btn.disabled = true;
    btn.style.opacity = "0.5";

    try {
        const r = await fetch('/analyze', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({url: url})
        });
        const data = await r.json();
        
        if(data.error) { 
            alert("Analysis Error: " + data.error); 
            load.classList.add('hidden'); 
            idle.classList.remove('hidden');
            btn.disabled = false; 
            btn.style.opacity = "1";
            return; 
        }

        // Mapping Intelligence Data
        document.getElementById('overallSentiment').textContent = data.sentiment;
        document.getElementById('commentsAnalyzed').textContent = data.comment_count.toLocaleString();
        document.getElementById('posP').textContent = data.positive + "%";
        document.getElementById('negP').textContent = data.negative + "%";
        
        // Progressive Bar Loading
        document.getElementById('positiveBar').style.width = "0%";
        document.getElementById('negativeBar').style.width = "0%";
        setTimeout(() => {
            document.getElementById('positiveBar').style.width = data.positive + "%";
            document.getElementById('negativeBar').style.width = data.negative + "%";
        }, 150);

        // Neural Tag Rendering
        const renderTags = (id, words, colorClass) => {
            document.getElementById(id).innerHTML = words.map(w => `
                <li class="px-3 py-1.5 rounded-xl border border-white/10 bg-white/5 text-[10px] font-mono font-bold tracking-tight flex items-center gap-2 group hover:border-cyan-500/50 transition-all">
                    <span class="w-1 h-1 rounded-full ${colorClass}"></span>
                    ${w.toUpperCase()}
                </li>
            `).join('');
        };
        renderTags('posList', data.positive_keywords, 'bg-cyan-400');
        renderTags('negList', data.negative_keywords, 'bg-rose-500');

        load.classList.add('hidden');
        res.classList.remove('hidden');
        
    } catch(e) { 
        console.error("Critical System Failure:", e); 
        alert("Fatal System Exception. Check console.");
    } finally {
        btn.disabled = false;
        btn.style.opacity = "1";
    }
}