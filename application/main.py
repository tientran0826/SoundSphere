import requests
from configs import configs
from flask import Flask, flash, g, redirect, render_template, request, session, url_for

app = Flask(__name__)
app.secret_key = configs.FLASK_SECRET_KEY


@app.before_request
def load_user_data():
    g.user_id = session.get("discord_user_id")
    g.username = session.get("discord_username")


@app.route("/")
def index():
    if g.user_id and session.get("current_guild_id"):
        return redirect(url_for("home"))
    elif g.user_id:
        return redirect(url_for("dashboard"))
    return render_template("login.html")


@app.route("/login")
def login():
    discord_auth_url = (
        f"https://discord.com/oauth2/authorize"
        f"?client_id={configs.DISCORD_CLIENT_ID}"
        f"&redirect_uri={configs.DISCORD_REDIRECT_URI}"
        f"&response_type=code"
        f"&scope={configs.OAUTH_SCOPE}"
    )
    return redirect(discord_auth_url)


@app.route("/discord/callback")
def callback():
    code = request.args.get("code")
    if not code:
        return redirect(url_for("index"))

    token_url = f"https://discord.com/oauth2/token"
    data = {
        "client_id": configs.DISCORD_CLIENT_ID,
        "client_secret": configs.DISCORD_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": configs.DISCORD_REDIRECT_URI,
        "scope": configs.OAUTH_SCOPE,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    token_response = requests.post(token_url, data=data, headers=headers)
    if token_response.status_code != 200:
        app.logger.error(f"Failed to get token: {token_response.text}")
        return "Failed to get token.", 400

    token_info = token_response.json()
    access_token = token_info.get("access_token")
    if not access_token:
        return "Token is not exist.", 400
    user_url = f"https://discord.com/api/users/@me"
    auth_headers = {"Authorization": f"Bearer {access_token}"}
    user_response = requests.get(user_url, headers=auth_headers)
    if user_response.status_code != 200:
        app.logger.error(f"Failed to get user info: {user_response.text}")
        return "Failed to get user info", 400

    discord_user = user_response.json()

    session["discord_user_id"] = discord_user["id"]
    session["discord_username"] = discord_user["username"]
    session["discord_access_token"] = access_token

    return redirect(url_for("dashboard"))


@app.route("/logout")
def logout():
    session.pop("discord_user_id", None)
    session.pop("discord_username", None)
    return redirect(url_for("index"))


def get_user_guilds(access_token):
    user_guilds_url = f"https://discord.com/api/users/@me/guilds"
    auth_headers = {"Authorization": f"Bearer {access_token}"}
    try:
        response = requests.get(user_guilds_url, headers=auth_headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Failed to fetch user guilds: {e}")
        return []


@app.before_request
def load_user_data():
    g.user_id = session.get("discord_user_id")
    g.username = session.get("discord_username")


def check_bot_connected(guild_id):
    try:
        status_res = requests.get(
            f"{configs.FASTAPI_BASE_URL}/api/bot/{guild_id}/status"
        )
        status_res.raise_for_status()
        guild_data = status_res.json()["status"]
        return guild_data.get("connected", False)
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Failed to check bot connection status: {e}")
        return False


@app.route("/search/<string:query>")
def search_track(query):
    if not session.get("current_guild_id"):
        return redirect(url_for("dashboard"))

    connect_bot = check_bot_connected(session.get("current_guild_id"))
    if not connect_bot:
        flash("Bot is not connect to voice channel.", "error")
        return redirect(url_for("home"))

    target_album = request.args.get("target_album")
    guild_id = session.get("current_guild_id")
    user_id = session.get("discord_user_id")
    guild_name = session.get("current_guild_name")
    if not g.user_id:
        return redirect(url_for("index"))
    if not guild_id:
        flash("Vui lòng chọn một server trước khi tìm kiếm.", "error")
        return redirect(url_for("dashboard"))
    if not query:
        return redirect(url_for("dashboard"))

    identifier = f"ytsearch:{query}"
    search_url = f"{configs.LAVALINK_URI}/v4/loadtracks"
    params = {"identifier": identifier}
    headers = {"Authorization": configs.LAVALINK_PASSWORD}

    search_results = []

    try:
        response = requests.get(search_url, headers=headers, params=params)
        response.raise_for_status()

        data = response.json()
        if data.get("loadType") == "search":
            for track_data in data.get("data", []):
                track_info = track_data.get("info", {})
                search_results.append(
                    {
                        "title": track_info.get("title"),
                        "author": track_info.get("author"),
                        "duration": track_info.get("length"),
                        "url": track_info.get("uri"),
                        "identifier": track_info.get("identifier"),
                    }
                )
        elif data.get("loadType") == "NO_MATCHES":
            app.logger.info(f"No matches found for {query}")
        elif data.get("loadType") in ["track", "playlist"]:
            if data.get("loadType") == "track":
                track_data = data.get("data", [None])[0]
                if track_data:
                    track_info = track_data.get("info", {})
                    search_results.append(
                        {
                            "title": track_info.get("title"),
                            "author": track_info.get("author"),
                            "duration": track_info.get("length"),
                            "url": track_info.get("uri"),
                            "identifier": track_info.get("identifier"),
                        }
                    )
            elif data.get("loadType") == "playlist":
                playlist_info = data.get("data", {}).get("info", {})
                flash(
                    f"Đã tìm thấy Playlist: {playlist_info.get('name')}. Vui lòng thêm từng track.",
                    "info",
                )

                for track_data in data.get("data", {}).get("tracks", []):
                    track_info = track_data.get("info", {})
                    search_results.append(
                        {
                            "title": track_info.get("title"),
                            "author": track_info.get("author"),
                            "duration": track_info.get("length"),
                            "url": track_info.get("uri"),
                            "identifier": track_info.get("identifier"),
                        }
                    )
            search_results = search_results[
                :17
            ]  # Limit 18 results to display because layout
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Lavalink search request failed: {e}")
        return render_template("error.html", message=f"Lỗi kết nối Lavalink: {e}"), 500

    return render_template(
        "search.html",
        query=query,
        results=search_results,
        query_type="YouTube",
        guild_id=guild_id,
        guild_name=guild_name,
        user_id=user_id,
        FASTAPI_BASE_URL=configs.FASTAPI_BASE_URL,  # Add this line
        target_album=target_album,
    )


@app.route("/dashboard")
def dashboard():
    if not g.user_id:
        return redirect(url_for("index"))
    try:
        status_res = requests.get(f"{configs.FASTAPI_BASE_URL}/api/bot/status")
        status_res.raise_for_status()
        bot_status_data = status_res.json()["status"]
        bot_guilds = {
            guild["guild_id"]: guild for guild in bot_status_data.get("guilds", [])
        }
    except requests.exceptions.RequestException:
        bot_status = {"status": "error", "message": "Could not connect to FastAPI"}

    access_token = session.get("discord_access_token")
    user_guilds_raw = get_user_guilds(access_token)
    shared_guilds = []

    for user_guild in user_guilds_raw:
        guild_id = int(user_guild["id"])
        if guild_id in bot_guilds:
            shared_info = bot_guilds[guild_id]
            shared_info["user_is_admin"] = (int(user_guild["permissions"]) & 0x8) == 0x8
            shared_guilds.append(shared_info)
    return render_template(
        "dashboard.html", bot_status=bot_status_data, shared_guilds=shared_guilds
    )


@app.route("/select_guild/<int:guild_id>")
def select_guild(guild_id):
    if not g.user_id:
        return redirect(url_for("index"))
    try:
        guild_status = requests.get(
            f"{configs.FASTAPI_BASE_URL}/api/bot/{guild_id}/status",
        )
        guild_status.raise_for_status()
        guild_data = guild_status.json()["status"]
    except requests.exceptions.RequestException:
        guild_data = {
            "guild_id": guild_id,
            "guild_name": "Error API",
            "connected": False,
        }

    session["current_guild_id"] = guild_id
    session["current_guild_name"] = guild_data.get(
        "guild_name", f"Guild ID: {guild_id}"
    )
    session["current_guild_info"] = guild_data
    return redirect(url_for("home"))


@app.route("/control/<string:action>/<int:guild_id>")
def control_bot_action(action, guild_id):
    if not g.user_id:
        return redirect(url_for("index"))

    user_id = session.get("discord_user_id")

    valid_actions = ["resume", "disconnect", "stop", "skip", "pause"]
    if action not in valid_actions:
        app.logger.warning(f"Invalid bot control action attempted: {action}")
        return redirect(url_for("home"))

    try:
        response = requests.post(
            f"{configs.FASTAPI_BASE_URL}/api/bot/{guild_id}/control",
            json={"action": action, "user_id": int(user_id)},
        )
        response.raise_for_status()

    except requests.exceptions.RequestException as e:
        app.logger.error(
            f"Failed to execute '{action}' command for Guild {guild_id}: {e}"
        )
    except ValueError as e:
        app.logger.error(str(e))

    return redirect(url_for("home"))


@app.route("/connect_bot/<int:guild_id>")
def connect_bot(guild_id):
    if not g.user_id:
        return redirect(url_for("index"))

    user_id = session.get("discord_user_id")
    try:
        connect_res = requests.post(
            f"{configs.FASTAPI_BASE_URL}/api/bot/{guild_id}/connect/{user_id}",
        )
        connect_res.raise_for_status()
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Failed to connect bot: {e}")

    return redirect(url_for("home"))


@app.route("/album/<guild_id>/<album_name>")
def album_page(guild_id, album_name):
    current_guild_name = session.get("current_guild_name", "Unknown Guild")
    user_id = session.get("discord_user_id")
    if not user_id:
        return redirect(url_for("index"))

    url = f"{configs.FASTAPI_BASE_URL}/api/albums/{guild_id}/{album_name}"
    resp = requests.get(url)

    if resp.status_code == 404:
        # Album not found
        return f"Album '{album_name}' does not exist.", 404
    elif resp.status_code != 200:
        # Some other error
        return f"Failed to load album {album_name}", resp.status_code

    album_data = resp.json()
    # Ensure tracks is always a list
    if "tracks" not in album_data or album_data["tracks"] is None:
        album_data["tracks"] = []

    return render_template(
        "album.html",
        album=album_data,
        FASTAPI_BASE_URL=configs.FASTAPI_BASE_URL,
        guild_id=guild_id,
        user_id=user_id,
        guild_name=current_guild_name,
    )


@app.route("/home")
def home():
    if not session.get("discord_user_id"):
        return redirect(url_for("index"))

    current_guild_id = session.get("current_guild_id")
    if not current_guild_id:
        return redirect(url_for("dashboard"))

    current_guild_name = session.get("current_guild_name", "Unknown Guild")
    user_id = session.get("discord_user_id")
    trending_regions = {"K-Pop": "KR", "VietPop": "VN", "Global": "US", "UK Hits": "GB"}

    # The main change: Use a dictionary to store data, keyed by the region name
    trending_data = {}

    for genre_name, region_code in trending_regions.items():
        url = "https://www.googleapis.com/youtube/v3/videos"
        params = {
            "key": configs.YOUTUBE_API_KEY,
            "part": "snippet,statistics",
            "chart": "mostPopular",
            "videoCategoryId": "10",
            "regionCode": region_code,
            "maxResults": 5,
        }

        response = requests.get(url, params=params).json()

        # Create an empty list for the current region/genre
        videos_for_region = []

        for item in response.get("items", []):
            videos_for_region.append(
                {
                    "title": item["snippet"]["title"],
                    "thumbnail": item["snippet"]["thumbnails"]["medium"]["url"],
                    "url": f"https://www.youtube.com/watch?v={item['id']}",
                    "video_id": item["id"],
                    "genre": genre_name,
                    "view_count": item["statistics"].get("viewCount", "N/A"),
                }
            )

        # Store the list of videos under the region name in the main dictionary
        trending_data[genre_name] = videos_for_region

    return render_template(
        "home.html",
        guild_id=current_guild_id,
        user_id=user_id,
        guild_name=current_guild_name,
        FASTAPI_BASE_URL=configs.FASTAPI_BASE_URL,
        trending_data=trending_data,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True, port=8000)
