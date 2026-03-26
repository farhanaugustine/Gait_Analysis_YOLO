import json
import json
import logging
import os
from datetime import datetime

import numpy as np
import pandas as pd

from kuramoto_report import write_kuramoto_report

logger = logging.getLogger(__name__)


def run_kuramoto_analysis(df, config):
    """
    Adds continuous limb phases to the frame-level dataframe, fits a simple
    four-oscillator Kuramoto model, exports pairwise metrics, and generates a
    standalone HTML report for experiment-facing review.
    """
    if df.empty:
        logger.warning("Skipping Kuramoto analysis because the input dataframe is empty.")
        return None

    if not getattr(config, "KURAMOTO_ENABLED", True):
        logger.info("Kuramoto analysis disabled in config.")
        return None

    paws = list(getattr(config, "GAIT_PAWS", []))
    if len(paws) < 2:
        logger.warning("Skipping Kuramoto analysis because fewer than two gait paws are configured.")
        return None

    missing_columns = [paw for paw in paws if f"{paw}_x" not in df.columns or f"{paw}_y" not in df.columns]
    if missing_columns:
        logger.warning("Skipping Kuramoto analysis because paw coordinates are missing: %s", ", ".join(missing_columns))
        return None

    _ensure_binary_phase_columns(df, config, paws)
    cycle_stats = _add_continuous_phase_columns(df, paws)

    phase_columns = [f"{paw}_theta" for paw in paws]
    unwrapped_columns = [f"{paw}_theta_unwrapped" for paw in paws]
    valid_mask = df[phase_columns].notna().all(axis=1)
    min_valid_frames = int(getattr(config, "KURAMOTO_MIN_VALID_FRAMES", 40))
    if int(valid_mask.sum()) < min_valid_frames:
        logger.warning(
            "Skipping Kuramoto analysis because only %s valid all-paw phase frames were found (need at least %s).",
            int(valid_mask.sum()),
            min_valid_frames,
        )
        return None

    valid_df = df.loc[valid_mask, ["frame", "track_id", *phase_columns, *unwrapped_columns]].copy()
    valid_df.reset_index(drop=False, inplace=True)

    observed = _build_observed_metrics(valid_df, paws)
    df["kuramoto_order_1"] = np.nan
    df["kuramoto_order_2"] = np.nan
    df.loc[valid_df["index"], "kuramoto_order_1"] = observed["order_1"]
    df.loc[valid_df["index"], "kuramoto_order_2"] = observed["order_2"]

    templates = _build_gait_template_library(valid_df, paws, observed, config)
    reference_template_id = getattr(config, "KURAMOTO_REFERENCE_TEMPLATE", "trot")
    ideal = templates.get(reference_template_id, templates["trot"])
    template_match = _build_template_match_data(df, valid_df, paws, observed, templates, config)
    template_timeline_df = _build_template_timeline_df(valid_df, template_match, templates)
    pair_records = _build_pair_records(paws, observed, ideal)
    summary = _build_summary(df, valid_df, paws, observed, ideal, cycle_stats, template_match, reference_template_id)
    report_data = _build_report_data(
        df,
        valid_df,
        paws,
        observed,
        ideal,
        templates,
        cycle_stats,
        summary,
        template_match,
        reference_template_id,
        config,
    )

    os.makedirs(config.RESULTS_DIR, exist_ok=True)
    phase_export_path = getattr(
        config,
        "KURAMOTO_PHASE_TIMESERIES_PATH",
        os.path.join(config.RESULTS_DIR, "kuramoto_phase_timeseries.csv"),
    )
    pairwise_export_path = getattr(
        config,
        "KURAMOTO_PAIRWISE_PATH",
        os.path.join(config.RESULTS_DIR, "kuramoto_pairwise_metrics.csv"),
    )
    summary_export_path = getattr(
        config,
        "KURAMOTO_SUMMARY_PATH",
        os.path.join(config.RESULTS_DIR, "kuramoto_summary.json"),
    )
    report_data_export_path = getattr(
        config,
        "KURAMOTO_REPORT_DATA_PATH",
        os.path.join(config.RESULTS_DIR, "kuramoto_report_data.json"),
    )
    report_html_path = getattr(
        config,
        "KURAMOTO_REPORT_PATH",
        os.path.join(config.RESULTS_DIR, "kuramoto_gait_report.html"),
    )
    template_timeline_export_path = getattr(
        config,
        "KURAMOTO_TEMPLATE_TIMELINE_PATH",
        os.path.join(config.RESULTS_DIR, "kuramoto_template_timeline.csv"),
    )

    phase_export_columns = ["frame", "track_id", *phase_columns, *unwrapped_columns, "kuramoto_order_1", "kuramoto_order_2"]
    df.loc[valid_mask, phase_export_columns].to_csv(phase_export_path, index=False)
    pd.DataFrame(pair_records).to_csv(pairwise_export_path, index=False)
    template_timeline_df.to_csv(template_timeline_export_path, index=False)

    with open(summary_export_path, "w", encoding="utf-8") as summary_file:
        json.dump(summary, summary_file, indent=2)

    with open(report_data_export_path, "w", encoding="utf-8") as report_data_file:
        json.dump(report_data, report_data_file, indent=2)

    write_kuramoto_report(report_html_path, report_data)
    logger.info("Kuramoto analysis complete. Report saved to %s", report_html_path)

    return {
        "phase_timeseries_path": phase_export_path,
        "pairwise_metrics_path": pairwise_export_path,
        "summary_path": summary_export_path,
        "report_data_path": report_data_export_path,
        "report_html_path": report_html_path,
        "template_timeline_path": template_timeline_export_path,
        "template_timeline_df": template_timeline_df,
        "report_data": report_data,
        "summary": summary,
    }


def _ensure_binary_phase_columns(df, config, paws):
    for paw in paws:
        speed_col = f"{paw}_speed"
        phase_col = f"{paw}_phase"
        if speed_col not in df.columns:
            dx = df.groupby("track_id")[f"{paw}_x"].diff()
            dy = df.groupby("track_id")[f"{paw}_y"].diff()
            df[speed_col] = np.sqrt(dx ** 2 + dy ** 2)
        if phase_col not in df.columns:
            df[phase_col] = np.where(
                df[speed_col] < config.PAW_SPEED_THRESHOLD_PX_PER_FRAME,
                "stance",
                "swing",
            )


def _add_continuous_phase_columns(df, paws):
    cycle_stats = {paw: {"cycle_lengths": [], "foot_strikes": 0} for paw in paws}

    for paw in paws:
        df[f"{paw}_theta"] = np.nan
        df[f"{paw}_theta_unwrapped"] = np.nan
        df[f"{paw}_cycle_progress"] = np.nan
        df[f"{paw}_cycle_id"] = np.nan

    for track_id, track_df in df.groupby("track_id"):
        frames = track_df["frame"].to_numpy(dtype=float)
        track_index = track_df.index

        for paw in paws:
            phase_series = track_df[f"{paw}_phase"]
            previous_phase = phase_series.shift(1)
            foot_strikes = track_df.loc[(phase_series == "stance") & (previous_phase == "swing"), "frame"].to_numpy(dtype=float)

            cycle_stats[paw]["foot_strikes"] += int(len(foot_strikes))
            if len(foot_strikes) < 2:
                continue

            theta = np.full(len(track_df), np.nan, dtype=float)
            theta_unwrapped = np.full(len(track_df), np.nan, dtype=float)
            cycle_progress = np.full(len(track_df), np.nan, dtype=float)
            cycle_id = np.full(len(track_df), np.nan, dtype=float)

            for cycle_idx in range(len(foot_strikes) - 1):
                start_frame = foot_strikes[cycle_idx]
                end_frame = foot_strikes[cycle_idx + 1]
                if end_frame <= start_frame:
                    continue

                cycle_stats[paw]["cycle_lengths"].append(float(end_frame - start_frame))
                if cycle_idx < len(foot_strikes) - 2:
                    cycle_mask = (frames >= start_frame) & (frames < end_frame)
                else:
                    cycle_mask = (frames >= start_frame) & (frames <= end_frame)

                if not np.any(cycle_mask):
                    continue

                progress = (frames[cycle_mask] - start_frame) / (end_frame - start_frame)
                theta[cycle_mask] = progress * 2.0 * np.pi
                theta_unwrapped[cycle_mask] = (cycle_idx + progress) * 2.0 * np.pi
                cycle_progress[cycle_mask] = progress
                cycle_id[cycle_mask] = cycle_idx

            df.loc[track_index, f"{paw}_theta"] = theta
            df.loc[track_index, f"{paw}_theta_unwrapped"] = theta_unwrapped
            df.loc[track_index, f"{paw}_cycle_progress"] = cycle_progress
            df.loc[track_index, f"{paw}_cycle_id"] = cycle_id

    return cycle_stats


def _build_observed_metrics(valid_df, paws):
    theta = valid_df[[f"{paw}_theta" for paw in paws]].to_numpy(dtype=float)
    theta_unwrapped = valid_df[[f"{paw}_theta_unwrapped" for paw in paws]].to_numpy(dtype=float)
    frame_values = valid_df["frame"].to_numpy(dtype=float)

    order_1 = np.abs(np.mean(np.exp(1j * theta), axis=1))
    order_2 = np.abs(np.mean(np.exp(2j * theta), axis=1))

    pair_count = len(paws)
    phase_matrix = np.zeros((pair_count, pair_count), dtype=float)
    lock_matrix = np.eye(pair_count, dtype=float)
    coordination_matrix = np.eye(pair_count, dtype=float)

    for i in range(pair_count):
        for j in range(pair_count):
            if i == j:
                continue
            phase_delta = _wrap_to_pi(theta[:, j] - theta[:, i])
            mean_vector = np.mean(np.exp(1j * phase_delta))
            phase_matrix[i, j] = float(np.angle(mean_vector))
            lock_matrix[i, j] = float(np.abs(mean_vector))
            coordination_matrix[i, j] = float(lock_matrix[i, j] * np.cos(phase_matrix[i, j]))

    dtheta = np.gradient(theta_unwrapped, frame_values, axis=0)
    coupling_matrix = np.zeros((pair_count, pair_count), dtype=float)
    omega = np.zeros(pair_count, dtype=float)
    regularization = 1e-3

    for i in range(pair_count):
        response = dtheta[:, i]
        predictors = [np.ones(len(valid_df), dtype=float)]
        target_indices = []
        for j in range(pair_count):
            if i == j:
                continue
            predictors.append(np.sin(theta[:, j] - theta[:, i]))
            target_indices.append(j)

        design_matrix = np.column_stack(predictors)
        ridge_eye = np.sqrt(regularization) * np.eye(design_matrix.shape[1], dtype=float)
        augmented_matrix = np.vstack([design_matrix, ridge_eye])
        augmented_response = np.concatenate([response, np.zeros(design_matrix.shape[1], dtype=float)])
        coefficients, _, _, _ = np.linalg.lstsq(augmented_matrix, augmented_response, rcond=None)

        omega[i] = float(coefficients[0])
        for coefficient_idx, j in enumerate(target_indices, start=1):
            coupling_matrix[i, j] = float(coefficients[coefficient_idx])

    return {
        "theta": theta,
        "theta_unwrapped": theta_unwrapped,
        "frames": frame_values,
        "order_1": order_1,
        "order_2": order_2,
        "phase_matrix": phase_matrix,
        "lock_matrix": lock_matrix,
        "coordination_matrix": coordination_matrix,
        "coupling_matrix": coupling_matrix,
        "network_matrix": 0.5 * (coupling_matrix + coupling_matrix.T),
        "omega": omega,
    }


def _build_gait_template_library(valid_df, paws, observed, config):
    template_specs = [
        ("trot", "Trot", "Diagonal pairs move together and oppose the other diagonal pair."),
        ("pace", "Pace", "Left-side limbs move together and oppose the right-side limbs."),
        ("bound", "Bound", "Forelimbs move together and oppose the hindlimbs."),
        ("walk", "Walk", "A simplified four-beat sequence with quarter-cycle offsets between limbs."),
        ("stationary", "Stationary", "Minimal rhythmic stepping. The limbs are treated as nearly static."),
    ]

    templates = {}
    for template_id, display_name, description in template_specs:
        target_offsets = _infer_target_phase_offsets(paws, config, template_id)
        templates[template_id] = _build_template_reference(
            template_id,
            display_name,
            description,
            paws,
            target_offsets,
            observed,
            config,
        )
    return templates


def _build_template_reference(template_id, display_name, description, paws, target_offsets, observed, config):
    pair_count = len(paws)
    phase_matrix = np.zeros((pair_count, pair_count), dtype=float)
    for i in range(pair_count):
        for j in range(pair_count):
            phase_matrix[i, j] = float(_wrap_to_pi(target_offsets[j] - target_offsets[i]))

    mean_omega = float(np.nanmean(observed["omega"])) if np.isfinite(np.nanmean(observed["omega"])) else (2.0 * np.pi / 20.0)
    coupling_gain = float(getattr(config, "KURAMOTO_IDEAL_COUPLING_GAIN", 0.35))

    if template_id == "stationary":
        lock_matrix = np.eye(pair_count, dtype=float)
        coordination_matrix = np.zeros((pair_count, pair_count), dtype=float)
        coupling_matrix = np.zeros((pair_count, pair_count), dtype=float)
        theta = np.tile(target_offsets, (len(observed["theta"]), 1))
        omega = np.zeros(pair_count, dtype=float)
    else:
        lock_matrix = np.ones((pair_count, pair_count), dtype=float)
        np.fill_diagonal(lock_matrix, 1.0)
        coordination_matrix = np.cos(phase_matrix)
        np.fill_diagonal(coordination_matrix, 0.0)
        coupling_matrix = coordination_matrix * max(abs(mean_omega), 0.05) * coupling_gain

        theta = np.zeros_like(observed["theta"])
        theta[0] = target_offsets
        for t in range(1, len(theta)):
            previous = theta[t - 1]
            interaction = np.array(
                [
                    np.sum(coupling_matrix[i] * np.sin(previous - previous[i]))
                    for i in range(pair_count)
                ],
                dtype=float,
            )
            theta[t] = previous + mean_omega + interaction
        theta = np.mod(theta, 2.0 * np.pi)
        omega = np.full(pair_count, mean_omega, dtype=float)

    return {
        "id": template_id,
        "display_name": display_name,
        "description": description,
        "target_offsets": target_offsets,
        "phase_matrix": phase_matrix,
        "lock_matrix": lock_matrix,
        "coordination_matrix": coordination_matrix,
        "coupling_matrix": coupling_matrix,
        "network_matrix": coupling_matrix,
        "theta": theta,
        "omega": omega,
    }


def _build_template_match_data(df, valid_df, paws, observed, templates, config):
    theta = observed["theta"]
    pair_indices = [(i, j) for i in range(len(paws)) for j in range(i + 1, len(paws))]
    window = max(int(getattr(config, "KURAMOTO_TEMPLATE_WINDOW", 15)), 3)
    if window % 2 == 0:
        window += 1
    half_window = window // 2

    source_indices = valid_df["index"].to_numpy(dtype=int)
    paw_speed_columns = [f"{paw}_speed" for paw in paws if f"{paw}_speed" in df.columns]
    if paw_speed_columns:
        paw_speed_values = df.loc[source_indices, paw_speed_columns].to_numpy(dtype=float)
        mean_paw_speed = np.nanmean(paw_speed_values, axis=1)
    else:
        mean_paw_speed = np.zeros(len(valid_df), dtype=float)

    body_speed_column = "speed" if "speed" in df.columns else "body_speed" if "body_speed" in df.columns else None
    if body_speed_column:
        body_speed = df.loc[source_indices, body_speed_column].to_numpy(dtype=float)
    else:
        body_speed = np.zeros(len(valid_df), dtype=float)

    movement_scale = max(
        float(getattr(config, "PAW_SPEED_THRESHOLD_PX_PER_FRAME", 5))
        * float(getattr(config, "KURAMOTO_STATIONARY_SPEED_SCALE", 0.7)),
        1.0,
    )
    body_movement_scale = max(
        float(getattr(config, "KURAMOTO_STATIONARY_BODY_SPEED_THRESHOLD", 1.4)),
        0.5,
    )
    raw_scores = {template_id: np.zeros(len(valid_df), dtype=float) for template_id in templates}

    for frame_idx in range(len(valid_df)):
        start_idx = max(0, frame_idx - half_window)
        end_idx = min(len(valid_df), frame_idx + half_window + 1)
        local_phase_matrix, _ = _window_phase_characteristics(theta[start_idx:end_idx])
        paw_motion_score = float(np.clip(mean_paw_speed[frame_idx] / movement_scale, 0.0, 1.0))
        body_motion_score = float(np.clip(body_speed[frame_idx] / body_movement_scale, 0.0, 1.0))
        movement_score = max(paw_motion_score, body_motion_score)

        for template_id, template in templates.items():
            if template_id == "stationary":
                raw_scores[template_id][frame_idx] = 1.0 - movement_score
                continue

            phase_error = np.mean(
                [
                    abs(_wrap_to_pi(local_phase_matrix[i, j] - template["phase_matrix"][i, j])) / np.pi
                    for i, j in pair_indices
                ]
            )
            raw_scores[template_id][frame_idx] = max(0.0, 1.0 - phase_error) * movement_score

    raw_matrix = np.column_stack([raw_scores[template_id] for template_id in templates])
    row_sums = raw_matrix.sum(axis=1, keepdims=True)
    normalized_matrix = np.divide(raw_matrix, row_sums, out=np.full_like(raw_matrix, 1.0 / raw_matrix.shape[1]), where=row_sums > 1e-8)
    template_ids = list(templates.keys())
    normalized_scores = {
        template_id: normalized_matrix[:, idx]
        for idx, template_id in enumerate(template_ids)
    }

    best_indices = np.argmax(normalized_matrix, axis=1)
    best_template_labels = [template_ids[idx] for idx in best_indices]
    confidence = normalized_matrix[np.arange(len(best_indices)), best_indices]
    overall_scores = {
        template_id: float(np.mean(normalized_scores[template_id]))
        for template_id in template_ids
    }
    best_overall_template = max(overall_scores.items(), key=lambda item: item[1])[0]

    return {
        "scores": normalized_scores,
        "best_template_labels": best_template_labels,
        "confidence": confidence,
        "overall_scores": overall_scores,
        "best_overall_template": best_overall_template,
        "mean_paw_speed": mean_paw_speed,
        "body_speed": body_speed,
    }


def _build_template_timeline_df(valid_df, template_match, templates):
    template_ids = list(templates.keys())
    timeline_df = valid_df[["frame", "track_id"]].copy()
    timeline_df["best_template"] = template_match["best_template_labels"]
    timeline_df["best_template_confidence"] = template_match["confidence"]
    timeline_df["mean_paw_speed"] = template_match["mean_paw_speed"]
    timeline_df["body_speed"] = template_match["body_speed"]

    for template_id in template_ids:
        timeline_df[f"score_{template_id}"] = template_match["scores"][template_id]

    return timeline_df


def _window_phase_characteristics(theta_window):
    pair_count = theta_window.shape[1]
    phase_matrix = np.zeros((pair_count, pair_count), dtype=float)
    lock_matrix = np.eye(pair_count, dtype=float)
    for i in range(pair_count):
        for j in range(pair_count):
            if i == j:
                continue
            delta = _wrap_to_pi(theta_window[:, j] - theta_window[:, i])
            mean_vector = np.mean(np.exp(1j * delta))
            phase_matrix[i, j] = float(np.angle(mean_vector))
            lock_matrix[i, j] = float(np.abs(mean_vector))
    return phase_matrix, lock_matrix


def _build_pair_records(paws, observed, ideal):
    records = []
    short_labels = {paw: _paw_short_label(paw) for paw in paws}

    for i, source_paw in enumerate(paws):
        for j, target_paw in enumerate(paws):
            records.append(
                {
                    "source_paw": source_paw,
                    "target_paw": target_paw,
                    "source_label": short_labels[source_paw],
                    "target_label": short_labels[target_paw],
                    "observed_phase_offset_rad": float(observed["phase_matrix"][i, j]),
                    "observed_phase_offset_pi": float(observed["phase_matrix"][i, j] / np.pi),
                    "ideal_phase_offset_rad": float(ideal["phase_matrix"][i, j]),
                    "ideal_phase_offset_pi": float(ideal["phase_matrix"][i, j] / np.pi),
                    "phase_lock_value": float(observed["lock_matrix"][i, j]),
                    "observed_coordination_score": float(observed["coordination_matrix"][i, j]),
                    "ideal_coordination_score": float(ideal["coordination_matrix"][i, j]),
                    "observed_effective_coupling": float(observed["coupling_matrix"][i, j]),
                    "ideal_effective_coupling": float(ideal["coupling_matrix"][i, j]),
                    "phase_error_rad": float(abs(_wrap_to_pi(observed["phase_matrix"][i, j] - ideal["phase_matrix"][i, j]))),
                }
            )

    return records


def _build_summary(df, valid_df, paws, observed, ideal, cycle_stats, template_match, reference_template_id):
    pair_groups = _classify_pair_groups(paws)
    diagonal_lock = _pair_group_mean(observed["lock_matrix"], pair_groups["diagonal"])
    contralateral_lock = _pair_group_mean(observed["lock_matrix"], pair_groups["contralateral"])
    ipsilateral_lock = _pair_group_mean(observed["lock_matrix"], pair_groups["ipsilateral"])

    strongest_pair = _pick_pair(paws, observed["lock_matrix"], pick_max=True)
    weakest_pair = _pick_pair(paws, observed["lock_matrix"], pick_max=False)
    most_deviant_pair = _pick_pair_against_ideal(paws, observed["phase_matrix"], ideal["phase_matrix"])

    mean_cycle_frames = {}
    for paw in paws:
        cycle_lengths = cycle_stats[paw]["cycle_lengths"]
        mean_cycle_frames[paw] = float(np.mean(cycle_lengths)) if cycle_lengths else None

    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total_frame_count": int(len(df)),
        "valid_phase_frame_count": int(len(valid_df)),
        "valid_phase_fraction": float(len(valid_df) / len(df)) if len(df) else 0.0,
        "track_ids": sorted(int(track_id) for track_id in df["track_id"].dropna().unique()),
        "paws": paws,
        "paw_short_labels": {_paw_short_label(paw): paw for paw in paws},
        "mean_cycle_frames": mean_cycle_frames,
        "observed_order_1_mean": float(np.mean(observed["order_1"])),
        "observed_order_2_mean": float(np.mean(observed["order_2"])),
        "observed_order_1_std": float(np.std(observed["order_1"])),
        "observed_order_2_std": float(np.std(observed["order_2"])),
        "observed_omega_mean": float(np.mean(observed["omega"])),
        "observed_omega_std": float(np.std(observed["omega"])),
        "diagonal_lock_mean": diagonal_lock,
        "contralateral_lock_mean": contralateral_lock,
        "ipsilateral_lock_mean": ipsilateral_lock,
        "reference_template_id": reference_template_id,
        "best_matching_template": template_match["best_overall_template"],
        "template_overall_scores": template_match["overall_scores"],
        "strongest_pair": strongest_pair,
        "weakest_pair": weakest_pair,
        "most_deviant_pair": most_deviant_pair,
        "headline": _build_headline(template_match["best_overall_template"], template_match["overall_scores"], diagonal_lock),
        "subheadline": _build_subheadline(diagonal_lock, contralateral_lock, ipsilateral_lock, template_match["best_overall_template"]),
    }
    summary["callouts"] = _build_callouts(summary)
    return summary


def _build_report_data(df, valid_df, paws, observed, ideal, templates, cycle_stats, summary, template_match, reference_template_id, config):
    sample_count = min(int(getattr(config, "KURAMOTO_MAX_REPORT_SAMPLES", 240)), len(valid_df))
    if sample_count <= 0:
        sample_count = min(240, len(valid_df))
    sample_indices = np.linspace(0, len(valid_df) - 1, sample_count, dtype=int)
    sampled_frames = valid_df["frame"].to_numpy(dtype=int)[sample_indices].tolist()

    short_labels = [_paw_short_label(paw) for paw in paws]
    paw_palette = [_paw_color_hex(paw) for paw in paws]

    observed_theta = observed["theta"][sample_indices]
    observed_network = observed["network_matrix"]

    cycle_counts = {
        paw: int(len(cycle_stats[paw]["cycle_lengths"]))
        for paw in paws
    }

    metadata = {
        "input_video_path": getattr(config, "INPUT_VIDEO_PATH", ""),
        "input_labels_dir": getattr(config, "INPUT_LABELS_DIR", ""),
        "generated_at": summary["generated_at"],
        "total_frame_count": summary["total_frame_count"],
        "valid_phase_frame_count": summary["valid_phase_frame_count"],
        "valid_phase_fraction": summary["valid_phase_fraction"],
    }

    templates_export = {}
    for template_id, template in templates.items():
        template_theta = template["theta"][sample_indices]
        templates_export[template_id] = {
            "id": template["id"],
            "display_name": template["display_name"],
            "description": template["description"],
            "target_offsets_rad": template["target_offsets"].tolist(),
            "phase_matrix_rad": template["phase_matrix"].tolist(),
            "lock_matrix": template["lock_matrix"].tolist(),
            "coordination_matrix": template["coordination_matrix"].tolist(),
            "coupling_matrix": template["coupling_matrix"].tolist(),
            "network_matrix": template["network_matrix"].tolist(),
            "omega": template["omega"].tolist(),
            "frames": sampled_frames,
            "theta_samples": template_theta.tolist(),
            "wave_samples": np.sin(template_theta).tolist(),
            "order_1_samples": np.abs(np.mean(np.exp(1j * template_theta), axis=1)).tolist(),
            "order_2_samples": np.abs(np.mean(np.exp(2j * template_theta), axis=1)).tolist(),
        }

    return {
        "metadata": metadata,
        "summary": summary,
        "reference_template_id": reference_template_id,
        "paws": paws,
        "paw_labels": short_labels,
        "paw_full_labels": paws,
        "paw_colors": paw_palette,
        "cycle_counts": cycle_counts,
        "observed": {
            "phase_matrix_rad": observed["phase_matrix"].tolist(),
            "lock_matrix": observed["lock_matrix"].tolist(),
            "coordination_matrix": observed["coordination_matrix"].tolist(),
            "coupling_matrix": observed["coupling_matrix"].tolist(),
            "network_matrix": observed_network.tolist(),
            "omega": observed["omega"].tolist(),
            "frames": sampled_frames,
            "theta_samples": observed_theta.tolist(),
            "wave_samples": np.sin(observed_theta).tolist(),
            "order_1_samples": observed["order_1"][sample_indices].tolist(),
            "order_2_samples": observed["order_2"][sample_indices].tolist(),
            "body_speed_samples": template_match["body_speed"][sample_indices].tolist(),
            "mean_paw_speed_samples": template_match["mean_paw_speed"][sample_indices].tolist(),
        },
        "ideal": {
            "template_id": reference_template_id,
            "target_offsets_rad": ideal["target_offsets"].tolist(),
            "phase_matrix_rad": ideal["phase_matrix"].tolist(),
            "lock_matrix": ideal["lock_matrix"].tolist(),
            "coordination_matrix": ideal["coordination_matrix"].tolist(),
            "coupling_matrix": ideal["coupling_matrix"].tolist(),
            "network_matrix": ideal["network_matrix"].tolist(),
            "omega": ideal["omega"].tolist(),
        },
        "templates": templates_export,
        "template_match": {
            "overall_scores": template_match["overall_scores"],
            "best_template_id": template_match["best_overall_template"],
            "sampled_scores": {
                template_id: template_match["scores"][template_id][sample_indices].tolist()
                for template_id in templates
            },
            "sampled_labels": [template_match["best_template_labels"][idx] for idx in sample_indices],
            "sampled_confidence": template_match["confidence"][sample_indices].tolist(),
        },
    }


def _build_headline(best_template_id, template_overall_scores, diagonal_lock):
    label = best_template_id.replace("_", " ").title()
    confidence = template_overall_scores.get(best_template_id, 0.0)
    if confidence >= 0.45:
        return f"The measured gait most closely matches the {label} pattern."
    if diagonal_lock >= 0.75:
        return f"The measured gait sits between patterns, with the strongest pull toward {label}."
    return f"The measured gait does not fit one pattern cleanly, though {label} is the closest overall match."


def _build_subheadline(diagonal_lock, contralateral_lock, ipsilateral_lock, best_template_id):
    return (
        f"Diagonal pairing averages {diagonal_lock:.2f}, left-right pairing {contralateral_lock:.2f}, "
        f"and same-side pairing {ipsilateral_lock:.2f}. The closest overall match is {best_template_id.replace('_', ' ')}."
    )


def _build_callouts(summary):
    strongest = summary["strongest_pair"]
    weakest = summary["weakest_pair"]
    deviant = summary["most_deviant_pair"]
    return [
        f"The alternating-group rhythm score (R2) averages {summary['observed_order_2_mean']:.2f}.",
        f"The closest overall match across the recording is {summary['best_matching_template'].replace('_', ' ')} with score {summary['template_overall_scores'][summary['best_matching_template']]:.2f}.",
        f"The most stable measured pair is {strongest['pair']} with stability {strongest['value']:.2f}.",
        f"The least stable measured pair is {weakest['pair']} with stability {weakest['value']:.2f}.",
        f"The largest difference from the selected reference pattern is {deviant['pair']} at {deviant['phase_error_rad'] / np.pi:.2f} pi radians.",
    ]


def _pair_group_mean(matrix, pair_indices):
    if not pair_indices:
        return float("nan")
    values = [float(matrix[i, j]) for i, j in pair_indices]
    return float(np.mean(values))


def _pick_pair(paws, matrix, pick_max):
    candidates = []
    for i in range(len(paws)):
        for j in range(i + 1, len(paws)):
            candidates.append((float(matrix[i, j]), i, j))

    selected = max(candidates, key=lambda item: item[0]) if pick_max else min(candidates, key=lambda item: item[0])
    value, i, j = selected
    return {
        "pair": f"{_paw_short_label(paws[i])}-{_paw_short_label(paws[j])}",
        "value": value,
        "source_paw": paws[i],
        "target_paw": paws[j],
    }


def _pick_pair_against_ideal(paws, observed_phase_matrix, ideal_phase_matrix):
    candidates = []
    for i in range(len(paws)):
        for j in range(i + 1, len(paws)):
            phase_error = float(abs(_wrap_to_pi(observed_phase_matrix[i, j] - ideal_phase_matrix[i, j])))
            candidates.append((phase_error, i, j))

    phase_error, i, j = max(candidates, key=lambda item: item[0])
    return {
        "pair": f"{_paw_short_label(paws[i])}-{_paw_short_label(paws[j])}",
        "phase_error_rad": phase_error,
        "source_paw": paws[i],
        "target_paw": paws[j],
    }


def _classify_pair_groups(paws):
    groups = {"diagonal": [], "contralateral": [], "ipsilateral": []}
    paw_roles = [_paw_role(paw) for paw in paws]

    for i in range(len(paws)):
        for j in range(i + 1, len(paws)):
            side_i, limb_i = paw_roles[i]
            side_j, limb_j = paw_roles[j]
            if side_i == "unknown" or side_j == "unknown" or limb_i == "unknown" or limb_j == "unknown":
                continue
            if side_i != side_j and limb_i != limb_j:
                groups["diagonal"].append((i, j))
            elif side_i != side_j and limb_i == limb_j:
                groups["contralateral"].append((i, j))
            elif side_i == side_j and limb_i != limb_j:
                groups["ipsilateral"].append((i, j))

    return groups


def _infer_target_phase_offsets(paws, config, template_id="trot"):
    configured_offsets = getattr(config, "KURAMOTO_IDEAL_PHASE_OFFSETS", {})
    offsets = []
    for paw in paws:
        if template_id == "trot" and paw in configured_offsets:
            offsets.append(float(configured_offsets[paw]))
            continue

        side, limb = _paw_role(paw)
        offsets.append(_template_phase_for_role(template_id, side, limb))

    offsets = np.array(offsets, dtype=float)
    offsets = np.mod(offsets - offsets[0], 2.0 * np.pi)
    return offsets


def _template_phase_for_role(template_id, side, limb):
    template_id = template_id.lower()

    if template_id == "stationary":
        return 0.0

    if template_id == "trot":
        if limb == "fore" and side == "left":
            return 0.0
        if limb == "hind" and side == "right":
            return 0.0
        if limb == "fore" and side == "right":
            return float(np.pi)
        if limb == "hind" and side == "left":
            return float(np.pi)

    if template_id == "pace":
        if side == "left":
            return 0.0
        if side == "right":
            return float(np.pi)

    if template_id == "bound":
        if limb == "fore":
            return 0.0
        if limb == "hind":
            return float(np.pi)

    if template_id == "walk":
        walk_offsets = {
            ("left", "hind"): 0.0,
            ("left", "fore"): 0.5 * np.pi,
            ("right", "hind"): 1.0 * np.pi,
            ("right", "fore"): 1.5 * np.pi,
        }
        return float(walk_offsets.get((side, limb), 0.0))

    return 0.0


def _paw_role(paw_name):
    paw_lower = paw_name.lower()
    side = "left" if "left" in paw_lower else "right" if "right" in paw_lower else "unknown"
    if any(token in paw_lower for token in ("shoulder", "fore", "front")):
        limb = "fore"
    elif any(token in paw_lower for token in ("hip", "hind", "rear")):
        limb = "hind"
    else:
        limb = "unknown"
    return side, limb


def _paw_short_label(paw_name):
    side, limb = _paw_role(paw_name)
    side_short = "L" if side == "left" else "R" if side == "right" else paw_name[:1].upper()
    limb_short = "F" if limb == "fore" else "H" if limb == "hind" else paw_name[-1:].upper()
    return f"{side_short}{limb_short}"


def _paw_color_hex(paw_name):
    label = _paw_short_label(paw_name)
    palette = {
        "LF": "#3f8efc",
        "RF": "#f25f5c",
        "LH": "#f3b33d",
        "RH": "#2fa56a",
    }
    return palette.get(label, "#7d6f91")


def _wrap_to_pi(values):
    return (values + np.pi) % (2.0 * np.pi) - np.pi
