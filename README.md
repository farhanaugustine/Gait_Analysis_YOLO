# Gait Analysis with Ultralytics YOLO Pose
Configurable Python project for analyzing gait in animal video experiments from Ultralytics pose-label TXT files.

This repository is a YOLO-pose gait-analysis pipeline built around Ultralytics/IntegraPose-style pose outputs. It ingests per-frame Ultralytics pose-label `.txt` files, converts them into a canonical dataframe, and then runs gait, pose, ROI, and Kuramoto-style limb coordination analysis on top of that data.

## Features

- Dynamic video dashboard with pose, ROI, gait, and stride summaries
- Gait analysis from user-mapped paw keypoints instead of a fixed landmark schema
- Bout-level gait review with stride summaries and validation clip export
- Kuramoto phase and coupling analysis with a user-facing HTML report and switchable gait templates
- Optional pose metrics such as body angle and elongation when the relevant keypoints are mapped
- Flexible keypoint-index mapping so the model does not need to match any fixed legacy landmark schema

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/farhanaugustine/Gait_Analysis_YOLO.git
   cd Gait_Analysis_YOLO
   ```

2. Install dependencies:
   ```bash
   pip install pandas numpy opencv-python tqdm scipy ultralytics
   ```

## Expected Input

The pipeline expects:

- an input video at `INPUT_VIDEO_PATH`
- a folder of per-frame Ultralytics pose `.txt` labels at `INPUT_LABELS_DIR`

The labels should come from an Ultralytics pose run with `save_txt=True`. The loader supports the standard normalized pose format with optional trailing detection confidence and track ID.

DeepLabCut CSV/HDF5 exports are not an input format for this pipeline; use YOLO pose TXT labels instead.

## Quick Start

### 1. Create a reusable runtime profile

Run:

```bash
python main.py --config profiles/mouse_setup.json
```

If `profiles/mouse_setup.json` does not exist yet, the script will prompt you for:

- input video path
- input labels directory
- left front paw index
- right front paw index
- left rear paw index
- right rear paw index
- optional center keypoint index
- optional body-angle keypoint pair
- optional elongation keypoint pair

It then saves that configuration for future runs.
Those optional metric indices are calculation-only by default. They do not need to appear as named overlay points.

On later runs, use the same command and the saved profile will be loaded automatically.

### 2. Optional: edit defaults in `config.py`

Edit [config.py](/C:/Users/Aegis-MSI/Documents/GitHub/Gait_Analysis_YOLO%20-%20Copy/config.py) if you want to change defaults such as colors, Kuramoto parameters, or dashboard layout:

- `INPUT_VIDEO_PATH`
- `INPUT_LABELS_DIR` pointing to your Ultralytics/YOLO pose label directory

### 3. Direct config editing is still supported
If you prefer not to use the interactive wizard, you can still set `KEYPOINT_INDEX_MAP` directly in `config.py`. Example:

```python
KEYPOINT_INDEX_MAP = {
    "LeftFrontPaw": 0,
    "RightFrontPaw": 1,
    "LeftRearPaw": 2,
    "RightRearPaw": 3,
    "Nose": 4,
    "TailBase": 5,
}
```

If you only care about gait, four paw points are enough.

### 4. Configure optional pose metrics
These are optional. Leave them as `None` to skip the calculation.

```python
CENTER_KEYPOINT_INDEX = None
BODY_ANGLE_KEYPOINT_INDICES = [0, 10]
ELONGATION_KEYPOINT_INDICES = [0, 11]
```

Use the index-based fields when you only need those points for calculations. This keeps the overlay clean.

The legacy name-based fields are still supported:

```python
CENTER_KEYPOINT = None
BODY_ANGLE_CONNECTION = ("TailBase", "Nose")
ELONGATION_CONNECTION = ("Nose", "TailBase")
```

If the chosen points are missing, those metrics are skipped automatically.

### 5. Configure frame size only if needed
Normally the loader uses the video metadata via OpenCV.

If that fails, set:

```python
YOLO_FRAME_SIZE = (1920, 1080)
```

The order is `(width, height)`. A string like `"1920,1080"` is also accepted.

### 6. Configure gait paw names
The gait pipeline uses names, not fixed indices. These names must match the keys you used in `KEYPOINT_INDEX_MAP`.

```python
GAIT_PAWS = ["LeftFrontPaw", "RightFrontPaw", "LeftRearPaw", "RightRearPaw"]
PAW_ORDER_HILDEBRAND = list(GAIT_PAWS)
STRIDE_REFERENCE_PAW = "LeftRearPaw"
```

### 7. Run the analysis

With a saved profile:

```bash
python main.py --config profiles/mouse_setup.json
```

Without a saved profile:

```bash
python main.py
```

## Outputs

The run generates files in `results/`, including:

- `final_analysis_data.csv`
- `gait_analysis_summary.csv`
- `gait_stride_details.csv`
- `gait_bout_summary.csv`
- `gait_review_report.html`
- `gait_bout_clips/`
- `behavior_analysis_output.mp4`
- `kuramoto_phase_timeseries.csv`
- `kuramoto_pairwise_metrics.csv`
- `kuramoto_template_timeline.csv`
- `kuramoto_summary.json`
- `kuramoto_gait_report.html`

## Configuration Notes

### Core input settings

- `KEYPOINT_INDEX_MAP`: maps your semantic names to Ultralytics keypoint indices
- `--config path/to/profile.json`: loads a saved runtime profile, or creates one interactively if it does not exist
- `KEYPOINT_ORDER`: controls overlay drawing order only
- `SKELETON_CONNECTIONS`: optional named pairs for the overlay skeleton
- `USE_PRIMARY_TRACK_ONLY`: keeps only the most complete track for single-animal analysis

### Optional pose metrics

- `CENTER_KEYPOINT_INDEX`: optional raw YOLO index used to override the mean-of-keypoints center estimate
- `BODY_ANGLE_KEYPOINT_INDICES`: optional raw YOLO index pair for body-angle calculation
- `ELONGATION_KEYPOINT_INDICES`: optional raw YOLO index pair for body elongation
- `CENTER_KEYPOINT`, `BODY_ANGLE_CONNECTION`, `ELONGATION_CONNECTION`: legacy name-based alternatives that still work if you prefer semantic names
- `KEYPOINT_CONF_THRESHOLD`: if greater than zero, low-confidence keypoints are dropped before analysis

### Ultralytics TXT parsing

- `YOLO_KEYPOINT_DIMENSIONS`: use `2`, `3`, or `"auto"`
- `YOLO_INCLUDE_DETECTION_CONF`: whether the TXT line includes a detection confidence field
- `YOLO_INCLUDE_TRACK_ID`: whether the TXT line includes a track ID
- `YOLO_SINGLE_EXTRA_FIELD`: disambiguates a single trailing extra value as `"conf"` or `"track"` if auto-detection is not enough
- `YOLO_TARGET_CLASS_ID`: optional class filter
- `YOLO_TARGET_TRACK_ID`: optional track filter
- `YOLO_DETECTION_SELECTION`: choose one detection per frame when multiple are present
- `YOLO_FRAME_NUMBER_OFFSET`: shifts inferred frame numbers if the label filenames are offset

### Gait and Kuramoto

- `PAW_SPEED_THRESHOLD_PX_PER_FRAME`: controls stance versus swing classification
- `GAIT_BOUT_MIN_STRIDES`: minimum number of neighboring strides required before a bout is exported
- `GAIT_BOUT_MAX_GAP_FACTOR`: auto gap threshold, expressed as a multiple of the median stride duration
- `GAIT_BOUT_MAX_GAP_FRAMES`: optional absolute gap override in frames for bout segmentation
- `GAIT_BOUT_DOMINANT_LABEL_MIN_FRACTION`: minimum fraction required before a bout gets one dominant label instead of `mixed`
- `GAIT_BOUT_MIN_BODY_SPEED`: minimum mean body speed for a stride interval to count as active locomotion during bout segmentation
- `GAIT_BOUT_STATIONARY_FRACTION_THRESHOLD`: if a stride interval is dominated by `stationary` above this fraction and body speed is low, it will be excluded from bout grouping
- `GAIT_BOUT_CLIP_PADDING_FRAMES`: extra frames added before and after each exported validation clip
- `GAIT_BOUT_CLIP_MAX_COUNT`: maximum number of bout clips exported per run
- `KURAMOTO_REFERENCE_TEMPLATE`: sets the initial HTML report view (`trot`, `pace`, `bound`, `walk`, or `stationary`)
- `KURAMOTO_IDEAL_PHASE_OFFSETS`: defines the trot reference phase pattern used when `KURAMOTO_REFERENCE_TEMPLATE = "trot"`
- `KURAMOTO_IDEAL_COUPLING_GAIN`: controls the visual strength of the ideal reference network
- `KURAMOTO_TEMPLATE_WINDOW`: controls the local phase window used for live gait-template classification in the HTML report
- `KURAMOTO_STATIONARY_BODY_SPEED_THRESHOLD`: body-motion threshold used to keep moving animals from being mislabeled as `stationary` when paw motion is modest

## Metric Notes

### Pose metrics

- Body speed is computed from `center_x` and `center_y`
- Body angle is only computed if `BODY_ANGLE_KEYPOINT_INDICES` or `BODY_ANGLE_CONNECTION` is configured and present
- Elongation is only computed if `ELONGATION_KEYPOINT_INDICES` or `ELONGATION_CONNECTION` is configured and present

### Gait metrics

- Continuous paw phases are derived from stance/swing transitions
- Stride metrics are computed relative to `STRIDE_REFERENCE_PAW`
- Contralateral step comparisons are inferred from the paw names, so names should include left/right and front/rear semantics
- Bout summaries group neighboring strides into larger locomotion segments so the final review is easier to interpret than frame-by-frame labels alone
- Long low-motion or stationary-dominant stride intervals are excluded from bout grouping so pauses do not merge an entire recording into one bout
- The bout report links each exported bout to a short source-video clip for manual verification

### Kuramoto metrics

- Per-paw continuous phase `theta`
- Pairwise phase offsets
- Phase-locking values
- Effective coupling matrix `K_ij`
- Global order parameters `R1` and `R2`
- Switchable reference templates for walk, trot, pace, bound, and stationary coordination
- Per-sample local template scores used to label the likely gait mode during report playback

### Interpreting the likely gait label

- The live gait label in the HTML report is the closest local match among five reference patterns: `walk`, `trot`, `pace`, `bound`, and `stationary`.
- It is not a calibrated probability and it is not a final diagnosis of what the animal is doing.
- A label is more trustworthy when it stays stable across many playback windows and its score is clearly higher than the alternatives.
- A label is less trustworthy when the scores are close together, the label flips rapidly, or the animal is slowing down, starting, stopping, or transitioning between patterns.
- `stationary` becomes more likely when paw motion is low, so very slow stepping can be pushed toward `stationary` if the movement threshold is too high.

The main settings that affect this interpretation are:

- `PAW_SPEED_THRESHOLD_PX_PER_FRAME`: separates low paw motion from active stepping
- `KURAMOTO_TEMPLATE_WINDOW`: controls how many nearby frames are blended into each live gait label
- `KURAMOTO_STATIONARY_SPEED_SCALE`: controls how easily low-motion windows are called `stationary`
- `KURAMOTO_STATIONARY_BODY_SPEED_THRESHOLD`: adds a body-motion safeguard so whole-animal movement can still count as locomotion even when per-paw motion is small

For final interpretation, start with the bout review report rather than the frame-by-frame label. Bouts are usually easier to trust because they aggregate multiple strides before assigning a dominant pattern.

### Choosing starting defaults

These thresholds are not universal physical units. The best values depend on:

- video resolution
- frame rate
- crop size
- how large the animal appears in frame
- how smooth or noisy the pose tracking is

The current defaults are meant as a practical starting point for short single-animal mouse clips with clear locomotion bouts separated by pauses:

- `PAW_SPEED_THRESHOLD_PX_PER_FRAME = 5`
- `GAIT_BOUT_MIN_STRIDES = 2`
- `GAIT_BOUT_MAX_GAP_FACTOR = 1.2`
- `GAIT_BOUT_DOMINANT_LABEL_MIN_FRACTION = 0.55`
- `GAIT_BOUT_MIN_BODY_SPEED = 1.4`
- `GAIT_BOUT_STATIONARY_FRACTION_THRESHOLD = 0.6`
- `KURAMOTO_TEMPLATE_WINDOW = 15`
- `KURAMOTO_STATIONARY_SPEED_SCALE = 0.7`
- `KURAMOTO_STATIONARY_BODY_SPEED_THRESHOLD = 1.4`

If you need to tune them, this order works well:

1. Start with the `stationary` label.
   If the animal is clearly moving but the report still says `stationary`, lower `KURAMOTO_STATIONARY_BODY_SPEED_THRESHOLD` first, then lower `KURAMOTO_STATIONARY_SPEED_SCALE`.
   If small tracking jitter is being mistaken for locomotion, raise those values instead.

2. Adjust stance and swing separation.
   If paw phases look too flat and slower steps disappear, lower `PAW_SPEED_THRESHOLD_PX_PER_FRAME`.
   If noisy paw jitter creates false stepping, raise it.

3. Adjust label stability.
   If the gait label flickers too much, increase `KURAMOTO_TEMPLATE_WINDOW`.
   If gait transitions feel too smeared or delayed, decrease it.

4. Adjust bout grouping.
   If separate runs are being merged into one long bout, lower `GAIT_BOUT_MAX_GAP_FACTOR` or set `GAIT_BOUT_MAX_GAP_FRAMES`.
   If one run is being broken into many short bouts, raise the gap threshold.

5. Adjust how easily pauses are removed from bout grouping.
   If stationary pauses are still being kept inside bouts, raise `GAIT_BOUT_MIN_BODY_SPEED` or lower `GAIT_BOUT_STATIONARY_FRACTION_THRESHOLD`.
   If true locomotion is being filtered out, lower `GAIT_BOUT_MIN_BODY_SPEED` or raise `GAIT_BOUT_STATIONARY_FRACTION_THRESHOLD`.

6. Adjust how strict the dominant bout label should be.
   If too many bouts become `mixed`, lower `GAIT_BOUT_DOMINANT_LABEL_MIN_FRACTION`.
   If you want only very consistent bouts to receive one dominant label, raise it.

Two simple rules are helpful:

- If you increase image resolution without changing the field of view, motion in pixels per frame usually increases, so the speed thresholds may need to go up.
- If you increase frame rate, motion per frame usually decreases, so the speed thresholds may need to go down.

## ROI Workflow

If `roi_config.json` does not exist, the script will prompt you to draw ROIs on the first frame of the video.

## Acknowledgements

This project builds on general stride-level pose-analysis ideas inspired by:

- Keith Sheppard et al., *Stride-level analysis of mouse open field behavior using deep-learning-based pose estimation*, Cell Reports (2021)

It also relies on Ultralytics pose outputs, OpenCV, pandas, NumPy, and SciPy.
