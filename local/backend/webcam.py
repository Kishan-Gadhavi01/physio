import uvicorn
import cv2
import asyncio
import json
import datetime
import warnings
import numpy as np

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from mmpose.apis import MMPoseInferencer

# --- WARNING FILTER FIX ---
warnings.filterwarnings(
    "ignore",
    message=".*autocast.*is deprecated.*",
    category=FutureWarning
)
# --------------------------

# -------------------- CONFIG --------------------
DEVICE = "cpu"  # Use 'cpu' for stability
OUTPUT_JSON_PATH = "web_session_data.json" # Base filename for saved files
# ------------------------------------------------

# ===================================================================
# --- KINEMATICS LOGIC (MERGED FROM kinematics.py) ---
# ===================================================================

# --- Joint names & skeleton layout (H36M 17 point mapping) ---
H36M_JOINT_NAMES = {
    0: 'Pelvis', 1: 'R_Hip', 2: 'R_Knee', 3: 'R_Ankle',
    4: 'L_Hip', 5: 'L_Knee', 6: 'L_Ankle', 7: 'Torso',
    8: 'Neck', 9: 'Head', 10: 'Headtop',
    11: 'R_Shoulder', 12: 'R_Elbow', 13: 'R_Wrist',
    14: 'L_Shoulder', 15: 'L_Elbow', 16: 'L_Wrist'
}

SKELETON_SEGMENTS = {
    'Pelvis_Torso_Head': {'color': 'red', 'links': [(0, 7), (7, 8), (8, 9), (9, 10)]},
    'Right_Arm': {'color': 'blue', 'links': [(8, 11), (11, 12), (12, 13)]},
    'Left_Arm': {'color': 'cyan', 'links': [(8, 14), (14, 15), (15, 16)]},
    'Right_Leg': {'color': 'green', 'links': [(0, 1), (1, 2), (2, 3)]},
    'Left_Leg': {'color': 'lime', 'links': [(0, 4), (4, 5), (5, 6)]}
}

# --- COMPLETE LIST OF 23 KINEMATIC ANGLES ---
ANGLE_KEYS = [
    "Neck (X-Axis Rotation)", "Neck (Y-Axis Rotation)", "Neck (Z-Axis Rotation)",
    "Torso-Neck (Vertical)",
    "Waist (X-Axis Rotation)", "Waist (Y-Axis Rotation)", "Waist (Z-Axis Rotation)",
    "R Shoulder (X-Axis Rotation)", "L Shoulder (X-Axis Rotation)",
    "R Shoulder (Y-Axis Rotation)", "L Shoulder (Y-Axis Rotation)",
    "R Shoulder (Z-Axis Rotation)", "L Shoulder (Z-Axis Rotation)",
    "R_Elbow (Bend)", "L_Elbow (Bend)",
    "R Hip (X-Axis Rotation)", "L Hip (X-Axis Rotation)",
    "R Hip (Y-Axis Rotation)", "L Hip (Y-Axis Rotation)",
    "R Hip (Z-Axis Rotation)", "L Hip (Z-Axis Rotation)",
    "R_Knee (Bend)", "L_Knee (Bend)",
]

# ---------------- KINEMATIC HELPERS ----------------
def calculate_3d_angle(A, B, C):
    """Calculates the 3D angle at joint B defined by segments BA and BC."""
    v1 = A - B
    v2 = C - B
    denom = np.linalg.norm(v1) * np.linalg.norm(v2)
    if denom < 1e-9: # Prevent division by zero
        return 0.0
    cosv = np.clip(np.dot(v1, v2) / denom, -1.0, 1.0)
    return np.degrees(np.arccos(cosv))

def calculate_vertical_angle(Start, End):
    """Calculates the angle of a segment (Start->End) relative to the vertical axis (Y-up)."""
    seg = End - Start
    norm = np.linalg.norm(seg)
    if norm < 1e-9: # Prevent division by zero
        return 0.0
    # Assumes Y is UP
    cosv = np.clip(np.dot(seg, np.array([0.0, 1.0, 0.0])) / norm, -1.0, 1.0)
    return np.degrees(np.arccos(cosv))

def compute_rotation_matrix(proximal_vec, distal_vec):
    """
    Computes a rotation matrix (local coordinate system) based on two segment vectors.
    Distal vector defines the Y-axis (length of the bone/segment).
    This implementation mirrors the THREE.js lookAt logic.
    """
    if np.linalg.norm(proximal_vec) < 1e-9 or np.linalg.norm(distal_vec) < 1e-9:
        return np.eye(3)
    
    # Y-axis is the distal segment (bone direction)
    y_axis = distal_vec / np.linalg.norm(distal_vec)
    
    # Z-axis is perpendicular to distal and proximal vectors
    z_axis = np.cross(y_axis, proximal_vec)
    if np.linalg.norm(z_axis) < 1e-9:
        # Fallback for collinear vectors
        if abs(y_axis[0]) > 0.8: # If y_axis is close to x-axis
            z_axis = np.cross(y_axis, np.array([0, 1, 0]))
        else:
            z_axis = np.cross(y_axis, np.array([1, 0, 0]))
    
    if np.linalg.norm(z_axis) < 1e-9: # Second fallback
        return np.eye(3)
    z_axis /= np.linalg.norm(z_axis)
    
    # X-axis is perpendicular to Y and Z
    x_axis = np.cross(y_axis, z_axis)
    x_axis /= np.linalg.norm(x_axis)
    
    # Return the basis matrix [X, Y, Z]
    return np.vstack([x_axis, y_axis, z_axis]).T


def rotation_matrix_to_euler_angles(R):
    """
    Converts a rotation matrix to Euler angles (YXZ order) in degrees.
    This order matches the THREE.js 'YXZ' implementation.
    """
    # YXZ intrinsic rotation
    r_x = np.arcsin(np.clip(R[1, 0], -1.0, 1.0))
    cos_rx = np.cos(r_x)

    if abs(cos_rx) > 1e-6:
        r_y = np.arctan2(-R[2, 0], R[0, 0])
        r_z = np.arctan2(-R[1, 2], R[1, 1])
    else:
        # Gimbal lock
        r_y = np.arctan2(R[0, 2], R[2, 2])
        r_z = 0.0

    return np.degrees(r_x), np.degrees(r_y), np.degrees(r_z)


def calculate_anatomical_angles(kp):
    """
    Calculates 3D Euler angles for all ball-and-socket and axial joints.
    """
    angles = {}
    
    if kp.shape[0] < 17:
        return {key: 0.0 for key in ANGLE_KEYS if 'Bend' not in key and 'Vertical' not in key}

    # --- WAIST/TORSO ROTATION (Joint Center: Torso 7) ---
    if kp.shape[0] > 8:
        try:
            proximal_y = kp[7] - kp[0] # Y-axis: Pelvis -> Torso
            x_axis_ref = kp[1] - kp[4] # X-axis (Lateral): R_Hip (1) -> L_Hip (4)
            
            if np.linalg.norm(proximal_y) > 1e-6 and np.linalg.norm(x_axis_ref) > 1e-6:
                proximal_y /= np.linalg.norm(proximal_y)
                x_axis_ref /= np.linalg.norm(x_axis_ref)
                
                z_axis_local = np.cross(proximal_y, x_axis_ref)
                z_axis_local /= np.linalg.norm(z_axis_local)
                x_axis_local = np.cross(proximal_y, z_axis_local)
                x_axis_local /= np.linalg.norm(x_axis_local)
                R_local = np.vstack([x_axis_local, proximal_y, z_axis_local]).T 
                
                torso_y = kp[8] - kp[7] # Torso to Neck
                if np.linalg.norm(torso_y) > 1e-6:
                    torso_y /= np.linalg.norm(torso_y)
                    z_axis_torso = np.cross(torso_y, x_axis_ref)
                    if np.linalg.norm(z_axis_torso) < 1e-9: # Fallback
                         z_axis_torso = np.cross(torso_y, np.array([0,0,1]))
                    z_axis_torso /= np.linalg.norm(z_axis_torso)
                    
                    x_axis_torso = np.cross(torso_y, z_axis_torso)
                    x_axis_torso /= np.linalg.norm(x_axis_torso)
                    R_torso = np.vstack([x_axis_torso, torso_y, z_axis_torso]).T 
                    
                    R_relative = R_torso @ np.linalg.inv(R_local)
                    rx, ry, rz = rotation_matrix_to_euler_angles(R_relative)
                    
                    angles["Waist (X-Axis Rotation)"] = round(rx, 1)
                    angles["Waist (Y-Axis Rotation)"] = round(ry, 1)
                    angles["Waist (Z-Axis Rotation)"] = round(rz, 1)
        except Exception as e:
            print(f"Error calculating waist: {e}")


    # --- NECK ROTATION (Joint Center: Neck 8) ---
    if kp.shape[0] > 9:
        proximal = kp[7] - kp[8] # Torso -> Neck
        distal = kp[9] - kp[8]   # Neck -> Head
        Rm = compute_rotation_matrix(proximal, distal)
        rx, ry, rz = rotation_matrix_to_euler_angles(Rm)
        angles["Neck (X-Axis Rotation)"] = round(rx, 1)
        angles["Neck (Y-Axis Rotation)"] = round(ry, 1)
        angles["Neck (Z-Axis Rotation)"] = round(rz, 1)

    # --- RIGHT SHOULDER (Joint Center: Shoulder 11) ---
    if kp.shape[0] > 12:
        proximal = kp[8] - kp[11] # Neck -> R_Shoulder
        distal = kp[12] - kp[11]  # R_Shoulder -> R_Elbow
        Rm = compute_rotation_matrix(proximal, distal)
        rx, ry, rz = rotation_matrix_to_euler_angles(Rm)
        angles["R Shoulder (X-Axis Rotation)"] = round(rx, 1)
        angles["R Shoulder (Y-Axis Rotation)"] = round(ry, 1)
        angles["R Shoulder (Z-Axis Rotation)"] = round(rz, 1)
        
    # --- LEFT SHOULDER (Joint Center: Shoulder 14) ---
    if kp.shape[0] > 15:
        proximal = kp[8] - kp[14] # Neck -> L_Shoulder
        distal = kp[15] - kp[14]  # L_Shoulder -> L_Elbow
        Rm = compute_rotation_matrix(proximal, distal)
        rx, ry, rz = rotation_matrix_to_euler_angles(Rm)
        
        # --- FIX: Negate Y and Z angles for left side ---
        angles["L Shoulder (X-Axis Rotation)"] = round(rx, 1)
        angles["L Shoulder (Y-Axis Rotation)"] = round(-ry, 1)
        angles["L Shoulder (Z-Axis Rotation)"] = round(-rz, 1)
        # -------------------------------------------------

    # --- RIGHT HIP (Joint Center: Hip 1) ---
    if kp.shape[0] > 2:
        proximal = kp[0] - kp[1] # Pelvis -> R_Hip
        distal = kp[2] - kp[1]   # R_Hip -> R_Knee
        Rm = compute_rotation_matrix(proximal, distal)
        rx, ry, rz = rotation_matrix_to_euler_angles(Rm)
        angles["R Hip (X-Axis Rotation)"] = round(rx, 1)
        angles["R Hip (Y-Axis Rotation)"] = round(ry, 1)
        angles["R Hip (Z-Axis Rotation)"] = round(rz, 1)

    # --- LEFT HIP (Joint Center: Hip 4) ---
    if kp.shape[0] > 5:
        proximal = kp[0] - kp[4] # Pelvis -> L_Hip
        distal = kp[5] - kp[4]   # L_Hip -> L_Knee
        Rm = compute_rotation_matrix(proximal, distal)
        rx, ry, rz = rotation_matrix_to_euler_angles(Rm)

        # --- FIX: Negate Y and Z angles for left side ---
        angles["L Hip (X-Axis Rotation)"] = round(rx, 1)
        angles["L Hip (Y-Axis Rotation)"] = round(-ry, 1)
        angles["L Hip (Z-Axis Rotation)"] = round(-rz, 1)
        # -------------------------------------------------
            
    return angles

def process_all_angles(kp, ANGLE_KEYS):
    """Calculates all 23 angles (simple bend + 3D Euler components)."""
    all_angles = {}
    
    if kp.shape[0] < 17:
        return {key: 0.0 for key in ANGLE_KEYS}

    # 1. Simple Bend Angles (Knee and Elbows)
    checks = [ 
        (1,2,3,"R_Knee"), (4,5,6,"L_Knee"), 
        (11,12,13,"R_Elbow"),
        (14,15,16,"L_Elbow")
    ]
    for A,B,C,name in checks:
        if C < kp.shape[0]:
            all_angles[f"{name} (Bend)"] = round(calculate_3d_angle(kp[A], kp[B], kp[C]), 1)
            
    # 2. Simple Vertical Angle (Torso)
    if 8 < kp.shape[0]:
        all_angles["Torso-Neck (Vertical)"] = round(calculate_vertical_angle(kp[7], kp[8]), 1)
            
    # 3. Complex 3D Euler Angles (Hip, Shoulder, Waist, Neck)
    all_angles.update(calculate_anatomical_angles(kp))
    
    # Ensure all keys are present, even if calculation failed
    for key in ANGLE_KEYS:
        if key not in all_angles:
            all_angles[key] = 0.0
            
    return all_angles

# ===================================================================
# --- END OF KINEMATICS LOGIC ---
# ===================================================================


app = FastAPI()

# --- Custom Frame Generator for Camera ---
class WebcamStreamGenerator:
    """
    Manages cv2.VideoCapture to be used as a generator for MMPose.
    """
    def __init__(self, source=0):
        self.cap = cv2.VideoCapture(source)
        if not self.cap.isOpened():
            raise IOError(f"ERROR: Could not open camera source: {source}.")
            
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        print("[API] WebcamStreamGenerator initialized.")

    def __iter__(self):
        return self

    def __next__(self):
        ret, frame = self.cap.read()
        if not ret:
            self.cap.release()
            print("[API] Webcam stream ended.")
            raise StopIteration("End of stream reached.")
        return frame

    def release(self):
        self.cap.release()

# --- WebSocket Endpoint ---
@app.websocket("/ws/pose")
async def websocket_pose_stream(websocket: WebSocket):
    """
    Main WebSocket endpoint for live pose estimation.
    """
    await websocket.accept()
    print("[API] WebSocket connection accepted.")
    
    inferencer = None
    frame_gen = None
    all_predictions = []
    frame_id = 0
    
    # Generate timestamped filename for saving
    now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    final_output_path = OUTPUT_JSON_PATH.replace(".json", f"_{now}.json")

    try:
        # 1. Initialize MMPose and Webcam
        print("[API] Initializing MMPoseInferencer...")
        inferencer = MMPoseInferencer(pose3d='human3d', device=DEVICE)
        print("[API] MMPoseInferencer initialized.")
        
        frame_gen = WebcamStreamGenerator(source=0)
        
        # 2. Create the processing pipeline generator
        results_gen = inferencer(inputs=frame_gen, return_vis=False)
        print("[API] MMPose pipeline generator created. Starting stream...")

        # 3. Stream processing loop
        for result in results_gen:
            
            # --- Data Extraction ---
            preds = []
            keypoints_3d_raw = None # This is the raw data (list or ndarray)
            
            if 'predictions' in result:
                for p_list in result['predictions']:
                    if p_list and isinstance(p_list, list) and len(p_list) > 0:
                        p_dict = p_list[0]
                        # Convert numpy arrays to lists for JSON serialization
                        safe_dict = {k: (v.tolist() if hasattr(v, 'tolist') else v) for k, v in p_dict.items()}
                        preds.append(safe_dict)
                        
                        # Extract keypoints for angle calculation
                        if 'keypoints' in p_dict and p_dict['keypoints'] is not None:
                            keypoints_3d_raw = p_dict['keypoints']

            # --- Angle Calculation ---
            angles = {}
            
            # --- ROBUSTNESS & COORDINATE FIX ---
            if keypoints_3d_raw is not None:
                try:
                    # 1. Ensure keypoints are a numpy array
                    kp_array = np.array(keypoints_3d_raw)
                    
                    if kp_array.shape[0] > 0:
                        
                        # 2. COORDINATE TRANSFORM
                        # Model outputs [X, Y-down, Z-fwd]
                        # Kinematics logic expects [X, Y-up, Z-fwd]
                        kp_for_angles = kp_array.copy()
                        kp_for_angles[:, 1] = -kp_for_angles[:, 1] # Flip Y-axis to be "up"
                        # ----------------------
                        
                        # 3. Call the local angle calculation function
                        angles = process_all_angles(kp_for_angles, ANGLE_KEYS)
                        
                except Exception as e:
                    print(f"[API] Error during angle calculation: {e}")
                    # angles will remain {}
            # --- END OF FIX ---

            # --- Prepare JSON Payload ---
            frame_data = {
                'frame_id': frame_id,
                'predictions': preds, # This contains the raw 3D keypoints
                'angles': angles      # This contains the calculated angles
            }
            
            # 4. Store for saving
            all_predictions.append(frame_data)
            frame_id += 1
            
            # 5. Send data to React client
            await websocket.send_json(frame_data)
            
            # Yield control to allow other tasks to run
            await asyncio.sleep(0.01) 

    except WebSocketDisconnect:
        print("[API] WebSocket client disconnected.")
    except Exception as e:
        print(f"[API] An error occurred: {e}")
        # Send a more concise error message to prevent "control frame too long"
        error_message = str(e).splitlines()[0] # Get first line of error
        await websocket.close(code=1011, reason=f"Server error: {error_message[:120]}")
    finally:
        # --- Cleanup and Save ---
        print("[API] Cleaning up resources...")
        if frame_gen:
            frame_gen.release()
            
        inferencer = None # Allow garbage collection
        
        if all_predictions:
            print(f"[API] Saving {len(all_predictions)} frames to {final_output_path}...")
            try:
                with open(final_output_path, 'w') as f:
                    json.dump(all_predictions, f, indent=4)
                print(f"[API] Successfully saved data.")
            except Exception as e:
                print(f"[API] Failed to save JSON file: {e}")
        else:
            print("[API] No data to save.")

# --- Main entry point to run the server ---
if __name__ == "__main__":
    print("[API] Starting FastAPI server on http://127.0.0.1:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000)