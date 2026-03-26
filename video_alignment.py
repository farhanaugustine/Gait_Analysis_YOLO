import os

import pandas as pd


def read_video_metadata(video_path):
    import cv2

    metadata = {"fps": 0.0, "frame_count": 0, "width": 1280, "height": 720}
    if not video_path or not os.path.exists(video_path):
        return metadata

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return metadata

    metadata["fps"] = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    metadata["frame_count"] = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    metadata["width"] = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or metadata["width"])
    metadata["height"] = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or metadata["height"])
    cap.release()
    return metadata


def resolve_video_frame_alignment(frame_numbers, video_frame_count, video_path="source video"):
    frames = pd.Series(frame_numbers).dropna()
    if frames.empty:
        raise ValueError("No pose frames were available to align with the source video.")

    if int(video_frame_count or 0) <= 0:
        raise ValueError(
            f"Could not read a valid frame count from {video_path}. "
            "Use the exact video that produced the Ultralytics pose labels."
        )

    unique_frames = sorted({int(frame_number) for frame_number in frames})
    analysis_start_frame = unique_frames[0]
    analysis_end_frame = unique_frames[-1]
    analysis_frame_span = analysis_end_frame - analysis_start_frame + 1
    missing_label_frames = max(analysis_frame_span - len(unique_frames), 0)

    tolerance = max(3, int(round(int(video_frame_count) * 0.01)))
    if abs(analysis_frame_span - int(video_frame_count)) > tolerance:
        raise ValueError(
            "Video/label mismatch detected. "
            f"{video_path} contains {int(video_frame_count)} frames, but the Ultralytics labels span "
            f"analysis frames {analysis_start_frame} to {analysis_end_frame} "
            f"({analysis_frame_span} frames). "
            "Ultralytics TXT keypoints are denormalized and rendered against the exact source video used "
            "for prediction, so INPUT_VIDEO_PATH (or the loaded --config profile) must point to that same video."
        )

    return {
        "analysis_start_frame": analysis_start_frame,
        "analysis_end_frame": analysis_end_frame,
        "analysis_frame_span": analysis_frame_span,
        "video_frame_count": int(video_frame_count),
        "missing_label_frames": missing_label_frames,
    }


def analysis_frame_to_video_index(analysis_frame, alignment):
    return int(analysis_frame) - int(alignment["analysis_start_frame"])


def video_index_to_analysis_frame(video_index, alignment):
    return int(alignment["analysis_start_frame"]) + int(video_index)
