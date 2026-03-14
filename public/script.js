// Init
updateClock();
fetchDepartures();
setInterval(fetchDepartures, POLL_INTERVAL);
setInterval(updateClock, 1000);


const API_URL = '/api/departures';
const POLL_INTERVAL = 15000; // 15 seconds

const clockEl = document.getElementById('clock');
const statusEl = document.getElementById('status-bar');

const containers = {
    direction0: document.getElementById('dir0-container'),
    direction1: document.getElementById('dir1-container')
};

function updateClock() {
    const now = new Date();
    const hours = String(now.getHours()).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');
    clockEl.innerHTML = `${hours}<span class="blink">:</span>${minutes}`;
}

function getMinutes(isoTime) {
    const diff = new Date(isoTime) - new Date();
    return Math.floor(diff / 60000);
}

function renderDirection(directionKey, data) {
    const container = containers[directionKey];
    if (!container) return;
    
    container.innerHTML = '';
    
    if (!data || data.length === 0) {
        container.innerHTML = '<div class="loading">Nic nejede</div>';
        return;
    }

    // Update Label if possible (e.g. from first departure's destination context, 
    // but we'll stick to generic or better info if we had it)
    
    const activeDeps = data.filter(dep => getMinutes(dep.departureTime) >= -1);
    
    activeDeps.slice(0, 12).forEach(dep => {
        const mins = getMinutes(dep.departureTime);
        const div = document.createElement('div');
        div.className = 'departure-row';
        
        let colorClass = 'status-green';
        if (mins <= 2) colorClass = 'status-red';
        else if (mins <= 5) colorClass = 'status-yellow';

        const timeText = mins <= 0 ? ">1" : `${mins} min`;

        div.innerHTML = `
            <span class="line-number">${dep.line}</span>
            <div class="destination">
                <span class="marquee-inner">${dep.destination}</span>
            </div>
            <span class="align-right ${colorClass}">${timeText}</span>
        `;
        container.appendChild(div);

        // Animate if overflowing
        const dest = div.querySelector('.destination');
        const inner = div.querySelector('.marquee-inner');
        if (inner.offsetWidth > dest.offsetWidth) {
            dest.classList.add('overflowing');
            // Duplicate for seamless loop
            const clone = inner.cloneNode(true);
            clone.setAttribute('aria-hidden', 'true');
            dest.appendChild(clone);
        }
    });
}

async function fetchDepartures() {
    try {
        const res = await fetch(API_URL);
        if(!res.ok) throw new Error("API Error");
        const data = await res.json();
        
        // Data is now grouped by direction
        renderDirection('direction0', data.direction0);
        renderDirection('direction1', data.direction1);
        
        // Handle any additional directions dynamically if they exist
        Object.keys(data).forEach(key => {
            if (key !== 'direction0' && key !== 'direction1' && key.startsWith('direction')) {
                // For now we only have two slots in HTML, but we could create them
                console.log("Extra direction found:", key);
            }
        });

        statusEl.innerText = "Server online • " + new Date().toLocaleTimeString('cs-CZ');
        statusEl.classList.remove('offline');
    } catch (e) {
        console.error(e);
        statusEl.innerText = "offline";
        statusEl.classList.add('offline');
    }
}

