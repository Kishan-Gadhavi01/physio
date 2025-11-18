import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

# Pose data string from the user
data_string = "3.296570,84.285820,-241.265750,-0.000010,29.699500,-0.000020,0.000000,21.697960,0.000000,0.000000,0.698960,0.000020,0.000000,6.355510,-0.000020,0.000000,14.446170,0.000020,1.629570,-0.300230,-0.129050,14.958850,0.000020,0.000020,21.190070,0.000010,0.000000,23.478280,-0.000020,-0.000040,-1.592280,-0.323540,-0.129030,-14.679210,-0.000010,0.000020,-22.545760,-0.000010,-0.000020,-23.715260,0.000010,0.000000,7.300280,-0.155230,3.317370,0.000000,-40.307770,0.000000,0.000000,-33.547820,-0.000020,0.000000,0.000000,11.502540,-7.083740,-0.169650,3.317350,0.000000,-38.469010,0.000000,0.000000,-35.988310,0.000000,0.000000,-0.000010,11.503740 "

# Parse the data: convert to float array, ignoring any extra elements if present
coords_list = [float(x) for x in data_string.split(',') if x.strip()]

num_joints = 17
expected_length = num_joints * 3

if len(coords_list) > expected_length:
    coords_flat = np.array(coords_list[:expected_length])
    print(f"Warning: Input data contained {len(coords_list)} values. Taking only the first {expected_length} for 17 joints.")
elif len(coords_list) < expected_length:
    raise ValueError(f"Error: Input data contained only {len(coords_list)} values, but {expected_length} were expected for 17 joints.")
else:
    coords_flat = np.array(coords_list)

# Reshape into a (17 joints, 3 coordinates) array
coords_3d = coords_flat.reshape(num_joints, 3)

# Create the 3D plot
fig = plt.figure(figsize=(10, 8))
ax = fig.add_subplot(111, projection='3d')

# Plot only the joints (3D points)
ax.scatter(coords_3d[:, 0], coords_3d[:, 1], coords_3d[:, 2], c='blue', marker='o', s=50, label='Joints')

# Set labels and title
ax.set_title('3D Human Pose - Joint Points Only', fontsize=14)
ax.set_xlabel('X (mm)', fontsize=12)
ax.set_ylabel('Y (mm)', fontsize=12)
ax.set_zlabel('Z (mm)', fontsize=12)

# Set equal aspect ratio to prevent distortion
max_range = np.array([coords_3d[:, 0].max()-coords_3d[:, 0].min(),
                      coords_3d[:, 1].max()-coords_3d[:, 1].min(),
                      coords_3d[:, 2].max()-coords_3d[:, 2].min()]).max() / 2.0

mid_x = (coords_3d[:, 0].max() + coords_3d[:, 0].min()) * 0.5
mid_y = (coords_3d[:, 1].max() + coords_3d[:, 1].min()) * 0.5
mid_z = (coords_3d[:, 2].max() + coords_3d[:, 2].min()) * 0.5

ax.set_xlim(mid_x - max_range, mid_x + max_range)
ax.set_ylim(mid_y - max_range, mid_y + max_range)
ax.set_zlim(mid_z - max_range, mid_z + max_range)

# Customize the view angle for better presentation
ax.view_init(elev=15, azim=-110)

# Add a grid and make background transparent for a cleaner look
ax.xaxis.pane.fill = False
ax.yaxis.pane.fill = False
ax.zaxis.pane.fill = False
ax.grid(True)

# Save the plot
plt.show()
print("human_pose_3d_points_only_plot.png")