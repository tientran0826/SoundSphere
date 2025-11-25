// ================================
// Global variable to hold track info
// ================================
let pendingTrack = {
    title: null,
    url: null,
    author: null,
    identifier: null
};


// ================================
// 1. OPEN MODAL & FETCH ALBUMS
// ================================
async function openAlbumSelectionModal(title, url, author, identifier) {
    // Store track info
    pendingTrack = { title, url, author, identifier };

    const modal = document.getElementById('album-select-modal');
    const listContainer = document.getElementById('modal-album-list');
    const trackNameElem = document.getElementById('modal-track-name');

    if (!modal || !listContainer || !trackNameElem) return;

    // Update UI
    trackNameElem.innerText = title;
    modal.classList.remove('hidden');
    listContainer.innerHTML = `<div class="text-center py-4 text-gray-500">Loading albums...</div>`;

    try {
        const response = await fetch(`${FASTAPI_URL}/api/albums/${GUILD_ID}`);
        if (!response.ok) throw new Error('Failed to load albums');

        const albums = await response.json();

        // Render list
        if (!albums.length) {
            listContainer.innerHTML = `<div class="text-center text-gray-500 py-4">No albums found. Create one in Home!</div>`;
            return;
        }

        listContainer.innerHTML = ''; // Clear loading
        albums.forEach(album => {
            const btn = document.createElement('button');
            btn.className = `
                flex items-center justify-between p-3 rounded-lg bg-white/5
                hover:bg-green-500/20 hover:text-green-400 border border-transparent
                hover:border-green-500/30 transition-all text-left group
            `;
            btn.innerHTML = `
                <span class="font-bold text-gray-200 group-hover:text-white">${album.name}</span>
                <span class="text-xs text-gray-500 bg-black/30 px-2 py-1 rounded">${album.track_count} tracks</span>
            `;

            // Click handler
            btn.onclick = () => saveTrackToAlbum(album.name, btn);

            listContainer.appendChild(btn);
        });

    } catch (error) {
        console.error(error);
        listContainer.innerHTML = `<div class="text-red-400 text-center py-4">Error loading albums.</div>`;
    }
}

// ================================
// 2. SAVE TRACK TO ALBUM
// ================================
async function saveTrackToAlbum(albumName, btnElement) {
    if (!pendingTrack) return;

    const originalContent = btnElement.innerHTML;
    btnElement.innerHTML = "Saving...";
    btnElement.disabled = true;

    try {
        const payload = {
            track_title: pendingTrack.title,
            url: pendingTrack.url,
            track_author: pendingTrack.author,
            requested_by: USER_ID,
            identifier: pendingTrack.identifier
        };

        const response = await fetch(
            `${FASTAPI_URL}/api/albums/${GUILD_ID}/${encodeURIComponent(albumName)}/tracks`,
            {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            }
        );

        if (!response.ok) throw new Error('Failed to save track');

        // Success feedback
        btnElement.classList.remove('bg-white/5', 'hover:bg-green-500/20');
        btnElement.classList.add('bg-green-500', 'text-black');
        btnElement.innerHTML = "Saved!";

        setTimeout(() => closeAlbumModal(), 800);

    } catch (error) {
        console.error(error);
        btnElement.innerHTML = "Error!";
        btnElement.classList.add('text-red-500');

        setTimeout(() => {
            btnElement.innerHTML = originalContent;
            btnElement.disabled = false;
            btnElement.classList.remove('text-red-500');
        }, 2000);
    }
}

// ================================
// 3. CLOSE MODAL HELPER
// ================================
function closeAlbumModal() {
    const modal = document.getElementById('album-select-modal');
    if (modal) modal.classList.add('hidden');
    pendingTrack = { title: null, url: null, author: null, identifier: null };
}

const createAlbumForm = document.getElementById("create-album-form");
const createAlbumBtn = document.getElementById("create-album-btn");
const createAlbumModal = document.getElementById("create-album-modal");
const cancelAlbumBtn = document.getElementById("cancel-album-btn");

createAlbumBtn.addEventListener("click", () => {
    createAlbumModal.classList.remove("hidden");
});

createAlbumModal.addEventListener("click", (e) => {
    if (e.target === createAlbumModal) {
        createAlbumModal.classList.add("hidden");
    }
});
createAlbumForm.addEventListener("submit", async (e) => {
    e.preventDefault();

    const albumName = document.getElementById("album-name").value;
    const albumImgUrl = document.getElementById("album-img-url").value;

    try {
        const response = await fetch(`${FASTAPI_URL}/api/albums/${GUILD_ID}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                album_name: albumName,
                album_img_url: albumImgUrl,
                requested_by: USER_ID
            }),
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.message || 'Failed to create album');
        }

        alert("Album created successfully!");

        // Close modal & reset form
        createAlbumForm.reset();
        createAlbumModal.classList.add("hidden");
        await loadAlbums();

    } catch (err) {
        console.error(err);
        alert("Error: " + err.message);
    }
});
