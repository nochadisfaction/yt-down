import subprocess
import sys
import shutil

def install(package):
    try:
        __import__(package)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        globals()[package] = __import__(package)

for pkg in ["yt_dlp", "rich"]:
    install(pkg)

if not shutil.which("ffmpeg"):
    print("\n[!] 'ffmpeg' is NOT installed or not in PATH.")
    print("    Download it from: https://ffmpeg.org/download.html")
    print("    Or run: choco install ffmpeg-full (Windows)")
    sys.exit(1)

import os
import threading
import threading_downloading
from converter import choose_and_convert
from rich import print
from rich.prompt import Prompt
from rich.console import Console
from rich.progress import track
import yt_dlp

console = Console()

def thanks():
    print("\n[bold green]Thank you for using this tool ❤️[/bold green]")

def playlist_download_handler(url, is_music):
    ydl_opts = {'quiet': True, 'force_generic_extractor': True, 'extract_flat': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        title = info['title']
        urls = [v['url'] for v in info['entries']]
        names = [v['title'] for v in info['entries']]
    print(f"\n[bold]Found {len(names)} items in playlist:[/bold] {title}")
    for i, (n, u) in enumerate(zip(names, urls), 1):
        print(f"[blue]{i}.[/blue] {n}")
    selected = Prompt.ask("Enter numbers (space-separated) or 'all'")
    indexes = list(range(len(urls))) if selected.lower() == 'all' else [int(i) - 1 for i in selected.split()]
    os.makedirs(title, exist_ok=True)
    threads = []
    for i in indexes:
        target = threading_downloading.download_youtube_music_multi if is_music else threading_downloading.download_youtube_video_multi
        t = threading.Thread(target=target, args=(urls[i], title))
        threads.append(t)
        t.start()
    for t in track(threads, description="Downloading..."):
        t.join()
    print(f"\n[green]All downloads saved to:[/green] [bold]{title}[/bold]")

def single_download(url, is_music):
    ydl_opts = {
        'format': 'bestaudio/best' if is_music else 'bestvideo+bestaudio/best',
        'merge_output_format': 'mp3' if is_music else 'mp4',
        'outtmpl': '%(title)s.%(ext)s'
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
    ext = info.get('ext', 'mp3' if is_music else 'mp4')
    print(f"[cyan]Title:[/cyan] {info.get('title')}\n[green]Saved as:[/green] {info.get('title')}.{ext}")

def determine_and_download(url):
    is_playlist = 'playlist' in url
    is_music = 'music' in url
    if is_playlist:
        playlist_download_handler(url, is_music)
    elif 'youtube' in url or 'youtu.be' in url:
        single_download(url, is_music)
    else:
        print("[red]Invalid YouTube URL[/red]")

def advanced_features():
    print("\n[bold]Advanced Options:[/bold]")
    print("1) Video to Music\n2) Video Playlist\n3) Music Playlist\n4) Convert MP4 → MP3\n5) Back")
    choice = Prompt.ask("Select option")
    if choice == "1":
        single_download(Prompt.ask("Video URL"), True)
    elif choice == "2":
        playlist_download_handler(Prompt.ask("Video Playlist URL"), False)
    elif choice == "3":
        playlist_download_handler(Prompt.ask("Music Playlist URL"), True)
    elif choice == "4":
        choose_and_convert()
    elif choice == "5":
        main_methods()

def main_methods():
    print("\n[bold magenta]Main Menu[/bold magenta]")
    print("1) Auto Detect\n2) YouTube Video\n3) YouTube Music\n4) Advanced")
    choice = Prompt.ask("Choose an option")
    if choice == "1":
        determine_and_download(Prompt.ask("Enter URL"))
    elif choice == "2":
        single_download(Prompt.ask("Video URL"), False)
    elif choice == "3":
        single_download(Prompt.ask("Music URL"), True)
    elif choice == "4":
        advanced_features()

if __name__ == "__main__":
    main_methods()
    thanks()
