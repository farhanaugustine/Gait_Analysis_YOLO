# stride_detector.py
import logging
import os

import numpy as np
import pandas as pd
from scipy.signal import find_peaks

import config

logger = logging.getLogger(__name__)


def _find_movement_tracks(track_df, speed_threshold=5):
    """
    Determines intervals where the animal is moving at sufficient speed.
    """
    track_df["in_track"] = track_df["body_speed"] >= speed_threshold
    track_intervals = []
    is_moving = False
    start_frame = None

    for _, row in track_df.iterrows():
        if row["in_track"] and not is_moving:
            start_frame = row["frame"]
            is_moving = True
        elif not row["in_track"] and is_moving:
            track_intervals.append((start_frame, row["frame"] - 1))
            is_moving = False

    if is_moving:
        track_intervals.append((start_frame, track_df["frame"].iloc[-1]))

    return track_intervals


def _detect_steps_for_paw(paw_df, paw_name, body_speed_series, peak_speed_threshold=15):
    """
    Identifies individual steps for a given paw using peak detection on paw speed.
    """
    paw_speed = paw_df[f"{paw_name}_speed"].values
    peaks, _ = find_peaks(paw_speed)
    troughs, _ = find_peaks(-paw_speed)

    valid_steps = []
    for peak_idx in peaks:
        animal_speed = body_speed_series.iloc[peak_idx]
        speed_filter = max(peak_speed_threshold, animal_speed if pd.notna(animal_speed) else 0)
        if paw_speed[peak_idx] < speed_filter:
            continue

        pre_troughs = troughs[troughs < peak_idx]
        post_troughs = troughs[troughs > peak_idx]
        if pre_troughs.size > 0 and post_troughs.size > 0:
            toe_off_idx = pre_troughs[-1]
            foot_strike_idx = post_troughs[0]
            valid_steps.append(
                {
                    "start_frame": paw_df["frame"].iloc[toe_off_idx],
                    "end_frame": paw_df["frame"].iloc[foot_strike_idx],
                    "peak_frame": paw_df["frame"].iloc[peak_idx],
                    "peak_speed": paw_speed[peak_idx],
                }
            )

    return sorted(valid_steps, key=lambda step: step["start_frame"])


def detect_and_filter_strides(df):
    """
    Main function to run the complete stride detection and filtering process.
    Takes a fully processed DataFrame as input.
    """
    logger.info("Starting stride detection and filtering process...")
    stride_paws = _select_stride_paws(config.GAIT_PAWS)
    if len(stride_paws) < 2:
        logger.warning("Need at least two gait paws to detect strides.")
        return pd.DataFrame()

    left_paw, right_paw = stride_paws[0], stride_paws[1]

    if "body_speed" not in df.columns:
        df["body_speed"] = np.sqrt(
            df.groupby("track_id")["center_x"].diff() ** 2 +
            df.groupby("track_id")["center_y"].diff() ** 2
        )

    for paw in [left_paw, right_paw]:
        if f"{paw}_speed" not in df.columns:
            df[f"{paw}_speed"] = np.sqrt(
                df.groupby("track_id")[f"{paw}_x"].diff() ** 2 +
                df.groupby("track_id")[f"{paw}_y"].diff() ** 2
            )

    all_valid_strides = []

    for track_id, animal_df in df.groupby("track_id"):
        logger.info("Processing animal track ID: %s", track_id)
        movement_tracks = _find_movement_tracks(animal_df.copy())
        unfiltered_strides_per_track = []

        for track_start, track_end in movement_tracks:
            track_df = animal_df[(animal_df["frame"] >= track_start) & (animal_df["frame"] <= track_end)]
            if track_df.empty:
                continue

            left_steps = _detect_steps_for_paw(track_df, left_paw, track_df["body_speed"])
            right_steps = _detect_steps_for_paw(track_df, right_paw, track_df["body_speed"])
            if not left_steps:
                continue

            potential_strides = []
            stride_start = left_steps[0]["start_frame"]
            for left_step in left_steps:
                stride_end = left_step["end_frame"]
                found_right_step = next(
                    (
                        right_step for right_step in right_steps
                        if stride_start <= right_step["end_frame"] <= stride_end
                    ),
                    None,
                )
                if found_right_step:
                    potential_strides.append(
                        {
                            "track_id": track_id,
                            "stride_start_frame": stride_start,
                            "stride_end_frame": stride_end,
                            "left_step_data": left_step,
                            "right_step_data": found_right_step,
                        }
                    )
                stride_start = stride_end + 1

            unfiltered_strides_per_track.append(potential_strides)

        for stride_list in unfiltered_strides_per_track:
            if len(stride_list) <= 2:
                continue

            strides_to_check = stride_list[1:-1]
            conf_keypoints = [paw for paw in config.GAIT_PAWS if f"{paw}_conf" in df.columns]
            conf_cols = [f"{kp}_conf" for kp in conf_keypoints]

            for stride in strides_to_check:
                stride_frames_df = df[
                    (df["frame"] >= stride["stride_start_frame"]) &
                    (df["frame"] <= stride["stride_end_frame"]) &
                    (df["track_id"] == stride["track_id"])
                ]
                if conf_cols:
                    min_confidence = stride_frames_df[conf_cols].min().min()
                    if min_confidence < 0.3:
                        continue
                all_valid_strides.append(stride)

    logger.info("Found %s high-quality strides after filtering.", len(all_valid_strides))
    return pd.DataFrame(all_valid_strides)


def _select_stride_paws(gait_paws):
    rear_like = [paw for paw in gait_paws if _paw_role(paw)[1] == "rear"]
    if len(rear_like) >= 2:
        return sorted(rear_like, key=lambda paw: 0 if _paw_role(paw)[0] == "left" else 1)
    front_like = [paw for paw in gait_paws if _paw_role(paw)[1] == "front"]
    if len(front_like) >= 2:
        return sorted(front_like, key=lambda paw: 0 if _paw_role(paw)[0] == "left" else 1)
    return list(gait_paws[:2])


def _paw_role(paw_name):
    paw_lower = paw_name.lower()
    side = "left" if "left" in paw_lower else "right" if "right" in paw_lower else "unknown"
    if any(token in paw_lower for token in ("front", "fore", "shoulder")):
        limb = "front"
    elif any(token in paw_lower for token in ("rear", "hind", "hip")):
        limb = "rear"
    else:
        limb = "unknown"
    return side, limb


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    logger.info("Running stride_detector.py as a standalone script for demonstration.")

    try:
        processed_df = pd.read_csv(os.path.join(config.RESULTS_DIR, "final_analysis_data.csv"))
    except FileNotFoundError:
        logger.error("Could not find 'final_analysis_data.csv'.")
        logger.error("Please run main.py first to generate the necessary data file.")
        raise SystemExit(1)

    filtered_strides_df = detect_and_filter_strides(processed_df)
    if not filtered_strides_df.empty:
        output_path = os.path.join(config.RESULTS_DIR, "custom_filtered_strides.csv")
        filtered_strides_df.to_csv(output_path, index=False)
        logger.info("Saved %s filtered strides to %s", len(filtered_strides_df), output_path)
