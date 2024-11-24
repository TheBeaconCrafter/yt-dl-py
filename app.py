import customtkinter
import tkinter.filedialog as fd
import yt_dlp
import threading
from queue import Queue
import re
import os

# Setting up the window
customtkinter.set_appearance_mode("System")
customtkinter.set_default_color_theme("blue")
version = "1.0.0"

# App frame
app = customtkinter.CTk()
app.geometry("600x400")
app.title("YouTube Downloader")
app.iconbitmap(os.path.join("assets", "icon.ico"))

# Queue for thread-safe UI updates
update_queue = Queue()

class CustomLogger:
    def debug(self, msg):
        # Send progress info to queue
        progress_info = self.capture_progress(msg)
        if progress_info:
            update_queue.put(progress_info)
        print(msg)  # Keep console output for debugging
        
    def warning(self, msg):
        print(msg)
        
    def error(self, msg):
        update_queue.put({
            'action': 'error',
            'status': f"Error: {msg}"
        })
        print(msg)

    def capture_progress(self, line):
        """Parse a line of output and return progress info"""
        # Check for download progress
        download_match = re.search(r'\[download\]\s+(\d+\.?\d*)%\s+of\s+([0-9.]+\w+)\s+at\s+([0-9.]+\w+/s)\s+ETA\s+(\d+:\d+)', line)
        if download_match:
            percentage = float(download_match.group(1))
            size = download_match.group(2)
            speed = download_match.group(3)
            eta = download_match.group(4)
            return {
                'action': 'progress',
                'progress': percentage / 100,
                'status': f"Downloading: {percentage:.1f}% of {size} at {speed} (ETA: {eta})"
            }
        
        # Check for different stages
        if '[youtube]' in line:
            return {
                'action': 'status',
                'status': 'Extracting video information...'
            }
        elif '[info]' in line:
            return {
                'action': 'status',
                'status': 'Starting download...'
            }
        # MP3 specific stages
        elif '[FixupM4a]' in line:
            return {
                'action': 'status',
                'status': 'Processing audio...'
            }
        elif '[ExtractAudio]' in line:
            return {
                'action': 'status',
                'status': 'Converting to MP3...'
            }
        # Video specific stages
        elif '[Merger]' in line:
            return {
                'action': 'status',
                'status': 'Merging video and audio...'
            }
        
        # Check for completion
        if 'Deleting original file' in line and '.m4a' in line:
            return {
                'action': 'complete',
                'status': 'Conversion completed!'
            }
        elif 'Deleting original file' in line and '.webm' in line:
            return {
                'action': 'complete',
                'status': 'Video download completed!'
            }
        elif 'Deleting original file' in line and '.mp4' in line:
            return {
                'action': 'complete',
                'status': 'Video download completed!'
            }
    
        return None

def update_ui():
    """Process any pending UI updates from the queue"""
    try:
        while True:  # Process all pending updates
            update = update_queue.get_nowait()
            action = update.get('action')
            
            if action == 'progress':
                progress_bar.set(update['progress'])
                status_label.configure(text=update['status'])
            elif action == 'status':
                status_label.configure(text=update['status'])
            elif action == 'complete':
                progress_bar.set(1)
                status_label.configure(text=update['status'])
                button.configure(state="normal")
            elif action == 'error':
                status_label.configure(text=update['status'])
                button.configure(state="normal")
            
            update_queue.task_done()
    except:
        pass
    finally:
        # Schedule the next UI update check
        app.after(100, update_ui)

def download_thread(url, format_type, download_dir):
    """Function to run in separate thread for downloading"""
    try:
        if format_type == "MP4":
            ydl_opts = {
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4',  # Prioritize MP4
                'logger': CustomLogger(),
                'progress_hooks': [progress_hook],
                'outtmpl': os.path.join(download_dir, '%(title)s.%(ext)s')
            }
        elif format_type == "WEBM":  # Renamed from MP4
            ydl_opts = {
                'format': 'bestvideo[ext=webm]+bestaudio/best',
                'logger': CustomLogger(),
                'progress_hooks': [progress_hook],
                'outtmpl': os.path.join(download_dir, '%(title)s.%(ext)s')
            }
        elif format_type == "MP3":
            ydl_opts = {
                'format': 'm4a/bestaudio/best',
                'logger': CustomLogger(),
                'progress_hooks': [progress_hook],
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                }],
                'outtmpl': os.path.join(download_dir, '%(title)s.%(ext)s')
            }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except Exception as e:
        update_queue.put({
            'action': 'error',
            'status': f"Error: {str(e)}"
        })

def progress_hook(d):
    if d['status'] == 'downloading':
        try:
            total_bytes = d.get('total_bytes', 0) or d.get('total_bytes_estimate', 0)
            downloaded_bytes = d.get('downloaded_bytes', 0)
            if total_bytes:
                percentage = (downloaded_bytes / total_bytes) * 100
                speed = d.get('speed', 0)
                if speed:
                    speed_mb = speed / 1024 / 1024
                    update_queue.put({
                        'action': 'progress',
                        'progress': percentage / 100,
                        'status': f"Downloading: {percentage:.1f}% (Speed: {speed_mb:.1f} MB/s)"
                    })
                else:
                    update_queue.put({
                        'action': 'progress',
                        'progress': percentage / 100,
                        'status': f"Downloading: {percentage:.1f}%"
                    })
        except Exception as e:
            update_queue.put({
                'action': 'status',
                'status': "Calculating..."
            })

def dropdown_callback(choice):
    print("combobox dropdown clicked:", choice)
    
def download():
    # Disable download button while processing
    button.configure(state="disabled")
    
    # Reset progress bar and status
    progress_bar.set(0)
    status_label.configure(text="Starting download...")
    
    url = link.get()
    format_type = dropdown_var.get()
    
    download_dir = fd.askdirectory(title="Select download folder")
    if not download_dir:  # If no directory is selected, return
        return
    
    # Start download in separate thread
    thread = threading.Thread(target=download_thread, args=(url, format_type, download_dir))
    thread.daemon = True
    thread.start()

# UI Elements
title = customtkinter.CTkLabel(app, text="YouTube Downloader", font=("Arial", 20))
title.pack(padx=10, pady=10)

link = customtkinter.CTkEntry(app, width=350)
link.pack(padx=10, pady=10)

dropdown_var = customtkinter.StringVar(value="MP4")
dropdown = customtkinter.CTkComboBox(app, state="readonly", values=["MP4", "MP3", "WEBM"], 
                                   command=dropdown_callback, variable=dropdown_var)
dropdown_var.set("MP4")
dropdown.pack(padx=10, pady=10)

button = customtkinter.CTkButton(app, text="Download", command=download)
button.pack(padx=10, pady=10)

progress_bar = customtkinter.CTkProgressBar(app, width=400)
progress_bar.pack(padx=10, pady=10)
progress_bar.set(0)

status_label = customtkinter.CTkLabel(app, text="Ready to download...")
status_label.pack(padx=10, pady=10)

footer_label = customtkinter.CTkLabel(app, text="V " + version + " by vncntwww")
footer_label.pack(side="bottom", fill="x")  # Place at the bottom and fill horizontally

# Start UI update checker
app.after(100, update_ui)

# Main loop
app.mainloop()