// ================================
// 1️⃣ Open Album Details Modal
// ================================

function openAlbumDetails(albumName) {
    if (!albumName) return;

    // Properly encode album name for URL
    const encodedAlbumName = encodeURIComponent(albumName);

    // Navigate directly to Flask album page
    window.location.href = `/album/${GUILD_ID}/${encodedAlbumName}`;
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
            // Create a card element for each album
            const albumCard = document.createElement("button"); // <--- define albumCard here
            albumCard.className = `
                album-card w-full p-4 rounded-3xl flex flex-col items-start
                transition duration-300 bg-white/5 border border-white/5
                hover:bg-white/10 hover:border-white/10 hover:-translate-y-2
                cursor-pointer text-left group relative
            `;

            // Attach click event to open modal
            albumCard.addEventListener("click", () => openAlbumDetails(album.name));
            console.log(album);
            albumCard.innerHTML = `

                <div class="w-full aspect-square overflow-hidden rounded-2xl mb-4 shadow-lg shadow-black/50 relative">
                    <img src="${album.album_img_url || "https://placehold.co/400x400/10b981/ffffff?text=Guild+Album"}"
                         alt="${album.name}"
                         class="object-cover w-full h-full transition duration-500 group-hover:scale-105 group-hover:rotate-2">
                </div>
                <div class="w-full">
                    <p class="text-base font-bold text-gray-100 truncate group-hover:text-green-400 transition-colors">${album.name}</p>
                    <p class="text-xs text-gray-500 truncate mt-1">${album.track_count || 0} tracks</p>
                    <p class="text-xs text-gray-500 truncate mt-1">
                        ${album.created_at ? new Date(album.created_at).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' }) : 'N/A'}
                    </p>
                </div>
            `;

            albumGrid.appendChild(albumCard); // append the card
        });

    } catch (err) {
        console.error("Error loading albums:", err);
        albumGrid.innerHTML = `<p class="col-span-full text-center text-gray-400">Failed to load albums.</p>`;
    }
}

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
function showSuccessNotification(message, type = "success") {
    const container = document.getElementById("notification-container");
    if (!container) return;

    // Themed colors
    let bgClass = "bg-white/5 border border-white/10"; // default
    let textClass = "text-green-400"; // success color
    if (type === "error") {
        bgClass = "bg-white/5 border border-red-500/30";
        textClass = "text-red-400";
    }

    const notif = document.createElement("div");
    notif.className = `
        ${bgClass} ${textClass} px-4 py-3 rounded-2xl backdrop-blur-md
        shadow-lg shadow-black/50 flex items-center gap-2 font-bold
        animate-slide-in opacity-0 transition-opacity duration-300
    `;
    notif.textContent = message;
    container.appendChild(notif);

    // Fade in
    requestAnimationFrame(() => {
        notif.classList.add("opacity-100");
    });

    // Auto remove after 3 seconds
    setTimeout(() => {
        notif.classList.remove("opacity-100");
        notif.classList.add("opacity-0");
        setTimeout(() => container.removeChild(notif), 300);
    }, 3000);
}


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

        showSuccessNotification("Album created successfully!");

        // Close modal & reset form
        createAlbumForm.reset();
        createAlbumModal.classList.add("hidden");
        await loadAlbums(GUILD_ID);

    } catch (err) {
        console.error(err);
        alert("Error: " + err.message);
    }
});

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

albumCard.addEventListener("click", () => {
    openAlbumDetails(album.name);
});
