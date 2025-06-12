import os
import yt_dlp

def download_youtube_music_multi(url, playlist_dir):
    ydl_opts = {
        'format': 'bestaudio[ext=m4a]/best[ext=mp3]',
        'merge_output_format': 'mp3',
        'outtmpl': os.path.join(playlist_dir, '%(title)s.%(ext)s'),
        'quiet': True
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

def download_youtube_video_multi(url, playlist_dir):
    ydl_opts = {
        'format': 'bestvideo+bestaudio/best',
        'merge_output_format': 'mp4',
        'outtmpl': os.path.join(playlist_dir, '%(title)s.%(ext)s'),
        'quiet': True
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
