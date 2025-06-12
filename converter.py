import os
import subprocess
from rich.prompt import Prompt
from rich.console import Console

console = Console()

def convert_specific_mp4_to_mp3(filename):
    if filename.endswith('.mp4'):
        mp3_file = filename.replace('.mp4', '.mp3')
        subprocess.run(['ffmpeg', '-i', filename, '-q:a', '0', '-map', 'a', mp3_file], check=True)
        console.print(f"[green]Converted:[/green] {filename} → {mp3_file}")

def list_mp4_files(directory='.'):
    return [os.path.join(root, file) for root, _, files in os.walk(directory) for file in files if file.endswith('.mp4')]

def choose_and_convert():
    files = list_mp4_files()
    if not files:
        console.print("[red]No .mp4 files found.[/red]")
        return
    console.print("[bold]Available .mp4 files:[/bold]")
    for i, f in enumerate(files, 1):
        console.print(f"{i}. {f}")
    try:
        selected = Prompt.ask("Enter file numbers (space-separated)").split()
        for i in [int(x) - 1 for x in selected]:
            if 0 <= i < len(files):
                convert_specific_mp4_to_mp3(files[i])
    except:
        console.print("[red]Invalid input.[/red]")
