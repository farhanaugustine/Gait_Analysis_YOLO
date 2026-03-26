import json
import os
from collections import OrderedDict

LEGACY_HELPER_NAMES = {"CenterPoint", "AngleStart", "AngleEnd", "ElongationStart", "ElongationEnd"}


def load_runtime_config(config_path):
    with open(config_path, "r", encoding="utf-8") as config_file:
        overrides = json.load(config_file)
    return _normalize_runtime_overrides(overrides)


def save_runtime_config(config_path, overrides):
    normalized = _normalize_runtime_overrides(overrides)
    directory = os.path.dirname(config_path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as config_file:
        json.dump(normalized, config_file, indent=2)
    return normalized


def apply_runtime_overrides(config_module, overrides):
    normalized = _normalize_runtime_overrides(overrides)
    for key, value in normalized.items():
        setattr(config_module, key, value)

    if not getattr(config_module, "KEYPOINT_ORDER", None):
        config_module.KEYPOINT_ORDER = list(getattr(config_module, "KEYPOINT_INDEX_MAP", {}).keys())

    if not getattr(config_module, "PAW_ORDER_HILDEBRAND", None):
        config_module.PAW_ORDER_HILDEBRAND = list(getattr(config_module, "GAIT_PAWS", []))

    return normalized


def build_interactive_runtime_config(config_module):
    print("Creating a YOLO pose analysis config profile.")
    print("Press Enter to accept the default shown in brackets.")
    print("")

    input_video_path = _prompt_text("Input video path", getattr(config_module, "INPUT_VIDEO_PATH", ""))
    input_labels_dir = _prompt_text("Input labels directory", getattr(config_module, "INPUT_LABELS_DIR", ""))
    frame_size_default = _format_frame_size(getattr(config_module, "YOLO_FRAME_SIZE", None))
    frame_size_text = _prompt_text("Frame size override width,height (blank for auto)", frame_size_default, allow_empty=True)
    yolo_frame_size = None if not frame_size_text else frame_size_text

    left_front_index = _prompt_int("Index for left front paw")
    right_front_index = _prompt_int("Index for right front paw")
    left_rear_index = _prompt_int("Index for left rear paw")
    right_rear_index = _prompt_int("Index for right rear paw")

    center_index = _prompt_optional_int("Index for center keypoint used in center calculation (blank to skip)")
    angle_start_index = _prompt_optional_int("Index for body-angle start keypoint used in calculations (blank to skip)")
    angle_end_index = None
    if angle_start_index is not None:
        angle_end_index = _prompt_int("Index for body-angle end keypoint used in calculations")

    elongation_start_index = _prompt_optional_int("Index for elongation start keypoint used in calculations (blank to skip)")
    elongation_end_index = None
    if elongation_start_index is not None:
        elongation_end_index = _prompt_int("Index for elongation end keypoint used in calculations")

    stride_reference_default = getattr(config_module, "STRIDE_REFERENCE_PAW", "LeftRearPaw")
    stride_reference_paw = _prompt_choice(
        "Stride reference paw",
        ["LeftFrontPaw", "RightFrontPaw", "LeftRearPaw", "RightRearPaw"],
        stride_reference_default,
    )

    keypoint_index_map = OrderedDict(
        [
            ("LeftFrontPaw", left_front_index),
            ("RightFrontPaw", right_front_index),
            ("LeftRearPaw", left_rear_index),
            ("RightRearPaw", right_rear_index),
        ]
    )

    return {
        "INPUT_VIDEO_PATH": input_video_path,
        "INPUT_LABELS_DIR": input_labels_dir,
        "YOLO_FRAME_SIZE": yolo_frame_size,
        "KEYPOINT_INDEX_MAP": dict(keypoint_index_map),
        "KEYPOINT_ORDER": list(keypoint_index_map.keys()),
        "CENTER_KEYPOINT_INDEX": center_index,
        "BODY_ANGLE_KEYPOINT_INDICES": [angle_start_index, angle_end_index] if angle_start_index is not None and angle_end_index is not None else None,
        "ELONGATION_KEYPOINT_INDICES": [elongation_start_index, elongation_end_index] if elongation_start_index is not None and elongation_end_index is not None else None,
        "CENTER_KEYPOINT": None,
        "BODY_ANGLE_CONNECTION": None,
        "ELONGATION_CONNECTION": None,
        "GAIT_PAWS": ["LeftFrontPaw", "RightFrontPaw", "LeftRearPaw", "RightRearPaw"],
        "PAW_ORDER_HILDEBRAND": ["LeftFrontPaw", "RightFrontPaw", "LeftRearPaw", "RightRearPaw"],
        "STRIDE_REFERENCE_PAW": stride_reference_paw,
        "KURAMOTO_IDEAL_PHASE_OFFSETS": {
            "LeftFrontPaw": 0.0,
            "RightFrontPaw": 3.141592653589793,
            "LeftRearPaw": 3.141592653589793,
            "RightRearPaw": 0.0,
        },
    }


def _normalize_runtime_overrides(overrides):
    normalized = dict(overrides)

    if "KEYPOINT_INDEX_MAP" in normalized and normalized["KEYPOINT_INDEX_MAP"] is not None:
        normalized["KEYPOINT_INDEX_MAP"] = {
            str(name): int(index)
            for name, index in normalized["KEYPOINT_INDEX_MAP"].items()
        }

    if "KEYPOINT_ORDER" in normalized and normalized["KEYPOINT_ORDER"] is not None:
        normalized["KEYPOINT_ORDER"] = [str(name) for name in normalized["KEYPOINT_ORDER"]]

    _migrate_legacy_helper_aliases(normalized)

    if "CENTER_KEYPOINT_INDEX" in normalized:
        normalized["CENTER_KEYPOINT_INDEX"] = _normalize_optional_int_value(normalized["CENTER_KEYPOINT_INDEX"])

    for key in ("BODY_ANGLE_KEYPOINT_INDICES", "ELONGATION_KEYPOINT_INDICES"):
        if key in normalized:
            normalized[key] = _normalize_optional_index_pair(normalized[key], key)

    for key in ("BODY_ANGLE_CONNECTION", "ELONGATION_CONNECTION"):
        if key in normalized and normalized[key] is not None:
            value = normalized[key]
            if len(value) != 2:
                raise ValueError(f"{key} must be a two-item list or null.")
            normalized[key] = [str(value[0]), str(value[1])]

    if "YOLO_FRAME_SIZE" in normalized:
        normalized["YOLO_FRAME_SIZE"] = _normalize_frame_size_value(normalized["YOLO_FRAME_SIZE"])

    if not normalized.get("KEYPOINT_ORDER"):
        normalized["KEYPOINT_ORDER"] = list(normalized.get("KEYPOINT_INDEX_MAP", {}).keys())

    return normalized


def _migrate_legacy_helper_aliases(normalized):
    keypoint_index_map = normalized.get("KEYPOINT_INDEX_MAP")
    if not keypoint_index_map:
        return

    center_index = keypoint_index_map.get("CenterPoint")
    if normalized.get("CENTER_KEYPOINT_INDEX") is None and center_index is not None:
        normalized["CENTER_KEYPOINT_INDEX"] = int(center_index)

    if normalized.get("BODY_ANGLE_KEYPOINT_INDICES") is None:
        angle_start = keypoint_index_map.get("AngleStart")
        angle_end = keypoint_index_map.get("AngleEnd")
        if angle_start is not None and angle_end is not None:
            normalized["BODY_ANGLE_KEYPOINT_INDICES"] = [int(angle_start), int(angle_end)]

    if normalized.get("ELONGATION_KEYPOINT_INDICES") is None:
        elongation_start = keypoint_index_map.get("ElongationStart")
        elongation_end = keypoint_index_map.get("ElongationEnd")
        if elongation_start is not None and elongation_end is not None:
            normalized["ELONGATION_KEYPOINT_INDICES"] = [int(elongation_start), int(elongation_end)]

    if any(name in keypoint_index_map for name in LEGACY_HELPER_NAMES):
        normalized["KEYPOINT_INDEX_MAP"] = {
            name: index
            for name, index in keypoint_index_map.items()
            if name not in LEGACY_HELPER_NAMES
        }

    if "KEYPOINT_ORDER" in normalized and normalized["KEYPOINT_ORDER"] is not None:
        normalized["KEYPOINT_ORDER"] = [
            name for name in normalized["KEYPOINT_ORDER"]
            if name not in LEGACY_HELPER_NAMES
        ]

    if normalized.get("CENTER_KEYPOINT") == "CenterPoint":
        normalized["CENTER_KEYPOINT"] = None
    if normalized.get("BODY_ANGLE_CONNECTION") == ["AngleStart", "AngleEnd"]:
        normalized["BODY_ANGLE_CONNECTION"] = None
    if normalized.get("ELONGATION_CONNECTION") == ["ElongationStart", "ElongationEnd"]:
        normalized["ELONGATION_CONNECTION"] = None


def _normalize_frame_size_value(value):
    if value in (None, ""):
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return [int(value[0]), int(value[1])]
    raise ValueError("YOLO_FRAME_SIZE must be null, 'width,height', or a two-item list/tuple.")


def _normalize_optional_int_value(value):
    if value in (None, ""):
        return None
    return int(value)


def _normalize_optional_index_pair(value, key_name):
    if value in (None, ""):
        return None
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return [int(value[0]), int(value[1])]
    raise ValueError(f"{key_name} must be null or a two-item list/tuple of integers.")


def _format_frame_size(frame_size):
    if frame_size in (None, ""):
        return ""
    if isinstance(frame_size, str):
        return frame_size
    if isinstance(frame_size, (list, tuple)) and len(frame_size) == 2:
        return f"{int(frame_size[0])},{int(frame_size[1])}"
    return ""


def _prompt_text(label, default="", allow_empty=False):
    suffix = f" [{default}]" if default else ""
    while True:
        response = input(f"{label}{suffix}: ").strip()
        if response:
            return response
        if default != "":
            return default
        if allow_empty:
            return ""
        print("A value is required.")


def _prompt_int(label):
    while True:
        response = input(f"{label}: ").strip()
        try:
            return int(response)
        except ValueError:
            print("Please enter an integer index.")


def _prompt_optional_int(label):
    while True:
        response = input(f"{label}: ").strip()
        if response == "":
            return None
        try:
            return int(response)
        except ValueError:
            print("Please enter an integer index or leave it blank.")


def _prompt_choice(label, choices, default):
    choice_list = "/".join(choices)
    while True:
        response = input(f"{label} [{default}] ({choice_list}): ").strip()
        if response == "":
            return default
        if response in choices:
            return response
        print(f"Please choose one of: {choice_list}")
