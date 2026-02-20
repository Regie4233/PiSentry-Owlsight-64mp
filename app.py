from flask import Flask, render_template, Response, request, jsonify, send_from_directory
import subprocess
import os
import time
import signal
import threading
import random
import string
import shutil
from datetime import datetime

app = Flask(__name__)

# Configuration
CAPTURE_DIR = 'static/captures'
THUMB_DIR = 'static/thumbnails'
META_DIR = 'static/metadata'
os.makedirs(CAPTURE_DIR, exist_ok=True)
os.makedirs(THUMB_DIR, exist_ok=True)
os.makedirs(META_DIR, exist_ok=True)

def save_metadata(filename, res, category="image"):
    """Saves capture-time metadata including camera settings."""
    try:
        source_path = os.path.join(CAPTURE_DIR, filename)
        meta_filename = filename + '.json'
        meta_path = os.path.join(META_DIR, meta_filename)
        
        # Get file stats
        size_bytes = os.path.getsize(source_path) if os.path.exists(source_path) else 0
        
        metadata = {
            "filename": filename,
            "category": category,
            "timestamp": datetime.now().isoformat(),
            "size_bytes": size_bytes,
            "size_human": f"{size_bytes / (1024*1024):.2f} MB",
            "resolution": f"{res['width']}x{res['height']}",
            "settings": {
                "shutter": camera_settings["shutter"],
                "gain": camera_settings["gain"],
                "awb": camera_settings["awb"],
                "focus_mode": camera_settings["focus_mode"],
                "lens_position": camera_settings["lens_position"],
                "zoom": camera_settings["zoom"],
                "rotation": camera_settings["rotation"]
            }
        }
        
        import json
        with open(meta_path, 'w') as f:
            json.dump(metadata, f, indent=4)
    except Exception as e:
        print(f"Error saving metadata for {filename}: {e}")

def get_metadata(filename):
    """Retrieves metadata for a specific file."""
    meta_path = os.path.join(META_DIR, filename + '.json')
    if os.path.exists(meta_path):
        import json
        try:
            with open(meta_path, 'r') as f:
                return json.load(f)
        except: pass
    return None

@app.route('/thumbnail/<path:filename>')
def get_thumbnail(filename):
    """Generates and serves a thumbnail for images and videos."""
    # Security check
    if '..' in filename or filename.startswith('/'):
        return "Invalid filename", 400

    source_path = os.path.join(CAPTURE_DIR, filename)
    thumb_filename = filename.replace('/', '_') + '.thumb.jpg'
    thumb_path = os.path.join(THUMB_DIR, thumb_filename)

    if not os.path.exists(source_path):
        return "File not found", 404

    # If thumbnail exists and is newer than source, serve it
    if os.path.exists(thumb_path) and os.path.getmtime(thumb_path) > os.path.getmtime(source_path):
        return send_from_directory(THUMB_DIR, thumb_filename)

    try:
        if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
            from PIL import Image
            with Image.open(source_path) as img:
                # Use a reasonable thumbnail size (e.g., 400px width)
                img.thumbnail((400, 400))
                img.save(thumb_path, "JPEG", quality=80)
        
        elif filename.lower().endswith(('.mp4', '.h264')):
            # Generate video thumbnail using ffmpeg
            cmd = [
                'ffmpeg', '-y', '-i', source_path,
                '-ss', '00:00:01', '-vframes', '1',
                '-vf', 'scale=400:-1',
                thumb_path
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        if os.path.exists(thumb_path):
            return send_from_directory(THUMB_DIR, thumb_filename)
        else:
            # Fallback to original if thumbnail generation failed
            return send_from_directory(CAPTURE_DIR, filename)
            
    except Exception as e:
        print(f"Thumbnail error for {filename}: {e}")
        return send_from_directory(CAPTURE_DIR, filename)

RESOLUTIONS = [
    {"width": 9248, "height": 6944, "label": "64MP (Max)"},
    {"width": 8000, "height": 6000, "label": "48MP"},
    {"width": 4624, "height": 3472, "label": "16MP"},
    {"width": 3840, "height": 2160, "label": "4K UHD"},
    {"width": 2312, "height": 1736, "label": "4MP"},
    {"width": 1920, "height": 1080, "label": "1080p Full HD"},
    {"width": 1280, "height": 720, "label": "720p HD"}
]

# Tied stream resolutions and framerates based on Arducam docs
def detect_link_frequency():
    try:
        config_path = '/boot/firmware/config.txt'
        if not os.path.exists(config_path):
            config_path = '/boot/config.txt'
        
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                content = f.read()
                if "link-frequency=456000000" in content:
                    return 456
                elif "link-frequency=360000000" in content:
                    return 360
    except:
        pass
    return 360 # Default to low speed

LINK_FREQ = detect_link_frequency()
IS_HIGH_SPEED = LINK_FREQ == 456

if IS_HIGH_SPEED:
    STREAM_RESOLUTIONS = [
        {"width": 1920, "height": 1080, "fps": 60, "label": "1080p Full HD (60 fps)"},
        {"width": 1280, "height": 720, "fps": 60, "label": "720p HD (60 fps)"},
        {"width": 640, "height": 480, "fps": 60, "label": "VGA (60 fps)"},
        {"width": 2312, "height": 1736, "fps": 30, "label": "4MP (30 fps)"},
        {"width": 3840, "height": 2160, "fps": 20, "label": "4K UHD (20 fps)"},
        {"width": 4624, "height": 3472, "fps": 10, "label": "16MP (10 fps)"},
        {"width": 8000, "height": 6000, "fps": 2.5, "label": "48MP (2.5 fps)"},
        {"width": 9248, "height": 6944, "fps": 2.6, "label": "64MP (2.6 fps)"}
    ]
else:
    STREAM_RESOLUTIONS = [
        {"width": 1920, "height": 1080, "fps": 45, "label": "1080p Full HD (45 fps)"},
        {"width": 1280, "height": 720, "fps": 45, "label": "720p HD (45 fps)"},
        {"width": 640, "height": 480, "fps": 45, "label": "VGA (45 fps)"},
        {"width": 2312, "height": 1736, "fps": 26.7, "label": "4MP (26.7 fps)"},
        {"width": 3840, "height": 2160, "fps": 14.8, "label": "4K UHD (14.8 fps)"},
        {"width": 4624, "height": 3472, "fps": 7.6, "label": "16MP (7.6 fps)"},
        {"width": 8000, "height": 6000, "fps": 2.5, "label": "48MP (2.5 fps)"},
        {"width": 9248, "height": 6944, "fps": 2, "label": "64MP (2 fps)"}
    ]

default_resolution = RESOLUTIONS[5] # 1080p for captures
default_stream = STREAM_RESOLUTIONS[2] # 640x480 for streaming

# State management
stream_process = None
recording_process = None
timelapse_thread = None
stop_timelapse = threading.Event()
stop_stream = threading.Event()
camera_lock = threading.Lock()

# New: Advanced Scheduling State
schedules = [] # List of dicts: {id, type, start, end, interval, res, status}

timelapse_status = {
    "active": False,
    "session_id": None,
    "last_image": None,
    "count": 0,
    "status": "Idle",
    "images": []
}

# New: Compilation state for background tasks
compilation_status = {}

def scheduler_worker():
    """Background thread that monitors and triggers scheduled events."""
    global recording_process, timelapse_thread
    print("Scheduler worker started.")
    while True:
        try:
            now = datetime.now()
            # Work on a copy of the list for basic thread safety during iteration
            for task in list(schedules):
                if task['status'] == 'scheduled':
                    try:
                        start_dt = datetime.strptime(task['start'], "%Y-%m-%dT%H:%M")
                        if now >= start_dt:
                            print(f"Triggering scheduled task: {task['type']} ({task['id']})")
                            task['status'] = 'in progress'
                            if task['type'] == 'recording':
                                threading.Thread(target=scheduled_record_task, args=(task,), daemon=True).start()
                            elif task['type'] == 'timelapse':
                                session_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{generate_timelapse_id()}"
                                task['session_id'] = session_id
                                # Duration is calculated from start/end
                                end_dt = datetime.strptime(task['end'], "%Y-%m-%dT%H:%M")
                                duration = (end_dt - now).total_seconds()
                                threading.Thread(target=timelapse_worker, 
                                               args=(task['interval'], duration, task['res'], session_id, task), daemon=True).start()
                    except Exception as e:
                        print(f"Error parsing/starting task {task['id']}: {e}")
                
                # Auto-complete expired tasks that might have been missed or failed
                if task['status'] == 'in progress':
                    try:
                        end_dt = datetime.strptime(task['end'], "%Y-%m-%dT%H:%M")
                        if now >= end_dt:
                            print(f"Task {task['id']} reached end time.")
                            if task['type'] == 'recording':
                                # Recording process is handled within scheduled_record_task
                                pass
                            task['status'] = 'completed'
                    except Exception as e:
                        print(f"Error checking completion for task {task['id']}: {e}")
        except Exception as ge:
            print(f"Global scheduler error: {ge}")
            
        time.sleep(5)

def scheduled_record_task(task):
    global recording_process
    print(f"Starting scheduled recording: {task['id']}")
    try:
        with camera_lock:
            stop_stream.set()
            kill_stream()
            time.sleep(2)
            
            res = task['res']
            rotation = camera_settings.get("rotation", 0)
            filename = f"sched_rec_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
            filepath = os.path.join(CAPTURE_DIR, filename)
            task['filename'] = filename
            
            # Calculate duration
            start_dt = datetime.strptime(task['start'], "%Y-%m-%dT%H:%M")
            end_dt = datetime.strptime(task['end'], "%Y-%m-%dT%H:%M")
            duration_ms = int((end_dt - datetime.now()).total_seconds() * 1000)
            
            if duration_ms <= 0:
                print(f"Scheduled recording {task['id']} duration is zero or negative.")
                task['status'] = 'completed'
                return

            # Always use ffmpeg for muxing to ensure valid MP4
            rpicam_cmd = [
                'rpicam-vid', '-t', str(duration_ms), '--width', str(res['width']),
                '--height', str(res['height']), '--inline', '-o', '-', '-n'
            ]
            rpicam_cmd.extend(get_camera_args())
            
            vf = ""
            if rotation == 90: vf = "transpose=1"
            elif rotation == 180: vf = "transpose=2,transpose=2"
            elif rotation == 270: vf = "transpose=2"
            
            ffmpeg_cmd = ['ffmpeg', '-i', '-']
            if vf:
                ffmpeg_cmd.extend(['-vf', vf, '-c:v', 'h264_v4l2m2m', '-b:v', '8M'])
            else:
                ffmpeg_cmd.extend(['-c:v', 'copy'])
            
            ffmpeg_cmd.extend(['-movflags', '+faststart', '-y', filepath])
            
            print(f"Executing piped command for scheduled recording (rotation={rotation})")
            p1 = subprocess.Popen(rpicam_cmd, stdout=subprocess.PIPE)
            p2 = subprocess.Popen(ffmpeg_cmd, stdin=p1.stdout)
            p2.wait()
            p1.wait()

        print(f"Scheduled recording {task['id']} finished.")
        task['status'] = 'completed'
        save_metadata(filename, res, category="video_scheduled")
    except Exception as e:
        print(f"Error in scheduled recording {task['id']}: {e}")
        task['status'] = 'error'
    finally:
        stop_stream.clear()

# Start scheduler thread
threading.Thread(target=scheduler_worker, daemon=True).start()

camera_settings = {
    "shutter": 0,           # 0 for auto
    "gain": 0,              # 0 for auto
    "awb": "auto",
    "focus_mode": "continuous", # manual, auto, continuous
    "lens_position": 0.0,   # for manual focus
    "brightness": 0.0,
    "contrast": 1.0,
    "saturation": 1.0,
    "sharpness": 1.0,
    "ev": 0.0,
    "zoom": 1.0,            # 1.0 to 10.0
    "rotation": 0,          # 0, 90, 180, 270
    "stream_width": default_stream["width"],
    "stream_height": default_stream["height"],
    "stream_framerate": default_stream["fps"]
}

def get_camera_args():
    args = []
    if camera_settings["shutter"] > 0:
        args.extend(["--shutter", str(camera_settings["shutter"])])
    if camera_settings["gain"] > 0:
        args.extend(["--gain", str(camera_settings["gain"])])
    
    args.extend(["--awb", camera_settings["awb"]])
    args.extend(["--autofocus-mode", camera_settings["focus_mode"]])
    
    if camera_settings["focus_mode"] == "manual":
        args.extend(["--lens-position", str(camera_settings["lens_position"])])
    
    args.extend(["--brightness", str(camera_settings["brightness"])])
    args.extend(["--contrast", str(camera_settings["contrast"])])
    args.extend(["--saturation", str(camera_settings["saturation"])])
    args.extend(["--sharpness", str(camera_settings["sharpness"])])
    args.extend(["--ev", str(camera_settings["ev"])])

    # Digital Zoom (ROI)
    # --roi x,y,w,h  (0,0,1,1 is full frame)
    if camera_settings["zoom"] > 1.0:
        zoom = camera_settings["zoom"]
        w = 1.0 / zoom
        h = 1.0 / zoom
        x = (1.0 - w) / 2.0
        y = (1.0 - h) / 2.0
        args.extend(["--roi", f"{x},{y},{w},{h}"])
    
    return args

def generate_timelapse_id():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

@app.route('/settings/update', methods=['POST'])
def update_settings():
    global camera_settings
    data = request.json
    for key in camera_settings:
        if key in data:
            if isinstance(camera_settings[key], float):
                camera_settings[key] = float(data[key])
            elif isinstance(camera_settings[key], int):
                camera_settings[key] = int(data[key])
            else:
                camera_settings[key] = data[key]
    
    return jsonify({"status": "success", "settings": camera_settings})

def get_disk_usage():
    total, used, free = shutil.disk_usage("/")
    return {
        "total_gb": round(total / (1024**3), 2),
        "used_gb": round(used / (1024**3), 2),
        "free_gb": round(free / (1024**3), 2),
        "percent": round((used / total) * 100, 1)
    }

@app.route('/timelapse/status')
def get_timelapse_status():
    return jsonify(timelapse_status)

@app.route('/camera/status')
def get_camera_status():
    return jsonify({
        "timelapse_active": timelapse_status["active"],
        "recording_active": recording_process is not None,
        "streaming_active": stream_process is not None,
        "timelapse_details": timelapse_status,
        "storage": get_disk_usage()
    })

@app.route('/')
def index():
    return render_template('index.html', 
                           resolutions=RESOLUTIONS, 
                           stream_resolutions=STREAM_RESOLUTIONS,
                           default_res=default_resolution, 
                           settings=camera_settings)

@app.route('/gallery/videos')
def list_videos():
    files = [f for f in os.listdir(CAPTURE_DIR) if f.endswith('.h264') or f.endswith('.mp4')]
    files.sort(reverse=True)
    video_data = []
    for f in files:
        meta = get_metadata(f)
        video_data.append({"filename": f, "meta": meta})
    return render_template('videos.html', files=video_data)

@app.route('/video/delete/<filename>', methods=['POST'])
def delete_video(filename):
    if '..' in filename or filename.startswith('/'):
        return jsonify({"status": "error", "message": "Invalid filename"}), 400
    filepath = os.path.join(CAPTURE_DIR, filename)
    meta_path = os.path.join(META_DIR, filename + '.json')
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
            if os.path.exists(meta_path): os.remove(meta_path)
            return jsonify({"status": "success"})
        return jsonify({"status": "error", "message": "File not found"}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/gallery/snaps')
def list_snaps():
    files = [f for f in os.listdir(CAPTURE_DIR) if f.endswith('.jpg') and f.startswith('snap_')]
    files.sort(reverse=True)
    snap_data = []
    for f in files:
        meta = get_metadata(f)
        snap_data.append({"filename": f, "meta": meta})
    return render_template('snaps.html', files=snap_data)

@app.route('/snap/delete/<filename>', methods=['POST'])
def delete_snap(filename):
    if '..' in filename or filename.startswith('/'):
        return jsonify({"status": "error", "message": "Invalid filename"}), 400
    filepath = os.path.join(CAPTURE_DIR, filename)
    meta_path = os.path.join(META_DIR, filename + '.json')
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
            if os.path.exists(meta_path): os.remove(meta_path)
            return jsonify({"status": "success"})
        return jsonify({"status": "error", "message": "File not found"}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/gallery/timelapses')
def list_timelapses():
    tl_dir = os.path.join(CAPTURE_DIR, 'timelapses')
    os.makedirs(tl_dir, exist_ok=True)
    sessions = []
    if os.path.exists(tl_dir):
        for d in os.listdir(tl_dir):
            path = os.path.join(tl_dir, d)
            if os.path.isdir(path):
                images = sorted([f for f in os.listdir(path) if f.endswith('.jpg')])
                # For timelapses, metadata is usually per session or per frame. 
                # Here we fetch session-level info if it exists.
                meta = get_metadata(d) 
                sessions.append({
                    'id': d,
                    'count': len(images),
                    'preview': images[0] if images else None,
                    'path': d,
                    'meta': meta
                })
    sessions.sort(key=lambda x: x['id'], reverse=True)
    return render_template('timelapses.html', sessions=sessions)

@app.route('/gallery/timelapses/<session_id>')
def view_timelapse(session_id):
    path = os.path.join(CAPTURE_DIR, 'timelapses', session_id)
    if not os.path.exists(path):
        return "Session not found", 404
    images = sorted([f for f in os.listdir(path) if f.endswith('.jpg')])
    
    # Check if a video or gif already exists for this session
    video_exists = os.path.exists(os.path.join(CAPTURE_DIR, f"{session_id}.mp4"))
    gif_exists = os.path.exists(os.path.join(CAPTURE_DIR, f"{session_id}.gif"))
    
    return render_template('timelapse_detail.html', 
                           session_id=session_id, 
                           images=images, 
                           video_exists=video_exists,
                           gif_exists=gif_exists)

def compile_worker(session_id, session_dir, output_file, format='mp4'):
    global compilation_status
    compilation_status[session_id] = {"status": "running", "message": "Starting compilation...", "format": format}
    
    if format == 'gif':
        # GIFs are scaled down more significantly for performance and size
        vf = "scale=640:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse"
        cmd = [
            'nice', '-n', '19',
            'ffmpeg', '-y',
            '-framerate', '10',
            '-pattern_type', 'glob', '-i', os.path.join(session_dir, '*.jpg'),
            '-vf', vf,
            output_file
        ]
    else: # mp4
        # Scale to 1080p height while maintaining aspect ratio (approx 1440x1080 for 4:3)
        # Using hardware acceleration h264_v4l2m2m
        cmd = [
            'nice', '-n', '19',
            'ffmpeg', '-y',
            '-framerate', '10',
            '-pattern_type', 'glob', '-i', os.path.join(session_dir, '*.jpg'),
            '-vf', 'scale=1440:1080',
            '-c:v', 'h264_v4l2m2m',
            '-b:v', '8M',
            '-pix_fmt', 'yuv420p',
            '-movflags', '+faststart',
            output_file
        ]

    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        compilation_status[session_id] = {"status": "success", "message": "Compilation finished", "format": format}
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.decode() if e.stderr else "Unknown error"
        compilation_status[session_id] = {"status": "error", "message": f"FFmpeg error: {error_msg}", "format": format}
    except Exception as e:
        compilation_status[session_id] = {"status": "error", "message": f"System error: {str(e)}", "format": format}

@app.route('/timelapse/compile/<session_id>', methods=['POST'])
def compile_timelapse(session_id):
    session_dir = os.path.join(CAPTURE_DIR, 'timelapses', session_id)
    
    data = request.json or {}
    fmt = data.get('format', 'mp4')
    extension = 'gif' if fmt == 'gif' else 'mp4'
    output_file = os.path.join(CAPTURE_DIR, f"{session_id}.{extension}")
    
    if not os.path.exists(session_dir):
        return jsonify({"status": "error", "message": "Session not found"})

    if session_id in compilation_status and compilation_status[session_id]["status"] == "running":
        return jsonify({"status": "error", "message": "Compilation already in progress"})

    threading.Thread(target=compile_worker, args=(session_id, session_dir, output_file, fmt)).start()
    return jsonify({"status": "success", "message": "Compilation started in background"})

@app.route('/timelapse/compile_status/<session_id>')
def get_compile_status(session_id):
    status = compilation_status.get(session_id, {"status": "idle"})
    return jsonify(status)

@app.route('/timelapse/delete/<session_id>', methods=['POST'])
def delete_timelapse(session_id):
    session_dir = os.path.join(CAPTURE_DIR, 'timelapses', session_id)
    video_file = os.path.join(CAPTURE_DIR, f"{session_id}.mp4")
    gif_file = os.path.join(CAPTURE_DIR, f"{session_id}.gif")
    
    try:
        if os.path.exists(session_dir):
            shutil.rmtree(session_dir)
        if os.path.exists(video_file):
            os.remove(video_file)
        if os.path.exists(gif_file):
            os.remove(gif_file)
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/video_feed')
def video_feed():
    return Response(generate_stream(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

def kill_stream():
    global stream_process
    if stream_process:
        try:
            pgid = os.getpgid(stream_process.pid)
            os.killpg(pgid, signal.SIGTERM)
            try:
                stream_process.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                os.killpg(pgid, signal.SIGKILL)
                stream_process.wait()
        except ProcessLookupError:
            pass # Already gone
        except Exception as e:
            print(f"Error killing stream: {e}")
        stream_process = None

def generate_stream():
    global stream_process
    stop_stream.clear()
    
    while not stop_stream.is_set():
        if timelapse_status["active"] or recording_process is not None:
            time.sleep(1)
            continue
            
        width = camera_settings.get('stream_width', 640)
        height = camera_settings.get('stream_height', 480)
        framerate = camera_settings.get('stream_framerate', 20)
        rotation = camera_settings.get('rotation', 0)
        current_args = get_camera_args()
        
        # Create a snapshot of all settings that affect the stream process
        current_state = (width, height, framerate, rotation, tuple(current_args))
        
        print(f"Starting stream: {width}x{height} @ {framerate}fps, rotation={rotation}")
        
        with camera_lock:
            if timelapse_status["active"] or recording_process is not None:
                continue
            kill_stream()
            cmd = [
                'rpicam-vid', '-t', '0', '--inline', '--width', str(width),
                '--height', str(height), '--codec', 'mjpeg', '--framerate', str(framerate),
                '--rotation', str(rotation),
                '--flush', '-n', '-o', '-'
            ]
            cmd.extend(current_args)
            
            try:
                stream_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, preexec_fn=os.setsid)
                local_process = stream_process
                
                # Make stdout and stderr non-blocking
                import fcntl
                for pipe in [local_process.stdout, local_process.stderr]:
                    fd = pipe.fileno()
                    fl = fcntl.fcntl(fd, fcntl.F_GETFL)
                    fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
            except Exception as e:
                print(f"Failed to start rpicam-vid: {e}")
                time.sleep(2)
                continue
        
        buffer = b""
        last_frame_time = time.time()
        try:
            while not stop_stream.is_set():
                # Check if ANY relevant setting changed
                new_state = (
                    camera_settings.get('stream_width'),
                    camera_settings.get('stream_height'),
                    camera_settings.get('stream_framerate'),
                    camera_settings.get('rotation'),
                    tuple(get_camera_args())
                )
                
                if current_state != new_state:
                    break
                
                if local_process.poll() is not None:
                    break

                try:
                    chunk = local_process.stdout.read(32768) # Larger buffer for high-res MJPEG
                    if not chunk:
                        if local_process.poll() is not None:
                            break
                        time.sleep(0.01)
                        if time.time() - last_frame_time > 5.0:
                            print("Stream timeout: No data received for 5 seconds")
                            break
                        continue
                except BlockingIOError:
                    time.sleep(0.01)
                    continue
                
                buffer += chunk
                
                # Robust MJPEG Parsing
                while True:
                    a = buffer.find(b'\xff\xd8') # Start of Frame
                    if a == -1:
                        # If buffer is getting too large without finding a start marker, clear it
                        if len(buffer) > 1000000: buffer = b""
                        break
                    
                    b = buffer.find(b'\xff\xd9', a) # End of Frame
                    if b == -1:
                        # Discard data before the start marker to keep buffer clean
                        if a > 0: buffer = buffer[a:]
                        # If we have a start but no end, and the buffer is huge, something is wrong
                        if len(buffer) > 2000000: buffer = b""
                        break
                    
                    jpg = buffer[a:b+2]
                    buffer = buffer[b+2:]
                    last_frame_time = time.time()
                    yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + jpg + b'\r\n')
        except Exception as e:
            print(f"Stream generation error: {e}")
        finally:
            with camera_lock:
                kill_stream()
        
        # Short sleep before trying to restart
        time.sleep(1.0) # Increased delay for stability

@app.route('/snap', methods=['POST'])
def snap():
    with camera_lock:
        stop_stream.set()
        kill_stream() # Release camera
        time.sleep(1) # Safety delay
        data = request.json
        res = data.get('resolution', default_resolution)
        filename = f"snap_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        filepath = os.path.join(CAPTURE_DIR, filename)
        
        cmd = ['rpicam-still', '--width', str(res['width']), '--height', str(res['height']), '-o', filepath, '-n']
        try:
            result = subprocess.run(cmd, timeout=30, capture_output=True, text=True)
            if result.returncode == 0:
                # Apply rotation if needed
                rotation = camera_settings.get("rotation", 0)
                if rotation != 0:
                    from PIL import Image
                    with Image.open(filepath) as img:
                        # PIL rotate is counter-clockwise, so we use -rotation or 360-rotation
                        # expand=True ensures the image isn't cropped when rotated by 90/270
                        rotated_img = img.rotate(-rotation, expand=True)
                        rotated_img.save(filepath, quality=95)
                
                save_metadata(filename, res, category="snapshot")
                return jsonify({"status": "success", "filename": filename})
            else:
                print(f"Capture error (Return code {result.returncode}): {result.stderr}")
                return jsonify({"status": "error", "message": f"Camera error: {result.stderr.splitlines()[-1] if result.stderr else 'Unknown error'}"})
        except subprocess.TimeoutExpired:
            print("Camera timeout during snapshot!")
            return jsonify({"status": "error", "message": "Camera timed out"})
        except Exception as e:
            print(f"Unexpected error during snapshot: {str(e)}")
            return jsonify({"status": "error", "message": str(e)})

@app.route('/record/start', methods=['POST'])
def start_record():
    global recording_process
    with camera_lock:
        if recording_process:
            return jsonify({"status": "error", "message": "Already recording"})
        
        stop_stream.set()
        kill_stream() # Release camera from stream
        time.sleep(2) # Increased safety delay
        data = request.json
        res = data.get('resolution', default_resolution)
        filename = f"rec_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4" # Changed to mp4 for easier playback
        filepath = os.path.join(CAPTURE_DIR, filename)
        
        rotation = camera_settings.get("rotation", 0)
        
        # We always use ffmpeg to mux into a proper MP4 container
        # This ensures the file is playable and has correct metadata
        rpicam_cmd = [
            'rpicam-vid', '-t', '0', '--width', str(res['width']),
            '--height', str(res['height']), '--inline', '-o', '-', '-n'
        ]
        rpicam_cmd.extend(get_camera_args())
        
        # Map degrees to ffmpeg transpose
        vf = ""
        if rotation == 90: vf = "transpose=1"
        elif rotation == 180: vf = "transpose=2,transpose=2"
        elif rotation == 270: vf = "transpose=2"
        
        ffmpeg_cmd = ['ffmpeg', '-i', '-']
        
        if vf:
            # If we have rotation, we must re-encode using hardware acceleration
            ffmpeg_cmd.extend(['-vf', vf, '-c:v', 'h264_v4l2m2m', '-b:v', '8M'])
        else:
            # No rotation: we can just copy the stream into the MP4 container
            # We use -vbsf h264_mp4toannexb if needed, but usually -c:v copy is enough for h264 in mp4
            ffmpeg_cmd.extend(['-c:v', 'copy'])
            
        ffmpeg_cmd.extend(['-movflags', '+faststart', '-y', filepath])
        
        p1 = subprocess.Popen(rpicam_cmd, stdout=subprocess.PIPE, preexec_fn=os.setsid)
        p2 = subprocess.Popen(ffmpeg_cmd, stdin=p1.stdout, stderr=subprocess.PIPE, preexec_fn=os.setsid)
        
        recording_process = p2
        recording_process.p1 = p1 # Store reference to first process to kill it later
        recording_process.metadata_info = (filename, res)

        
        # Quick check if it failed immediately
        time.sleep(1)
        if recording_process.poll() is not None:
            stderr = recording_process.stderr.read().decode()
            recording_process = None
            return jsonify({"status": "error", "message": f"Failed to start recording: {stderr.splitlines()[-1] if stderr else 'Unknown error'}"})
            
        return jsonify({"status": "success", "filename": filename})

@app.route('/record/stop', methods=['POST'])
def stop_record():
    global recording_process
    if recording_process:
        try:
            if hasattr(recording_process, 'p1'):
                try:
                    os.killpg(os.getpgid(recording_process.p1.pid), signal.SIGTERM)
                except: pass
            
            try:
                os.killpg(os.getpgid(recording_process.pid), signal.SIGTERM)
            except: pass
        except Exception as e:
            print(f"Error stopping recording: {e}")
        
        # Save metadata before clearing process
        if hasattr(recording_process, 'metadata_info'):
            filename, res = recording_process.metadata_info
            save_metadata(filename, res, category="video")

        recording_process = None
        stop_stream.clear() # Allow stream to resume
        return jsonify({"status": "success"})
    return jsonify({"status": "error", "message": "Not recording"})

@app.route('/schedules', methods=['GET'])
def list_schedules():
    return jsonify(schedules)

@app.route('/schedules/add', methods=['POST'])
def add_schedule():
    data = request.json
    new_task = {
        "id": generate_timelapse_id(),
        "type": data.get('type'), # 'recording' or 'timelapse'
        "start": data.get('start'),
        "end": data.get('end'),
        "interval": int(data.get('interval', 5)),
        "duration": int(data.get('duration', 60)),
        "res": data.get('resolution', default_resolution),
        "status": "scheduled",
        "session_id": None
    }
    schedules.append(new_task)
    return jsonify({"status": "success", "task": new_task})

@app.route('/schedules/delete/<task_id>', methods=['POST'])
def delete_schedule(task_id):
    global schedules
    schedules = [s for s in schedules if s['id'] != task_id]
    return jsonify({"status": "success"})

def timelapse_worker(interval, duration, res, session_id, task=None):
    global timelapse_status
    start_time = time.time()
    count = 0
    session_dir = os.path.join(CAPTURE_DIR, 'timelapses', session_id)
    os.makedirs(session_dir, exist_ok=True)
    
    timelapse_status["active"] = True
    timelapse_status["session_id"] = session_id
    timelapse_status["count"] = 0
    timelapse_status["images"] = []
    
    print(f"Timelapse worker started: {session_id}, duration: {duration}s")
    
    # If it's a scheduled task, determine duration from start/end
    if task:
        fmt = "%Y-%m-%dT%H:%M"
        end_dt = datetime.strptime(task['end'], fmt)
        total_seconds = (end_dt - datetime.now()).total_seconds()
        duration = max(total_seconds, duration)

    try:
        while not stop_timelapse.is_set() and (time.time() - start_time < duration):
            timelapse_status["status"] = f"Capturing image {count+1}..."
            with camera_lock:
                stop_stream.set()
                kill_stream()
                time.sleep(2)
                
                filename = f"{session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{count:04d}.jpg"
                filepath = os.path.join(session_dir, filename)
                cmd = [
                    'rpicam-still',
                    '--width', str(res['width']),
                    '--height', str(res['height']),
                    '-o', filepath,
                    '-n'
                ]
                cmd.extend(get_camera_args())
                
                success = False
                for attempt in range(2):
                    try:
                        result = subprocess.run(cmd, timeout=40, capture_output=True, text=True)
                        if result.returncode == 0:
                            success = True
                            break
                        else:
                            print(f"Timelapse capture failed (attempt {attempt+1}): {result.stderr}")
                            time.sleep(2)
                    except subprocess.TimeoutExpired:
                        print(f"Timelapse capture timed out (attempt {attempt+1})")
                        time.sleep(2)
                
                if not success:
                    timelapse_status["status"] = "Capture failed"
                    continue
            
            # Apply rotation
            rotation = camera_settings.get("rotation", 0)
            if rotation != 0:
                try:
                    from PIL import Image
                    with Image.open(filepath) as img:
                        rotated_img = img.rotate(-rotation, expand=True)
                        rotated_img.save(filepath, quality=95)
                except Exception as e:
                    print(f"Timelapse rotation error: {e}")

            rel_path = f"timelapses/{session_id}/{filename}"
            timelapse_status["last_image"] = rel_path
            timelapse_status["images"].append(rel_path)
            count += 1
            timelapse_status["count"] = count
            
            timelapse_status["status"] = f"Waiting {interval}s..."
            for _ in range(interval):
                if stop_timelapse.is_set(): break
                time.sleep(1)
        
        if task:
            task['status'] = 'completed'
        print(f"Timelapse {session_id} finished.")
        save_metadata(session_id, res, category="timelapse")
    except Exception as e:
        print(f"Error in timelapse worker {session_id}: {e}")
        if task:
            task['status'] = 'error'
    finally:
        timelapse_status["active"] = False
        timelapse_status["status"] = "Finished"
        stop_stream.clear()

@app.route('/timelapse/start', methods=['POST'])
def start_timelapse():
    global timelapse_thread
    if timelapse_thread and timelapse_thread.is_alive():
        return jsonify({"status": "error", "message": "Timelapse already running"})
    
    data = request.json
    res = data.get('resolution', default_resolution)
    interval = int(data.get('interval', 5))
    duration = int(data.get('duration', 60))
    
    # Generate ID with timestamp for uniqueness and sorting
    session_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{generate_timelapse_id()}"
    stop_timelapse.clear()
    
    timelapse_thread = threading.Thread(target=timelapse_worker, args=(interval, duration, res, session_id), daemon=True)
    timelapse_thread.start()
    return jsonify({"status": "success", "session_id": session_id})

@app.route('/timelapse/stop', methods=['POST'])
def stop_timelapse_route():
    global timelapse_status
    stop_timelapse.set()
    timelapse_status["active"] = False
    timelapse_status["status"] = "Stopped by user"
    return jsonify({"status": "success"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
