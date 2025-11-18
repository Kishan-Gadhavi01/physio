import numpy as np
import json
from mmpose.apis import MMPoseInferencer

# Path to your video file
video_path = '/home/popoy/robotics/output_from_bag_FIXED.mp4' 

# --- Stage 1: Run 2D Pose Estimation (without saving video) ---
inferencer_2d = MMPoseInferencer('human')
print("✅ Stage 1: Running 2D Pose Estimation on the video...")
# Removed vis_out_dir to prevent saving the 2D video
results_2d_generator = inferencer_2d(video_path, show=False) 
results_2d = [r for r in results_2d_generator]
print("...Finished 2D Pose Estimation.\n")


# --- Stage 2: Run 3D Pose Lifting (without saving video) ---
inferencer_3d = MMPoseInferencer(pose3d='motionbert_dstformer-ft-243frm_8xb32-120e_h36m')
print("✅ Stage 2: Running 3D Pose Lifting using the 2D results...")
# Removed vis_out_dir and set show=False to prevent saving/showing the 3D video
results_3d_generator = inferencer_3d(video_path, pose_results=results_2d, show=False) 


# --- Stage 3: Process and COLLECT the Results ---
print("\n✅ Stage 3: Processing and collecting combined results...")
all_frames_data = [] # Create a list to hold data for all frames

for frame_idx, result_3d in enumerate(results_3d_generator):
    result_2d = results_2d[frame_idx]
    
    # This print statement is useful to track progress
    print(f"--- Processing Frame {frame_idx} ---")

    predictions_2d = result_2d['predictions'][0]
    predictions_3d = result_3d['predictions'][0]

    # Create a dictionary to hold data for the current frame
    frame_data = {'frame_id': frame_idx, 'instances': []}

    if not predictions_2d or not predictions_3d:
        all_frames_data.append(frame_data)
        continue

    for instance_idx in range(len(predictions_3d)):
        
        keypoints_2d = np.array(predictions_2d[instance_idx]['keypoints'])
        keypoints_3d = np.array(predictions_3d[instance_idx]['keypoints'])
        
        # Create a dictionary for the current person (instance)
        instance_data = {
            'instance_id': instance_idx,
            'keypoints_2d': keypoints_2d.tolist(), 
            'keypoints_3d': keypoints_3d.tolist()
        }
        frame_data['instances'].append(instance_data)

    all_frames_data.append(frame_data)

# --- Stage 4: Save the Collected Data to JSON ---
output_filepath = 'keypoints_output.json'
print(f"\n✅ Stage 4: Saving all keypoint data to {output_filepath}...")
with open(output_filepath, 'w') as f:
    json.dump(all_frames_data, f, indent=4)

print("...Done!")