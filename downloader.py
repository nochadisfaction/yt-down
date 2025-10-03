import os
import re
import sys
import threading
import subprocess
import shutil
import requests
import pyperclip
import json
import tempfile
import argparse
import glob
from PIL import Image
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3, APIC
from mutagen.flac import FLAC, Picture
from rich.console import Console
from rich.progress import (
    Progress,
    BarColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.prompt import Prompt, Confirm
from rich.table import Table

CONFIG_FILE = "yt_downloader_config.json"
COOKIES_FILE = os.path.join(os.path.dirname(__file__), "cookies.txt")
COOKIEFILE = COOKIES_FILE if os.path.exists(COOKIES_FILE) else None
PROXY = None


class GracefulExit(Exception):
    pass


def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                return json.load(f)
        except:
            return {}
    return {}


def save_config(config):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f)
    except:
        pass


def ensure_dirs():
    if not os.path.exists("Downloads"):
        os.makedirs("Downloads")


def get_clipboard_url():
    try:
        text = pyperclip.paste().strip()
        if re.search(
            r"(https?://)?(www\.)?(youtube\.com|youtu\.be|music\.youtube\.com)/", text
        ):
            return text
    except:
        pass
    return None


def check_yt_dlp_update(console):
    try:
        res = requests.get("https://pypi.org/pypi/yt-dlp/json", timeout=5)
        latest = res.json()["info"]["version"]
        out = subprocess.run(["yt-dlp", "--version"], capture_output=True, text=True)
        current = out.stdout.strip()
        if current != latest:
            ans = Prompt.ask(
                f"Update available for yt-dlp: {latest}. Update? [Y/n]",
                choices=["Y", "n"],
                default="Y",
            )
            if ans.lower() == "y":
                console.print("Updating yt-dlp...")
                subprocess.run([sys.executable, "-m", "pip", "install", "-U", "yt-dlp"])
                console.print("yt-dlp updated. Please restart the program.")
                raise GracefulExit
    except:
        pass


def natural_size(num):
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(num) < 1024.0:
            return "%3.1f %s" % (num, unit)
        num /= 1024.0
    return "%.1f PB" % num


def guess_is_music(url):
    return "music.youtube.com" in url


def is_playlist(url):
    return (
        "list=" in url or "/playlist?" in url or "/playlist/" in url
    ) and "watch?" not in url


def parse_selection(selection, total):
    indices = set()
    for part in selection.split(","):
        part = part.strip()
        if "-" in part:
            try:
                start, end = [int(x) for x in part.split("-")]
                indices.update(range(start, end + 1))
            except:
                continue
        elif part.isdigit():
            indices.add(int(part))
    return sorted(i for i in indices if 1 <= i <= total)


def fetch_playlist_entries(url):
    from yt_dlp import YoutubeDL

    entries = []
    ydl_opts = {"quiet": True, "extract_flat": True, "forcejson": True}
    if COOKIEFILE:
        ydl_opts["cookiefile"] = COOKIEFILE
    if PROXY:
        ydl_opts["proxy"] = PROXY
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        if "entries" in info:
            for i, e in enumerate(info["entries"], 1):
                title = e.get("title") or f"Untitled {i}"
                entries.append({"index": i, "id": e.get("id"), "title": title})
    return entries


def validate_proxy(proxy: str) -> bool:
    """Return True if proxy looks like a valid proxy URL (has scheme and netloc)."""
    try:
        from urllib.parse import urlparse

        p = urlparse(proxy)
        return bool(p.scheme and p.netloc)
    except Exception:
        return False


def sanitize(s):
    return re.sub(r'[\/\\\:\*\?"<>\|]', "_", s)


def resume_check(entries_list, out_folder, fmt, playlist_mode_flag):
    """Return (to_download_urls, skipped_paths, summary_by_dir).
    entries_list: list of dicts (playlist) or urls (not used here).
    For playlists we search recursively under out_folder for expected filenames
    like '01 - Title.mp3'."""
    skipped = []
    to_download = []
    for_dir_counts = {}
    if (
        playlist_mode_flag
        and isinstance(entries_list, list)
        and entries_list
        and isinstance(entries_list[0], dict)
    ):
        for e in entries_list:
            title = sanitize(e.get("title") or "")
            idx = e.get("index")
            fname = f"{idx:02d} - {title}.{fmt}"
            # recursive search for filename under out_folder
            matches = glob.glob(os.path.join(out_folder, "**", fname), recursive=True)
            if matches:
                # pick first match
                match = matches[0]
                skipped.append(match)
                d = os.path.dirname(match)
                for_dir_counts[d] = for_dir_counts.get(d, 0) + 1
            else:
                to_download.append(f"https://www.youtube.com/watch?v={e.get('id')}")
    else:
        # Not used for single-video resume per design; treat all as to_download
        to_download = list(entries_list)
    return to_download, skipped, for_dir_counts


def download_thumbnail_convert(thumbnail_url):
    if os.path.exists(thumbnail_url):
        return thumbnail_url
    response = requests.get(thumbnail_url, stream=True, timeout=8)
    ext = os.path.splitext(thumbnail_url)[-1].lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as out_img:
        if ext in [".jpg", ".jpeg"]:
            for chunk in response.iter_content(1024):
                out_img.write(chunk)
        else:
            with tempfile.NamedTemporaryFile(delete=True, suffix=ext) as temp_orig:
                for chunk in response.iter_content(1024):
                    temp_orig.write(chunk)
                temp_orig.flush()
                im = Image.open(temp_orig.name).convert("RGB")
                im.save(out_img, "JPEG")
        return out_img.name


def embed_cover_audiofile(path, img_file, fmt):
    if fmt == "mp3":
        audio = None
        try:
            audio = ID3(path)
        except:
            audio = ID3()
        with open(img_file, "rb") as imgf:
            audio.add(
                APIC(
                    encoding=3,
                    mime="image/jpeg",
                    type=3,
                    desc="Cover",
                    data=imgf.read(),
                )
            )
        audio.save(path)
    elif fmt == "flac":
        audio = FLAC(path)
        image = Picture()
        with open(img_file, "rb") as imgf:
            image.data = imgf.read()
        image.type = 3
        image.mime = "image/jpeg"
        audio.add_picture(image)
        audio.save()


def write_tags(path, info, fmt, idx=None, album=None):
    tags = {}
    tags["title"] = info.get("title", "")
    tags["artist"] = info.get("uploader") or info.get("channel") or ""
    tags["album"] = album or info.get("album") or info.get("playlist_title") or ""
    tags["date"] = str(info.get("release_year", "") or info.get("upload_date", "")[:4])
    tags["genre"] = info.get("genre", "")
    if idx:
        tags["tracknumber"] = str(idx)
    if fmt == "mp3":
        try:
            audio = EasyID3(path)
        except Exception:
            audio = EasyID3()
        for k, v in tags.items():
            if v:
                audio[k] = v
        audio.save(path)
    elif fmt == "flac":
        audio = FLAC(path)
        for k, v in tags.items():
            if v:
                audio[k] = v
        audio.save()


def save_yt_description(path, desc):
    if desc:
        fn = os.path.splitext(path)[0] + ".txt"
        with open(fn, "w", encoding="utf-8") as f:
            f.write(desc)


def download_task(
    opts,
    url_list,
    summary,
    mode,
    console,
    fmt,
    playlist_seq=None,
    album=None,
    do_lyrics=True,
    max_retries=2,
):
    from yt_dlp import YoutubeDL

    with Progress(
        TextColumn("{task.description}"),
        BarColumn(),
        "[progress.percentage]{task.percentage:>3.1f}%",
        TimeElapsedColumn(),
        TimeRemainingColumn(),
    ) as progress:
        total_vids = len(url_list)
        failed = []
        for idx, url in enumerate(url_list, 1):
            retry = 0
            while retry < max_retries:
                task = progress.add_task(
                    f"Downloading {idx} of {total_vids}: {url}", total=None
                )
                status = "Success"
                final_path = None
                file_type = "Video"
                size = None
                try:
                    with YoutubeDL(opts) as ydl:
                        info = ydl.extract_info(url, download=True)
                        if "requested_downloads" in info:
                            info = info["requested_downloads"][0]
                        if "filepath" in info:
                            final_path = info["filepath"]
                        else:
                            outtmpl = opts.get(
                                "outtmpl", info.get("title", "audiofile") + "." + fmt
                            )
                            final_path = (
                                outtmpl
                                if isinstance(outtmpl, str)
                                else outtmpl.get("default")
                            )
                        if final_path and os.path.exists(final_path):
                            size = os.path.getsize(final_path)
                        if mode == "audio" or (
                            final_path
                            and final_path.lower().endswith(
                                tuple([".mp3", ".flac", ".m4a"])
                            )
                        ):
                            file_type = "Audio"
                            tn_url = info.get("thumbnail")
                            if not tn_url:
                                t_list = info.get("thumbnails", [])
                                tn_url = t_list[-1]["url"] if t_list else None
                            print("Thumbnail URL:", tn_url)
                            if tn_url and final_path:
                                try:
                                    img = download_thumbnail_convert(tn_url)
                                    print("Downloaded image file:", img)
                                    embed_cover_audiofile(final_path, img, fmt)
                                    if (
                                        img
                                        and os.path.exists(img)
                                        and not os.path.abspath(img).endswith(
                                            "default.jpg"
                                        )
                                    ):
                                        os.remove(img)
                                except Exception as e:
                                    print("Thumbnail error:", e)
                            else:
                                print("No thumbnail found for this audio.")
                            ix = playlist_seq[idx - 1] if playlist_seq else None
                            write_tags(final_path, info, fmt, ix, album)
                            if do_lyrics:
                                save_yt_description(final_path, info.get("description"))
                    summary.append(
                        [
                            final_path if final_path else url,
                            file_type,
                            status,
                            natural_size(size) if size else "",
                        ]
                    )
                    progress.remove_task(task)
                    break
                except Exception as e:
                    status = f"FAIL: {e}"
                    retry += 1
                    progress.remove_task(task)
                    if retry >= max_retries:
                        console.print(f"❌ Failed to download: {url} - {str(e)}")
                        failed.append(url)
                        summary.append(
                            [
                                final_path if final_path else url,
                                file_type,
                                status,
                                natural_size(size) if size else "",
                            ]
                        )
                        break
                    else:
                        console.print(f"Retrying ({retry}/{max_retries}) for {url} ...")
                        continue
        if failed:
            console.print("[bold red]These failed:[/bold red]")
            for url in failed:
                console.print(url)


def open_folder(path):
    try:
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.run(["open", path])
        else:
            subprocess.run(["xdg-open", path])
    except:
        pass


def has_gui_open() -> bool:
    """Return True if we are likely able to open a folder in a GUI.

    On Windows and macOS assume GUI is present. On Linux, require an
    xdg-open binary and a display (X11/Wayland) session environment variable
    to be set. This avoids calling xdg-open on headless servers which will
    try to fall back to text browsers and print errors.
    """
    if sys.platform == "win32" or sys.platform == "darwin":
        return True
    # For other Unixes (Linux) check for xdg-open and a display
    if shutil.which("xdg-open") is None:
        return False
    if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
        return True
    # Some systems set XDG_SESSION_TYPE to 'wayland' or 'x11'
    session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
    if session_type in ("wayland", "x11"):
        return True
    return False


def pick_audio_format():
    ch = Prompt.ask("Pick audio format", choices=["mp3", "m4a", "flac"], default="mp3")
    return ch


def main():
    console = Console()
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--cookies", "-c", help="Path to yt-dlp cookies.txt file", default=None
    )
    parser.add_argument(
        "--proxy",
        "-p",
        help="Proxy URL for yt-dlp (e.g. http://host:port or socks5://host:port)",
        default=None,
    )
    parser.add_argument(
        "--config",
        help="Config subcommand: 'set-proxy', 'clear-proxy', 'show'",
        choices=["set-proxy", "clear-proxy", "show"],
        default=None,
    )
    args, _ = parser.parse_known_args()
    env_cookie = os.environ.get("YT_DOWNLOADER_COOKIES")
    env_proxy = os.environ.get("YT_DOWNLOADER_PROXY")
    global COOKIEFILE, PROXY
    config = load_config()
    # Handle simple config subcommands non-interactively
    if args.config:
        if args.config == "show":
            console.print(json.dumps(config, indent=2))
            sys.exit(0)
        if args.config == "clear-proxy":
            if "proxy" in config:
                del config["proxy"]
                save_config(config)
                console.print("[green]Proxy cleared from config.[/green]")
            else:
                console.print("[yellow]No proxy set in config.[/yellow]")
            sys.exit(0)
        if args.config == "set-proxy":
            # If CLI proxy provided, use that; otherwise prompt interactively
            if args.proxy:
                if validate_proxy(args.proxy):
                    config["proxy"] = args.proxy
                    save_config(config)
                    console.print("[green]Proxy saved to config.[/green]")
                else:
                    console.print("[red]Provided proxy is invalid.[/red]")
            else:
                # interactive prompt to set proxy
                p = Prompt.ask(
                    "Enter proxy URL to save to config (empty to cancel)", default=""
                )
                if p:
                    if validate_proxy(p):
                        config["proxy"] = p
                        save_config(config)
                        console.print("[green]Proxy saved to config.[/green]")
                    else:
                        console.print("[red]Invalid proxy URL. Nothing saved.[/red]")
            sys.exit(0)
    if args.cookies:
        COOKIEFILE = args.cookies if os.path.exists(args.cookies) else None
        if COOKIEFILE:
            config["cookies_path"] = COOKIEFILE
            save_config(config)
    elif env_cookie:
        COOKIEFILE = env_cookie if os.path.exists(env_cookie) else COOKIEFILE
    else:
        cfg_cookie = config.get("cookies_path")
        if cfg_cookie and os.path.exists(cfg_cookie):
            COOKIEFILE = cfg_cookie

    # Proxy precedence: CLI arg > env var > config file
    if args.proxy:
        PROXY = args.proxy
        config["proxy"] = PROXY
        save_config(config)
    elif env_proxy:
        PROXY = env_proxy
    else:
        cfg_proxy = config.get("proxy")
        if cfg_proxy:
            PROXY = cfg_proxy

    # If still no proxy, offer to set one interactively
    if not PROXY:
        try:
            if Confirm.ask(
                "No proxy configured. Would you like to set a proxy now?", default=False
            ):
                p = Prompt.ask(
                    "Enter proxy URL (e.g. http://host:port or socks5://host:port)"
                )
                if validate_proxy(p):
                    PROXY = p
                    config["proxy"] = PROXY
                    save_config(config)
                else:
                    console.print(
                        "[red]Invalid proxy URL. Skipping proxy configuration.[/red]"
                    )
        except KeyboardInterrupt:
            pass

    if COOKIEFILE:
        console.print(
            f"Who Told You You Could Eat My Cookies? [green]{COOKIEFILE}[/green]"
        )
    else:
        console.print(
            "No cookies file detected. To use one, place cookies.txt next to the script, set YT_DOWNLOADER_COOKIES, or pass --cookies / -c <path>"
        )
    if PROXY:
        console.print(f"Using proxy: [green]{PROXY}[/green]")
    else:
        console.print(
            "No proxy configured. To set one, use --proxy / -p or set YT_DOWNLOADER_PROXY or save it in config."
        )

    while True:
        try:
            ensure_dirs()
            check_yt_dlp_update(console)
        except GracefulExit:
            sys.exit(0)
        config = load_config()
        last_output_folder = config.get("last_output_folder", "Downloads")
        urls = []
        input_was_file = False
        clipboard_url = get_clipboard_url()
        if clipboard_url:
            try:
                if Confirm.ask(
                    f"Detected a YouTube link: {clipboard_url} Use it?", default=True
                ):
                    urls = [clipboard_url]
            except KeyboardInterrupt:
                console.print("\n[red]Operation cancelled by user.[/red]")
                sys.exit(0)
        if not urls:
            try:
                url_input = Prompt.ask(
                    "Enter YouTube URL or type 'file' to load URLs from file or 'q' to quit",
                    default="",
                )
                if url_input.lower() == "q":
                    console.print("Goodbye!")
                    sys.exit(0)
                if url_input.lower() == "file":
                    file_path = Prompt.ask("Enter the path to the txt file with URLs")
                    with open(file_path) as f:
                        urls = [x.strip() for x in f if x.strip()]
                    input_was_file = True
                else:
                    urls = [url_input]
            except KeyboardInterrupt:
                console.print("\n[red]Operation cancelled by user.[/red]")
                sys.exit(0)
        url = urls[0]
        use_video = not guess_is_music(url)
        pick_audio = False
        fmt = "mp3"
        if use_video:
            pick_audio = Confirm.ask("Download as audio (mp3/m4a/flac)?", default=False)
            if pick_audio:
                fmt = pick_audio_format()
        else:
            fmt = pick_audio_format()
        mode = "audio" if guess_is_music(url) or pick_audio else "video"
        folder = Prompt.ask("Output folder", default=last_output_folder)
        if not os.path.exists(folder):
            os.makedirs(folder)
        config["last_output_folder"] = folder
        save_config(config)
        opts = {}
        playlist_mode = False
        playlist_indices = None
        playlist_urls = []
        playlist_seq = None
        album = None
        if is_playlist(url):
            playlist_mode = True
            entries = fetch_playlist_entries(url)
            console.print(
                f"[bold]Playlist detected. {len(entries)} videos found:[/bold]"
            )
            for e in entries:
                console.print(f"[{e['index']:>2}] {e['title']}")
            try:
                sel = Prompt.ask(
                    "Enter numbers or ranges to download (e.g. 1,2,5-7) or leave blank for all",
                    default="",
                )
            except KeyboardInterrupt:
                console.print("\n[red]Operation cancelled by user.[/red]")
                sys.exit(0)
            if sel.strip():
                playlist_indices = parse_selection(sel, len(entries))
                opts["playlist_items"] = ",".join(str(i) for i in playlist_indices)
            else:
                playlist_indices = list(range(1, len(entries) + 1))
            for ix in playlist_indices:
                entry = entries[ix - 1]
                playlist_urls.append(f"https://www.youtube.com/watch?v={entry['id']}")
            playlist_seq = list(range(1, len(playlist_urls) + 1))
            album = entries[0].get("playlist_title") or None
        fnpat = "%(uploader)s"
        if mode == "audio":
            if playlist_mode and album:
                fnpat += os.sep + sanitize(album)
                outtmpl = os.path.join(
                    folder, fnpat, "%(playlist_index)02d - %(title)s.%(ext)s"
                )
            elif playlist_mode:
                outtmpl = os.path.join(
                    folder, fnpat, "%(playlist_index)02d - %(title)s.%(ext)s"
                )
            else:
                outtmpl = os.path.join(folder, fnpat, "%(title)s.%(ext)s")
            if fmt == "mp3":
                opts = dict(
                    format="bestaudio/best",
                    extractaudio=True,
                    audioformat="mp3",
                    postprocessors=[
                        {"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}
                    ],
                    outtmpl=outtmpl,
                )
            elif fmt == "m4a":
                opts = dict(
                    format="bestaudio[ext=m4a]/bestaudio/best",
                    extractaudio=True,
                    audioformat="m4a",
                    postprocessors=[
                        {"key": "FFmpegExtractAudio", "preferredcodec": "m4a"}
                    ],
                    outtmpl=outtmpl,
                )
            elif fmt == "flac":
                opts = dict(
                    format="bestaudio/best",
                    extractaudio=True,
                    audioformat="flac",
                    postprocessors=[
                        {"key": "FFmpegExtractAudio", "preferredcodec": "flac"}
                    ],
                    outtmpl=outtmpl,
                )
            if COOKIEFILE:
                opts["cookiefile"] = COOKIEFILE
            if PROXY:
                opts["proxy"] = PROXY
        else:
            outtmpl = os.path.join(folder, fnpat, "%(title)s.%(ext)s")
            opts["format"] = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
            opts["merge_output_format"] = "mp4"
            opts["outtmpl"] = outtmpl
            opts["writesubtitles"] = True
            opts["embedsubtitles"] = True
            opts["subtitleslangs"] = ["en"]
            opts["writeautomaticsub"] = True
            opts["sponsorblock_remove"] = ["all"]
            if COOKIEFILE:
                opts["cookiefile"] = COOKIEFILE
            if PROXY:
                opts["proxy"] = PROXY
        summary = []
        urls_to_download = playlist_urls if playlist_mode else urls

        # If this was a playlist or the URLs were loaded from a file, offer a resume check
        def resume_check(entries_list, out_folder, fmt, playlist_mode_flag):
            """Return (to_download_urls, skipped_count). entries_list is list of dicts with title/id or list of urls."""
            skipped = []
            to_download = []
            if (
                playlist_mode_flag
                and isinstance(entries_list, list)
                and entries_list
                and isinstance(entries_list[0], dict)
            ):
                # Build expected filenames for playlist entries
                for e in entries_list:
                    title = sanitize(e.get("title") or "")
                    idx = e.get("index")
                    fname = f"{idx:02d} - {title}.{fmt}"
                    path = os.path.join(out_folder, fname)
                    if os.path.exists(path):
                        skipped.append(path)
                    else:
                        to_download.append(
                            f"https://www.youtube.com/watch?v={e.get('id')}"
                        )
            else:
                # entries_list is list of urls; check by title extraction is expensive, so check by filename existence heuristics
                for u in entries_list:
                    # try to guess title from url id
                    vid = None
                    m = re.search(r"v=([\w-]+)", u)
                    if m:
                        vid = m.group(1)
                    # try glob for files containing the video id or any sanitized text
                    matches = (
                        list(glob.glob(os.path.join(out_folder, f"*{vid}*.{fmt}")))
                        if vid
                        else []
                    )
                    if matches:
                        skipped.extend(matches)
                    else:
                        to_download.append(u)
            return to_download, skipped

        if (playlist_mode or input_was_file) and Confirm.ask(
            "Check Downloads folder and skip files that already exist?", default=True
        ):
            # for file-loaded lists we treat them like playlists and pass the raw URLs list
            if playlist_mode:
                to_download, skipped, summary_by_dir = resume_check(
                    entries, os.path.abspath(folder), fmt, True
                )
            else:
                to_download, skipped, summary_by_dir = resume_check(
                    urls_to_download, os.path.abspath(folder), fmt, False
                )
            if skipped:
                console.print(
                    f"Found {len(skipped)} existing files, they will be skipped:"
                )
                # print per-directory summary
                for d, count in summary_by_dir.items():
                    rel = os.path.relpath(d, os.path.abspath(folder))
                    console.print(f"  {rel or '.'}: {count}")
                if Confirm.ask("Show file list?", default=False):
                    for s in skipped:
                        console.print(s)
                if not Confirm.ask("Proceed and skip these files?", default=True):
                    console.print("Download cancelled.")
                    sys.exit(0)
            urls_to_download = to_download
        if playlist_mode and playlist_indices:
            table = Table(title="Selected Videos to Download")
            table.add_column("Index", justify="right")
            table.add_column("Title")
            for i, ix in enumerate(playlist_indices, 1):
                e = entries[ix - 1]
                table.add_row(str(i), e["title"])
            console.print(table)
            try:
                proceed = Confirm.ask(
                    f"You have selected {len(playlist_indices)} videos to download. Proceed?",
                    default=True,
                )
            except KeyboardInterrupt:
                console.print("\n[red]Operation cancelled by user.[/red]")
                sys.exit(0)
            if not proceed:
                console.print("Download cancelled.")
                sys.exit(0)
        try:
            if Confirm.ask("Start download?", default=True):
                download_task(
                    opts,
                    urls_to_download,
                    summary,
                    mode,
                    console,
                    fmt,
                    playlist_seq,
                    album,
                    True,
                )
        except KeyboardInterrupt:
            console.print("\n[red]Download interrupted by user.[/red]")
            sys.exit(0)
        table = Table(title="Download Summary")
        table.add_column("File")
        table.add_column("Type", justify="center")
        table.add_column("Status", justify="center")
        table.add_column("Size", justify="right")
        for row in summary:
            table.add_row(*[str(x) if x else "" for x in row])
        console.print(table)
        again = Confirm.ask("Download another batch?", default=False)
        if not again:
            try:
                if has_gui_open():
                    if Confirm.ask("Open download folder now?", default=True):
                        open_folder(os.path.abspath(folder))
                else:
                    console.print(
                        f"Download folder: [green]{os.path.abspath(folder)}[/green]"
                    )
            except KeyboardInterrupt:
                console.print("\n[red]Operation cancelled by user.[/red]")
            break


if __name__ == "__main__":
    try:
        main()
    except GracefulExit:
        pass
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)
