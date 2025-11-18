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
    8: 'Neck', 9: 'Head', 10: 'Headtop', 11: 'L_Shoulder',
    12: 'L_Elbow', 13: 'L_Wrist', 14: 'R_Shoulder', 15: 'R_Elbow',
    16: 'R_Wrist'
}

SKELETON_SEGMENTS = {
    'Pelvis_Torso_Head': {'color': 'red', 'links': [(0, 7), (7, 8), (8, 9), (9, 10)]},
    'Right_Arm': {'color': 'blue', 'links': [(8, 14), (14, 15), (15, 16)]},
    'Left_Arm': {'color': 'cyan', 'links': [(8, 11), (11, 12), (12, 13)]},
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
    if denom == 0:
        return 0.0
    cosv = np.clip(np.dot(v1, v2) / denom, -1.0, 1.0)
    return np.degrees(np.arccos(cosv))

def calculate_vertical_angle(Start, End):
    """Calculates the angle of a segment (Start->End) relative to the vertical axis (Y-up)."""
    seg = End - Start
    norm = np.linalg.norm(seg)
    if norm == 0:
        return 0.0
    cosv = np.clip(np.dot(seg, np.array([0.0, 1.0, 0.0])) / norm, -1.0, 1.0)
    return np.degrees(np.arccos(cosv))

def compute_rotation_matrix(proximal_vec, distal_vec, invert_z=False):
    """
    Computes a rotation matrix (local coordinate system) based on two segment vectors.
    Distal vector defines the Y-axis (length of the bone/segment).
    If invert_z is True, the resulting Z-axis is flipped, ensuring mirrored symmetry.
    """
    if np.linalg.norm(proximal_vec) < 1e-9 or np.linalg.norm(distal_vec) < 1e-9:
        return np.eye(3)
    
    p = proximal_vec / np.linalg.norm(proximal_vec)
    d = distal_vec / np.linalg.norm(distal_vec)
    
    y_axis = d
    x_temp = np.cross(p, d)
    
    if np.linalg.norm(x_temp) < 1e-6:
        # Fallback for near-collinear vectors: use a world axis for x-temp
        if np.abs(np.dot(d, np.array([1.0, 0.0, 0.0]))) < 0.8:
            x_temp = np.cross(np.array([1.0, 0.0, 0.0]), d)
        else:
            x_temp = np.cross(np.cross(d, np.array([0.0, 0.0, 1.0])), d)
            
        if np.linalg.norm(x_temp) < 1e-6:
             return np.eye(3)
        
    z_axis = x_temp / np.linalg.norm(x_temp)
    
    # --- Symmetry Fix ---
    if invert_z:
        z_axis *= -1
    # --------------------
    
    x_axis = np.cross(y_axis, z_axis)
    x_axis /= np.linalg.norm(x_axis) 
    
    return np.vstack([x_axis, y_axis, z_axis]).T

def rotation_matrix_to_euler_angles(R):
    """Converts a rotation matrix to ZYX (Tait-Bryan) Euler angles (in degrees).
    The return order is (Rx, Ry, Rz).
    """
    r_x = np.arcsin(np.clip(R[2, 0], -1.0, 1.0))
    cos_rx = np.cos(r_x)
    
    if abs(cos_rx) < 1e-6:
        r_y = 0.0
        r_z = np.arctan2(R[1, 1], R[0, 1])
    else:
        r_y = np.arctan2(R[1, 0] / cos_rx, R[0, 0] / cos_rx)
        r_z = np.arctan2(R[2, 1] / cos_rx, R[2, 2] / cos_rx)
        
    return np.degrees(r_x), np.degrees(r_y), np.degrees(r_z)


def calculate_anatomical_angles(kp):
    """
    Calculates 3D Euler angles for all ball-and-socket and axial joints.
    The order corresponds to (X-Axis, Y-Axis, Z-Axis) rotation.
    """
    angles = {}
    
    # --- WAIST/TORSO ROTATION (Joint Center: Torso 7) ---
    if kp.shape[0] > 8:
        # Define Pelvis Local Frame (R_local)
        proximal_y = kp[7] - kp[0] # Y-axis: Pelvis -> Torso
        proximal_y /= np.linalg.norm(proximal_y)
        x_axis_ref = kp[4] - kp[1] # X-axis (Lateral): L_Hip (4) -> R_Hip (1)
        x_axis_ref /= np.linalg.norm(x_axis_ref)
        z_axis = np.cross(proximal_y, x_axis_ref)
        z_axis /= np.linalg.norm(z_axis)
        x_axis = np.cross(proximal_y, z_axis)
        x_axis /= np.linalg.norm(x_axis)
        R_local = np.vstack([x_axis, proximal_y, z_axis]).T 
        
        # Define Torso Segment Local Matrix (R_torso)
        distal_segment = kp[8] - kp[7] # Torso to Neck
        torso_y = distal_segment / np.linalg.norm(distal_segment)
        torso_x_temp = np.cross(x_axis_ref, torso_y)
        torso_z = torso_x_temp / np.linalg.norm(torso_x_temp)
        torso_x = np.cross(torso_y, torso_z)
        torso_x /= np.linalg.norm(torso_x)
        R_torso = np.vstack([torso_x, torso_y, torso_z]).T 
        
        # Rotation Matrix R_torso_relative_pelvis = R_torso @ R_local.T
        R_relative = R_torso @ R_local.T
        
        rx, ry, rz = rotation_matrix_to_euler_angles(R_relative)
        
        angles["Waist (X-Axis Rotation)"] = round(rx, 1)
        angles["Waist (Y-Axis Rotation)"] = round(ry, 1)
        angles["Waist (Z-Axis Rotation)"] = round(rz, 1)

    # --- NECK ROTATION (Joint Center: Neck 8) ---
    if kp.shape[0] > 9:
        # Proximal vector: Torso (7) -> Neck (8)
        # Distal segment: Neck (8) -> Head (9)
        Rm = compute_rotation_matrix(kp[7] - kp[8], kp[9] - kp[8])
        rx, ry, rz = rotation_matrix_to_euler_angles(Rm)
        angles["Neck (X-Axis Rotation)"] = round(rx, 1)
        angles["Neck (Y-Axis Rotation)"] = round(ry, 1)
        angles["Neck (Z-Axis Rotation)"] = round(rz, 1)

    # --- SHOULDER CALCULATION ---
    
    # Use the vertical spine segment as the common, stable proximal reference for both arms.
    # Defines a vector pointing down the spine (Torso 7 -> Neck 8)
    proximal_torso_ref = kp[7] - kp[8] 
    proximal_torso_ref /= np.linalg.norm(proximal_torso_ref)
    
    # --- RIGHT SHOULDER (Joint Center: Shoulder 14) ---
    if kp.shape[0] > 15:
        # Proximal Reference (P): Vertical spine segment
        # Distal Segment (D): Upper arm (Elbow 15 - Shoulder 14)
        # No Z-inversion needed for the right side
        Rm = compute_rotation_matrix(proximal_torso_ref, kp[15] - kp[14], invert_z=False)
        rx, ry, rz = rotation_matrix_to_euler_angles(Rm)
        angles["R Shoulder (X-Axis Rotation)"] = round(rx, 1)
        angles["R Shoulder (Y-Axis Rotation)"] = round(ry, 1)
        angles["R Shoulder (Z-Axis Rotation)"] = round(rz, 1)
        
    # --- LEFT SHOULDER (Joint Center: Shoulder 11) ---
    if kp.shape[0] > 12:
        # Proximal Reference (P): Vertical spine segment
        # Distal Segment (D): Upper arm (Elbow 12 - Shoulder 11)
        
        # --- FIX: Invert the Z-axis of the local coordinate system 
        # to ensure the left arm mirrors the right arm's rotation plane.
        
        # We use the ORIGINAL proximal_torso_ref (no * -1) but invert the Z axis 
        # in the rotation matrix calculation.
        Rm = compute_rotation_matrix(proximal_torso_ref, kp[12] - kp[11], invert_z=True)
        
        rx, ry, rz = rotation_matrix_to_euler_angles(Rm)
        angles["L Shoulder (X-Axis Rotation)"] = round(rx, 1)
        angles["L Shoulder (Y-Axis Rotation)"] = round(ry, 1)
        angles["L Shoulder (Z-Axis Rotation)"] = round(rz, 1)

    # --- RIGHT HIP (Joint Center: Hip 1) ---
    if kp.shape[0] > 2:
        Rm = compute_rotation_matrix(kp[0] - kp[1], kp[2] - kp[1])
        rx, ry, rz = rotation_matrix_to_euler_angles(Rm)
        angles["R Hip (X-Axis Rotation)"] = round(rx, 1)
        angles["R Hip (Y-Axis Rotation)"] = round(ry, 1)
        angles["R Hip (Z-Axis Rotation)"] = round(rz, 1)

    # --- LEFT HIP (Joint Center: Hip 4) ---
    if kp.shape[0] > 5:
        Rm = compute_rotation_matrix(kp[0] - kp[4], kp[5] - kp[4])
        rx, ry, rz = rotation_matrix_to_euler_angles(Rm)
        angles["L Hip (X-Axis Rotation)"] = round(rx, 1)
        angles["L Hip (Y-Axis Rotation)"] = round(ry, 1)
        angles["L Hip (Z-Axis Rotation)"] = round(rz, 1)
        
    return angles

def process_all_angles(kp, ANGLE_KEYS):
    """Calculates all 23 angles (simple bend + 3D Euler components)."""
    all_angles = {}
    
    # 1. Simple Bend Angles (Knee and Elbows)
    checks = [ 
        (1,2,3,"R_Knee"), (4,5,6,"L_Knee"), 
        (14,15,16,"R_Elbow"), 
        (11,12,13,"L_Elbow") 
    ]
    for A,B,C,name in checks:
        if C < kp.shape[0]:
            all_angles[f"{name} (Bend)"] = round(calculate_3d_angle(kp[A], kp[B], kp[C]), 1)
            
    # 2. Simple Vertical Angle (Torso)
    if 8 < kp.shape[0]:
        all_angles["Torso-Neck (Vertical)"] = round(calculate_vertical_angle(kp[7], kp[8]), 1)
        
    # 3. Complex 3D Euler Angles (Hip, Shoulder, Waist, Neck)
    all_angles.update(calculate_anatomical_angles(kp))
    
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
