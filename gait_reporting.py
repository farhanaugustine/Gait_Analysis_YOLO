import json
import logging
import os

import cv2
import numpy as np
import pandas as pd

from gait_review_report import write_gait_review_report
from video_alignment import (
    analysis_frame_to_video_index,
    read_video_metadata,
    resolve_video_frame_alignment,
    video_index_to_analysis_frame,
)

logger = logging.getLogger(__name__)


def run_gait_reporting(full_df, gait_df, kuramoto_outputs, config, video_alignment=None):
    if gait_df is None or gait_df.empty:
        logger.info("Skipping gait review reporting because no gait strides were available.")
        return None

    os.makedirs(config.RESULTS_DIR, exist_ok=True)
    video_meta = read_video_metadata(getattr(config, "INPUT_VIDEO_PATH", ""))
    if video_alignment is None:
        video_alignment = resolve_video_frame_alignment(full_df["frame"], video_meta["frame_count"], getattr(config, "INPUT_VIDEO_PATH", "source video"))
    fps = video_meta["fps"] if video_meta["fps"] > 0 else 30.0
    template_timeline_df = _resolve_template_timeline(kuramoto_outputs)

    stride_details_df = _build_stride_details(full_df, gait_df, template_timeline_df, fps, config)
    stride_details_df, bout_summary_df = _build_bout_summary(full_df, stride_details_df, template_timeline_df, fps, config)
    clip_records = _export_bout_clips(getattr(config, "INPUT_VIDEO_PATH", ""), bout_summary_df, config, video_meta, video_alignment)
    if clip_records:
        clip_df = pd.DataFrame(clip_records)
        bout_summary_df = bout_summary_df.merge(clip_df, on="bout_id", how="left")
    else:
        bout_summary_df["clip_path"] = None
        bout_summary_df["clip_relpath"] = None

    stride_path = getattr(config, "GAIT_STRIDE_DETAIL_PATH", os.path.join(config.RESULTS_DIR, "gait_stride_details.csv"))
    bout_path = getattr(config, "GAIT_BOUT_SUMMARY_PATH", os.path.join(config.RESULTS_DIR, "gait_bout_summary.csv"))
    bout_json_path = getattr(config, "GAIT_BOUT_SUMMARY_JSON_PATH", os.path.join(config.RESULTS_DIR, "gait_bout_summary.json"))
    report_path = getattr(config, "GAIT_REVIEW_REPORT_PATH", os.path.join(config.RESULTS_DIR, "gait_review_report.html"))

    stride_details_df.to_csv(stride_path, index=False)
    bout_summary_df.to_csv(bout_path, index=False)

    report_data = _build_report_data(stride_details_df, bout_summary_df, video_meta, config)
    with open(bout_json_path, "w", encoding="utf-8") as handle:
        json.dump(report_data["summary"], handle, indent=2)

    write_gait_review_report(report_path, report_data)
    logger.info("Gait review report saved to %s", report_path)

    return {
        "stride_details_path": stride_path,
        "bout_summary_path": bout_path,
        "bout_summary_json_path": bout_json_path,
        "report_html_path": report_path,
        "clip_dir": getattr(config, "GAIT_CLIPS_DIR", os.path.join(config.RESULTS_DIR, "gait_bout_clips")),
        "stride_details_df": stride_details_df,
        "bout_summary_df": bout_summary_df,
    }


def _resolve_template_timeline(kuramoto_outputs):
    if not kuramoto_outputs:
        return pd.DataFrame()

    timeline_df = kuramoto_outputs.get("template_timeline_df")
    if isinstance(timeline_df, pd.DataFrame):
        return timeline_df.copy()

    timeline_path = kuramoto_outputs.get("template_timeline_path")
    if timeline_path and os.path.exists(timeline_path):
        return pd.read_csv(timeline_path)

    return pd.DataFrame()


def _build_stride_details(full_df, gait_df, template_timeline_df, fps, config):
    strides = gait_df.copy().sort_values(["track_id", "start_frame", "end_frame"]).reset_index(drop=True)
    strides["stride_id"] = [f"S{idx:04d}" for idx in range(1, len(strides) + 1)]
    strides["duration_frames"] = strides["end_frame"] - strides["start_frame"] + 1
    strides["duration_seconds"] = strides["duration_frames"] / fps if fps > 0 else np.nan
    strides["bout_id"] = None

    body_speed_column = "body_speed" if "body_speed" in full_df.columns else "speed" if "speed" in full_df.columns else None
    min_fraction = float(getattr(config, "GAIT_BOUT_DOMINANT_LABEL_MIN_FRACTION", 0.55))

    body_speeds = []
    order_1_means = []
    order_2_means = []
    dominant_labels = []
    dominant_fractions = []
    mean_confidences = []
    label_breakdowns = []
    stationary_fractions = []
    eligible_for_bout = []
    eligibility_reason = []

    for stride in strides.itertuples(index=False):
        stride_frames = full_df[
            (full_df["track_id"] == stride.track_id)
            & (full_df["frame"] >= stride.start_frame)
            & (full_df["frame"] <= stride.end_frame)
        ]
        template_window = template_timeline_df[
            (template_timeline_df["track_id"] == stride.track_id)
            & (template_timeline_df["frame"] >= stride.start_frame)
            & (template_timeline_df["frame"] <= stride.end_frame)
        ]
        template_summary = _summarize_template_window(template_window, min_fraction)

        body_speeds.append(_safe_mean(stride_frames[body_speed_column]) if body_speed_column else np.nan)
        order_1_means.append(_safe_mean(stride_frames["kuramoto_order_1"]) if "kuramoto_order_1" in stride_frames.columns else np.nan)
        order_2_means.append(_safe_mean(stride_frames["kuramoto_order_2"]) if "kuramoto_order_2" in stride_frames.columns else np.nan)
        dominant_labels.append(template_summary["dominant_label"])
        dominant_fractions.append(template_summary["dominant_fraction"])
        mean_confidences.append(template_summary["mean_confidence"])
        label_breakdowns.append(template_summary["label_breakdown"])
        stationary_fractions.append(template_summary["stationary_fraction"])

        active_stride, reason = _is_stride_eligible_for_bout(
            template_summary["dominant_label"],
            template_summary["stationary_fraction"],
            body_speeds[-1],
            config,
        )
        eligible_for_bout.append(active_stride)
        eligibility_reason.append(reason)

    strides["mean_body_speed"] = body_speeds
    strides["mean_order_1"] = order_1_means
    strides["mean_order_2"] = order_2_means
    strides["dominant_label"] = dominant_labels
    strides["dominant_fraction"] = dominant_fractions
    strides["mean_template_confidence"] = mean_confidences
    strides["label_breakdown"] = label_breakdowns
    strides["stationary_fraction"] = stationary_fractions
    strides["eligible_for_bout"] = eligible_for_bout
    strides["eligibility_reason"] = eligibility_reason

    return strides


def _build_bout_summary(full_df, stride_details_df, template_timeline_df, fps, config):
    if stride_details_df.empty:
        return stride_details_df, pd.DataFrame()

    body_speed_column = "body_speed" if "body_speed" in full_df.columns else "speed" if "speed" in full_df.columns else None
    min_fraction = float(getattr(config, "GAIT_BOUT_DOMINANT_LABEL_MIN_FRACTION", 0.55))
    min_strides = max(int(getattr(config, "GAIT_BOUT_MIN_STRIDES", 2)), 1)
    gap_limit = _resolve_bout_gap_limit(stride_details_df, config)

    all_records = []
    stride_details_df = stride_details_df.sort_values(["track_id", "start_frame", "end_frame"]).copy()
    stride_details_df["bout_id"] = None
    stride_details_df["bout_status"] = np.where(stride_details_df["eligible_for_bout"], "isolated", "filtered_out")

    next_bout_number = 1
    for track_id, track_strides in stride_details_df.groupby("track_id", sort=True):
        track_strides = track_strides[track_strides["eligible_for_bout"]]
        if track_strides.empty:
            continue
        group_indices = []
        previous_end = None
        for stride_index, stride in track_strides.iterrows():
            if previous_end is None or (stride["start_frame"] - previous_end) <= gap_limit:
                group_indices.append(stride_index)
            else:
                next_bout_number = _finalize_bout_group(
                    full_df,
                    stride_details_df,
                    template_timeline_df,
                    group_indices,
                    all_records,
                    next_bout_number,
                    min_strides,
                    min_fraction,
                    body_speed_column,
                    fps,
                )
                group_indices = [stride_index]
            previous_end = stride["end_frame"]

        if group_indices:
            next_bout_number = _finalize_bout_group(
                full_df,
                stride_details_df,
                template_timeline_df,
                group_indices,
                all_records,
                next_bout_number,
                min_strides,
                min_fraction,
                body_speed_column,
                fps,
            )

    stride_details_df["bout_id"] = stride_details_df["bout_id"].where(pd.notna(stride_details_df["bout_id"]), None)
    if not all_records:
        return stride_details_df, pd.DataFrame()

    bout_summary_df = pd.DataFrame(all_records).sort_values("start_frame").reset_index(drop=True)
    logger.info(
        "Bout review kept %s of %s strides for bout segmentation and produced %s bouts.",
        int(stride_details_df["eligible_for_bout"].sum()),
        len(stride_details_df),
        len(bout_summary_df),
    )
    return stride_details_df, bout_summary_df


def _finalize_bout_group(
    full_df,
    stride_details_df,
    template_timeline_df,
    group_indices,
    all_records,
    next_bout_number,
    min_strides,
    min_fraction,
    body_speed_column,
    fps,
):
    if not group_indices:
        return next_bout_number

    stride_group = stride_details_df.loc[group_indices].sort_values("start_frame")
    if len(stride_group) < min_strides:
        stride_details_df.loc[group_indices, "bout_status"] = "isolated"
        return next_bout_number

    bout_id = f"B{next_bout_number:03d}"
    start_frame = int(stride_group["start_frame"].min())
    end_frame = int(stride_group["end_frame"].max())
    track_id = int(stride_group["track_id"].iloc[0])

    stride_details_df.loc[group_indices, "bout_id"] = bout_id
    stride_details_df.loc[group_indices, "bout_status"] = "qualified"

    bout_frames = full_df[
        (full_df["track_id"] == track_id)
        & (full_df["frame"] >= start_frame)
        & (full_df["frame"] <= end_frame)
    ]
    template_window = template_timeline_df[
        (template_timeline_df["track_id"] == track_id)
        & (template_timeline_df["frame"] >= start_frame)
        & (template_timeline_df["frame"] <= end_frame)
    ]
    template_summary = _summarize_template_window(template_window, min_fraction)

    all_records.append(
        {
            "bout_id": bout_id,
            "track_id": track_id,
            "start_frame": start_frame,
            "end_frame": end_frame,
            "duration_frames": end_frame - start_frame + 1,
            "duration_seconds": (end_frame - start_frame + 1) / fps if fps > 0 else np.nan,
            "stride_count": int(len(stride_group)),
            "dominant_label": template_summary["dominant_label"],
            "dominant_fraction": template_summary["dominant_fraction"],
            "mean_template_confidence": template_summary["mean_confidence"],
            "label_breakdown": template_summary["label_breakdown"],
            "mean_stride_length": _safe_mean(stride_group["stride_length"]),
            "std_stride_length": _safe_std(stride_group["stride_length"]),
            "mean_stride_speed": _safe_mean(stride_group["stride_speed"]),
            "std_stride_speed": _safe_std(stride_group["stride_speed"]),
            "mean_step_length": _safe_mean(stride_group["step_length"]),
            "mean_step_width": _safe_mean(stride_group["step_width"]),
            "mean_body_speed": _safe_mean(bout_frames[body_speed_column]) if body_speed_column else np.nan,
            "mean_order_1": _safe_mean(bout_frames["kuramoto_order_1"]) if "kuramoto_order_1" in bout_frames.columns else np.nan,
            "mean_order_2": _safe_mean(bout_frames["kuramoto_order_2"]) if "kuramoto_order_2" in bout_frames.columns else np.nan,
        }
    )

    return next_bout_number + 1


def _resolve_bout_gap_limit(stride_details_df, config):
    configured_limit = getattr(config, "GAIT_BOUT_MAX_GAP_FRAMES", None)
    if configured_limit not in (None, ""):
        return max(int(configured_limit), 0)

    durations = stride_details_df["duration_frames"].dropna().to_numpy(dtype=float)
    median_duration = float(np.median(durations)) if len(durations) else 1.0
    factor = float(getattr(config, "GAIT_BOUT_MAX_GAP_FACTOR", 1.5))
    return max(int(round(median_duration * factor)), 1)


def _summarize_template_window(template_window, min_fraction):
    if template_window.empty or "best_template" not in template_window.columns:
        return {
            "dominant_label": "unknown",
            "dominant_fraction": np.nan,
            "mean_confidence": np.nan,
            "label_breakdown": "",
            "stationary_fraction": np.nan,
        }

    counts = template_window["best_template"].value_counts(normalize=True)
    dominant_label = str(counts.index[0])
    dominant_fraction = float(counts.iloc[0])
    if len(counts) > 1 and dominant_fraction < min_fraction:
        dominant_label = "mixed"

    breakdown = ", ".join(f"{label}:{fraction:.2f}" for label, fraction in counts.items())
    mean_confidence = _safe_mean(template_window["best_template_confidence"])

    return {
        "dominant_label": dominant_label,
        "dominant_fraction": dominant_fraction,
        "mean_confidence": mean_confidence,
        "label_breakdown": breakdown,
        "stationary_fraction": float(counts.get("stationary", 0.0)),
    }


def _is_stride_eligible_for_bout(dominant_label, stationary_fraction, mean_body_speed, config):
    min_body_speed = float(
        getattr(
            config,
            "GAIT_BOUT_MIN_BODY_SPEED",
            getattr(config, "KURAMOTO_STATIONARY_BODY_SPEED_THRESHOLD", 1.4),
        )
    )
    stationary_fraction_threshold = float(getattr(config, "GAIT_BOUT_STATIONARY_FRACTION_THRESHOLD", 0.6))

    if pd.notna(mean_body_speed) and float(mean_body_speed) >= min_body_speed:
        return True, "body_speed"

    if dominant_label in {"stationary", "unknown"}:
        return False, "stationary_or_unknown"

    if pd.notna(stationary_fraction) and float(stationary_fraction) >= stationary_fraction_threshold:
        return False, "stationary_fraction"

    return True, "template_label"


def _export_bout_clips(video_path, bout_summary_df, config, video_meta, video_alignment):
    if bout_summary_df.empty:
        return []
    if not video_path or not os.path.exists(video_path):
        logger.warning("Skipping bout clip export because the source video could not be found: %s", video_path)
        return []

    os.makedirs(getattr(config, "GAIT_CLIPS_DIR", os.path.join(config.RESULTS_DIR, "gait_bout_clips")), exist_ok=True)
    max_clips = max(int(getattr(config, "GAIT_BOUT_CLIP_MAX_COUNT", 12)), 0)
    if max_clips == 0:
        return []

    padding = max(int(getattr(config, "GAIT_BOUT_CLIP_PADDING_FRAMES", 10)), 0)
    overlay_enabled = bool(getattr(config, "GAIT_BOUT_CLIP_OVERLAY", True))
    total_frames = int(video_meta["frame_count"]) if video_meta["frame_count"] > 0 else None
    fps = video_meta["fps"] if video_meta["fps"] > 0 else 30.0
    width = video_meta["width"]
    height = video_meta["height"]
    analysis_start_frame = int(video_alignment["analysis_start_frame"])
    max_analysis_frame = analysis_start_frame + (total_frames - 1) if total_frames is not None else None

    selected_bouts = bout_summary_df.sort_values(["stride_count", "duration_frames", "start_frame"], ascending=[False, False, True]).head(max_clips)
    clip_records = []

    for bout in selected_bouts.itertuples(index=False):
        clip_start = max(int(bout.start_frame) - padding, analysis_start_frame)
        clip_end = int(bout.end_frame) + padding
        if max_analysis_frame is not None:
            clip_end = min(clip_end, max_analysis_frame)
        clip_start_index = max(analysis_frame_to_video_index(clip_start, video_alignment), 0)
        clip_end_index = analysis_frame_to_video_index(clip_end, video_alignment)
        if total_frames is not None:
            clip_end_index = min(clip_end_index, total_frames - 1)
        if clip_end_index < clip_start_index:
            logger.warning("Skipping %s because the aligned video-frame range was invalid.", bout.bout_id)
            continue

        safe_label = str(bout.dominant_label).replace(" ", "_").lower()
        clip_filename = f"{bout.bout_id}_{safe_label}_f{clip_start:06d}_{clip_end:06d}.mp4"
        clip_path = os.path.join(getattr(config, "GAIT_CLIPS_DIR", os.path.join(config.RESULTS_DIR, "gait_bout_clips")), clip_filename)
        success = _write_video_clip(
            video_path,
            clip_path,
            clip_start_index,
            clip_end_index,
            fps,
            width,
            height,
            bout,
            overlay_enabled,
            video_alignment,
        )
        if not success:
            continue

        clip_records.append(
            {
                "bout_id": bout.bout_id,
                "clip_path": clip_path,
                "clip_relpath": os.path.relpath(clip_path, start=config.RESULTS_DIR).replace("\\", "/"),
            }
        )

    return clip_records


def _write_video_clip(video_path, clip_path, start_frame, end_frame, fps, width, height, bout, overlay_enabled, video_alignment):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logger.warning("Could not open video for clip export: %s", video_path)
        return False

    out = None
    try:
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        out = cv2.VideoWriter(clip_path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
        if not out.isOpened():
            logger.warning("Could not open output clip for writing: %s", clip_path)
            return False

        frames_written = 0
        for video_frame_index in range(start_frame, end_frame + 1):
            success, frame = cap.read()
            if not success:
                break

            if overlay_enabled:
                analysis_frame = video_index_to_analysis_frame(video_frame_index, video_alignment)
                _draw_clip_overlay(frame, bout, analysis_frame)

            out.write(frame)
            frames_written += 1

        if frames_written == 0:
            logger.warning("Clip export for %s wrote zero frames.", bout.bout_id)
            return False

        out.release()
        out = None
        return _validate_written_video(clip_path, frames_written)
    finally:
        if out is not None:
            out.release()
        cap.release()


def _draw_clip_overlay(frame, bout, frame_number):
    panel_color = (245, 247, 252)
    cv2.rectangle(frame, (16, 16), (420, 110), panel_color, thickness=-1)
    cv2.rectangle(frame, (16, 16), (420, 110), (70, 86, 108), thickness=2)
    cv2.putText(frame, f"{bout.bout_id} | {bout.dominant_label}", (28, 46), cv2.FONT_HERSHEY_SIMPLEX, 0.76, (29, 42, 58), 2, cv2.LINE_AA)
    cv2.putText(frame, f"Frame {frame_number}", (28, 74), cv2.FONT_HERSHEY_SIMPLEX, 0.64, (58, 74, 91), 2, cv2.LINE_AA)
    cv2.putText(frame, f"{bout.stride_count} strides | {bout.duration_seconds:.2f} s", (28, 99), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (58, 74, 91), 2, cv2.LINE_AA)


def _build_report_data(stride_details_df, bout_summary_df, video_meta, config):
    qualified_strides = stride_details_df[stride_details_df["bout_id"].notna()].copy()
    dominant_counts = bout_summary_df["dominant_label"].value_counts().to_dict() if not bout_summary_df.empty else {}
    summary = {
        "total_bouts": int(len(bout_summary_df)),
        "total_strides": int(len(qualified_strides)),
        "total_locomotion_seconds": _safe_sum(bout_summary_df["duration_seconds"]) if not bout_summary_df.empty else 0.0,
        "median_bout_seconds": _safe_median(bout_summary_df["duration_seconds"]) if not bout_summary_df.empty else np.nan,
        "mean_stride_length": _safe_mean(qualified_strides["stride_length"]) if not qualified_strides.empty else np.nan,
        "mean_stride_speed": _safe_mean(qualified_strides["stride_speed"]) if not qualified_strides.empty else np.nan,
        "mean_order_2": _safe_mean(qualified_strides["mean_order_2"]) if not qualified_strides.empty else np.nan,
        "clips_exported": int(bout_summary_df["clip_relpath"].notna().sum()) if "clip_relpath" in bout_summary_df.columns else 0,
        "dominant_pattern_counts": dominant_counts,
    }

    metadata = {
        "input_video_path": getattr(config, "INPUT_VIDEO_PATH", ""),
        "input_labels_dir": getattr(config, "INPUT_LABELS_DIR", ""),
        "generated_at": pd.Timestamp.now().isoformat(timespec="seconds"),
        "video_fps": video_meta["fps"],
        "video_frame_count": video_meta["frame_count"],
    }

    bouts_export = bout_summary_df.where(pd.notna(bout_summary_df), None).to_dict("records")
    strides_export = qualified_strides.where(pd.notna(qualified_strides), None).to_dict("records")

    return {
        "metadata": metadata,
        "summary": summary,
        "bouts": bouts_export,
        "strides": strides_export,
    }


def _validate_written_video(clip_path, minimum_frames):
    if not os.path.exists(clip_path) or os.path.getsize(clip_path) <= 0:
        return False

    cap = cv2.VideoCapture(clip_path)
    try:
        if not cap.isOpened():
            return False
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        return frame_count >= max(int(minimum_frames), 1)
    finally:
        cap.release()


def _safe_mean(series):
    if series is None:
        return np.nan
    values = pd.Series(series).dropna()
    return float(values.mean()) if not values.empty else np.nan


def _safe_std(series):
    if series is None:
        return np.nan
    values = pd.Series(series).dropna()
    return float(values.std(ddof=0)) if not values.empty else np.nan


def _safe_sum(series):
    if series is None:
        return 0.0
    values = pd.Series(series).dropna()
    return float(values.sum()) if not values.empty else 0.0


def _safe_median(series):
    if series is None:
        return np.nan
    values = pd.Series(series).dropna()
    return float(values.median()) if not values.empty else np.nan
