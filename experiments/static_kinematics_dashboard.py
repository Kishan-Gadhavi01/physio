"""
Standalone script to load a full JSON motion analysis file (saved from the live dashboard),
calculate all 23 kinematic angles, save the angles to a highly compressed, indexed JSON file,
and generate a single, static figure containing all kinematic angle plots.
"""
import matplotlib.pyplot as plt
import numpy as np
import json
import math
import sys
import warnings

# --- Suppress warnings ---
warnings.filterwarnings(
    "ignore",
    message=".*autocast.*is deprecated.*",
    category=FutureWarning
)
# ----------------------------------------------------------------------------------

# -------------------------------------------------
# 1. KINEMATIC DEFINITIONS (From User's Saved Info)
# -------------------------------------------------

# NOTE: Using the user's custom H36M_JOINT_NAMES map for consistency, 
# though the angle calculations rely on the index/position.
H36M_JOINT_NAMES = {
    0: 'Pelvis', 1: 'R_Hip', 2: 'R_Knee', 3: 'R_Ankle',
    4: 'L_Hip', 5: 'L_Knee', 6: 'L_Ankle', 7: 'Torso',
    8: 'Neck', 9: 'Head', 10: 'Headtop', 11: 'R_Shoulder',
    12: 'R_Elbow', 13: 'R_Wrist', 14: 'L_Shoulder', 15: 'L_Elbow',
    16: 'L_Wrist'
}

# --- COMPLETE LIST OF 23 KINEMATIC ANGLES (DEFINING THE INDEX ORDER) ---
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

# ------------------- KINEMATIC MATH FUNCTIONS -------------------
def calculate_3d_angle(A, B, C):
    v1 = A - B
    v2 = C - B
    denom = np.linalg.norm(v1) * np.linalg.norm(v2)
    if denom == 0: return 0.0
    cosv = np.clip(np.dot(v1, v2) / denom, -1.0, 1.0)
    return np.degrees(np.arccos(cosv))

def calculate_vertical_angle(Start, End):
    seg = End - Start
    norm = np.linalg.norm(seg)
    if norm == 0: return 0.0
    cosv = np.clip(np.dot(seg, np.array([0.0, 1.0, 0.0])) / norm, -1.0, 1.0)
    return np.degrees(np.arccos(cosv))

def compute_rotation_matrix(proximal_vec, distal_vec, invert_z=False):
    if np.linalg.norm(proximal_vec) < 1e-9 or np.linalg.norm(distal_vec) < 1e-9: return np.eye(3)
    p, d = proximal_vec / np.linalg.norm(proximal_vec), distal_vec / np.linalg.norm(distal_vec)
    y_axis = d
    x_temp = np.cross(p, d)
    if np.linalg.norm(x_temp) < 1e-6:
        if np.abs(np.dot(d, np.array([1.0, 0.0, 0.0]))) < 0.8:
            x_temp = np.cross(np.array([1.0, 0.0, 0.0]), d)
        else:
            x_temp = np.cross(np.cross(d, np.array([0.0, 0.0, 1.0])), d)
        if np.linalg.norm(x_temp) < 1e-6: return np.eye(3)
        
    z_axis = x_temp / np.linalg.norm(x_temp)
    if invert_z: z_axis *= -1
    x_axis = np.cross(y_axis, z_axis)
    x_axis /= np.linalg.norm(x_axis) 
    return np.vstack([x_axis, y_axis, z_axis]).T

def rotation_matrix_to_euler_angles(R):
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
    angles = {}
    
    # WAIST/TORSO
    if kp.shape[0] > 8:
        proximal_y = kp[7] - kp[0]; proximal_y /= np.linalg.norm(proximal_y)
        x_axis_ref = kp[4] - kp[1]; x_axis_ref /= np.linalg.norm(x_axis_ref)
        z_axis = np.cross(proximal_y, x_axis_ref); z_axis /= np.linalg.norm(z_axis)
        x_axis = np.cross(proximal_y, z_axis); x_axis /= np.linalg.norm(x_axis)
        R_local = np.vstack([x_axis, proximal_y, z_axis]).T 
        distal_segment = kp[8] - kp[7]; torso_y = distal_segment / np.linalg.norm(distal_segment)
        torso_x_temp = np.cross(x_axis_ref, torso_y); torso_z = torso_x_temp / np.linalg.norm(torso_x_temp)
        torso_x = np.cross(torso_y, torso_z); torso_x /= np.linalg.norm(torso_x)
        R_torso = np.vstack([torso_x, torso_y, torso_z]).T 
        R_relative = R_torso @ R_local.T
        rx, ry, rz = rotation_matrix_to_euler_angles(R_relative)
        angles["Waist (X-Axis Rotation)"] = round(rx, 1); angles["Waist (Y-Axis Rotation)"] = round(ry, 1); angles["Waist (Z-Axis Rotation)"] = round(rz, 1)

    # NECK
    if kp.shape[0] > 9:
        Rm = compute_rotation_matrix(kp[7] - kp[8], kp[9] - kp[8])
        rx, ry, rz = rotation_matrix_to_euler_angles(Rm)
        angles["Neck (X-Axis Rotation)"] = round(rx, 1); angles["Neck (Y-Axis Rotation)"] = round(ry, 1); angles["Neck (Z-Axis Rotation)"] = round(rz, 1)

    # RIGHT SHOULDER (R_Shoulder: 14 in the script's H36M_JOINT_NAMES)
    if kp.shape[0] > 15:
        proximal_torso_ref = kp[7] - kp[8]; proximal_torso_ref /= np.linalg.norm(proximal_torso_ref)
        # Note: Indexing must be based on the provided H36M_JOINT_NAMES which uses 14/15/16 for R_Arm
        Rm = compute_rotation_matrix(proximal_torso_ref, kp[15] - kp[14], invert_z=False)
        rx, ry, rz = rotation_matrix_to_euler_angles(Rm)
        angles["R Shoulder (X-Axis Rotation)"] = round(rx, 1); angles["R Shoulder (Y-Axis Rotation)"] = round(ry, 1); angles["R Shoulder (Z-Axis Rotation)"] = round(rz, 1)
        
    # LEFT SHOULDER (L_Shoulder: 11 in the script's H36M_JOINT_NAMES)
    if kp.shape[0] > 12:
        proximal_torso_ref = kp[7] - kp[8]; proximal_torso_ref /= np.linalg.norm(proximal_torso_ref)
        # Note: Indexing must be based on the provided H36M_JOINT_NAMES which uses 11/12/13 for L_Arm
        Rm = compute_rotation_matrix(proximal_torso_ref, kp[12] - kp[11], invert_z=True)
        rx, ry, rz = rotation_matrix_to_euler_angles(Rm)
        angles["L Shoulder (X-Axis Rotation)"] = round(rx, 1); angles["L Shoulder (Y-Axis Rotation)"] = round(ry, 1); angles["L Shoulder (Z-Axis Rotation)"] = round(rz, 1)

    # RIGHT HIP
    if kp.shape[0] > 2:
        Rm = compute_rotation_matrix(kp[0] - kp[1], kp[2] - kp[1])
        rx, ry, rz = rotation_matrix_to_euler_angles(Rm)
        angles["R Hip (X-Axis Rotation)"] = round(rx, 1); angles["R Hip (Y-Axis Rotation)"] = round(ry, 1); angles["R Hip (Z-Axis Rotation)"] = round(rz, 1)

    # LEFT HIP
    if kp.shape[0] > 5:
        Rm = compute_rotation_matrix(kp[0] - kp[4], kp[5] - kp[4])
        rx, ry, rz = rotation_matrix_to_euler_angles(Rm)
        angles["L Hip (X-Axis Rotation)"] = round(rx, 1); angles["L Hip (Y-Axis Rotation)"] = round(ry, 1); angles["L Hip (Z-Axis Rotation)"] = round(rz, 1)
        
    return angles

def process_all_angles(kp, angle_keys):
    all_angles = {}
    
    # 1. Simple Bend Angles (Knee and Elbows)
    # R_Knee: (R_Hip=1, R_Knee=2, R_Ankle=3)
    # L_Knee: (L_Hip=4, L_Knee=5, L_Ankle=6)
    # R_Elbow: (R_Shoulder=14, R_Elbow=15, R_Wrist=16) -- using script's H36M_JOINT_NAMES
    # L_Elbow: (L_Shoulder=11, L_Elbow=12, L_Wrist=13) -- using script's H36M_JOINT_NAMES
    checks = [(1,2,3,"R_Knee"), (4,5,6,"L_Knee"), (14,15,16,"R_Elbow"), (11,12,13,"L_Elbow")]
    for A,B,C,name in checks:
        if C < kp.shape[0]: all_angles[f"{name} (Bend)"] = round(calculate_3d_angle(kp[A], kp[B], kp[C]), 1)
            
    # 2. Simple Vertical Angle (Torso)
    if 8 < kp.shape[0]: all_angles["Torso-Neck (Vertical)"] = round(calculate_vertical_angle(kp[7], kp[8]), 1)
        
    # 3. Complex 3D Euler Angles
    all_angles.update(calculate_anatomical_angles(kp))
    
    return all_angles
# ----------------------------------------------------------------------------------


# -------------------------------------------------
# 2. SAVING AND PLOTTING IMPLEMENTATION (INDEXED & COMPRESSED)
# -------------------------------------------------

def process_and_save_angles_indexed(all_frame_data, output_filepath, angle_keys):
    """
    Processes all frames, calculates all angles, and saves the results to a 
    new JSON file using only numerical indices for angles and no indentation.
    """
    if not all_frame_data:
        print("Error: No data loaded to process.")
        return None

    angle_history = []
    
    print(f"Processing {len(all_frame_data)} frames...")
    
    for frame_data in all_frame_data:
        frame_id = frame_data.get('frame_id', -1)
        
        preds = frame_data.get('predictions', [])
        
        # Initialize a list of 23 None values for the angles
        indexed_angles = [None] * len(angle_keys)

        if preds and preds[0] and 'keypoints' in preds[0] and preds[0]['keypoints'] is not None:
            kp = np.array(preds[0]['keypoints'])
            
            # Flip Y axis (consistent with processing in live mode)
            if kp.shape[1] >= 2:
                kp[:, 1] = -kp[:, 1]

            # Process angles
            current_angles_named = process_all_angles(kp, angle_keys)
            
            # Map the named angles to the numerical index list using ANGLE_KEYS order
            for i, key_name in enumerate(angle_keys):
                value = current_angles_named.get(key_name)
                indexed_angles[i] = value
                
        # Prepare data structure for saving: [frame_id, [angle_0, angle_1, ..., angle_22]]
        frame_output = [frame_id, indexed_angles]
        angle_history.append(frame_output)

    # --- FINAL JSON STRUCTURE ---
    final_output = {
        # Save the map from index to name once at the top
        "angle_map": {str(i): key for i, key in enumerate(angle_keys)},
        "frame_data": angle_history
    }
    
    # Save the processed data to the new JSON file
    try:
        # Use separators=(',', ':') to eliminate all unnecessary spaces for compression
        with open(output_filepath, 'w') as f:
            json.dump(final_output, f, separators=(',', ':'))
        print(f"✅ Successfully saved {len(angle_history)} frames of **indexed** angle data to: {output_filepath}")
        print("NOTE: The file is compressed (no extra spaces/indentation) for space efficiency.")
    except Exception as e:
        print(f"❌ Error saving data to file: {e}")
        
    return final_output

def get_plot_color(key):
    """Determines plot color based on key word matching."""
    if 'Knee' in key or 'Hip' in key:
        return '#2ecc71' # Green (Legs)
    elif 'Shoulder' in key or 'Elbow' in key:
        return '#3498db' # Blue (Arms)
    elif 'Neck' in key or 'Torso' in key or 'Waist' in key:
        return '#9b59b6' # Purple (Core)
    return '#333333' # Default

def plot_indexed_angles_dashboard(processed_data, source_filepath):
    """Plots the angle data from the processed indexed structure."""
    
    frame_data = processed_data['frame_data']
    
    if not frame_data:
        print("No angle data to plot.")
        return
        
    # 1. Reformat the indexed list data for plotting
    history = {key: [] for key in ANGLE_KEYS}
    frame_count = len(frame_data)
    num_angles = len(ANGLE_KEYS)
    
    for _, angle_list in frame_data:
        for i, key_name in enumerate(ANGLE_KEYS):
            # Use np.nan if the value is None (for missing data)
            value = angle_list[i] if i < len(angle_list) else None
            history[key_name].append(value if value is not None else np.nan)
            
    # 2. Setup the Static Figure
    FIGSIZE_H = 18 
    FIGSIZE_W = 22
    
    fig = plt.figure(figsize=(FIGSIZE_W, FIGSIZE_H))
    
    # 12 rows needed for 23 plots (12 * 2 = 24 slots)
    gs = fig.add_gridspec(12, 2, wspace=0.3, hspace=0.4) 
    plt.subplots_adjust(left=0.04, right=0.98, top=0.95, bottom=0.05) 

    # 3. Plotting Loop
    for i, key in enumerate(ANGLE_KEYS):
        if i >= num_angles: break 
        
        row, col = i // 2, i % 2 
        ax = fig.add_subplot(gs[row, col])
        
        plot_color = get_plot_color(key)
        y_data = np.array(history[key])
        x_data = np.arange(frame_count)

        ax.plot(x_data, y_data, lw=1.5, color=plot_color)
        
        # Set Title
        title_color = plot_color
        ax.set_title(key, fontsize=10, color=title_color)
        
        # Set Y limits
        if 'Bend' in key or 'Vertical' in key:
            ax.set_ylim([0, 180])
        else:
            ax.set_ylim([-180, 180])
            
        ax.tick_params(axis='y', labelsize=8)
        
        # Label X-axis only for the bottom plots
        if row == 11:
            ax.set_xlabel("Frame ID", fontsize=9)
        else:
            ax.set_xticks([])
            
        # Add a light horizontal line at 0 for rotation plots
        if not ('Bend' in key or 'Vertical' in key):
            ax.axhline(0, color='gray', linestyle='--', linewidth=0.5, alpha=0.5)

    # Add super title
    fig.suptitle(f"Static Kinematic Analysis Dashboard\nSource: {source_filepath} ({frame_count} Frames)", fontsize=14, fontweight='bold')
    
    # Show the plot
    plt.show()

# -------------------------------------------------
# 3. MAIN EXECUTION
# -------------------------------------------------

def main_static():
    """
    Main function to load the raw JSON, process it to get all 23 angles, 
    save the angles to a compressed, indexed JSON file, and then plot the results.
    """
    
    # === EDIT THIS PATH TO YOUR SAVED KEYPOINT JSON FILE ===
    JSON_FILE_TO_LOAD = "/home/popoy/projects/proj_1/videos/Jsons/webcam_3d_pose_recording2.json"
    # =======================================================
    
    # === NEW PATH TO SAVE THE PROCESSED, INDEXED ANGLE DATA ===
    OUTPUT_ANGLE_INDEXED_JSON = "/home/popoy/projects/proj_1/processed_angles_indexed.json"
    # ===============================================

    print(f"Attempting to load data from: {JSON_FILE_TO_LOAD}")

    try:
        with open(JSON_FILE_TO_LOAD, 'r') as f:
            all_frame_data = json.load(f)

        if not isinstance(all_frame_data, list) or not all_frame_data:
            raise ValueError("Loaded data is empty or malformed.")

        print(f"Successfully loaded {len(all_frame_data)} frames.")
        
        # 1. Process and Save the Angles (using the new indexed/compressed function)
        processed_data = process_and_save_angles_indexed(all_frame_data, OUTPUT_ANGLE_INDEXED_JSON, ANGLE_KEYS)
        
        # 2. Plot the Results (using the modified plotting function)
        if processed_data:
            plot_indexed_angles_dashboard(processed_data, OUTPUT_ANGLE_INDEXED_JSON)

    except FileNotFoundError:
        print(f"ERROR: File not found at {JSON_FILE_TO_LOAD}")
        print("Please check the JSON_FILE_TO_LOAD path in the script.")
    except json.JSONDecodeError:
        print("ERROR: Invalid JSON format. Data corruption possible.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        
if __name__ == "__main__":
    main_static()