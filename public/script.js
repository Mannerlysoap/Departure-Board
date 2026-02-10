const API_URL = '/api/departures';
const POLL_INTERVAL = 10000; // 10 seconds

const container = document.getElementById('departures-container');
const clockEl = document.getElementById('clock');
const statusEl = document.getElementById('status-bar');

function updateClock() {
    const now = new Date();
    // Get hours and minutes, ensuring they always have 2 digits (e.g., "09" instead of "9")
    const hours = String(now.getHours()).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');
    
    // Insert the HTML with the blinking class
    clockEl.innerHTML = `${hours}<span class="blink">:</span>${minutes}`;
}
function getMinutes(isoTime) {
    const diff = new Date(isoTime) - new Date();
    return Math.floor(diff / 60000);
}

function render(data) {
    container.innerHTML = '';
    
    if (data.length === 0) {
        container.innerHTML = '<div class="departure-row">Žádné odjezdy / No Service</div>';
        return;
    }

    data.forEach(dep => {
        const mins = getMinutes(dep.departureTime);
        if (mins < -1) return; // Hide departed

        const div = document.createElement('div');
        div.className = 'departure-row';
        
        // Color logic
        let colorClass = 'status-green';
        if (mins <= 1) colorClass = 'status-red';
        else if (mins <= 5) colorClass = 'status-yellow';

        // Time logic
        const timeText = mins <= 0 ? "TEĎ" : `${mins} min`;

        div.innerHTML = `
            <span class="line-number">${dep.line}</span>
            <span class="destination">${dep.destination}</span>
            <span class="align-right ${colorClass}">${timeText}</span>
        `;
        container.appendChild(div);
    });
}

async function fetchDepartures() {
    try {
        const res = await fetch(API_URL);
        if(!res.ok) throw new Error("API Error");
        const data = await res.json();
        render(data);
        statusEl.innerText = "PID Online • " + new Date().toLocaleTimeString('cs-CZ');
        statusEl.classList.remove('offline');
    } catch (e) {
        console.error(e);
        statusEl.innerText = "⚠ OFFLINE - Reconnecting...";
        statusEl.classList.add('offline');
    }
}

// Init
updateClock();
fetchDepartures();
setInterval(fetchDepartures, POLL_INTERVAL);
setInterval(updateClock, 1000);
