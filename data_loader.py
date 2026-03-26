import logging
import re
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)
_MISSING_OPTIONAL_KEYPOINT_WARNINGS = set()

CALC_CENTER_ALIAS = "_calc_center"
CALC_BODY_ANGLE_START_ALIAS = "_calc_body_angle_start"
CALC_BODY_ANGLE_END_ALIAS = "_calc_body_angle_end"
CALC_ELONGATION_START_ALIAS = "_calc_elongation_start"
CALC_ELONGATION_END_ALIAS = "_calc_elongation_end"


def load_pose_data(config):
    """
    Loads per-frame Ultralytics pose label TXT files into the canonical dataframe
    expected by the analysis pipeline.
    """
    labels_dir = Path(getattr(config, "INPUT_LABELS_DIR", ""))
    if not labels_dir.exists():
        raise FileNotFoundError(f"Ultralytics label directory not found: {labels_dir}")

    keypoint_index_map = getattr(config, "KEYPOINT_INDEX_MAP", {})
    if not keypoint_index_map:
        raise ValueError("KEYPOINT_INDEX_MAP is empty. Map output names to keypoint indices in config.py.")

    normalized_assignment = {
        str(name): int(index) - int(getattr(config, "YOLO_KEYPOINT_INDEX_BASE", 0))
        for name, index in keypoint_index_map.items()
    }
    if min(normalized_assignment.values()) < 0:
        raise ValueError("KEYPOINT_INDEX_MAP contains indices below YOLO_KEYPOINT_INDEX_BASE.")
    calculation_assignment = _build_calculation_assignment(config)
    parse_assignment = dict(normalized_assignment)
    parse_assignment.update(calculation_assignment)
    required_keypoint_names = _required_keypoint_names(config)
    required_assignment = {
        keypoint_name: keypoint_index
        for keypoint_name, keypoint_index in parse_assignment.items()
        if keypoint_name in required_keypoint_names
    }
    if not required_assignment:
        raise ValueError("No required gait paw keypoints were found in KEYPOINT_INDEX_MAP.")

    frame_width, frame_height = _get_frame_dimensions(config)
    label_paths = sorted(labels_dir.glob("*.txt"), key=_label_sort_key)
    if not label_paths:
        raise FileNotFoundError(f"No .txt pose label files were found in {labels_dir}")

    logger.info("Loading Ultralytics pose labels from: %s", labels_dir)
    records = []

    for fallback_frame, label_path in enumerate(label_paths):
        frame_number = _infer_frame_number(label_path.stem, fallback_frame, config)
        detections = _parse_ultralytics_label_file(
            label_path,
            parse_assignment,
            required_assignment,
            frame_width,
            frame_height,
            config,
        )
        if not detections:
            continue

        selected_detection = _select_detection_for_frame(detections, config)
        record = {
            "frame": frame_number,
            "track_id": int(selected_detection["track_id"]),
            "class_id": selected_detection["class_id"],
            "bbox_conf": selected_detection["bbox_conf"],
        }

        for keypoint_name, keypoint_data in selected_detection["keypoints"].items():
            record[f"{keypoint_name}_x"] = keypoint_data["x"]
            record[f"{keypoint_name}_y"] = keypoint_data["y"]
            record[f"{keypoint_name}_conf"] = keypoint_data["conf"]

        records.append(record)

    if not records:
        logger.warning("No usable Ultralytics detections were found in %s", labels_dir)
        return pd.DataFrame()

    pose_df = pd.DataFrame(records).sort_values(["track_id", "frame"]).reset_index(drop=True)
    logger.info("Successfully loaded %s pose rows from Ultralytics TXT labels.", len(pose_df))
    return _finalize_pose_dataframe(pose_df, config)


def _parse_ultralytics_label_file(label_path, keypoint_assignment, required_assignment, frame_width, frame_height, config):
    detections = []
    target_class = getattr(config, "YOLO_TARGET_CLASS_ID", None)
    detection_conf_threshold = float(getattr(config, "YOLO_DETECTION_CONF_THRESHOLD", 0.0))

    with open(label_path, "r", encoding="utf-8") as label_file:
        for line_idx, raw_line in enumerate(label_file):
            line = raw_line.strip()
            if not line:
                continue
            parsed = _parse_ultralytics_pose_line(
                line,
                keypoint_assignment,
                required_assignment,
                frame_width,
                frame_height,
                config,
            )
            if parsed is None:
                logger.warning("Skipping malformed pose line %s in %s", line_idx + 1, label_path.name)
                continue
            if target_class is not None and parsed["class_id"] != int(target_class):
                continue
            if parsed["bbox_conf"] is not None and parsed["bbox_conf"] < detection_conf_threshold:
                continue
            detections.append(parsed)

    return detections


def _parse_ultralytics_pose_line(line, keypoint_assignment, required_assignment, frame_width, frame_height, config):
    try:
        values = [float(token) for token in line.split()]
    except ValueError:
        return None

    if len(values) < 5:
        return None

    class_id = int(round(values[0]))
    pose_values = values[5:]
    required_max_index = max(required_assignment.values())
    keypoint_dims, extra_count = _infer_keypoint_layout(pose_values, required_max_index, config)
    if keypoint_dims is None:
        return None

    keypoint_values = pose_values[: len(pose_values) - extra_count] if extra_count else pose_values
    extra_values = pose_values[len(keypoint_values):]
    keypoint_array = np.array(keypoint_values, dtype=float).reshape(-1, keypoint_dims)
    bbox_conf, track_id = _parse_pose_extras(extra_values, config)

    keypoints = {}
    optional_keypoint_warnings = []
    for keypoint_name, keypoint_index in keypoint_assignment.items():
        if keypoint_index >= len(keypoint_array):
            if keypoint_name in required_assignment:
                return None
            optional_keypoint_warnings.append((keypoint_name, keypoint_index, len(keypoint_array)))
            continue
        kp_values = keypoint_array[keypoint_index]
        x_value = float(kp_values[0]) * frame_width
        y_value = float(kp_values[1]) * frame_height
        conf_value = float(kp_values[2]) if keypoint_dims == 3 else 1.0
        keypoints[keypoint_name] = {"x": x_value, "y": y_value, "conf": conf_value}

    for keypoint_name, keypoint_index, detected_count in optional_keypoint_warnings:
        warning_key = (keypoint_name, keypoint_index, detected_count)
        if warning_key in _MISSING_OPTIONAL_KEYPOINT_WARNINGS:
            continue
        _MISSING_OPTIONAL_KEYPOINT_WARNINGS.add(warning_key)
        logger.warning(
            "Skipping optional keypoint '%s' at index %s because the YOLO labels only contain %s keypoints.",
            keypoint_name,
            keypoint_index,
            detected_count,
        )

    mean_keypoint_conf = float(np.mean([kp["conf"] for kp in keypoints.values()])) if keypoints else 0.0
    if bbox_conf is None:
        bbox_conf = mean_keypoint_conf

    return {
        "class_id": class_id,
        "bbox_conf": bbox_conf,
        "track_id": 0 if track_id is None else int(track_id),
        "keypoints": keypoints,
        "mean_keypoint_conf": mean_keypoint_conf,
    }


def _infer_keypoint_layout(pose_values, max_index, config):
    dims_setting = getattr(config, "YOLO_KEYPOINT_DIMENSIONS", "auto")
    dims_candidates = [int(dims_setting)] if str(dims_setting).isdigit() else [3, 2]

    include_conf = getattr(config, "YOLO_INCLUDE_DETECTION_CONF", "auto")
    include_track = getattr(config, "YOLO_INCLUDE_TRACK_ID", "auto")
    if include_conf == "auto" or include_track == "auto":
        extra_candidates = [0, 1, 2]
    else:
        extra_candidates = [int(bool(include_conf)) + int(bool(include_track))]

    for keypoint_dims in dims_candidates:
        for extra_count in extra_candidates:
            if len(pose_values) < extra_count:
                continue
            keypoint_value_count = len(pose_values) - extra_count
            if keypoint_value_count <= 0 or keypoint_value_count % keypoint_dims != 0:
                continue
            keypoint_count = keypoint_value_count // keypoint_dims
            if keypoint_count > max_index:
                return keypoint_dims, extra_count

    return None, None


def _required_keypoint_names(config):
    return {str(name) for name in getattr(config, "GAIT_PAWS", []) if str(name)}


def _parse_pose_extras(extra_values, config):
    bbox_conf = None
    track_id = None
    single_extra_mode = getattr(config, "YOLO_SINGLE_EXTRA_FIELD", "auto")

    if len(extra_values) == 2:
        bbox_conf = float(extra_values[0])
        track_id = int(round(extra_values[1]))
    elif len(extra_values) == 1:
        value = float(extra_values[0])
        if single_extra_mode == "conf":
            bbox_conf = value
        elif single_extra_mode == "track":
            track_id = int(round(value))
        elif 0.0 <= value <= 1.0:
            bbox_conf = value
        elif abs(value - round(value)) < 1e-6:
            track_id = int(round(value))
        else:
            bbox_conf = value

    return bbox_conf, track_id


def _select_detection_for_frame(detections, config):
    selection_mode = getattr(config, "YOLO_DETECTION_SELECTION", "highest_conf").lower()
    target_track = getattr(config, "YOLO_TARGET_TRACK_ID", None)

    if target_track is not None:
        track_matches = [detection for detection in detections if detection["track_id"] == int(target_track)]
        if track_matches:
            detections = track_matches

    if selection_mode == "first":
        return detections[0]

    if selection_mode == "highest_mean_keypoint_conf":
        return max(detections, key=lambda detection: detection["mean_keypoint_conf"])

    return max(
        detections,
        key=lambda detection: (
            -1.0 if detection["bbox_conf"] is None else detection["bbox_conf"],
            detection["mean_keypoint_conf"],
        ),
    )


def _get_frame_dimensions(config):
    override_size = _normalize_frame_size(getattr(config, "YOLO_FRAME_SIZE", None))
    if override_size is not None:
        return override_size

    cap = cv2.VideoCapture(config.INPUT_VIDEO_PATH)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()

    if width <= 0 or height <= 0:
        raise ValueError(
            "Could not infer frame dimensions from INPUT_VIDEO_PATH. "
            "Set YOLO_FRAME_SIZE = (width, height) in config.py."
        )
    return width, height


def _normalize_frame_size(frame_size):
    if frame_size is None:
        return None
    if isinstance(frame_size, str):
        tokens = [token.strip() for token in frame_size.split(",") if token.strip()]
        if len(tokens) != 2:
            raise ValueError("YOLO_FRAME_SIZE must look like 'width,height' or (width, height).")
        return int(tokens[0]), int(tokens[1])
    if isinstance(frame_size, (list, tuple)) and len(frame_size) == 2:
        return int(frame_size[0]), int(frame_size[1])
    raise ValueError("YOLO_FRAME_SIZE must be None, 'width,height', or a two-item tuple/list.")


def _label_sort_key(label_path):
    numbers = re.findall(r"\d+", label_path.stem)
    if numbers:
        return (0, int(numbers[-1]), label_path.stem)
    return (1, label_path.stem)


def _infer_frame_number(stem, fallback_frame, config):
    frame_offset = int(getattr(config, "YOLO_FRAME_NUMBER_OFFSET", 0))
    numbers = re.findall(r"\d+", stem)
    if numbers:
        return int(numbers[-1]) + frame_offset
    return int(fallback_frame) + frame_offset


def _finalize_pose_dataframe(df, config):
    if df.empty:
        return df

    conf_threshold = float(getattr(config, "KEYPOINT_CONF_THRESHOLD", 0.0))
    if conf_threshold > 0:
        conf_columns = [column for column in df.columns if column.endswith("_conf")]
        for conf_column in conf_columns:
            keypoint_name = conf_column[:-5]
            low_confidence = df[conf_column] < conf_threshold
            x_column = f"{keypoint_name}_x"
            y_column = f"{keypoint_name}_y"
            if x_column in df.columns:
                df.loc[low_confidence, x_column] = np.nan
            if y_column in df.columns:
                df.loc[low_confidence, y_column] = np.nan

    public_keypoint_names = [str(name) for name in getattr(config, "KEYPOINT_INDEX_MAP", {}).keys()]
    x_columns = [f"{name}_x" for name in public_keypoint_names if f"{name}_x" in df.columns]
    y_columns = [f"{name}_y" for name in public_keypoint_names if f"{name}_y" in df.columns]

    if x_columns:
        df["center_x"] = df[x_columns].mean(axis=1)
    if y_columns:
        df["center_y"] = df[y_columns].mean(axis=1)

    center_alias = _resolve_center_keypoint_alias(config)
    if center_alias:
        x_column = f"{center_alias}_x"
        y_column = f"{center_alias}_y"
        if x_column in df.columns and y_column in df.columns:
            if "center_x" in df.columns:
                df["center_x"] = df[x_column].fillna(df["center_x"])
                df["center_y"] = df[y_column].fillna(df["center_y"])
            else:
                df["center_x"] = df[x_column]
                df["center_y"] = df[y_column]

    logger.info("Successfully loaded and processed %s rows of pose data.", len(df))
    return df


def _build_calculation_assignment(config):
    base_index = int(getattr(config, "YOLO_KEYPOINT_INDEX_BASE", 0))
    assignment = {}

    center_index = _normalize_optional_index(getattr(config, "CENTER_KEYPOINT_INDEX", None))
    if center_index is not None:
        assignment[CALC_CENTER_ALIAS] = center_index - base_index

    angle_indices = _normalize_optional_pair(getattr(config, "BODY_ANGLE_KEYPOINT_INDICES", None))
    if angle_indices is not None:
        assignment[CALC_BODY_ANGLE_START_ALIAS] = angle_indices[0] - base_index
        assignment[CALC_BODY_ANGLE_END_ALIAS] = angle_indices[1] - base_index

    elongation_indices = _normalize_optional_pair(getattr(config, "ELONGATION_KEYPOINT_INDICES", None))
    if elongation_indices is not None:
        assignment[CALC_ELONGATION_START_ALIAS] = elongation_indices[0] - base_index
        assignment[CALC_ELONGATION_END_ALIAS] = elongation_indices[1] - base_index

    negative_assignments = {
        name: index
        for name, index in assignment.items()
        if index < 0
    }
    if negative_assignments:
        invalid_names = ", ".join(f"{name}={index}" for name, index in sorted(negative_assignments.items()))
        raise ValueError(f"Calculation keypoint indices are below YOLO_KEYPOINT_INDEX_BASE: {invalid_names}")

    return assignment


def _resolve_center_keypoint_alias(config):
    if _normalize_optional_index(getattr(config, "CENTER_KEYPOINT_INDEX", None)) is not None:
        return CALC_CENTER_ALIAS
    return getattr(config, "CENTER_KEYPOINT", None)


def _normalize_optional_index(value):
    if value in (None, ""):
        return None
    return int(value)


def _normalize_optional_pair(value):
    if value in (None, ""):
        return None
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return int(value[0]), int(value[1])
    raise ValueError("Expected a two-item index pair or None.")
