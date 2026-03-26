# utils.py
import cv2
import numpy as np
import json
import os
import logging

logger = logging.getLogger(__name__)

# --- ROI SELECTION ---
# Global variables for mouse callback
roi_points = []
frame_clone = None

def select_roi_on_frame(event, x, y, flags, param):
    """Mouse callback function to select ROI points on a frame."""
    global roi_points, frame_clone
    if event == cv2.EVENT_LBUTTONDOWN:
        roi_points.append((x, y))
        cv2.circle(frame_clone, (x, y), 5, (0, 255, 0), -1)
        if len(roi_points) > 1:
            cv2.line(frame_clone, roi_points[-2], roi_points[-1], (0, 255, 0), 2)
        cv2.imshow("Select ROI", frame_clone)

def get_rois(video_path, config_path):
    """
    Loads ROIs from a config file or prompts user to draw them interactively.
    """
    global roi_points, frame_clone
    
    # Load existing ROIs if the file exists
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                rois_data = json.load(f)
            # Convert loaded lists back to NumPy arrays
            for roi in rois_data:
                roi['coords'] = np.array(roi['coords'], dtype=np.int32)
            logger.info(f"Loaded {len(rois_data)} ROIs from {config_path}")
            return rois_data
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to load or parse ROIs from {config_path}: {e}. Please fix or delete the file.")
            raise
    
    # Manual ROI selection if no config file is found
    logger.info(f"ROI config not found at '{config_path}'. Starting interactive selection...")
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video for ROI selection: {video_path}")
    
    success, first_frame = cap.read()
    cap.release()
    if not success:
        raise ValueError(f"Cannot read first frame from {video_path}")
    
    all_rois = []
    while True:
        roi_name = input(f"Enter a name for ROI #{len(all_rois) + 1} (or press Enter to finish): ")
        if not roi_name:
            if not all_rois:
                logger.warning("No ROIs were defined.")
            break
        
        roi_points = []
        frame_clone = first_frame.copy()
        cv2.namedWindow("Select ROI")
        cv2.setMouseCallback("Select ROI", select_roi_on_frame)
        
        print(f"Drawing ROI '{roi_name}': Left-click to add points. Press 'c' to confirm, 'r' to reset.")
        while True:
            cv2.imshow("Select ROI", frame_clone)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('r'): # Reset points for the current ROI
                roi_points = []
                frame_clone = first_frame.copy()
            elif key == ord('c'): # Confirm current ROI
                if len(roi_points) < 3:
                    logger.warning(f"ROI '{roi_name}' needs at least 3 points to form a polygon.")
                else:
                    all_rois.append({'name': roi_name, 'coords': roi_points})
                    logger.info(f"ROI '{roi_name}' saved with {len(roi_points)} points.")
                    break
    
    cv2.destroyWindow("Select ROI")
    
    if all_rois:
        try:
            # Prepare for JSON serialization (no NumPy arrays allowed)
            serializable_rois = [{'name': r['name'], 'coords': r['coords']} for r in all_rois]
            with open(config_path, 'w') as f:
                json.dump(serializable_rois, f, indent=4)
            logger.info(f"Saved {len(all_rois)} ROIs to {config_path}")
        except IOError as e:
            logger.error(f"Failed to save ROIs to {config_path}: {e}")
            raise
        
        # Convert lists to NumPy arrays for use in the program
        for roi in all_rois:
            roi['coords'] = np.array(roi['coords'], dtype=np.int32)
            
    return all_rois


# --- DRAWING UTILITIES ---
def build_skeleton_indices(keypoint_order, connections):
    """
    Translates named keypoint connections into index-based list for drawing.
    """
    name_to_idx = {name: i for i, name in enumerate(keypoint_order)}
    indexed_connections = []
    for start_name, end_name in connections:
        if start_name in name_to_idx and end_name in name_to_idx:
            indexed_connections.append((name_to_idx[start_name], name_to_idx[end_name]))
        else:
            logger.warning(f"Invalid skeleton connection: ({start_name}, {end_name})")
    return indexed_connections

def draw_skeleton(frame, keypoints, connections_indices, kpt_color, sk_color, radius):
    """
    Draws keypoints and skeleton lines on a frame.
    Keypoints should be a NumPy array of shape (N, 2).
    """
    if keypoints is None or len(keypoints) == 0:
        return
    
    h, w = frame.shape[:2]
    # Draw keypoints
    for kpt in keypoints:
        if np.isnan(kpt).any():
            continue
        x, y = int(kpt[0]), int(kpt[1])
        if 0 <= x < w and 0 <= y < h:
            cv2.circle(frame, (x, y), radius, kpt_color, -1, lineType=cv2.LINE_AA)
    
    # Draw skeleton connections
    for i, j in connections_indices:
        if i >= len(keypoints) or j >= len(keypoints):
            continue
        p1, p2 = keypoints[i], keypoints[j]
        if np.isnan(p1).any() or np.isnan(p2).any():
            continue
            
        p1_int = (int(p1[0]), int(p1[1]))
        p2_int = (int(p2[0]), int(p2[1]))
        
        if (0 <= p1_int[0] < w and 0 <= p1_int[1] < h and 
            0 <= p2_int[0] < w and 0 <= p2_int[1] < h):
            cv2.line(frame, p1_int, p2_int, sk_color, 2, lineType=cv2.LINE_AA)