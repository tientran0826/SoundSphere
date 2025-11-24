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
