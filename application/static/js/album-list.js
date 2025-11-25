// ================================
// 1️⃣ Open Album Details Modal
// ================================
async function openAlbumDetails(albumName) {
    try {
        const response = await fetch(`${FASTAPI_URL}/api/albums/${GUILD_ID}/${encodeURIComponent(albumName)}`);
        if (!response.ok) throw new Error("Failed to load album details");

        const albumData = await response.json();

        // Show modal
        const modal = document.getElementById("message-box");
        if (!modal) return;
        modal.classList.remove("hidden");

        // Fill modal content
        document.getElementById("modal-album-art").src =
            albumData.album_img_url || "https://placehold.co/400x400/10b981/ffffff?text=Album";
        document.getElementById("modal-album-name").textContent = albumData.album_name || "";
        document.getElementById("modal-album-author").textContent = "Created by " + (albumData.created_by || "Unknown");
        document.getElementById("modal-album-track-count").textContent = `${albumData.tracks?.length || 0} tracks`;

        const trackList = document.getElementById("modal-album-tracks");
        trackList.innerHTML = "";

        if (!albumData.tracks || !albumData.tracks.length) {
            trackList.innerHTML = `<p class="text-gray-500">No tracks in this album yet.</p>`;
            return;
        }

        albumData.tracks.forEach((track, i) => {
            const el = document.createElement("div");
            el.className = "p-2 bg-white/5 text-gray-100 rounded-lg hover:bg-white/10 transition";
            el.innerHTML = `${i + 1}. <a href="${track.url}" target="_blank" class="underline">${track.title}</a> — ${track.author}`;
            trackList.appendChild(el);
        });

    } catch (err) {
        console.error("openAlbumDetails error:", err);
    }
}

// ================================
// 2️⃣ Load Albums into Grid
// ================================
async function loadAlbums(guildId) {
    const albumGrid = document.getElementById("album-list-grid");
    if (!albumGrid) return;

    try {
        const response = await fetch(`${FASTAPI_URL}/api/albums/${guildId}`);
        if (!response.ok) throw new Error("Failed to fetch albums");

        const albums = await response.json();
        albumGrid.innerHTML = "";

        albums.forEach(album => {
            const btn = document.createElement("button");
            btn.className = `
                album-card w-full p-4 rounded-3xl flex flex-col items-start
                transition duration-300 bg-white/5 border border-white/5
                hover:bg-white/10 hover:border-white/10 hover:-translate-y-2
                cursor-pointer text-left group relative
            `;

            // ✅ Attach click event to open modal
            btn.addEventListener("click", () => openAlbumDetails(album.name));

            btn.innerHTML = `
                <div class="w-full aspect-square overflow-hidden rounded-2xl mb-4 shadow-lg shadow-black/50 relative">
                    <img src="${album.album_img_url || "https://placehold.co/400x400/10b981/ffffff?text=Guild+Mix"}"
                         alt="${album.name}"
                         class="object-cover w-full h-full transition duration-500 group-hover:scale-105 group-hover:rotate-2">
                </div>
                <div class="w-full">
                    <p class="text-base font-bold text-gray-100 truncate group-hover:text-green-400 transition-colors">${album.name}</p>
                    <p class="text-xs text-gray-400 truncate mt-1">Curated by <span class="text-gray-300 font-medium">${album.created_by || "Unknown"}</span></p>
                    <p class="text-xs text-gray-500 truncate mt-1">${album.track_count || 0} tracks</p>
                </div>
            `;

            albumGrid.appendChild(btn);
        });

    } catch (err) {
        console.error("Error loading albums:", err);
        albumGrid.innerHTML = `<p class="col-span-full text-center text-gray-400">Failed to load albums.</p>`;
    }
}

// ================================
// 3️⃣ Album Search Handler
// ================================
function handleAlbumSearch(event, albumName) {
    if (event.key === 'Enter') {
        const query = event.target.value.trim();
        if (query) {
            // Redirect to search page with target_album param
            window.location.href = `/search/${encodeURIComponent(query)}?target_album=${encodeURIComponent(albumName)}`;
        }
    }
}

// ================================
// 4️⃣ Auto-load on page load
// ================================
document.addEventListener("DOMContentLoaded", () => {
    if (typeof GUILD_ID !== "undefined") {
        loadAlbums(GUILD_ID);
    }
});
