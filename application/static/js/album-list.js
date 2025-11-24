const ALBUMS_API_ENDPOINT = `${FASTAPI_URL}/api/albums/${GUILD_ID}`;
const ALBUM_GRID_ID = "album-list-grid";
const TRACK_COUNT_LIMIT = 5; // Tracks to display in the modal

/**
 * Utility function to display a custom notification (using your existing modal structure)
 * @param {string} title
 * @param {string} message
 * @param {boolean} isSuccess
 */
function showStatusNotification(title, message, isSuccess = true) {
    // This assumes a global function/modal structure exists for notifications
    const colorClass = isSuccess ? 'text-primary-green' : 'text-red-500';

    // Fallback to the generic message box structure from base.html if 'showConfirmation' is not available
    const modal = document.getElementById('message-box');
    const modalTitle = document.getElementById('message-box-title');
    const modalContent = document.getElementById('message-box-content');
    const modalActions = document.getElementById('message-box-actions');

    if (modal && modalTitle && modalContent && modalActions) {
        modalTitle.textContent = title;
        modalTitle.className = `text-xl font-bold mb-3 ${colorClass}`;
        modalContent.textContent = message;

        // Clear old actions and add a simple OK button
        modalActions.innerHTML = '';
        const okButton = document.createElement('button');
        okButton.textContent = 'OK';
        okButton.className = 'bg-primary-green text-black px-4 py-2 rounded-full hover:bg-[#1ed760] transition font-bold';
        okButton.onclick = () => modal.classList.remove('active');
        modalActions.appendChild(okButton);

        modal.classList.add('active');
    } else {
        console.warn('Custom modal structure not found. Falling back to alert.');
        alert(`${title}: ${message}`);
    }
}


/**
 * -----------------------------------------------------------
 * RENDER FUNCTIONS
 * -----------------------------------------------------------
 */

/**
 * Creates the HTML for a single album card.
 * @param {object} album
 * @returns {string} HTML string
 */
function createAlbumCardHTML(album) {
    // Note: Since the API doesn't provide album art, we use a placeholder based on the album name.
    const albumArtUrl = `https://placehold.co/200x200/${album.name.length > 5 ? '1db954' : '7a7a7a'}/ffffff?text=${encodeURIComponent(album.name.substring(0, 10).replace(/\s/g, '+'))}`;

    return `
        <button
            type="button"
            class="album-card w-full p-4 rounded-lg flex flex-col items-start transition transform hover:bg-dark-hover hover:-translate-y-1 hover:ring-2 hover:ring-primary-green cursor-pointer text-left group"
            onclick="openAlbumDetails('${album.name}')"
        >
            <div class="w-full aspect-square overflow-hidden rounded-lg mb-3 shadow-lg">
                <img
                    src="${albumArtUrl}"
                    alt="Album Art for ${album.name}"
                    class="object-cover w-full h-full transition duration-300 group-hover:scale-105"
                >
            </div>
            <div class="flex-grow w-full">
                <p class="text-base font-bold text-white truncate" title="${album.name}">${album.name}</p>
                <p class="text-xs text-gray-400 truncate">${album.track_count} tracks</p>
            </div>
        </button>
    `;
}

/**
 * Fetches all albums and populates the grid.
 */
async function loadServerAlbums() {
    const grid = document.getElementById(ALBUM_GRID_ID);
    if (!grid) return;

    try {
        const res = await fetch(ALBUMS_API_ENDPOINT);
        const albums = await res.json();

        if (res.status !== 200 || !albums || albums.detail) {
             grid.innerHTML = `<p class="text-gray-500 italic p-4">Error loading albums. API Status: ${res.status}</p>`;
             return;
        }

        if (albums.length === 0) {
            grid.innerHTML = `<p class="text-gray-500 italic p-4">No server albums found. Create one using the track search!</p>`;
        } else {
            grid.innerHTML = albums.map(createAlbumCardHTML).join("");
        }
    } catch (error) {
        console.error("Failed to fetch server albums:", error);
        grid.innerHTML = `<p class="text-red-500 italic p-4">Network error: Could not connect to the album service.</p>`;
    }
}


/**
 * -----------------------------------------------------------
 * ACTION FUNCTIONS
 * -----------------------------------------------------------
 */

/**
 * Plays all tracks from a selected album by adding them to the queue.
 * @param {string} albumName
 */
async function playAlbum(albumName) {
    showStatusNotification("Adding Album...", `Sending request to queue tracks from "${albumName}"...`, true);
    try {
        const res = await fetch(`${ALBUMS_API_ENDPOINT}/${albumName}/play`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
        });
        const data = await res.json();

        if (res.ok && data.success) {
            showStatusNotification("Queue Updated 🎶", data.message, true);
        } else {
            showStatusNotification("Error Playing Album", data.detail || `Failed to add album ${albumName} to queue.`, false);
        }

    } catch (error) {
        console.error("Error playing album:", error);
        showStatusNotification("Network Error", `Failed to communicate with music bot service.`, false);
    }
}

/**
 * Deletes a server album.
 * @param {string} albumName
 */
async function deleteAlbum(albumName) {
    if (!confirm(`Are you sure you want to delete the album "${albumName}" and ALL its tracks? This cannot be undone.`)) {
        return;
    }

    try {
        const res = await fetch(`${ALBUMS_API_ENDPOINT}/${albumName}`, {
            method: 'DELETE',
        });
        const data = await res.json();

        if (res.ok && data.success) {
            showStatusNotification("Album Deleted ✅", data.message, true);
            loadServerAlbums(); // Refresh list
        } else {
            showStatusNotification("Error Deleting Album", data.detail || `Failed to delete album ${albumName}.`, false);
        }
    } catch (error) {
        console.error("Error deleting album:", error);
        showStatusNotification("Network Error", `Failed to communicate with music bot service.`, false);
    }
}


/**
 * Opens a modal to display album details (tracks).
 * Note: This requires a separate modal structure in base.html or a dedicated section.
 * For simplicity, we'll use the existing message box structure but greatly expand its content.
 * @param {string} albumName
 */
async function openAlbumDetails(albumName) {
    // Assuming 'message-box' can be repurposed as a flexible modal
    const modal = document.getElementById('message-box');
    const modalContainer = modal.querySelector('div');
    const modalTitle = document.getElementById('message-box-title');
    const modalContent = document.getElementById('message-box-content');
    const modalActions = document.getElementById('message-box-actions');

    if (!modal) return;

    modalContainer.className = 'bg-card-bg p-6 rounded-xl shadow-2xl max-w-xl w-full transform transition-all mx-4 border border-gray-700';
    modalTitle.textContent = `Tracks in "${albumName}"`;
    modalTitle.className = 'text-2xl font-bold mb-4 text-primary-green';
    modalActions.innerHTML = '';
    modalContent.innerHTML = `<p class="text-gray-400">Loading tracks...</p>`;
    modal.classList.add('active');

    try {
        const res = await fetch(`${ALBUMS_API_ENDPOINT}/${albumName}`);
        const data = await res.json();

        if (res.ok && data.success) {
            const tracks = data.tracks;
            let trackListHTML = tracks.slice(0, TRACK_COUNT_LIMIT).map(t => `
                <div class="flex items-center justify-between py-2 border-b border-gray-700 last:border-b-0 text-gray-300 hover:text-white transition">
                    <div class="truncate mr-2">
                        <span class="font-semibold">${t.track_number}. ${t.title}</span>
                        <span class="text-xs text-gray-500 block">${t.author}</span>
                    </div>
                    <a href="${t.url}" target="_blank" class="text-primary-green hover:text-[#1ed760] text-sm flex-shrink-0">View</a>
                </div>
            `).join('');

            if (tracks.length > TRACK_COUNT_LIMIT) {
                trackListHTML += `<p class="text-gray-500 text-sm mt-2 italic">+ ${tracks.length - TRACK_COUNT_LIMIT} more tracks...</p>`;
            }

            modalContent.innerHTML = `<div class="space-y-2">${trackListHTML}</div>`;
        } else {
            modalContent.innerHTML = `<p class="text-red-500">${data.detail || 'Failed to load tracks.'}</p>`;
        }
    } catch (error) {
        console.error("Error loading album details:", error);
        modalContent.innerHTML = `<p class="text-red-500">Network error loading tracks.</p>`;
    }

    // Add action buttons
    modalActions.innerHTML = `
        <button onclick="playAlbum('${albumName}'); document.getElementById('message-box').classList.remove('active');"
                class="bg-primary-green text-black px-4 py-2 rounded-full hover:bg-[#1ed760] transition font-bold">
            ▶️ Play Album
        </button>
        <button onclick="deleteAlbum('${albumName}'); document.getElementById('message-box').classList.remove('active');"
                class="bg-red-600 text-white px-4 py-2 rounded-full hover:bg-red-700 transition font-bold">
            🗑️ Delete
        </button>
        <button onclick="document.getElementById('message-box').classList.remove('active');"
                class="bg-gray-700 text-white px-4 py-2 rounded-full hover:bg-gray-600 transition font-bold">
            Close
        </button>
    `;
    modalActions.className = 'flex justify-end space-x-3 pt-4';
}


// Load albums when the DOM is ready
document.addEventListener("DOMContentLoaded", () => {
    loadServerAlbums();
});
