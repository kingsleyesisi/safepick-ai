document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('predictionForm');
    const analyzeBtn = document.getElementById('analyzeBtn');
    const btnText = analyzeBtn.querySelector('.btn-text');
    const btnLoader = analyzeBtn.querySelector('.btn-loader');
    const resultSection = document.getElementById('resultSection');

    // Result Elements
    const matchTitle = document.getElementById('matchTitle');
    const leagueBadge = document.getElementById('leagueBadge');
    const bestPick = document.getElementById('bestPick');
    const safePick = document.getElementById('safePick');
    const reasoningList = document.getElementById('reasoningList');
    const disclaimerText = document.getElementById('disclaimerText');

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        // Reset and show loader
        setLoading(true);
        resultSection.classList.add('hidden');

        const home = document.getElementById('homeTeam').value;
        const away = document.getElementById('awayTeam').value;
        const league = document.getElementById('league').value;

        try {
            const response = await fetch('/api/predict', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ home, away, league })
            });

            const data = await response.json();

            if (data.status === 'success') {
                displayResults(data);
            } else {
                alert('Analysis failed: ' + (data.message || 'Unknown error'));
            }
        } catch (error) {
            console.error('Error:', error);
            alert('An error occurred while connecting to the server.');
        } finally {
            setLoading(false);
        }
    });

    function setLoading(isLoading) {
        analyzeBtn.disabled = isLoading;
        if (isLoading) {
            btnText.classList.add('hidden');
            btnLoader.classList.remove('hidden');
        } else {
            btnText.classList.remove('hidden');
            btnLoader.classList.add('hidden');
        }
    }

    function displayResults(data) {
        matchTitle.textContent = data.match;
        leagueBadge.textContent = document.getElementById('league').value; // Or from data if available
        bestPick.textContent = data.best_pick;
        safePick.textContent = data.safer_alternative;
        
        reasoningList.innerHTML = '';
        data.reasoning.forEach(reason => {
            const li = document.createElement('li');
            li.textContent = reason;
            reasoningList.appendChild(li);
        });

        disclaimerText.textContent = data.disclaimer;
        
        resultSection.classList.remove('hidden');
        
        // Smooth scroll to results
        resultSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
});
