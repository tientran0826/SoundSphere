let isPlaying = false;
let currentTrackDuration = 0;
let resolveMessageBox = null;
let isQueueOpen = false;
let queueInterval = null;


// --- Message Box (Custom Alert/Confirm) Implementation ---
function showMessage(title, message, isConfirm = false, onConfirm = null) {
    const box = document.getElementById('message-box');
    document.getElementById('message-box-title').textContent = title;
    document.getElementById('message-box-content').textContent = message;

    const actions = document.getElementById('message-box-actions');
    actions.innerHTML = '';

    if (isConfirm) {
        const cancelBtn = document.createElement('button');
        cancelBtn.textContent = 'Cancel';
        cancelBtn.className = 'bg-gray-300 hover:bg-gray-400 text-gray-800 font-semibold py-2 px-4 rounded-lg transition';
        cancelBtn.onclick = () => {
            box.classList.remove('active');
            if (resolveMessageBox) resolveMessageBox(false);
            resolveMessageBox = null;
        };
        actions.appendChild(cancelBtn);

        const confirmBtn = document.createElement('button');
        confirmBtn.textContent = 'Confirm';
        confirmBtn.className = 'bg-red-500 hover:bg-red-600 text-white font-semibold py-2 px-4 rounded-lg transition';
        confirmBtn.onclick = () => {
            box.classList.remove('active');
            if (resolveMessageBox) resolveMessageBox(true);
            if (onConfirm) onConfirm();
            resolveMessageBox = null;
        };
        actions.appendChild(confirmBtn);

        return new Promise(resolve => {
            resolveMessageBox = resolve;
        });
    } else {
        const okBtn = document.createElement('button');
        okBtn.textContent = 'OK';
        okBtn.className = 'bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-2 px-4 rounded-lg transition';
        okBtn.onclick = () => box.classList.remove('active');
        actions.appendChild(okBtn);
    }

    box.classList.add('active');
}

function showConfirmation(message, title, action) {
    showMessage(title, message, true, action);
}

// --- Utility Functions ---
function formatDuration(seconds) {
    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${minutes}:${secs.toString().padStart(2, '0')}`;
}

function toggleQueue() {
    isQueueOpen = !isQueueOpen;
    const sidebar = document.getElementById('queue-sidebar');
    const overlay = document.getElementById('queue-overlay');
    if (!sidebar || !overlay) return;

    if (isQueueOpen) {
        // This is the critical line to show the sidebar using your custom CSS
        sidebar.classList.add('open');

        overlay.classList.remove('hidden');
        overlay.classList.add('active');
        fetchQueueData();
        queueInterval = setInterval(fetchQueueData, 1000);
    } else {
        // This is the critical line to hide the sidebar
        sidebar.classList.remove('open');

        overlay.classList.add('hidden');
        overlay.classList.remove('active');
        if (queueInterval) {
            clearInterval(queueInterval);
            queueInterval = null;
        }
    }
}
document.getElementById('queue-overlay')?.addEventListener('click', () => {
    if (isQueueOpen) toggleQueue();
});

async function togglePlayPause() {
    const response = await fetch(`${FASTAPI_URL}/api/bot/${GUILD_ID}/status`);
    const data = await response.json();
    const info = data.status || {};

    isPlaying = info.playing;
    isPaused = info.paused;
    currentTrack = info.current_track;

    if (isPlaying) {
        const command = isPaused ? 'resume' : 'pause';
        console.log("Toggling play/pause:", command);
        sendControlCommand(command);
    }
}

function sendSeek(seconds) {
    console.log("Sending seek with:", USER_ID); // debug
    console.log("Seeking to seconds:", seconds);
    fetch(`${FASTAPI_URL}/api/bot/${GUILD_ID}/seek`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            user_id: USER_ID,    // must be number
            position: seconds    // seconds
        })
    })
    .then(response => response.json())
    .then(data => {
        fetchBotStatus();    // update UI after seek
    })
    .catch(err => console.error("Seek error:", err));
}

function seek(event) {
    const bar = event.currentTarget;
    const rect = bar.getBoundingClientRect();
    const clickX = event.clientX - rect.left;
    const width = rect.width;

    // Percent user clicked
    const percent = clickX / width;

    // totalSeconds: update this every fetchBotStatus()
    const totalSeconds = window.currentTrackDuration || 0;

    // New seek position (in seconds)
    const newPosition = Math.floor(percent * totalSeconds);

    console.log("Seeking to:", newPosition, "seconds");

    // Send to backend
    sendSeek(newPosition);
}

function sendControlCommand(command) {
    let url = '';

    if (command === 'connect_bot') {
        url = `/connect_bot/${GUILD_ID}`;
    } else {
        url = `/control/${command}/${GUILD_ID}`;
    }

    fetch(url)
        .then(response => {
            if (!response.ok) {
                if (response.status === 302) {
                    return;
                }
                throw new Error(`Server returned status ${response.status}`);
            }
            fetchBotStatus();
        })
        .catch(error => {
            console.error(`Error executing ${command}:`, error);
            showMessage('Action Failed', `❌ Failed to ${command}: ${error.message}`);
        });
}

function sendQueueControlCommand(path, method = 'POST', body = null) {
    const url = `${FASTAPI_URL}/api/queue/${GUILD_ID}/${path}`;

    const options = {
        method: method,
        headers: {
            'Content-Type': 'application/json',
        },
    };

    if (body) {
        options.body = JSON.stringify(body);
    }

    fetch(url, options)
        .then(response => {
            if (response.ok) {
                fetchQueueData();
                fetchBotStatus();
                return;
            } else {
                return response.json().then(err => { throw new Error(err.detail || 'Command failed'); });
            }
        })
        .catch(error => {
            console.error(`Error executing queue command:`, error);
            showMessage('Action Failed', `❌ Failed to execute queue action: ${error.message}`);
        });
}

function clearQueueAction() {
    sendQueueControlCommand('', 'DELETE');
}

function shuffleQueue() {
    sendQueueControlCommand('shuffle');
}
function queueMusic(query) {
    const url = `/search/${encodeURIComponent(query)}`;
    window.location.href = url;
}

function searchAndPlay() {
    const query = document.getElementById('search-input').value.trim();
    if (!query) return showMessage('Input Required', 'Please enter a song name or a YouTube URL.');
    queueMusic(query);
}
function setVolume(volume) {
    console.log("Setting volume to:", volume);
    document.getElementById('volume-slider').value = volume;
}

function seek(event) {
    if (!currentTrackDuration) return;

    const progressBar = event.currentTarget;
    const rect = progressBar.getBoundingClientRect();
    const clickX = event.clientX - rect.left;
    const width = rect.width;

    const seekPercentage = clickX / width;
    const seekTimeMs = Math.floor(currentTrackDuration * seekPercentage);

    document.getElementById('progress-bar-fill').style.width = `${seekPercentage * 100}%`;
    document.getElementById('current-time').textContent = formatDuration(seekTimeMs);
    console.log("Seeking to:", seekTimeMs, "ms");
}

function fetchQueueData() {
    fetch(`${FASTAPI_URL}/api/queue/${GUILD_ID}`)
        .then(response => response.ok ? response.json() : { queue: [] })
        .then(data => {
            const queue = Array.isArray(data.queue) ? data.queue : [];
            renderQueue(queue);
        })
        .catch(error => {
            console.error("Error fetching queue:", error);
            const queueList = document.getElementById('queue-list');
            if (queueList) {
                queueList.innerHTML = '<p class="text-red-500 text-center py-8">❌ Failed to load queue</p>';
            }
        });
}

function renderQueue(queue) {
    const container = document.getElementById('queue-list');
    if (!container) return;

    if (!Array.isArray(queue) || queue.length === 0) {
        container.innerHTML = '<p class="text-gray-500 text-center py-8">Queue is empty. Add a track!</p>';
        return;
    }

    let html = '';
    queue.forEach(track => {
        html += `
            <div class="queue-item p-3 rounded-lg border border-gray-700 flex justify-between items-center mb-2">
                <div class="flex items-center space-x-3 flex-1 min-w-0">
                    <span class="text-gray-400 font-semibold text-sm w-6">${track.position}</span>
                    <img src="https://img.youtube.com/vi/${track.identifier}/hqdefault.jpg" alt="Thumbnail" class="w-12 h-12 rounded">
                    <div class="flex-1 min-w-0">
                        <p class="text-sm font-medium text-white truncate">${track.title}</p>
                        <p class="text-xs text-gray-400 truncate">${track.author || 'Unknown'}</p>
                    </div>
                </div>
                <div class="flex space-x-2">
                    <button onclick="jumpToTrack(${track.position})" class="text-green-400 hover:text-green-500 font-bold px-2 py-1 rounded transition">
                        ▶
                    </button>
                    <button onclick="removeTrackFromQueue(${track.position})" class="text-red-500 hover:text-red-600 font-bold px-2 py-1 rounded transition">
                        ✖
                    </button>
                </div>
            </div>
        `;
    });

    container.innerHTML = html;
}


function jumpToTrack(position) {
    fetch(`${FASTAPI_URL}/api/queue/${GUILD_ID}/jump?index=${position}`, {
        method: 'POST'
    })
    .then(async response => {
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `HTTP ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        console.log('Jump success:', data.message);
        fetchQueueData(); // refresh queue after jump
    })
    .catch(err => {
        console.error('Error jumping to track:', err.message || err);
        alert(`❌ Jump failed: ${err.message || 'Unknown error'}`);
    });
}

function removeTrackFromQueue(position) {
    fetch(`${FASTAPI_URL}/api/queue/${GUILD_ID}/${position}`, { method: 'DELETE' })
        .then(response => {
            if (!response.ok) throw new Error('Failed to remove track');
            fetchQueueData();
        })
        .catch(err => console.error('Error removing track:', err));
}

// Auto-refresh queue every 1 second
setInterval(fetchQueueData, 1000);

function fetchBotStatus() {
    fetch(`${FASTAPI_URL}/api/bot/${GUILD_ID}/status`)
        .then(response => {
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return response.json();
        })
        .then(data => {
            const info = data.status || {};
            const track = info.current_track;
            const isConnected = info.connected;

            // Toggle Connect/Disconnect buttons safely
            const disconnectBtn = document.getElementById('disconnect-btn');
            const connectBtn = document.getElementById('connect-btn');
            if (disconnectBtn) disconnectBtn.classList.toggle('hidden', !isConnected);
            if (connectBtn) connectBtn.classList.toggle('hidden', isConnected);

            // Enable/disable controls safely
            const controls = ['play-pause-btn', 'prev-btn', 'skip-btn'];
            controls.forEach(id => {
                const el = document.getElementById(id);
                if (el) el.disabled = !isConnected;
            });

            // Track info
            const albumArtBar = document.getElementById('album-art-bar');
            const trackInfo = document.getElementById('track-info-bar');

            if (track) {
                albumArtBar.src = track.identifier
                    ? `https://img.youtube.com/vi/${track.identifier}/hqdefault.jpg`
                    : '/static/images/avatar.jpg';

                trackInfo.innerHTML = `
                    <p class="text-sm font-semibold truncate">${track.title}</p>
                    <p class="text-xs text-gray-400 truncate">${track.author || 'Unknown Artist'}</p>
                `;
            } else {
                albumArtBar.src = '/static/images/avatar.jpg'; // reset default
                const subText = isConnected
                    ? '<p class="text-xs text-gray-400 truncate">Queue a song</p>'
                    : `<p onclick="sendControlCommand('connect_bot')" class="cursor-pointer text-green-400 hover:text-green-300">Connect Bot</p>`;

                trackInfo.innerHTML = `
                    <p class="text-sm font-semibold text-gray-400">No track playing</p>
                    ${subText}
                `;
            }

            // Progress bar
            const currentPos = track ? track.position : 0;
            const totalDur = track ? track.duration : 1;
            const progressPercent = (currentPos / totalDur) * 100;
            const currentTime = document.getElementById('current-time');
            const totalTime = document.getElementById('total-time');
            const progressFill = document.getElementById('progress-bar-fill');

            if (currentTime) currentTime.textContent = formatDuration(currentPos);
            if (totalTime) totalTime.textContent = formatDuration(totalDur);
            if (progressFill) progressFill.style.width = `${progressPercent}%`;

            // Play/Pause icons
            const playIcon = document.getElementById('play-icon');
            const pauseIcon = document.getElementById('pause-icon');
            if (playIcon && pauseIcon) {
                if (track && !info.paused && info.playing) {
                    playIcon.classList.add('hidden');
                    pauseIcon.classList.remove('hidden');
                } else {
                    playIcon.classList.remove('hidden');
                    pauseIcon.classList.add('hidden');
                }
            }

            // Volume bar
            const volumeContainer = document.getElementById('volume-bar-container');
            const volumeFill = document.getElementById('volume-bar-fill');
            if (volumeFill) {
                if (info.volume != null) volumeFill.style.width = `${info.volume * 100}%`;
            }
            if (volumeContainer) {
                volumeContainer.classList.toggle('opacity-50', !isConnected);
                volumeContainer.classList.toggle('cursor-not-allowed', !isConnected);
                volumeContainer.style.pointerEvents = isConnected ? 'auto' : 'none';
            }
            if (isQueueOpen) fetchQueueData();
        })
        .catch(error => {
            console.error("Error fetching bot status:", error);

            const trackInfo = document.getElementById('track-info-bar');
            const albumArtBar = document.getElementById('album-art-bar');

            if (trackInfo) {
                albumArtBar.src = `https://img.youtube.com/vi/${track.identifier}/hqdefault.jpg`;
                trackInfo.innerHTML = `
                    <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-700/20 text-gray-300 backdrop-blur-sm">
                        API Offline
                    </span>
                `;
            }

            document.getElementById('disconnect-btn')?.classList.add('hidden');
            document.getElementById('connect-btn')?.classList.remove('hidden');

            const controls = ['play-pause-btn', 'prev-btn', 'skip-btn'];
            controls.forEach(id => {
                const el = document.getElementById(id);
                if (el) el.disabled = true;
            });
        });
}


function fetchUserVoiceStatus() {
    fetch(`${FASTAPI_URL}/api/bot/${GUILD_ID}/user/${USER_ID}/voice-check`)
        .then(response => {
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return response.json();
        })
        .then(data => {
            const userInVoice = data.in_voice || false;
            const display = document.getElementById('status-user-voice-badge');
            if (!display) return;

            // Smooth transition wrapper
            display.classList.add("transition-all", "duration-300");

            let statusHTML;

            if (userInVoice) {
                statusHTML = `
                    <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-700/20 text-green-400 backdrop-blur-sm">
                        <svg class="w-3 h-3 mr-1 text-green-400" fill="currentColor" viewBox="0 0 20 20">
                            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/>
                        </svg>
                        Connected
                    </span>
                `;
            } else {
                statusHTML = `
                    <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-700/20 text-red-400 backdrop-blur-sm">
                        <svg class="w-3 h-3 mr-1 text-red-400" fill="currentColor" viewBox="0 0 24 24">
                            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/>
                        </svg>
                        Join a voice chat
                    </span>
                `;
            }

            display.innerHTML = statusHTML;
        })
        .catch(error => {
            console.error("Error fetching user voice status:", error);
            const display = document.getElementById('status-user-voice-badge');
            if (!display) return;

            display.innerHTML = `
                <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-700/20 text-gray-300 backdrop-blur-sm">
                    <svg class="w-3 h-3 mr-1 text-gray-300" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/>
                    </svg>
                    API Offline
                </span>
            `;
        });

}

// document.addEventListener('DOMContentLoaded', () => {
//     // Open the queue automatically
//     isQueueOpen = true;
//     const sidebar = document.getElementById('queue-sidebar');
//     const overlay = document.getElementById('queue-overlay');

//     if (sidebar && overlay) {
//         sidebar.classList.add('open');
//         overlay.classList.add('active');
//         fetchQueueData(); // fetch immediately

//         // Auto-refresh queue every 1 second
//         setInterval(fetchQueueData, 1000);
//     }
// });
// Initialize player on page load
document.addEventListener('DOMContentLoaded', () => {
    // Display guild name
    const guildNameDisplay = document.getElementById('guild-name-display');
    if (guildNameDisplay && typeof GUILD_NAME !== 'undefined') {
        guildNameDisplay.textContent = GUILD_NAME;
    }

    // Search input - Enter key action
    const searchInput = document.getElementById('search-input');
    if (searchInput) {
        searchInput.addEventListener('keyup', function(event) {
            if (event.key === 'Enter') {
                event.preventDefault();
                searchAndPlay();
            }
        });
    }

    // Initialize bot/user status
    if (typeof FASTAPI_URL !== 'undefined' && FASTAPI_URL && FASTAPI_URL !== "None") {
        fetchBotStatus();
        fetchUserVoiceStatus();
        setInterval(fetchBotStatus, 1000);
        setInterval(fetchUserVoiceStatus, 500);
    } else {
        console.warn('FastAPI URL not configured. Bot status features disabled.');

        const trackInfo = document.getElementById('track-info-bar');
        if (trackInfo) {
            trackInfo.innerHTML = '<p class="text-sm font-semibold text-gray-400">Login to use</p>';
        }

        const statusBadge = document.getElementById('status-user-voice-badge');
        if (statusBadge) {
            statusBadge.innerHTML = `
                <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600">
                    Login to use
                </span>
            `;
        }
    }
});

function showConfirmPopup(trackTitle) {
    const modal = document.getElementById("confirm-modal");
    const message = document.getElementById("confirm-message");

    message.textContent = `Added "${trackTitle}" to the queue.`;

    // Make modal visible
    modal.classList.remove("opacity-0", "pointer-events-none");
    modal.classList.add("opacity-100");

    // Close on OK click
    const okBtn = document.getElementById("confirm-ok-btn");
    okBtn.onclick = () => {
        modal.classList.add("opacity-0", "pointer-events-none");
        modal.classList.remove("opacity-100");
    };
}

document.addEventListener('DOMContentLoaded', () => {
    const addButtons = document.querySelectorAll('.add-track-btn');

    addButtons.forEach(btn => {
        btn.addEventListener('click', function () {
            const button = this;
            const trackUri = button.dataset.trackUri;
            const trackTitle = button.dataset.trackTitle;
            const guildId = button.dataset.guildId;
            const trackAuthor = button.dataset.trackAuthor;
            const requestBy = button.dataset.userId;
            const identifier = button.dataset.identifier;
            console.log("Adding track:", trackTitle, "URI:", trackUri, "Identifier:", identifier);
            // Prevent double clicks
            button.disabled = true;
            button.classList.add('opacity-75', 'cursor-wait');

            if (typeof FASTAPI_URL === 'undefined' || !FASTAPI_URL) {
                console.error('FASTAPI_URL not defined');
                showErrorToast('API Error', '❌ API URL not configured');
                button.disabled = false;
                button.classList.remove('opacity-75', 'cursor-wait');
                return;
            }

            fetch(`${FASTAPI_URL}/api/bot/${guildId}/status`)
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`HTTP ${response.status}`);
                    }
                    return response.json();
                })
                .then(data => {
                    const info = data.status || {};
                    const isPlaying = info.playing;
                    const isConnected = info.connected;

                    // If not playing but connected → play immediately
                    if (!isPlaying && isConnected) {
                        return fetch(`${FASTAPI_URL}/api/bot/${guildId}/play`, {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                            },
                            body: JSON.stringify({
                                url: trackUri,
                                track_title: trackTitle,
                                track_author: trackAuthor,
                                requested_by: requestBy,
                                identifier: identifier
                            })
                        }).then(response => response.json())
                        .then(data => {
                            console.log("Track started:", data);
                            // Now render the queue after the track starts
                            renderQueue();
                        })
                        .catch(err => {
                            console.error("Failed to play track:", err);
                        });
                    }

                    // Otherwise → add to queue
                    return fetch(`${FASTAPI_URL}/api/queue/${guildId}`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            url: trackUri,
                            track_title: trackTitle,
                            track_author: trackAuthor,
                            requested_by: requestBy,
                            identifier: identifier
                        })
                    })
                        .then(response => {
                            if (!response.ok) {
                                return response.json().then(err => {
                                    throw new Error(err.detail || 'Server error');
                                });
                            }
                            return response.json();
                        })
                        .then(() => {
                            showConfirmPopup(trackTitle);
                        });
                })
                .catch(error => {
                    console.error('Error adding track:', error);
                    alert(`❌ Failed to add track: ${error.message}`);
                })
                .finally(() => {
                    // Re-enable button
                    setTimeout(() => {
                        button.disabled = false;
                        button.classList.remove('opacity-75', 'cursor-wait');
                    }, 1500);
                });
        });
    });
});
let isDraggingVolume = false;

const container = document.getElementById('volume-bar-container');
const fill = document.getElementById('volume-bar-fill');

// Start dragging
container.addEventListener('mousedown', e => {
    isDraggingVolume = true;
    updateVolume(e); // update immediately
});

// Dragging
document.addEventListener('mousemove', e => {
    if (!isDraggingVolume) return;
    updateVolume(e);
});

// Stop dragging
document.addEventListener('mouseup', () => {
    isDraggingVolume = false;
});

// Update volume visually and send to backend
function updateVolume(e) {
    if (!container || !fill) return;

    const rect = container.getBoundingClientRect();
    let width = e.clientX - rect.left;
    width = Math.max(0, Math.min(width, rect.width));
    const volumePercent = Math.round((width / rect.width) * 100);
    fill.style.width = `${volumePercent}%`;

    // Send absolute volume to backend
    fetch(`${FASTAPI_URL}/api/bot/${GUILD_ID}/volume_absolute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            user_id: USER_ID,   // your current user ID
            volume: volumePercent
        })
    })
    .then(res => res.json())
    .catch(err => console.error('Volume update failed', err));
}

let isSeeking = false;
let progressBar;
let progressFill;

document.addEventListener("DOMContentLoaded", () => {
    progressBar = document.querySelector(".progress-bar-container");
    progressFill = document.getElementById("progress-bar-fill");

    // Mouse Events
    progressBar.addEventListener("mousedown", startSeek);
    window.addEventListener("mousemove", moveSeek);
    window.addEventListener("mouseup", endSeek);

    // Touch Events
    progressBar.addEventListener("touchstart", startSeek);
    window.addEventListener("touchmove", moveSeek);
    window.addEventListener("touchend", endSeek);
});

function startSeek(e) {
    isSeeking = true;
    updateSeekPreview(e);
}

function moveSeek(e) {
    if (!isSeeking) return;
    updateSeekPreview(e);
}

async function endSeek(e) {
    if (!isSeeking) return;
    isSeeking = false;

    const newPosition = await getSeekSeconds(e); // await Promise
    console.log("Final seek:", newPosition);

    sendSeek(newPosition);
}

async function getSeekSeconds(e) {
    const rect = progressBar.getBoundingClientRect();
    const clientX = e.clientX ?? e.touches?.[0]?.clientX;
    const x = Math.min(Math.max(clientX - rect.left, 0), rect.width);

    const percent = x / rect.width;

    // ⚠ You are fetching status AGAIN here — not good
    const response = await fetch(`${FASTAPI_URL}/api/bot/${GUILD_ID}/status`);
    const data = await response.json();
    const info = data.status || {};

    const totalSeconds = info.current_track ? info.current_track.duration : 0;
    console.log("Total track duration:", totalSeconds);
    console.log("Seek percent:", percent * totalSeconds);
    return Math.floor(percent * totalSeconds);
}

function updateSeekPreview(e) {
    const rect = progressBar.getBoundingClientRect();
    const clientX = e.clientX ?? e.touches?.[0]?.clientX;
    const x = Math.min(Math.max(clientX - rect.left, 0), rect.width);

    const percent = (x / rect.width) * 100;
    progressFill.style.width = `${percent}%`;
}
