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

### Music Commands

| Command | Description | Example |
|---------|-------------|---------|
| `!play <query>` | Play a song or add it to the queue | `!play Never Gonna Give You Up` |
| `!pause` | Pause the currently playing track | `!pause` |
| `!resume` | Resume a paused track | `!resume` |
| `!skip` | Skip the current track and play the next one | `!skip` |
| `!stop` | Stop playback and clear the queue | `!stop` |
| `!disconnect` | Disconnect the bot from the voice channel | `!disconnect` |
| `!queue` | Show all tracks in the queue | `!queue` |
| `!now` | Show the currently playing track | `!now` |
| `!shuffle` | Shuffle the current queue | `!shuffle` |
| `!music_help` or `!mh` | Show help info for music commands | `!music_help` |

---

## Setup

### Requirements

- Python 3.10+
- Discord Bot Token
- Lavalink server (for Wavelink music streaming)
- PostgreSQL or compatible SQL database

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
git clone https://github.com/yourusername/SoundSphere.git
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
