# main.py
import argparse
import cv2
import numpy as np
import pandas as pd
import os
import logging
from collections import defaultdict
from tqdm import tqdm

import config
from data_loader import load_pose_data
from analysis import (
    process_data,
    calculate_roi_event_timeline
)
from dashboard import Dashboard
from gait_reporting import run_gait_reporting
from kuramoto_analysis import run_kuramoto_analysis
from runtime_config import (
    apply_runtime_overrides,
    build_interactive_runtime_config,
    load_runtime_config,
    save_runtime_config,
)
from utils import get_rois, build_skeleton_indices, draw_skeleton
from video_alignment import read_video_metadata, resolve_video_frame_alignment, video_index_to_analysis_frame

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def _parse_args():
    parser = argparse.ArgumentParser(description="YOLO pose gait analysis pipeline.")
    parser.add_argument(
        "--config",
        dest="runtime_config_path",
        help=(
            "Path to a JSON runtime config profile. If the file does not exist, "
            "the script will prompt for required inputs and save it there."
        ),
    )
    return parser.parse_args()


def _configured_keypoint_order(config):
    configured = list(getattr(config, 'KEYPOINT_ORDER', []))
    if configured:
        return configured
    return list(getattr(config, 'KEYPOINT_INDEX_MAP', {}).keys())


def _select_primary_track(raw_df, config):
    if raw_df.empty or not getattr(config, 'USE_PRIMARY_TRACK_ONLY', True):
        return raw_df

    track_counts = raw_df.groupby('track_id').size().sort_values(ascending=False)
    if track_counts.empty:
        return raw_df

    primary_track_id = track_counts.index[0]
    selected_df = raw_df[raw_df['track_id'] == primary_track_id].copy()
    selected_df['track_id'] = 1
    logger.info(
        "Track consolidation complete. Using the most complete detected track (track_id=%s, %s rows).",
        primary_track_id,
        len(selected_df),
    )
    return selected_df


def _write_future_directions(config):
    future_path = getattr(config, "FUTURE_DIRECTIONS_PATH", "FUTURE_DIRECTIONS.md")
    future_text = """# Future Directions

## Deferred Features

- Save a custom reference template from a known-good recording and compare future animals against that saved template.
- Add condition-to-condition comparison views for baseline, treatment, recovery, or other cohorts. This can also be done post hoc from the exported CSV and JSON outputs, but a native report view would make it easier.
"""
    with open(future_path, "w", encoding="utf-8") as future_file:
        future_file.write(future_text)
    logger.info("Saved future directions note to %s", future_path)

def render_video(df, gait_df, config, rois, video_alignment):
    logger.info("Starting video rendering process...")
    try:
        cap = cv2.VideoCapture(config.INPUT_VIDEO_PATH)
        w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
        video_frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        cap.release()
    except Exception as e:
        logger.error(f"Failed to initialize video properties: {e}", exc_info=True)
        raise

    roi_event_timeline = calculate_roi_event_timeline(df)
    frame_data_map = {frame: group for frame, group in df.groupby('frame')}
    stride_end_map = {}
    if gait_df is not None and not gait_df.empty:
        for _, stride in gait_df.iterrows():
            stride_end_map[stride['end_frame']] = stride.to_dict()

    video_w, dash_w = config.RESIZED_VIDEO_WIDTH, config.DASHBOARD_WIDTH
    out_w, out_h = video_w + dash_w, h
    scale_x, scale_y = video_w / w, out_h / h

    cap = cv2.VideoCapture(config.INPUT_VIDEO_PATH)
    out = cv2.VideoWriter(config.OUTPUT_VIDEO_PATH, cv2.VideoWriter_fourcc(*'mp4v'), fps, (out_w, out_h))
    dashboard = Dashboard(config, video_height=out_h, fps=fps)
    configured_keypoints = _configured_keypoint_order(config)
    available_keypoints = [
        name for name in configured_keypoints
        if f'{name}_x' in df.columns and f'{name}_y' in df.columns
    ]
    available_keypoint_set = set(available_keypoints)
    available_connections = [
        connection for connection in config.SKELETON_CONNECTIONS
        if connection[0] in available_keypoint_set and connection[1] in available_keypoint_set
    ]
    skeleton_indices = build_skeleton_indices(available_keypoints, available_connections)
    roi_stats = defaultdict(lambda: {'time_s': 0, 'entries': 0})

    logger.info(
        "Starting frame-by-frame rendering with aligned analysis frames %s..%s over %s video frames.",
        video_alignment["analysis_start_frame"],
        video_alignment["analysis_end_frame"],
        video_frame_count,
    )
    frames_written = 0
    for video_frame_index in tqdm(range(video_frame_count), desc="Rendering Video"):
        success, frame = cap.read()
        if not success:
            logger.warning("Video decoding stopped at source frame %s before rendering completed.", video_frame_index)
            break
        frame_number = video_index_to_analysis_frame(video_frame_index, video_alignment)
        if frame_number in roi_event_timeline:
            for event in roi_event_timeline[frame_number]:
                if event['type'] == 'entry': roi_stats[event['roi_name']]['entries'] += 1

        animals_on_frame_df = frame_data_map.get(frame_number, pd.DataFrame())
        animals_on_frame = [] if animals_on_frame_df.empty else animals_on_frame_df.to_dict('records')

        for animal in animals_on_frame:
            roi_name = animal.get('current_roi')
            if roi_name and roi_name != 'None': roi_stats[roi_name]['time_s'] += 1 / fps

        speed_values = [a['speed'] for a in animals_on_frame if pd.notna(a.get('speed'))]
        posture_values = [a['posture_variability'] for a in animals_on_frame if pd.notna(a.get('posture_variability'))]
        
        stats_for_drawing = {
            'animals_on_frame': animals_on_frame,
            'speed_mean': np.mean(speed_values) if speed_values else 0,
            'posture_mean': np.mean(posture_values) if posture_values else 0,
            'newly_completed_stride': stride_end_map.get(frame_number),
            'roi_stats': roi_stats,
        }

        resized_frame = cv2.resize(frame, (video_w, out_h), interpolation=cv2.INTER_AREA)
        canvas = np.zeros((out_h, out_w, 3), dtype=np.uint8)
        canvas[0:out_h, 0:video_w] = resized_frame

        for roi in rois:
            scaled_coords = (roi['coords'] * [scale_x, scale_y]).astype(np.int32)
            cv2.polylines(canvas, [scaled_coords], True, (255, 0, 0), 2)

        for animal in animals_on_frame:
            if available_keypoints:
                keypoints = np.array([[animal.get(f'{name}_x'), animal.get(f'{name}_y')] for name in available_keypoints], dtype=np.float32)
                scaled_keypoints = keypoints * [scale_x, scale_y]
                draw_skeleton(canvas, scaled_keypoints, skeleton_indices, config.KEYPOINT_COLOR, config.SKELETON_COLOR, config.KEYPOINT_RADIUS)

        canvas = dashboard.update_and_draw(canvas, stats_for_drawing, frame_number)
        out.write(canvas)
        frames_written += 1
        
    cap.release()
    out.release()
    if frames_written == 0:
        logger.warning("No frames were written to %s.", config.OUTPUT_VIDEO_PATH)
    else:
        logger.info("Video rendering complete. Saved %s frames to %s", frames_written, config.OUTPUT_VIDEO_PATH)

def run():
    os.makedirs(config.RESULTS_DIR, exist_ok=True)
    logger.info("Using source video: %s", config.INPUT_VIDEO_PATH)
    logger.info("Using labels directory: %s", config.INPUT_LABELS_DIR)
    rois = get_rois(config.INPUT_VIDEO_PATH, config.ROI_CONFIG_PATH)
    raw_df = load_pose_data(config)
    if raw_df.empty:
        logger.error("Failed to load any pose data. Exiting.")
        return

    video_meta = read_video_metadata(getattr(config, "INPUT_VIDEO_PATH", ""))
    video_alignment = resolve_video_frame_alignment(raw_df["frame"], video_meta["frame_count"], config.INPUT_VIDEO_PATH)
    if video_alignment["missing_label_frames"] > 0:
        logger.warning(
            "Detected %s missing pose-label frames inside the analysis span. Rendering will preserve the video frames and leave those frames unlabeled.",
            video_alignment["missing_label_frames"],
        )
    logger.info(
        "Aligned analysis frames %s..%s to video frames 0..%s.",
        video_alignment["analysis_start_frame"],
        video_alignment["analysis_end_frame"],
        max(video_alignment["video_frame_count"] - 1, 0),
    )

    if getattr(config, 'USE_PRIMARY_TRACK_ONLY', True):
        logger.info("Selecting the primary track for single-animal analysis...")
        raw_df = _select_primary_track(raw_df, config)

    final_df, gait_df = process_data(raw_df, rois)
    kuramoto_outputs = run_kuramoto_analysis(final_df, config)
    final_df.to_csv(config.OUTPUT_CSV_PATH, index=False)
    logger.info(f"Saved final processed data to {config.OUTPUT_CSV_PATH}")

    if kuramoto_outputs:
        logger.info(f"Saved Kuramoto phase timeseries to {kuramoto_outputs['phase_timeseries_path']}")
        logger.info(f"Saved Kuramoto pairwise metrics to {kuramoto_outputs['pairwise_metrics_path']}")
        logger.info(f"Saved Kuramoto report data to {kuramoto_outputs['report_data_path']}")
        logger.info(f"Saved Kuramoto HTML report to {kuramoto_outputs['report_html_path']}")

    if gait_df is not None and not gait_df.empty:
        gait_df.to_csv(config.GAIT_ANALYSIS_PATH, index=False)
        logger.info(f"Saved gait analysis summary to {config.GAIT_ANALYSIS_PATH}")

        gait_review_outputs = run_gait_reporting(final_df, gait_df, kuramoto_outputs, config, video_alignment=video_alignment)
        if gait_review_outputs:
            logger.info(f"Saved stride details to {gait_review_outputs['stride_details_path']}")
            logger.info(f"Saved bout summary to {gait_review_outputs['bout_summary_path']}")
            logger.info(f"Saved gait review HTML report to {gait_review_outputs['report_html_path']}")

        logger.info("Using reliable gait data for stride video generation.")
        strides_for_videos = gait_df.rename(columns={'start_frame': 'stride_start_frame', 'end_frame': 'stride_end_frame'})
        stride_output_path = os.path.join(config.RESULTS_DIR, 'custom_filtered_strides.csv')
        columns_to_save = ['track_id', 'stride_start_frame', 'stride_end_frame']
        if all(c in strides_for_videos.columns for c in columns_to_save):
            strides_for_videos[columns_to_save].to_csv(stride_output_path, index=False)
            logger.info(f"Saved reliable stride data for video generation to {stride_output_path}")
    else:
        logger.warning("No gait data was generated. Stride video generation will be skipped.")

    _write_future_directions(config)
    render_video(final_df, gait_df, config, rois, video_alignment)
    logger.info("Analysis complete.")

if __name__ == "__main__":
    args = _parse_args()
    if args.runtime_config_path:
        if os.path.exists(args.runtime_config_path):
            runtime_overrides = load_runtime_config(args.runtime_config_path)
            apply_runtime_overrides(config, runtime_overrides)
            logger.info("Loaded runtime config profile from %s", args.runtime_config_path)
        else:
            runtime_overrides = build_interactive_runtime_config(config)
            runtime_overrides = save_runtime_config(args.runtime_config_path, runtime_overrides)
            apply_runtime_overrides(config, runtime_overrides)
            logger.info("Saved new runtime config profile to %s", args.runtime_config_path)

    run()
