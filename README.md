# PiSentry Camera UI

PiSentry Camera UI is a sophisticated web-based control interface designed specifically for the Arducam OwlSight 64MP camera on Raspberry Pi platforms. It provides a seamless bridge between high-level user requirements and low-level camera hardware control.

## Features
- **Real-time MJPEG Preview**: Low-latency 720p stream for positioning and focus.
- **High-Resolution Capture**: Full 64MP image acquisition with customizable resolutions.
- **Video Recording**: Raw H.264 video capture directly to local storage.
- **Advanced Time-lapse System**:
  - Unique 6-digit session identification.
  - Duration-based or scheduled (timestamped) modes.
  - Automated directory grouping by session.
- **Integrated Video Compiler**: Built-in logic to compile time-lapse image sequences into high-quality MP4 videos using FFmpeg.
- **Centralized Gallery**: Dedicated views for managing recorded videos and time-lapse sessions.

---

## Technical Paper: Architectural Overview

### 1. Introduction
The PiSentry Camera UI addresses the challenge of managing high-resolution imaging on embedded systems. By decoupling the capture logic from the user interface, it provides a robust platform for long-term monitoring and high-fidelity photography.

### 2. System Architecture
The application follows a **Producer-Consumer model** built on the Flask micro-framework.

#### A. Backend (Python/Flask)
The backend acts as an orchestrator for the `rpicam-apps` suite. It manages three primary process types:
- **Streaming**: A persistent subprocess utilizing `rpicam-vid` to pipe MJPEG data to a Python generator.
- **Asynchronous Tasks**: Time-lapse operations run in isolated `threading.Thread` instances, managed by a global `camera_lock` to prevent hardware resource contention.
- **Post-Processing**: Utilizes `ffmpeg` for transcoding image sequences. By using the `libx264` codec and `yuv420p` pixel format, the system ensures maximum compatibility across modern devices.

#### B. Hardware Integration
The system leverages the `ov64a40` kernel driver. Performance is optimized through custom `dtoverlay` configurations in `/boot/config.txt`, specifically tuning the CSI-2 link frequency to handle 64MP data bursts.

#### C. Data Management
Data is structured hierarchically:
- `static/captures/`: Root storage.
- `static/captures/*.h264`: Raw video files.
- `static/captures/timelapses/<session_id>/`: Grouped image sequences.
- `static/captures/<session_id>.mp4`: Post-processed time-lapse videos.

### 3. Concurrency Control
To ensure stability, the system implements a strict locking mechanism. Since the Raspberry Pi camera subsystem (libcamera) allows only one primary owner, the application gracefully kills the preview stream whenever a high-resolution snapshot or video recording is initiated, auto-restoring it upon completion.

### 4. Conclusion
PiSentry Camera UI provides a production-ready interface that maximizes the capabilities of the 64MP OwlSight sensor while maintaining a lightweight footprint suitable for the Raspberry Pi.

---

## Setup & Installation

### 1. Hardware Configuration
Run the setup script to configure the Arducam overlays:
```bash
sudo python3 setup_pi.py
```
**Reboot your Pi** after running this script.

### 2. Dependencies
Ensure FFmpeg is installed for video compilation:
```bash
sudo apt update && sudo apt install ffmpeg -y
```

Install Python requirements:
```bash
pip install -r requirements.txt
```

### 3. Usage
Start the application using the provided launch script:
```bash
chmod +x launch.sh
./launch.sh
```
Access the UI at `http://<your-pi-ip>:5000`

### 4. Optional: Run as a System Service
To have the UI start automatically on boot:
1. Edit `pisentry.service` and replace `your_username` and `/home/your_username/...` with your actual system details.
2. Copy the service file: `sudo cp pisentry.service /etc/systemd/system/`
3. Enable and start:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable pisentry.service
   sudo systemctl start pisentry.service
   ```
