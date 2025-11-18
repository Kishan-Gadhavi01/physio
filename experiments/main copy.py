import argparse
import json
from mmpose.apis import MMPoseInferencer
import numpy as np
import sys

def process_video(video_path, output_path, device):
    """
    Processes a video file using MMPose to extract and save 2D keypoints.

    Args:
        video_path (str): Path to the input video file.
        output_path (str): Path to save the output JSON file.
        device (str): The device to run inference on (e.g., 'cuda:0' or 'cpu').
    """
    try:
        # Initialize the MMPose inferencer. We use 'human3d' as it reliably provides
        # the 'keypoints_2d' field needed for the next step in your pipeline.
        print(f"Initializing MMPose inferencer on device '{device}'...")
        inferencer = MMPoseInferencer(pose3d='human3d', device=device)
    except Exception as e:
        print(f"Error initializing MMPose: {e}")
        print("Please ensure MMPose is installed correctly and the device is available.")
        sys.exit(1)

    # The inferencer can process the video path directly
    print(f"Starting inference on video: {video_path}")
    result_generator = inferencer(video_path, return_vis=False)
    
    all_frames_data = []
    frame_id = 0
    
    for result in result_generator:
        # The result from the generator corresponds to one frame
        predictions_2d = []
        if 'predictions' in result and result['predictions']:
            for person_prediction_list in result['predictions']:
                if person_prediction_list:
                    # Get data for the first detected person in the list
                    p_dict = person_prediction_list[0]
                    
                    # --- CRITICAL STEP: Extract ONLY the 2D data ---
                    if 'keypoints_2d' in p_dict and 'keypoint_scores' in p_dict:
                        # Create a clean dictionary with just the 2D keypoints and their scores
                        person_data_2d = {
                            'keypoints_2d': p_dict['keypoints_2d'].tolist(),
                            'keypoint_scores': p_dict['keypoint_scores'].tolist()
                        }
                        predictions_2d.append(person_data_2d)
                    else:
                        print(f"Warning: 'keypoints_2d' not found in frame {frame_id}. Skipping person.")

        # Structure the data for the current frame
        frame_data = {
            'frame_id': frame_id,
            'predictions': predictions_2d # This will be a list of people found in the frame
        }
        all_frames_data.append(frame_data)
        
        # Print progress
        print(f"Processed frame {frame_id}...", end='\r')
        frame_id += 1

    # Save all collected data to the output JSON file
    if all_frames_data:
        print(f"\nInference complete. Processed {len(all_frames_data)} frames.")
        try:
            with open(output_path, 'w') as f:
                json.dump(all_frames_data, f, indent=4)
            print(f"✅ 2D keypoints successfully saved to: {output_path}")
        except Exception as e:
            print(f"\nError saving JSON file: {e}")
    else:
        print("\nNo predictions were generated from the video.")

if __name__ == "__main__":
    # --- Set up argument parser for command-line use ---
    parser = argparse.ArgumentParser(
        description="Process a video to extract 2D human pose keypoints using MMPose."
    )
    parser.add_argument(
        "input_video", 
        help="Path to the input video file (e.g., /path/to/your/video.mp4)"
    )
    parser.add_argument(
        "--output-json", 
        default="video_2d_keypoints.json",
        help="Path to save the output JSON file (default: video_2d_keypoints.json)"
    )
    parser.add_argument(
        "--device", 
        default="cuda:0",
        help="Device to use for inference (e.g., 'cuda:0' or 'cpu')"
    )
    
    args = parser.parse_args()
    
    process_video(args.input_video, args.output_json, args.device)
