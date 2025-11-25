function loadUsersInChannel() {
    const guildId = GUILD_ID;
    const container = document.getElementById("voice-users-list");
    if (!container) return;

    fetch(`${FASTAPI_URL}/api/bot/${guildId}/users-in-channel`)
        .then(res => res.json())
        .then(data => {
            container.innerHTML = ""; // clear before rendering

            if (!data.success || !data.members || data.members.length === 0) {
                container.innerHTML = `
                    <p class="text-gray-400 italic">
                        Bot is not in a voice channel.
                    </p>
                `;
                return;
            }

            data.members.forEach(member => {
                const userCard = document.createElement("div");
                userCard.className = "user-card";

                userCard.innerHTML = `
                    <img src="${member.avatar}" class="user-avatar">
                    <div class="text-sm truncate">${member.name}</div>
                `;

                container.appendChild(userCard);
            });
        })
        .catch(err => {
            console.error("Failed to load users in channel:", err);
            container.innerHTML = `<p class="text-red-500 italic">Error loading users</p>`;
        });
}
async function loadPlayHistory(guildId, limit = 5) {
    const res = await fetch(`${FASTAPI_URL}/api/history/${guildId}?limit=${limit}`);
    const data = await res.json();

    const container = document.getElementById("play-history-list");
    container.innerHTML = "";

    if (!data?.length) {
        container.innerHTML = `<p class="text-gray-500 italic text-sm">No history yet.</p>`;
        return;
    }

    container.innerHTML = data.map(i => `
        <div class="history-row group flex items-center justify-between px-3 py-2 rounded-md
                     bg-gray-800/60 hover:bg-gray-700/80 transition cursor-pointer">

            <div class="flex flex-col overflow-hidden">
                <a href="${i.url}" target="_blank"
                   class="text-[#1db954] group-hover:text-[#1ed760] font-medium truncate transition-colors duration-200">
                    ${i.title}
                </a>
                <span class="text-gray-400 text-xs truncate">${i.author}</span>
            </div>

            <span class="text-gray-500 text-xs ml-2 whitespace-nowrap">
                ${new Date(i.played_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </span>
        </div>
    `).join("");
}

// Run once on page load
document.addEventListener("DOMContentLoaded", () => {
    loadUsersInChannel();

    // Refresh every 1 second
    setInterval(loadUsersInChannel, 1000);

    // Also load play history
    loadPlayHistory(GUILD_ID, 3);
});

async function addToSpecificAlbum(btnElement, guildId, albumName, title, url, author, userId) {
    // 1. Visual Loading State
    const originalContent = btnElement.innerHTML;
    btnElement.innerHTML = `<svg class="animate-spin h-4 w-4 text-current" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>`;
    btnElement.disabled = true;

    try {
        // 2. Prepare Payload matches TrackCreate model
        const payload = {
            track_title: title,
            url: url,
            track_author: author,
            requested_by: parseInt(userId) // Ensure generic int if userId is string
        };

        // 3. Call FastAPI
        const response = await fetch(`${FASTAPI_URL}/api/albums/${guildId}/${encodeURIComponent(albumName)}/tracks`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });

        if (!response.ok) throw new Error('Failed to add');

        const data = await response.json();

        // 4. Success State
        btnElement.innerHTML = `<svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg> Added`;
        btnElement.classList.remove('bg-blue-500/20', 'text-blue-400');
        btnElement.classList.add('bg-green-500', 'text-black');

        // Optional: Notification toast
        // showToast("Track added successfully!");

    } catch (error) {
        console.error(error);
        btnElement.innerHTML = "Error";
        btnElement.classList.add('bg-red-500/20', 'text-red-400');
        setTimeout(() => {
            btnElement.innerHTML = originalContent;
            btnElement.disabled = false;
            btnElement.classList.remove('bg-red-500/20', 'text-red-400');
        }, 2000);
    }
}
