import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Button
from mpl_toolkits.mplot3d import Axes3D
import kinematics # Import module for constants

class DashboardManager:
    """
    Manages the Matplotlib figure layout and drawing elements (plots, skeleton, image).
    """
    REQUIRED_JOINTS = 17
    
    def __init__(self, angle_keys, skeleton_segments):
        self.angle_keys = angle_keys
        self.skeleton_segments = skeleton_segments
        self.angle_history = {k: [] for k in angle_keys}
        self.HISTORY_LIMIT = 200 # Fixed History Limit
        
        # Color mapping for organized charts
        self.color_map = self._get_color_map()
        
        # Initialize figure structure
        self.fig, self.ax_webcam, self.ax_3d, self.AXES_DASHBOARD, self.ANGLE_LINES, self.text_artist = self._setup_figure()
        
        # FIX: Expose the reset frame attribute directly (Fixes the AttributeError in main.py)
        self.reset_frame = np.zeros((480, 640, 3), dtype=np.uint8) 
        self.im_artist = self._setup_webcam_placeholder()

        self.scatter_3d, self.skeleton_lines = self._setup_3d_placeholders()

        # Buttons are initialized here and exposed
        self.plt = plt
        self.Button = Button 
        # UPDATED: Initialize all four buttons and expose them
        self.btn_start, self.btn_stop, self.btn_replay, self.btn_video = self._setup_buttons()


    def _get_color_map(self):
        """Defines colors for angle plots based on joint name prefixes."""
        cmap = {}
        for key in self.angle_keys:
            if 'Knee' in key or 'Hip' in key:
                cmap[key] = '#2ecc71' # Green (Legs)
            elif 'Shoulder' in key or 'Elbow' in key:
                cmap[key] = '#3498db' # Blue (Arms)
            elif 'Neck' in key or 'Torso' in key or 'Waist' in key:
                cmap[key] = '#9b59b6' # Purple (Core)
            else:
                cmap[key] = '#333333' # Default
        return cmap

    def _setup_figure(self):
        """Initializes the main figure and subplots with custom aspect ratios."""
        fig = plt.figure(figsize=(22, 18))
        
        # 13 rows total: 12 rows for plots/views + 1 row for text box
        gs = fig.add_gridspec(
            13, 3, 
            wspace=0.3, hspace=0.4,
            width_ratios=[1, 1.5, 1.5]
        )
        
        # Adjust figure margins to reduce empty space
        plt.subplots_adjust(left=0.03, right=0.98, top=0.95, bottom=0.1)

        # Left column: webcam (top, Rows 0-5) and 3D skeleton (bottom, Rows 6-11)
        ax_webcam = fig.add_subplot(gs[0:6, 0])
        ax_webcam.set_title("Live Webcam Feed (Headless Mode)", fontsize=10)
        ax_webcam.axis('off')

        ax_3d = fig.add_subplot(gs[6:12, 0], projection='3d')
        ax_3d.set_title("3D Skeleton View", fontsize=10)
        ax_3d.view_init(elev=15., azim=70)

        # Right columns: angle plots 
        AXES_DASHBOARD = {}
        ANGLE_LINES = {}
        for i, key in enumerate(self.angle_keys):
            row, col_offset = i // 2, i % 2 
            ax = fig.add_subplot(gs[row, 1 + col_offset])
            AXES_DASHBOARD[key] = ax
            ax.set_title(key, fontsize=9, color=self.color_map[key])
            ax.set_xticks([])
            ax.grid(True, ls='--', alpha=0.5)
            
            line, = ax.plot([], [], lw=1.5, color=self.color_map[key])
            ANGLE_LINES[key] = line
            
            # Set Y limits based on angle type
            if 'Bend' in key or 'Vertical' in key:
                ax.set_ylim([0, 180])
            else:
                ax.set_ylim([-180, 180])
                
            ax.tick_params(axis='y', labelsize=8)

        # Small text box bottom-right (Placed in the final row index 12, column 2)
        ax_text = fig.add_subplot(gs[12, 2])
        ax_text.axis('off')
        text_artist = ax_text.text(0.01, 0.98, "Idle", transform=ax_text.transAxes,
                                   fontsize=9, va='top', 
                                   bbox=dict(facecolor='white', alpha=0.8, edgecolor='black'))

        return fig, ax_webcam, ax_3d, AXES_DASHBOARD, ANGLE_LINES, text_artist

    def _setup_webcam_placeholder(self):
        """Initializes the webcam image artist using the exposed reset_frame."""
        im_artist = self.ax_webcam.imshow(self.reset_frame)
        return im_artist

    def _setup_3d_placeholders(self):
        """Initializes 3D scatter plot and skeleton lines."""
        scatter_3d = self.ax_3d.scatter(np.zeros(self.REQUIRED_JOINTS), 
                                        np.zeros(self.REQUIRED_JOINTS), 
                                        np.zeros(self.REQUIRED_JOINTS), s=30)
        
        skeleton_lines = []
        for seg in self.skeleton_segments.values():
            for s, e in seg['links']:
                line_3d, = self.ax_3d.plot([0, 0], [0, 0], [0, 0], color=seg['color'], linewidth=3)
                skeleton_lines.append((line_3d, s, e))
        
        self.ax_3d.set_xlim([-1, 1])
        self.ax_3d.set_ylim([-1, 1])
        self.ax_3d.set_zlim([-1, 1])
        
        return scatter_3d, skeleton_lines

    def _setup_buttons(self):
        """Initializes the Start/Stop, Replay, and Video buttons."""
        
        # Coordinate positions for 4 buttons (start at ~0.15, end at ~0.85)
        # B1: Start/Pause, B2: Stop/Reset, B3: Process Video, B4: Load/Replay JSON
        
        ax_start = plt.axes([0.15, 0.01, 0.14, 0.05])
        ax_stop = plt.axes([0.31, 0.01, 0.14, 0.05])
        ax_video = plt.axes([0.47, 0.01, 0.18, 0.05])
        ax_replay = plt.axes([0.67, 0.01, 0.18, 0.05])
        
        btn_start = Button(ax_start, 'Start / Pause', hovercolor='lime')
        btn_stop = Button(ax_stop, 'Stop / Reset', hovercolor='red')
        btn_video = Button(ax_video, 'Process Video', hovercolor='#ffd700')
        btn_replay = Button(ax_replay, 'Load/Replay JSON', hovercolor='#add8e6')
        
        return btn_start, btn_stop, btn_replay, btn_video

    def reset_history(self):
        """Clears all angle history for a fresh recording/replay."""
        self.angle_history = {k: [] for k in self.angle_keys}

    def get_artists(self):
        """Returns all artists that need to be updated in the animation loop."""
        return [self.im_artist, self.scatter_3d, self.text_artist] + \
               list(self.ANGLE_LINES.values()) + \
               [ln for ln, _, _ in self.skeleton_lines]

    def update_dashboard(self, result, vis_frame, angle_keys):
        """
        Processes keypoints from result, updates 3D skeleton, angle plots, 
        and the webcam image.
        """
        
        # 1. Update Webcam Display
        self.im_artist.set_data(vis_frame)

        # 2. Extract Keypoints and Update 3D/Angles
        kp = None
        # Result structure is {'predictions': [[{keypoints: [..]}]]}
        preds = result.get('predictions', [])
        
        # Safely extract keypoints from the first detected person
        if preds and preds[0] and 'keypoints' in preds[0] and preds[0]['keypoints'] is not None:
            # Note: We assume keypoints are stored as lists/arrays in the JSON
            kp = np.array(preds[0]['keypoints'])
            
            # Flip Y axis (consistent with typical conventions)
            if kp.shape[1] >= 2:
                kp[:, 1] = -kp[:, 1]
        
        if kp is not None:
            # Calculate and plot angles
            angles = kinematics.process_all_angles(kp, angle_keys)
            
            # Update 3D plot
            self._update_3d_plot(kp)
            
        else:
            # If no keypoints, use a dummy array for visualization updates
            angles = {key: 0.0 for key in angle_keys}
            kp = np.zeros((self.REQUIRED_JOINTS, 3), dtype=np.float32)
            self._update_3d_plot(kp) # clear 3D view
            

        # 3. Update Angle Lines and Titles
        for key in angle_keys:
            val = angles.get(key, 0.0)
            self.angle_history[key].append(val)
            if len(self.angle_history[key]) > self.HISTORY_LIMIT:
                self.angle_history[key].pop(0)
                
            x = np.arange(len(self.angle_history[key]))
            self.ANGLE_LINES[key].set_data(x, self.angle_history[key])
            
            # Dynamically set X limits to scroll the plot
            self.AXES_DASHBOARD[key].set_xlim(max(0, len(x) - self.HISTORY_LIMIT), len(x))
            
            # Update title with current angle value
            self.AXES_DASHBOARD[key].set_title(f"{key}: {val}°", 
                                              fontsize=9, color=self.color_map[key])


    def _update_3d_plot(self, kp):
        """Updates the scatter plot and skeleton lines."""
        pts_count = min(self.REQUIRED_JOINTS, kp.shape[0])
        xs = kp[:pts_count, 0]
        ys = kp[:pts_count, 1]
        zs = kp[:pts_count, 2] if kp.shape[1] > 2 else np.zeros(pts_count)
        
        # Pad with zeros if fewer than 17 joints are detected
        if pts_count < self.REQUIRED_JOINTS:
            pad = self.REQUIRED_JOINTS - pts_count
            xs = np.concatenate([xs, np.zeros(pad)])
            ys = np.concatenate([ys, np.zeros(pad)])
            zs = np.concatenate([zs, np.zeros(pad)])
            
        # Update scatter plot
        self.scatter_3d._offsets3d = (xs, ys, zs)
        
        # Recenter and rescale axes based on pelvis position (index 0)
        if kp.shape[0] > 0 and (kp[0] != 0).any(): # Check if keypoints are non-zero
            center = kp[0]
            center_z = center[2] if center.shape[0] > 2 else 0
            
            # Adjust range based on a standard human size (2 units wide)
            self.ax_3d.set_xlim([center[0] - 1, center[0] + 1])
            self.ax_3d.set_ylim([center[1] - 1, center[1] + 1])
            self.ax_3d.set_zlim([center_z - 1, center_z + 1])

        # Update skeleton lines
        for line_obj, s, e in self.skeleton_lines:
            if s < kp.shape[0] and e < kp.shape[0] and kp.shape[0] >= self.REQUIRED_JOINTS:
                p1 = kp[s]
                p2 = kp[e]
                line_obj.set_data_3d([p1[0], p2[0]], [p1[1], p2[1]], [p1[2] if p1.shape[0] > 2 else 0, p2[2] if p2.shape[0] > 2 else 0])
            else:
                 line_obj.set_data_3d([0, 0], [0, 0], [0, 0]) # Hide lines if data is invalid/missing

    def cleanup(self, frame_gen):
        """Performs final cleanup on stop/quit."""
        if frame_gen:
            frame_gen.release()
        self.plt.close(self.fig)
