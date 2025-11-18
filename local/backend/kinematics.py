import numpy as np
import json
import datetime
import warnings

# --- WARNING FILTER FIX ---
warnings.filterwarnings(
    "ignore",
    message=".*autocast.*is deprecated.*",
    category=FutureWarning
)
# --------------------------

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

# --- COMPLETE LIST OF 23 KINEMATIC ANGLES (Organized for Dashboard Layout) ---
ANGLE_KEYS = [
    # 1. Neck/Head (3D + 1 simple vertical)
    "Neck (X-Axis Rotation)", "Neck (Y-Axis Rotation)", "Neck (Z-Axis Rotation)",
    "Torso-Neck (Vertical)",
    
    # 2. Waist/Torso (3D)
    "Waist (X-Axis Rotation)", "Waist (Y-Axis Rotation)", "Waist (Z-Axis Rotation)",
    
    # 3. Shoulders (3D, Grouped by axis)
    "R Shoulder (X-Axis Rotation)", "L Shoulder (X-Axis Rotation)",
    "R Shoulder (Y-Axis Rotation)", "L Shoulder (Y-Axis Rotation)",
    "R Shoulder (Z-Axis Rotation)", "L Shoulder (Z-Axis Rotation)",

    # 4. Elbows (Simple Bend)
    "R_Elbow (Bend)", "L_Elbow (Bend)",

    # 5. Hips (3D, Grouped by axis)
    "R Hip (X-Axis Rotation)", "L Hip (X-Axis Rotation)",
    "R Hip (Y-Axis Rotation)", "L Hip (Y-Axis Rotation)",
    "R Hip (Z-Axis Rotation)", "L Hip (Z-Axis Rotation)",
    
    # 6. Knees (Simple Bend)
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
    # R[1,0] = sin(x)
    # R[1,2] = -cos(x)sin(z)
    # R[1,1] = cos(x)cos(z)
    # R[0,0] = cos(y)cos(z) + sin(y)sin(x)sin(z)
    # R[2,0] = -sin(y)cos(z) + cos(y)sin(x)sin(z)

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
    The order corresponds to (X-Axis, Y-Axis, Z-Axis) rotation.
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
        # This mirrors the logic in kinematics.js
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
        # This mirrors the logic in kinematics.js
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

def save_predictions_to_json(all_predictions, final_output_path):
    """Saves collected prediction data to a JSON file."""
    if all_predictions:
        try:
            with open(final_output_path, 'w') as f:
                json.dump(all_predictions, f, indent=4)
            print(f"[KINEMATICS] Saved {len(all_predictions)} frames to {final_output_path}")
            return f"Saved {len(all_predictions)} frames to JSON."
        except Exception as e:
            print(f"[KINEMATICS] Failed to save JSON: {e}")
            return f"Failed to save JSON: ERROR ({e})"
    else:
        print("[KINEMATICS] No frames to save.")
        return "No frames to save."