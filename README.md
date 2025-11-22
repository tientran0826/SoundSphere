# 🎵 SoundSphere Music Bot


SoundSphere is a feature-rich Discord music bot built with **discord.py**, **Wavelink**, and **SQLAlchemy**.
It allows users to play music in voice channels, manage queues, and keep track of playback history.

**Note:** SoundSphere is based on **Lavalink** streaming, so you need a Lavalink server to use it.
You can either self-host a Lavalink server or use a free hosted server included in this code.

![SoundSphere Banner](images/banner.jpg)

---

## Features

- Play music from YouTube and other sources via Lavalink/Wavelink
- Pause, resume, skip, stop, and disconnect commands
- Music queue management with persistent storage
- Now playing and shuffle support
- Idle detection: bot automatically disconnects after a period of inactivity
- Server-specific configurations (command prefix, music channel)
- Music request tracking in database (play history)

---

## Commands

### 🎵 Music Commands

#### 🔊 Playback & Control

| Command | Description | Example |
|---|---|---|
| `!play <query/url>` | Play a track immediately, or add a search query/URL to the queue | `!play Never Gonna Give You Up` |
| `!pause` | Pause the currently playing track | `!pause` |
| `!resume` | Resume the paused track | `!resume` |
| `!skip` | Skip the current track and play the next one | `!skip` |
| `!stop` | Stop the current track and clear the queue | `!stop` |
| `!disconnect` | Disconnect the bot from the voice channel | `!disconnect` |
| `!now` | Show information about the currently playing track | `!now` |
| `!music_help` / `!mh` | Show help info for all music commands | `!music_help` |

---

#### 📃 Queue Management

| Command | Description | Example |
|---|---|---|
| `!queue` | View all tracks currently in the queue | `!queue` |
| `!shuffle` | Shuffle the current queue | `!shuffle` |
| `!remove <position>` | Remove a track from the queue by its index number | `!remove 2` |
| `!clear` | Clear the entire queue | `!clear` |

---

#### 💿 Album Management

| Command | Description | Example |
|---|---|---|
| `!create_album <name>` | Create a new album | `!create_album Chill` |
| `!remove_album <name>` | Delete an album and all its tracks | `!remove_album Chill` |
| `!albums` | List all albums for the server | `!albums` |
| `!show_album <name>` | Display all tracks in the specified album | `!show_album Chill` |
| `!play_album <name>` | Clear the queue and play all tracks from that album | `!play_album Chill` |
| `!start_add <album_name>` | Enter add mode to store tracks into an album | `!start_add Chill` |
| `!add <query>` | Add a found track to the currently active album | `!add Numb` |
| `!end` | Exit album add mode manually | `!end` |
| `!remove_from_album <album> <track_number>` | Remove a track from the album by index | `!remove_from_album Chill 3` |

---

### 🛠 Server Commands

| Command | Description | Example |
|---|---|---|
| `!set_prefix <prefix>` | Change the bot's command prefix | `!set_prefix !` |
| `!set_default_channel <#channel>` | Set the default channel for music commands | `!set_default_channel #music` |

---
## Architecture

SoundSphere is designed with maintainability and automation in mind. Key components of the architecture include:

- **Database Version Control with Alembic:**  
  All database schema changes are managed using **Alembic**, allowing you to version, migrate, and rollback database changes safely and reliably.

- **Deployment with Argo CD:**  
  The bot is deployed using **Argo CD**, enabling GitOps-based continuous deployment.  
  Any changes pushed to the GitHub repository can automatically sync to your Kubernetes cluster.

- **CI/CD with GitHub Actions:**  
  GitHub Actions are used to build Docker images of the bot whenever changes are pushed to the repository.  
  This ensures that your deployment always uses the latest version of the code.

- **Poetry for Dependency Management:**  
  The bot uses **Poetry** to manage Python dependencies, keeping the environment consistent across development and production.

- **Lavalink for Music Streaming:**  
  Music playback is handled through **Lavalink**, which can be self-hosted or run on a free hosted instance.

This architecture allows for:  
1. Safe, version-controlled database management  
2. Automated container builds and deployments  
3. Reliable music streaming with scalable infrastructure

---
## Setup

### Requirements

- Python 3.10+
- Discord Bot Token
- Lavalink server (for Wavelink music streaming)
- PostgreSQL or compatible SQL database
- Poetry (for dependency management)

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/tientran0826/SoundSphere.git
cd SoundSphere
```
2. **Install dependencies via Poetry**
```bash
poetry install
```
3. **Configure environment variables**
Copy the example .env file and fill in your credentials:
```bash
cp env.example .env
```
4. **Start the bot**
```bash
poetry run python main.py
```
