import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from mpl_toolkits.mplot3d import Axes3D
import os
import math
import warnings

# Suppress NumPy warnings that occur during angle calculation near zero/NaN
warnings.filterwarnings('ignore', category=RuntimeWarning)

# --- 1. KINEMATIC UTILITIES AND CONSTANTS ---
H36M_JOINT_NAMES = {
    0: 'Pelvis', 1: 'R_Hip', 2: 'R_Knee', 3: 'R_Ankle',
    4: 'L_Hip', 5: 'L_Knee', 6: 'L_Ankle', 7: 'Torso',
    8: 'Neck', 9: 'Head', 10: 'Headtop', 11: 'L_Shoulder',
    12: 'L_Elbow', 13: 'L_Wrist', 14: 'R_Shoulder', 15: 'R_Elbow',
    16: 'R_Wrist'
}
REQUIRED_JOINTS = 17

# H36M SKELETON SEGMENTS for Matplotlib drawing
SKELETON_SEGMENTS_DRAW = [
    (0, 7), (7, 8), (8, 9), (9, 10), # Core/Head Segment
    (8, 14), (14, 15), (15, 16), # Right Arm
    (8, 11), (11, 12), (12, 13), # Left Arm
    (0, 1), (1, 2), (2, 3), # Right Leg
    (0, 4), (4, 5), (5, 6) # Left Leg 
]

# Vicon (39 markers) to H36M (17 joints) Mapping
VICON_TO_H36M_MAP = {
    0: ('avg', 23, 24), 1: 33, 2: 34, 3: 36, 4: 27, 5: 28, 6: 30, 7: 5, 8: 4, 
    9: ('avg', 0, 1), 11: 9, 12: 11, 13: 13, 14: 16, 15: 18, 16: 20,
}
NUM_V_MARKERS = 39

# --- MOCKED/SIMPLIFIED KINEMATICS (Retained for execution compatibility) ---
def calculate_3d_angle(*args): return 90.0
def calculate_vertical_angle(*args): return 90.0
def compute_rotation_matrix(*args, **kwargs): return np.eye(3)
def rotation_matrix_to_euler_angles(*args): return 0.0, 0.0, 0.0
def calculate_anatomical_angles(kp): return {}
def process_all_angles(kp, angle_keys): return {} 
# ------------------------------------------------------------------------

def transform_uiprmd_to_h36m(vicon_data_39_points):
    """
    Transforms a single frame of 39 Vicon markers to 17 H36M-equivalent joints.
    FIXED: Anchors H36M index 10 (Headtop) to Head (index 9) position.
    """
    h36m_points = np.zeros((REQUIRED_JOINTS, 3), dtype=np.float32)
    
    # 1. Map all Vicon markers to their H36M counterparts
    for h36m_idx in range(REQUIRED_JOINTS):
        if h36m_idx in VICON_TO_H36M_MAP:
            vicon_mapping = VICON_TO_H36M_MAP[h36m_idx]
            
            if isinstance(vicon_mapping, int):
                h36m_points[h36m_idx] = vicon_data_39_points[vicon_mapping]
            
            elif isinstance(vicon_mapping, tuple) and vicon_mapping[0] == 'avg':
                idx1, idx2 = vicon_mapping[1], vicon_mapping[2]
                h36m_points[h36m_idx] = (vicon_data_39_points[idx1] + vicon_data_39_points[idx2]) / 2.0
                
    # 2. ANCHOR THE HEADTOP (Index 10) to the Head (Index 9)
    # This prevents the Headtop from floating to (0,0,0) due to lack of a direct Vicon marker.
    h36m_points[10] = h36m_points[9] 
    
    return h36m_points


def load_and_transform_single_episode(file_path):
    """Loads a Vicon positions file, applies delimiter fix, and transforms to H36M."""
    try:
        # Load Data with COMMA DELIMITER
        coords_session = np.loadtxt(file_path, delimiter=',')
        
        if coords_session.ndim == 1:
            coords_session = coords_session.reshape(1, -1)
        
        coords_reshaped = coords_session.reshape(-1, NUM_V_MARKERS, 3)
        
        h36m_frames = []
        for frame_data in coords_reshaped:
            h36m_kp = transform_uiprmd_to_h36m(frame_data)
            h36m_frames.append(h36m_kp)
            
        print(f"[Verification] Successfully transformed {len(h36m_frames)} frames to H36M format.")
        
        h36m_array = np.array(h36m_frames)
        return h36m_array

    except Exception as e:
        print(f"[ERROR] Loading/transforming file failed: {e}")
        return None

# --- 3. ANIMATION FUNCTION ---

def animate_3d_skeleton(h36m_data, title="Vicon to H36M Verification"):
    """Animates the 3D skeleton data using Matplotlib, including ALL 17 joint labels."""
    if h36m_data is None or h36m_data.size == 0:
        print("No data to animate.")
        return

    # Calculate fixed plot limits and center
    all_coords = h36m_data.reshape(-1, 3)
    coord_min = all_coords.min(axis=0)
    coord_max = all_coords.max(axis=0)
    max_range = max(coord_max - coord_min) / 2.0 * 1.1 
    center = (coord_min + coord_max) / 2.0
    mid_x, mid_y, mid_z = center
    
    # Setup Figure
    fig = plt.figure(figsize=(12, 12))
    ax = fig.add_subplot(111, projection='3d')
    ax.set_title(title)
    
    # Set fixed limits
    ax.set_xlim(mid_x - max_range, mid_x + max_range)
    ax.set_ylim(mid_y - max_range, mid_y + max_range)
    ax.set_zlim(mid_z - max_range, mid_z + max_range)
    
    ax.set_xlabel('X (Lateral)'); ax.set_ylabel('Y (Vicon Axis 2)'); ax.set_zlabel('Z (Vicon Axis 3)')
    
    # Initial scatter plot and line placeholders
    first_frame = h36m_data[0]
    scatter = ax.scatter(first_frame[:, 0], first_frame[:, 1], first_frame[:, 2], s=50, c='red')
    lines = []
    for s, e in SKELETON_SEGMENTS_DRAW:
        line, = ax.plot([0, 0], [0, 0], [0, 0], color='blue', linewidth=2)
        lines.append(line)

    # --- JOINT LABELING SETUP: LABEL ALL 17 JOINTS ---
    text_artists = []
    all_joint_indices = list(range(REQUIRED_JOINTS))
    
    for idx in all_joint_indices:
        x, y, z = first_frame[idx]
        label = H36M_JOINT_NAMES.get(idx, f'J{idx}')
        text = ax.text(x + max_range*0.02, y, z, label, fontsize=6, color='black') 
        text_artists.append(text)
    
    all_artists = [scatter] + lines + text_artists

    # Update function for the animation
    def update_animation(frame_idx):
        frame_data = h36m_data[frame_idx]
        
        # 1. Update Joint Positions
        scatter._offsets3d = (frame_data[:, 0], frame_data[:, 1], frame_data[:, 2])

        # 2. Update Connections
        for i, (start_idx, end_idx) in enumerate(SKELETON_SEGMENTS_DRAW):
            p1 = frame_data[start_idx]
            p2 = frame_data[end_idx]
            lines[i].set_data([p1[0], p2[0]], [p1[1], p2[1]])
            lines[i].set_3d_properties([p1[2], p2[2]])
            
        # 3. Update Joint Labels
        for i, idx in enumerate(all_joint_indices):
            x, y, z = frame_data[idx]
            text_artists[i].set_position((x + max_range*0.02, y))
            text_artists[i].set_3d_properties(z, zdir='z')
            
        ax.set_title(f"{title} | Frame: {frame_idx + 1} / {h36m_data.shape[0]}")

        return all_artists

    # Create and show the animation
    anim = FuncAnimation(fig, update_animation, frames=len(h36m_data), interval=33, blit=False)
    plt.show()

# --- EXECUTION BLOCK ---
if __name__ == '__main__':
    # Define the root path to your UI-PRMD directory and the target file
    UI_PRMD_ROOT = '/home/popoy/projects/proj_1/webapp/Physio/public/UI-PRMD/data/'
    TARGET_FILE_NAME = 'm01_s01_e01_positions.txt'
    SINGLE_FILE_PATH = os.path.join(UI_PRMD_ROOT, 'Segmented Movements/Vicon/Positions', TARGET_FILE_NAME)

    print(f"Attempting to load and transform: {SINGLE_FILE_PATH}")
    h36m_episode_data = load_and_transform_single_episode(SINGLE_FILE_PATH)

    if h36m_episode_data is not None:
        animate_3d_skeleton(h36m_episode_data, title=f"Verification: {TARGET_FILE_NAME}")
        print("Verification complete. Check the visualization for correct anatomical movement.")
            