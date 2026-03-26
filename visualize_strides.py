# visualize_strides.py
import cv2
import pandas as pd
import numpy as np
import os
import logging
from collections import defaultdict, deque

import config
from utils import build_skeleton_indices, draw_skeleton

# --- Basic Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def _configured_keypoint_order():
    configured = list(getattr(config, 'KEYPOINT_ORDER', []))
    if configured:
        return configured
    return list(getattr(config, 'KEYPOINT_INDEX_MAP', {}).keys())

def create_stride_visualization(data_df, strides_df):
    """
    Generates a single dashboard-style video visualizing all strides with fading paw trajectories.
    """
    video_path = config.INPUT_VIDEO_PATH
    if not os.path.exists(video_path):
        logger.error(f"Input video not found at: {video_path}")
        return

    # --- Setup Video I/O ---
    cap = cv2.VideoCapture(video_path)
    original_fps = int(cap.get(cv2.CAP_PROP_FPS))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    max_frame = int(data_df['frame'].max())

    output_path = os.path.join(config.RESULTS_DIR, 'stride_visualization.mp4')
    out = cv2.VideoWriter(output_path, cv2.VideoWriter_fourcc(*'mp4v'), original_fps, (width, height))
    logger.info(f"Generating stride visualization video, saving to: {output_path}")

    # --- Prepare data for efficient lookup ---
    configured_keypoints = _configured_keypoint_order()
    available_keypoints = [
        name for name in configured_keypoints
        if f'{name}_x' in data_df.columns and f'{name}_y' in data_df.columns
    ]
    available_keypoint_set = set(available_keypoints)
    available_connections = [
        connection for connection in config.SKELETON_CONNECTIONS
        if connection[0] in available_keypoint_set and connection[1] in available_keypoint_set
    ]
    skeleton_indices = build_skeleton_indices(available_keypoints, available_connections)
    frame_data_map = {frame: group for frame, group in data_df.groupby('frame')}

    # Create a map to quickly find the active stride for any frame
    stride_map = pd.Series(index=range(max_frame + 1), dtype='Int64')
    for idx, stride in strides_df.iterrows():
        stride_map.loc[stride['stride_start_frame']:stride['stride_end_frame']] = idx

    # --- Data structure for storing recent paw positions ---
    # Stores the last 15 frames of coordinates for each paw to create a fading trail
    paw_trajectories = defaultdict(lambda: deque(maxlen=15))

    # --- Main Rendering Loop ---
    # We read sequentially from frame 0 to the end, just like the main dashboard video.
    # This is the most robust method and avoids any frame-seeking errors.
    for frame_idx in range(max_frame + 1):
        success, frame = cap.read()
        if not success:
            logger.warning(f"Could not read frame {frame_idx}. Ending video.")
            break

        # Get data for the current animal
        animal_data_df = frame_data_map.get(frame_idx)
        
        if animal_data_df is not None and not animal_data_df.empty:
            animal_data = animal_data_df.iloc[0]

            # 1. Update and draw paw trajectories
            for paw_name in config.GAIT_PAWS:
                paw_x, paw_y = animal_data.get(f'{paw_name}_x'), animal_data.get(f'{paw_name}_y')
                if pd.notna(paw_x) and pd.notna(paw_y):
                    # Add current position to the trail
                    paw_trajectories[paw_name].append((int(paw_x), int(paw_y)))
                
                # Draw the fading trail for the current paw
                points = list(paw_trajectories[paw_name])
                for i in range(1, len(points)):
                    # As 'i' gets larger, the trail segment is older. We make it dimmer.
                    fade_intensity = (i / len(points)) * 0.8 + 0.2  # Ranges from 0.2 to 1.0
                    color = np.array(config.PAW_PLOT_COLORS[paw_name]) * fade_intensity
                    cv2.line(frame, points[i-1], points[i], color, 2)

            # 2. Draw the current skeleton
            if available_keypoints:
                keypoints = np.array([[animal_data.get(f'{name}_x'), animal_data.get(f'{name}_y')] for name in available_keypoints])
                draw_skeleton(frame, keypoints, skeleton_indices, config.KEYPOINT_COLOR, config.SKELETON_COLOR, config.KEYPOINT_RADIUS)

        # 3. Draw the on-screen text display
        active_stride_id = stride_map.get(frame_idx)
        stride_text = f"Stride: {active_stride_id}" if pd.notna(active_stride_id) else "Stride: None"
        cv2.putText(frame, f"Frame: {frame_idx}", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.putText(frame, stride_text, (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        out.write(frame)
        if frame_idx % 100 == 0:
            logger.info(f"Processed frame {frame_idx}/{max_frame}")

    # --- Cleanup ---
    cap.release()
    out.release()
    logger.info("Stride visualization complete.")

if __name__ == '__main__':
    try:
        main_data_path = os.path.join(config.RESULTS_DIR, 'final_analysis_data.csv')
        full_df = pd.read_csv(main_data_path)
        strides_data_path = os.path.join(config.RESULTS_DIR, 'custom_filtered_strides.csv')
        strides_df = pd.read_csv(strides_data_path)
    except FileNotFoundError as e:
        logger.error(f"Could not find necessary data file: {e}")
        logger.error("Please run main.py first to generate the necessary data.")
        exit()
        
    if not strides_df.empty:
        create_stride_visualization(full_df, strides_df)
    else:
        logger.warning("Stride data file is empty. No visualization to generate.")
