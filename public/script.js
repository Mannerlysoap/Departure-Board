const API_URL = '/api/departures';
const CONFIG_URL = '/api/config';
const POLL_INTERVAL = 15000; // 15 seconds

const clockEl = document.getElementById('clock');
const statusEl = document.getElementById('status-bar');
const headerTitleEl = document.getElementById('header-title');
const dir0LabelEl = document.getElementById('dir0-label');
const dir1LabelEl = document.getElementById('dir1-label');

const containers = {
    direction0: document.getElementById('dir0-container'),
    direction1: document.getElementById('dir1-container')
};

async function fetchConfig() {
    try {
        const res = await fetch(`${CONFIG_URL}?t=${new Date().getTime()}`);
        if (!res.ok) throw new Error("Config API Error");
        const config = await res.json();
        
        if (headerTitleEl) headerTitleEl.innerText = config.header_title;
        if (dir0LabelEl) dir0LabelEl.innerText = config.dir0_label;
        if (dir1LabelEl) dir1LabelEl.innerText = config.dir1_label;
        
        const imgEl = document.getElementById('display-image');
        const overlayEl = document.getElementById('image-overlay');
        
        if (config.image_filename) {
            imgEl.src = `/uploads/${config.image_filename}?t=${new Date().getTime()}`;
            imgEl.style.display = 'block';
            
            if (config.image_overlay_text) {
                overlayEl.innerText = config.image_overlay_text;
                overlayEl.style.display = 'block';
            } else {
                overlayEl.style.display = 'none';
            }
        } else {
            imgEl.style.display = 'none';
            overlayEl.style.display = 'none';
        }

        window.siteConfig = config;
    } catch (e) {
        console.error("Failed to fetch config:", e);
    }
}

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

    const activeDeps = data.filter(dep => getMinutes(dep.departureTime) >= -1);
    
    activeDeps.slice(0, 7).forEach(dep => {
        const mins = getMinutes(dep.departureTime);
        const div = document.createElement('div');
        div.className = 'departure-row';
        
        let colorClass = 'status-green';
        if (mins <= 2) colorClass = 'status-red';
        else if (mins <= 5) colorClass = 'status-yellow';

        const timeText = mins <= 0 ? "TED" : `${mins} min`;

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
        
        renderDirection('direction0', data.direction0);
        renderDirection('direction1', data.direction1);
        
        const statusText = window.siteConfig ? window.siteConfig.status_bar : "System Online";
        statusEl.innerText = statusText + " • " + new Date().toLocaleTimeString('cs-CZ');
        statusEl.classList.remove('offline');
    } catch (e) {
        console.error(e);
        statusEl.innerText = "offline";
        statusEl.classList.add('offline');
    }
}

// Initial calls
fetchConfig().then(() => {
    fetchDepartures();
});
updateClock();

// Intervals
setInterval(fetchConfig, 60000);
setInterval(fetchDepartures, POLL_INTERVAL);
setInterval(updateClock, 1000);
