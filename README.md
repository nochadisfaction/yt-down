# YouTube \& YouTube Music CLI Downloader

A modern, all-in-one Python tool to download **audio (MP3, FLAC, M4A)** and **video (MP4)** from YouTube and YouTube Music—**with album art**, smart file/folder naming, playlist support, lyrics saving, batch mode, and automatic metadata tagging.

## Features

- Download individual videos/music or full playlists
- Extract audio as MP3, FLAC, or M4A (your choice)
- Save videos as MP4 (best available quality)
- **Embed YouTube cover art as album art for audio files (when possible)**
- Write artist, album, title, year, genre, and track numbers into tags
- Save lyrics/video descriptions as text files alongside your music
- Batch/playlist downloading, clean UX, automatic retries
- Works on Windows, macOS, Linux


## Step 1: Prerequisites

### 1. Python 3.8+ Installed

[Download Python](https://www.python.org/downloads/) if you don't have it.

- On Windows, add it to your system PATH!
- Check with `python --version` in terminal.


### 2. ffmpeg Installed

#### Why?

- This script needs ffmpeg to extract/convert audio and embed cover art.


#### How to install:

<details>
<summary><strong>Windows</strong></summary>

- Download an [ffmpeg build](https://www.gyan.dev/ffmpeg/builds/), unzip, put `ffmpeg.exe` from `bin/` in a folder such as `C:\ffmpeg\bin\`
- Add that folder to your **PATH**  
  *(Control Panel → System → Advanced → Environment Variables → PATH)*
- Open a new terminal and check:

  ```
  ffmpeg -version
  ```

</details>
<details>
<summary><strong>macOS (with Homebrew)</strong></summary>

```
brew install ffmpeg
ffmpeg -version
```

</details>
<details>
<summary><strong>Linux (Debian/Ubuntu)</strong></summary>

```
sudo apt update
sudo apt install ffmpeg
ffmpeg -version
```

</details>

## Step 2: Get the Downloader Script & Requirements with Git

### Clone the Repository (Recommended Way)

If you have Git installed, the fastest and most reliable method to get the script—including all future updates and documentation—is to clone the public repository from GitHub. Cloning ensures you get the exact folder structure and all supporting files, and allows for easy updating later.

**How to do it:**

1. **Open a terminal** (Command Prompt, PowerShell, Terminal, etc.).

2. **Navigate to the parent folder** where you want your downloader (for example, `Documents`):

    ```bash
    cd ~/Documents
    ```
    (On Windows, you can also use `cd %USERPROFILE%\Documents`)

3. **Clone the repository:**

    ```bash
    git clone https://github.com/aswinop/yt-downloader.git
    ```

4. **Change into the new folder:**

    ```bash
    cd yt-downloader
    ```

**After these steps, your directory will look like:**

```

yt-downloader/
├── downloader.py
├── requirements.txt
├── README.md
└── Downloads/    \# (created automatically by the script after first run)

```


## Step 3: Install Python Packages

Run this in your `yt-downloader` folder:

```bash
pip install -r requirements.txt
```

**Dependencies:**

- `rich` – Pretty/interactive CLI UI
- `yt-dlp` – YouTube/YouTube Music backend
- `pyperclip` – Auto-reads clipboard links
- `requests` – Downloads images/metadata
- `pillow` – Image conversion (for cover art)
- `mutagen` – Writes artist/album/tags and embeds art in music files


## Step 4: Running the Downloader

```bash
python downloader.py
```

or (if Python 3 is not default):

```bash
python3 downloader.py
```


## Step 5: Usage Guide

1. **Clipboard/Manual Link Paste**
    - If you already copied a YouTube or YT Music link, it will prompt:
_"Detected a YouTube link: ... Use it? [y/n]"_
    - Otherwise, paste or type a link, or type `file` to load a .txt file of links.
2. **Pick Audio/Video Format**
    - Choose `mp3`, `flac`, or `m4a` for audio, or `mp4` for video.
3. **Output Folder**
    - Choose where files save; default is `Downloads/` in the script's folder.
4. **Playlist Selection**
    - For playlists, see all available items and select which ones to download (e.g. `1-3,5` or leave blank for all).
5. **Batch Mode**
    - You’ll be asked if you want to download another batch.
6. **Summary/Table**
    - At the end, view a table of all files saved, with types and sizes.
7. **Open Folder**
    - After finishing all batches, you’ll be asked if you want to open the output folder.

## What to Expect

- **For each audio file:**
    - Cover art is embedded (if YouTube provides a thumbnail)
    - Tags: artist, album, title, year, genre, tracknumber
    - Lyrics or video description saved as a `.txt` next to the song (if available)
- **For playlists:**
    - Songs are auto-numbered for album/playback order
- **All file/folder names** are sanitized for your OS


## Sample Session

Here’s what real output looks like:

```text
$ python downloader.py
Detected a YouTube link: https://music.youtube.com/watch?v=pqrUQrAcfo4 Use it? [y/n] (y):
Pick audio format [mp3/m4a/flac] (mp3): flac
Output folder (Downloads):
Start download? [y/n] (y):
Downloading 1 of 1: https://music.youtube.com/watch?v=pqrUQrAcfo4 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 0.0% 0:00:00

Thumbnail URL: https://i.ytimg.com/vi/pqrUQrAcfo4/hqdefault.jpg
Downloaded image file: /tmp/tmpvd2a11x9.jpg


                                  Download Summary
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━━┳━━━━━━━━━┓
┃ File                                               ┃ Type  ┃ Status  ┃    Size ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━━╇━━━━━━━━━┩
│ Downloads/Artist Name/SongTitle.flac               │ Audio │ Success │ 52.3 MB │
└────────────────────────────────────────────────────┴───────┴─────────┴─────────┘

Download another batch? [y/n] (n):
Open download folder now? [y/n] (y):

🎉 All downloads complete!
Files saved in: /your/path/to/yt-downloader/Downloads
```


## Troubleshooting

- **No album art in audio file?**
If you see "No thumbnail found for this audio." then YouTube didn't supply one.
- **ffmpeg not found?**
Make sure you can run `ffmpeg -version` in your terminal and that it's in your PATH.
- **Metadata/tags missing?**
Make sure `mutagen` is installed: `pip install mutagen`.


## FAQ

- **Can I download private/region-locked videos?**
Not unless yt-dlp is configured with cookies and authorization (see yt-dlp docs).
- **Will every song have lyrics?**
Only if provided in the video's description or as available via YouTube.
- **Cover art for every file?**
Only if YouTube provides it—no default images are added.


## Summary

- Install Python and ffmpeg
- Clone or copy the repository
- `pip install -r requirements.txt`
- Run: `python downloader.py`
- Follow the prompts!

If you need more features or run into an issue, open an issue or request support.

## Contributing

Feel free to submit issues or pull requests to improve the script.

## License

This project is licensed under the MIT License – see the [LICENSE](LICENSE) file for details.