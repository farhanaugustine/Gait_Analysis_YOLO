import os
import numpy as np

# --- Central Output Directory ---
RESULTS_DIR = "results"

# =============================================================================
# SECTION 1: FILE PATHS
# =============================================================================
INPUT_VIDEO_PATH = r"c:\Users\Aegis-MSI\Documents\GitHub\Gait_Analysis_DeepLabCut - Copy\predict\trimmed-LL6-2_C57BL6J.avi"
INPUT_LABELS_DIR = r"c:\Users\Aegis-MSI\Documents\GitHub\Gait_Analysis_DeepLabCut - Copy\predict\labels"
ROI_CONFIG_PATH = "roi_config.json"

# Output files
OUTPUT_CSV_PATH = os.path.join(RESULTS_DIR, "final_analysis_data.csv")
GAIT_ANALYSIS_PATH = os.path.join(RESULTS_DIR, "gait_analysis_summary.csv")
GAIT_STRIDE_DETAIL_PATH = os.path.join(RESULTS_DIR, "gait_stride_details.csv")
GAIT_BOUT_SUMMARY_PATH = os.path.join(RESULTS_DIR, "gait_bout_summary.csv")
GAIT_BOUT_SUMMARY_JSON_PATH = os.path.join(RESULTS_DIR, "gait_bout_summary.json")
GAIT_REVIEW_REPORT_PATH = os.path.join(RESULTS_DIR, "gait_review_report.html")
GAIT_CLIPS_DIR = os.path.join(RESULTS_DIR, "gait_bout_clips")
FUTURE_DIRECTIONS_PATH = "FUTURE_DIRECTIONS.md"
ANALYSIS_SUMMARY_PATH = os.path.join(RESULTS_DIR, "analysis_summary.json")
OUTPUT_VIDEO_PATH = os.path.join(RESULTS_DIR, "behavior_analysis_output.mp4")
KURAMOTO_PHASE_TIMESERIES_PATH = os.path.join(RESULTS_DIR, "kuramoto_phase_timeseries.csv")
KURAMOTO_PAIRWISE_PATH = os.path.join(RESULTS_DIR, "kuramoto_pairwise_metrics.csv")
KURAMOTO_SUMMARY_PATH = os.path.join(RESULTS_DIR, "kuramoto_summary.json")
KURAMOTO_REPORT_DATA_PATH = os.path.join(RESULTS_DIR, "kuramoto_report_data.json")
KURAMOTO_REPORT_PATH = os.path.join(RESULTS_DIR, "kuramoto_gait_report.html")
KURAMOTO_TEMPLATE_TIMELINE_PATH = os.path.join(RESULTS_DIR, "kuramoto_template_timeline.csv")

# =============================================================================
# SECTION 2: YOLO POSE INPUT
# =============================================================================
# Map output names to the zero-based keypoint indices used by the Ultralytics model.
# Add as many extra keypoints as your model provides if you want angle, elongation,
# skeleton drawing, or custom center definitions.
KEYPOINT_INDEX_MAP = {
    "LeftFrontPaw": 4,
    "RightFrontPaw": 5,
    "LeftRearPaw": 7,
    "RightRearPaw": 8,
}

# Drawing order for skeleton visualization. By default this follows the mapped keys.
KEYPOINT_ORDER = list(KEYPOINT_INDEX_MAP.keys())

# Optional skeleton connections between named keypoints.
SKELETON_CONNECTIONS = []

# Optional pose metric helpers. Leave as None to skip those calculations.
# Use the index-based fields for a cleaner setup. The legacy name-based fields
# remain supported for backward compatibility.
CENTER_KEYPOINT_INDEX = None
BODY_ANGLE_KEYPOINT_INDICES = None
ELONGATION_KEYPOINT_INDICES = None
CENTER_KEYPOINT = None
BODY_ANGLE_CONNECTION = None
ELONGATION_CONNECTION = None

USE_PRIMARY_TRACK_ONLY = True
KEYPOINT_CONF_THRESHOLD = 0.0

# Ultralytics TXT parsing options.
YOLO_KEYPOINT_INDEX_BASE = 0
YOLO_KEYPOINT_DIMENSIONS = "auto"  # "auto", 2, or 3
YOLO_INCLUDE_DETECTION_CONF = "auto"
YOLO_INCLUDE_TRACK_ID = "auto"
YOLO_SINGLE_EXTRA_FIELD = "auto"  # "auto", "conf", or "track"
YOLO_TARGET_CLASS_ID = None
YOLO_TARGET_TRACK_ID = None
YOLO_DETECTION_SELECTION = "highest_conf"  # "highest_conf", "highest_mean_keypoint_conf", or "first"
YOLO_FRAME_SIZE = None  # Optional width,height or (width, height) override
YOLO_FRAME_NUMBER_OFFSET = 0
YOLO_DETECTION_CONF_THRESHOLD = 0.0

# =============================================================================
# SECTION 3: GAIT ANALYSIS PARAMETERS
# =============================================================================
GAIT_PAWS = ["LeftFrontPaw", "RightFrontPaw", "LeftRearPaw", "RightRearPaw"]
PAW_ORDER_HILDEBRAND = list(GAIT_PAWS)
PAW_SPEED_THRESHOLD_PX_PER_FRAME = 5
STRIDE_REFERENCE_PAW = "LeftRearPaw"
PAW_PLOT_COLORS = {
    "LeftFrontPaw": (255, 100, 100),
    "RightFrontPaw": (100, 100, 255),
    "LeftRearPaw": (255, 255, 100),
    "RightRearPaw": (100, 255, 100),
}
GAIT_BOUT_MIN_STRIDES = 2
GAIT_BOUT_MAX_GAP_FACTOR = 1.2
GAIT_BOUT_MAX_GAP_FRAMES = None
GAIT_BOUT_DOMINANT_LABEL_MIN_FRACTION = 0.55
GAIT_BOUT_MIN_BODY_SPEED = 1.4
GAIT_BOUT_STATIONARY_FRACTION_THRESHOLD = 0.6
GAIT_BOUT_CLIP_PADDING_FRAMES = 10
GAIT_BOUT_CLIP_MAX_COUNT = 12
GAIT_BOUT_CLIP_OVERLAY = True

KURAMOTO_ENABLED = True
KURAMOTO_MIN_VALID_FRAMES = 40
KURAMOTO_MAX_REPORT_SAMPLES = 240
KURAMOTO_IDEAL_COUPLING_GAIN = 0.35
KURAMOTO_REFERENCE_TEMPLATE = "trot"  # Initial report view: trot, pace, bound, walk, or stationary
KURAMOTO_TEMPLATE_WINDOW = 15
KURAMOTO_STATIONARY_SPEED_SCALE = 0.7
KURAMOTO_STATIONARY_BODY_SPEED_THRESHOLD = 1.4
KURAMOTO_IDEAL_PHASE_OFFSETS = {
    "LeftFrontPaw": 0.0,
    "RightFrontPaw": np.pi,
    "LeftRearPaw": np.pi,
    "RightRearPaw": 0.0,
}

# =============================================================================
# SECTION 4: DISPLAY & DRAWING SETTINGS
# =============================================================================
BEHAVIOR_COLORS = {"stance": (100, 255, 100), "swing": (255, 100, 100)}
SKELETON_COLOR = (255, 255, 255)
KEYPOINT_COLOR = (0, 0, 255)
KEYPOINT_RADIUS = 3
RESIZED_VIDEO_WIDTH = 500
DASHBOARD_WIDTH = 680
GRAPH_WINDOW_SECONDS = 5
HILDEBRAND_WINDOW_SECONDS = 4
MAX_LIST_ITEMS = 4
