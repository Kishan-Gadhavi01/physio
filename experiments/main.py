#!/usr/bin/env python3
"""
Main driver for the 3D Pose and Kinematic Dashboard.
Handles application state, webcam input, MMPose inference, and button callbacks
for Live Analysis, Video Processing, and JSON Replay modes.
"""
import numpy as np
import cv2
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from mmpose.apis import MMPoseInferencer
import datetime
import json
import warnings
import sys
import math

# Local Imports
import kinematics
from dashboard import DashboardManager

# --- WARNING FILTER FIX ---
warnings.filterwarnings(
    "ignore", 
    message=".*autocast.*is deprecated.*", 
    category=FutureWarning
)
# --------------------------

# -------------------- CONFIG --------------------
OUTPUT_JSON_PATH = "rom5.json" # Base filename for timestamping
DEVICE = "cuda:0"  # change to 'cpu' if you don't have CUDA
TARGET_VIDEO_FPS = 10 # Target processing FPS for video files
# ------------------------------------------------

# ---------------- GLOBAL STATE ----------------
manager = None 
inferencer = None
results_gen = None
frame_gen = None 
FINAL_OUTPUT_PATH = None 

# Mode State
running = False         # True when actively capturing/replaying frames
live_mode_active = False # True if currently capturing from webcam
REPLAY_MODE = False      # True if currently playing back JSON or VIDEO
VIDEO_MODE = False       # True if currently processing a video file
stop_requested = False

# Data Storage
all_predictions = [] # Data collected in LIVE mode
frame_id = 0 
LOADED_FRAMES = []
REPLAY_INDEX = 0
# ----------------------------------------------


# --- Custom Frame Generator for Camera or Video File ---
class WebcamFrameGenerator:
    """Manages cv2.VideoCapture for live camera (index) or video file (path), 
    with frame skipping enabled for video files to speed up processing."""
    def __init__(self, source):
        self.is_video_file = isinstance(source, str)
        self.cap = cv2.VideoCapture(source)
            
        if not self.cap.isOpened():
            raise IOError(f"ERROR: Could not open source: {source}.")
            
        # Set resolution for camera (does nothing for video file)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        
        self.current_frame = np.zeros((480, 640, 3), dtype=np.uint8)

        # --- VIDEO FRAME SKIPPING LOGIC ---
        self.skip_frames = 0
        if self.is_video_file:
            video_fps = self.cap.get(cv2.CAP_PROP_FPS)
            if video_fps > 0:
                # Calculate how many frames to skip to hit the TARGET_VIDEO_FPS
                self.skip_frames = math.ceil(video_fps / TARGET_VIDEO_FPS) - 1
                print(f"[VIDEO] Original FPS: {video_fps:.1f}. Processing FPS (approx): {video_fps / (self.skip_frames + 1):.1f}")
        # ----------------------------------


    def __iter__(self):
        return self

    def __next__(self):
        # --- VIDEO FRAME SKIPPING EXECUTION ---
        if self.is_video_file and self.skip_frames > 0:
            for _ in range(self.skip_frames):
                # Read and discard frames to skip ahead, checking for end of stream
                if not self.cap.read()[0]:
                    self.cap.release()
                    raise StopIteration("End of stream reached.")
        # --------------------------------------

        ret, frame = self.cap.read()
        if not ret:
            self.cap.release()
            raise StopIteration("End of stream reached.")
        self.current_frame = frame
        return frame

    def get_rgb_frame(self):
        # Convert BGR (OpenCV) to RGB (Matplotlib)
        if self.current_frame.size > 0:
            return cv2.cvtColor(self.current_frame, cv2.COLOR_BGR2RGB)
        return np.zeros((480, 640, 3), dtype=np.uint8)

    def release(self):
        self.cap.release()
        
# ---------------- MODE TRANSITIONS ----------------

def reset_state():
    """Resets all global variables for a clean start."""
    global running, live_mode_active, REPLAY_MODE, VIDEO_MODE, stop_requested, all_predictions, frame_id, LOADED_FRAMES, REPLAY_INDEX, inferencer, results_gen, frame_gen
    
    # 1. Stop animation and clean up I/O
    running = False
    stop_requested = False
    if frame_gen:
        frame_gen.release()
    inferencer = None
    results_gen = None

    # 2. Reset data
    all_predictions = []
    LOADED_FRAMES = []
    frame_id = 0
    REPLAY_INDEX = 0

    # 3. Reset mode flags
    live_mode_active = False
    REPLAY_MODE = False
    VIDEO_MODE = False
    
    # 4. Reset UI
    if manager:
        manager.reset_history()
        # Set frame back to black/reset state
        manager.im_artist.set_data(manager.reset_frame)
        manager.text_artist.set_text("Idle. Ready for Live, Video, or Replay.")


def start_live_mode():
    """Initializes MMPose and starts the live webcam stream."""
    global inferencer, results_gen, frame_gen, running, live_mode_active, FINAL_OUTPUT_PATH
    
    reset_state() # Always reset state before starting live mode

    try:
        # Generate new timestamped filename
        now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        FINAL_OUTPUT_PATH = OUTPUT_JSON_PATH.replace(".json", f"_{now}.json")

        # Setup inferencer using camera index (0)
        frame_gen = WebcamFrameGenerator(source=0)
        inferencer = MMPoseInferencer(pose3d='human3d', device=DEVICE)
        results_gen = inferencer(inputs=frame_gen, return_vis=False) 
        
        # Set state flags
        live_mode_active = True
        running = True
        manager.text_artist.set_text(f"LIVE: Started. Data saving to {FINAL_OUTPUT_PATH}")
        print(f"[MAIN] Live Stream Started. Output: {FINAL_OUTPUT_PATH}")
        
    except IOError:
        manager.text_artist.set_text("ERROR: Camera not found.")
        print("[MAIN] ERROR: Camera not found.")
    except Exception as e:
        manager.text_artist.set_text(f"Error starting MMPose: {e}")
        print(f"[MAIN] Error starting inferencer: {e}")
        reset_state()


def start_video_mode(file_path):
    """Initializes MMPose and starts video file processing."""
    global inferencer, results_gen, frame_gen, running, VIDEO_MODE, FINAL_OUTPUT_PATH
    
    reset_state() # Always reset state before starting video mode

    try:
        # Generate new timestamped filename for video output
        now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        FINAL_OUTPUT_PATH = f"video_analysis_{now}.json"

        # Setup inferencer using video file path
        frame_gen = WebcamFrameGenerator(source=file_path)
        inferencer = MMPoseInferencer(pose3d='human3d', device=DEVICE)
        results_gen = inferencer(inputs=frame_gen, return_vis=False) 
        
        # Set state flags
        VIDEO_MODE = True
        running = True
        manager.text_artist.set_text(f"VIDEO: Processing {file_path}. Data saving to {FINAL_OUTPUT_PATH}")
        print(f"[MAIN] Video Processing Started: {file_path}. Output: {FINAL_OUTPUT_PATH}")
        
    except IOError:
        manager.text_artist.set_text(f"ERROR: Video file not found: {file_path}")
        print(f"[MAIN] ERROR: Video file not found: {file_path}")
    except Exception as e:
        manager.text_artist.set_text(f"Error starting MMPose: {e}")
        print(f"[MAIN] Error starting inferencer: {e}")
        reset_state()


def load_json_file(file_path):
    """Loads saved JSON data into the global replay state."""
    global LOADED_FRAMES, REPLAY_MODE, REPLAY_INDEX, running

    reset_state() # Always reset state before loading a new file

    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        if not isinstance(data, list) or not data or 'predictions' not in data[0]:
            raise ValueError("JSON file structure is invalid or empty.")
            
        LOADED_FRAMES = data
        REPLAY_INDEX = 0
        REPLAY_MODE = True
        running = True # Start replay playback immediately
        
        manager.text_artist.set_text(f"REPLAY: Loaded {len(LOADED_FRAMES)} frames. Playing...")
        print(f"[REPLAY] Started playback of {len(LOADED_FRAMES)} frames from {file_path}.")

    except FileNotFoundError:
        manager.text_artist.set_text(f"Error: File not found at {file_path}")
        print(f"[REPLAY] Error: File not found at {file_path}")
    except json.JSONDecodeError:
        manager.text_artist.set_text("Error: Invalid JSON format.")
        print("[REPLAY] Error: Invalid JSON format.")
    except Exception as e:
        manager.text_artist.set_text(f"Error loading file: {e}")
        print(f"[REPLAY] Error loading file: {e}")
        reset_state()


# ---------------- BUTTON CALLBACKS ----------------

def start_pause_callback(event):
    """Handles Start Live, Pause, and Resume for all active modes."""
    global running, live_mode_active, REPLAY_MODE, VIDEO_MODE
    
    if live_mode_active or REPLAY_MODE or VIDEO_MODE:
        # Toggle play/pause if already in a mode
        running = not running
        mode = "REPLAY" if REPLAY_MODE else ("VIDEO" if VIDEO_MODE else "LIVE")
        status = "Paused" if not running else "Running"
        
        if REPLAY_MODE:
            text = f"REPLAY: {status}. Frame {REPLAY_INDEX}/{len(LOADED_FRAMES)}"
        elif VIDEO_MODE or live_mode_active:
             text = f"{mode}: {status}. Frames processed: {len(all_predictions)}"
        
        manager.text_artist.set_text(text)
    else:
        # If idle, start the live analysis pipeline
        start_live_mode()

def stop_reset_callback(event):
    """Handles full stop, saving, and reset."""
    global running, stop_requested, live_mode_active, VIDEO_MODE, all_predictions, FINAL_OUTPUT_PATH
    
    running = False # Pause immediately

    if live_mode_active or VIDEO_MODE:
        # Stop live/video mode: save data and trigger full cleanup on next update cycle
        if live_mode_active:
            mode_tag = "LIVE"
        else:
            mode_tag = "VIDEO"
            
        status_msg = kinematics.save_predictions_to_json(all_predictions, FINAL_OUTPUT_PATH)
        
        stop_requested = True # Signal the animation loop to close Matplotlib
        manager.text_artist.set_text(f"{mode_tag}: Stopping & Saving... {status_msg}")
        print(f"[{mode_tag}] Stop requested. {status_msg}")
        
    elif REPLAY_MODE:
        # Stop replay mode: reset state immediately
        reset_state()
    else:
        # If idle, quit the application (cleanest way to exit Matplotlib)
        stop_requested = True
        plt.close(manager.fig)
        sys.exit()

def replay_callback(event):
    """Handles the Replay button click. Loads JSON file for playback."""
    # === EDIT THIS LINE to the name of the file you want to replay! ===
    file_to_load = "/home/popoy/projects/proj_1/videos/Jsons/webcam_3d_pose_recording.json" 
    # ==================================================================
    
    print("\n-------------------------------------------------")
    print(f"Attempting to load replay file: '{file_to_load}'")
    print("-------------------------------------------------")
    load_json_file(file_to_load)

def video_callback(event):
    """Handles the Process Video button click. Starts video processing."""
    # === EDIT THIS LINE to the name of the video file you want to process! ===
    # Example: "my_exercise_video.mp4"
    video_file_to_load = "/home/popoy/robotics/output_from_bag_FIXED.mp4" 
    # =========================================================================
    
    print("\n-------------------------------------------------")
    print(f"Attempting to process video: '{video_file_to_load}'")
    print("-------------------------------------------------")
    start_video_mode(video_file_to_load)

# ---------------- MAIN ANIMATION LOOP ----------------
def update(frame):
    global running, stop_requested, REPLAY_MODE, REPLAY_INDEX, LOADED_FRAMES, live_mode_active, all_predictions, frame_gen, inferencer, results_gen, frame_id, VIDEO_MODE

    # --- Stop/Cleanup Logic (Quits the Matplotlib window) ---
    if stop_requested:
        # Stop/Reset callback handles saving/cleanup, we just need to exit Matplotlib
        plt.close(manager.fig)
        sys.exit()
        
    if not running:
        return manager.get_artists()

    # --- REPLAY MODE LOGIC (JSON Playback) ---
    if REPLAY_MODE and not VIDEO_MODE: # Check REPLAY_MODE is NOT VIDEO_MODE
        if REPLAY_INDEX >= len(LOADED_FRAMES):
            running = False
            manager.text_artist.set_text("Replay finished. Click Stop/Reset to clear.")
            return manager.get_artists()

        result = LOADED_FRAMES[REPLAY_INDEX]
        # Dark gray placeholder for webcam image in replay mode
        vis_frame = np.full((480, 640, 3), 50, dtype=np.uint8) 
        
        manager.update_dashboard(result, vis_frame, kinematics.ANGLE_KEYS)
        
        REPLAY_INDEX += 1
        if running:
             manager.text_artist.set_text(
                f"REPLAY: Frame {REPLAY_INDEX}/{len(LOADED_FRAMES)} (Playing)"
            )
        return manager.get_artists()

    # --- LIVE/VIDEO PROCESSING LOGIC ---
    elif live_mode_active or VIDEO_MODE:
        try:
            # 1. Get raw MMPose result
            result = next(results_gen)
            
            # 2. Get RGB frame from our generator for display
            vis_frame = frame_gen.get_rgb_frame()

        except StopIteration:
            # End of stream (Video finished or camera closed)
            print(f"[{'VIDEO' if VIDEO_MODE else 'LIVE'}] Stream ended. Saving data.")
            stop_reset_callback(None)
            return []
        except Exception as e:
            print(f"Error during processing: {e}")
            manager.text_artist.set_text(f"Error: Stream Failure ({e})")
            stop_reset_callback(None) # Attempt to save what we have
            return []

        # 3. Extract and store predictions
        preds = []
        if 'predictions' in result:
            for p_list in result['predictions']:
                if p_list and isinstance(p_list, list) and len(p_list) > 0:
                    p_dict = p_list[0]
                    safe_dict = {k: (v.tolist() if hasattr(v, 'tolist') else v) for k, v in p_dict.items()}
                    preds.append(safe_dict)

        all_predictions.append({'frame_id': frame_id, 'predictions': preds})
        frame_id += 1

        # 4. Update Dashboard
        dashboard_result = {'predictions': preds}
        manager.update_dashboard(dashboard_result, vis_frame, kinematics.ANGLE_KEYS)

        # 5. Update text box
        mode_tag = "VIDEO" if VIDEO_MODE else "LIVE"
        if running:
             manager.text_artist.set_text(
                f"{mode_tag}: Running. Frames processed: {len(all_predictions)}"
            )
        return manager.get_artists()
    
# ---------------- APPLICATION START ----------------
def main():
    global manager, anim

    # 1. Setup Dashboard UI (Using constants from kinematics)
    manager = DashboardManager(kinematics.ANGLE_KEYS, kinematics.SKELETON_SEGMENTS)
    
    # 2. Connect Callbacks to Buttons
    manager.btn_start.on_clicked(start_pause_callback)
    manager.btn_stop.on_clicked(stop_reset_callback)
    manager.btn_replay.on_clicked(replay_callback)
    manager.btn_video.on_clicked(video_callback) # NEW VIDEO BUTTON

    # 3. Create animation loop
    anim = FuncAnimation(manager.fig, update, interval=50, blit=False)

    # 4. Start the UI
    try:
        manager.plt.show()
    except Exception as e:
        print(f"Matplotlib Show Error: {e}")

if __name__ == "__main__":
    main()
