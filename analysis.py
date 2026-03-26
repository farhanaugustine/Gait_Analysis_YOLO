# analysis.py
import pandas as pd
import numpy as np
import cv2
import logging
from collections import defaultdict

import config

logger = logging.getLogger(__name__)

CALC_ALIAS_PREFIX = "_calc_"
CALC_BODY_ANGLE_START_ALIAS = "_calc_body_angle_start"
CALC_BODY_ANGLE_END_ALIAS = "_calc_body_angle_end"
CALC_ELONGATION_START_ALIAS = "_calc_elongation_start"
CALC_ELONGATION_END_ALIAS = "_calc_elongation_end"

def process_data(df, rois):
    if df.empty: return df, pd.DataFrame()
    df = df.sort_values(by=['track_id', 'frame']).reset_index(drop=True)
    logger.info("Calculating pose metrics...")
    df = calculate_pose_metrics(df, config)
    logger.info("Assigning ROIs to detections...")
    df['current_roi'] = assign_rois(df, rois)
    logger.info("Performing gait and step analysis (if keypoints are available)...")
    gait_df = perform_gait_analysis(df, config)
    return df, gait_df

def perform_gait_analysis(df, config):
    paw_names = config.GAIT_PAWS
    if not paw_names:
        logger.warning("Gait analysis is disabled because 'GAIT_PAWS' is empty in the config.")
        return pd.DataFrame()
    if not all(f'{p}_x' in df.columns for p in paw_names):
        logger.warning("Required paw keypoints for gait analysis not found in data. Skipping.")
        return pd.DataFrame()

    for paw in paw_names:
        df[f'{paw}_speed'] = np.sqrt(df.groupby('track_id')[f'{paw}_x'].diff()**2 + df.groupby('track_id')[f'{paw}_y'].diff()**2)
        df[f'{paw}_phase'] = np.where(df[f'{paw}_speed'] < config.PAW_SPEED_THRESHOLD_PX_PER_FRAME, 'stance', 'swing')

    gait_events = []
    for track_id, track_df in df.groupby('track_id'):
        for paw in paw_names:
            phase, prev_phase = track_df[f'{paw}_phase'], track_df[f'{paw}_phase'].shift(1)
            toe_offs = track_df[(phase == 'swing') & (prev_phase == 'stance')]
            foot_strikes = track_df[(phase == 'stance') & (prev_phase == 'swing')]
            for _, row in toe_offs.iterrows():
                gait_events.append({'track_id': track_id, 'frame': row['frame'], 'paw': paw, 'event': 'toe_off', 'x': row[f'{paw}_x'], 'y': row[f'{paw}_y']})
            for _, row in foot_strikes.iterrows():
                gait_events.append({'track_id': track_id, 'frame': row['frame'], 'paw': paw, 'event': 'foot_strike', 'x': row[f'{paw}_x'], 'y': row[f'{paw}_y']})

    if not gait_events: return pd.DataFrame()
    events_df = pd.DataFrame(gait_events).sort_values(by=['track_id', 'frame'])
    all_cycles_df = calculate_all_gait_metrics(events_df, df, config)
    return all_cycles_df

def calculate_all_gait_metrics(events_df, full_df, config):
    all_cycles_data = []
    ref_paw = config.STRIDE_REFERENCE_PAW
    other_paws = [p for p in config.GAIT_PAWS if p != ref_paw]
    ref_side, ref_limb = _paw_role(ref_paw)
    opposing_paw_name = next(
        (
            paw for paw in other_paws
            if _paw_role(paw)[0] != ref_side and _paw_role(paw)[1] == ref_limb
        ),
        None,
    )

    if 'center_x' in full_df.columns and 'center_y' in full_df.columns:
        full_df['body_speed'] = np.sqrt(
            full_df.groupby('track_id')['center_x'].diff()**2 +
            full_df.groupby('track_id')['center_y'].diff()**2
        )
    else:
        full_df['body_speed'] = 0

    ref_paw_events = events_df[events_df['paw'] == ref_paw]
    for track_id, track_events in ref_paw_events.groupby('track_id'):
        ref_foot_strikes = track_events[track_events['event'] == 'foot_strike'].sort_values('frame')
        for i in range(len(ref_foot_strikes) - 1):
            start_strike, end_strike = ref_foot_strikes.iloc[i], ref_foot_strikes.iloc[i+1]
            stride_length = np.linalg.norm([start_strike['x'] - end_strike['x'], start_strike['y'] - end_strike['y']])
            stride_frames = full_df[(full_df['track_id'] == track_id) & (full_df['frame'] >= start_strike['frame']) & (full_df['frame'] <= end_strike['frame'])]
            stride_speed = stride_frames['body_speed'].mean()
            step_length, step_width = np.nan, np.nan
            
            if opposing_paw_name:
                opposing_strikes = events_df[(events_df['track_id'] == track_id) & (events_df['paw'] == opposing_paw_name) & (events_df['event'] == 'foot_strike')]
                opposing_strike_df = opposing_strikes[(opposing_strikes['frame'] > start_strike['frame']) & (opposing_strikes['frame'] < end_strike['frame'])]
                if not opposing_strike_df.empty:
                    opposing_strike = opposing_strike_df.iloc[0]
                    step_length = np.linalg.norm([opposing_strike['x'] - start_strike['x'], opposing_strike['y'] - start_strike['y']])
                    p1, p2, p3 = np.array([start_strike['x'], start_strike['y']]), np.array([end_strike['x'], end_strike['y']]), np.array([opposing_strike['x'], opposing_strike['y']])
                    if np.linalg.norm(p2-p1) > 0:
                        step_width = np.abs(np.cross(p2-p1, p1-p3)) / np.linalg.norm(p2-p1)
            
            all_cycles_data.append({
                'track_id': track_id, 'paw': ref_paw, 'start_frame': start_strike['frame'], 'end_frame': end_strike['frame'],
                'stride_length': stride_length, 'stride_speed': stride_speed, 'step_length': step_length, 'step_width': step_width
            })
    return pd.DataFrame(all_cycles_data)

def calculate_pose_metrics(df, config):
    df['dx'] = df.groupby('track_id')['center_x'].diff()
    df['dy'] = df.groupby('track_id')['center_y'].diff()
    df['speed'] = np.sqrt(df['dx']**2 + df['dy']**2)
    p1_elong, p2_elong = _resolve_metric_connection(
        config,
        "ELONGATION_KEYPOINT_INDICES",
        "ELONGATION_CONNECTION",
        (CALC_ELONGATION_START_ALIAS, CALC_ELONGATION_END_ALIAS),
    )

    if p1_elong and f'{p1_elong}_x' in df.columns and f'{p2_elong}_x' in df.columns:
        df['elongation'] = np.linalg.norm(df[[f'{p1_elong}_x', f'{p1_elong}_y']].values - df[[f'{p2_elong}_x', f'{p2_elong}_y']].values, axis=1)
        df['posture_variability'] = df.groupby('track_id')['elongation'].transform(lambda x: x.rolling(window=30, min_periods=1).std())
    else:
        df[['elongation', 'posture_variability']] = np.nan

    p1_angle, p2_angle = _resolve_metric_connection(
        config,
        "BODY_ANGLE_KEYPOINT_INDICES",
        "BODY_ANGLE_CONNECTION",
        (CALC_BODY_ANGLE_START_ALIAS, CALC_BODY_ANGLE_END_ALIAS),
    )

    if p1_angle and f'{p1_angle}_x' in df.columns and f'{p2_angle}_x' in df.columns:
        vec = df[[f'{p2_angle}_x', f'{p2_angle}_y']].values - df[[f'{p1_angle}_x', f'{p1_angle}_y']].values
        rad = np.arctan2(vec[:, 1], vec[:, 0])
        df['body_angle_rad'] = rad
        angle_diff = df.groupby('track_id')['body_angle_rad'].diff()
        angle_diff_wrapped = np.arctan2(np.sin(angle_diff), np.cos(angle_diff))
        df['body_angle_deg'] = np.degrees(rad)
        df['turning_speed_rad_per_frame'] = angle_diff_wrapped
        df['turning_speed_deg_per_frame'] = np.degrees(angle_diff_wrapped)
    else:
        df[['body_angle_rad', 'body_angle_deg', 'turning_speed_rad_per_frame', 'turning_speed_deg_per_frame']] = np.nan

    calc_columns = [column for column in df.columns if column.startswith(CALC_ALIAS_PREFIX)]
    if calc_columns:
        df = df.drop(columns=calc_columns)
    return df

def assign_rois(df, rois):
    if not rois: return 'None'
    def get_roi(row):
        point = (row['center_x'], row['center_y'])
        if pd.isna(point[0]): return 'None'
        for roi in rois:
            if cv2.pointPolygonTest(roi['coords'], point, False) >= 0: return roi['name']
        return 'None'
    return df.apply(get_roi, axis=1)

def calculate_roi_event_timeline(df):
    timeline = defaultdict(list)
    for _, track_df in df.groupby('track_id'):
        last, current = track_df['current_roi'].shift(1).fillna('None'), track_df['current_roi'].fillna('None')
        for idx, row in track_df[last != current].iterrows():
            frame, lr, cr = int(row['frame']), last.loc[idx], current.loc[idx]
            if lr != 'None': timeline[frame].append({'type': 'exit', 'roi_name': lr})
            if cr != 'None': timeline[frame].append({'type': 'entry', 'roi_name': cr})
    return timeline


def _normalize_connection(connection):
    if connection is None:
        return None
    if isinstance(connection, (list, tuple)) and len(connection) == 2 and all(connection):
        return connection[0], connection[1]
    return None


def _resolve_metric_connection(config, index_field_name, legacy_connection_name, calc_aliases):
    index_pair = getattr(config, index_field_name, None)
    if isinstance(index_pair, (list, tuple)) and len(index_pair) == 2:
        return calc_aliases

    connection = _normalize_connection(getattr(config, legacy_connection_name, None))
    if connection:
        return connection
    return None, None


def _paw_role(paw_name):
    paw_lower = paw_name.lower()
    side = 'left' if 'left' in paw_lower else 'right' if 'right' in paw_lower else 'unknown'
    if any(token in paw_lower for token in ('front', 'fore', 'shoulder')):
        limb = 'front'
    elif any(token in paw_lower for token in ('rear', 'hind', 'hip')):
        limb = 'rear'
    else:
        limb = 'unknown'
    return side, limb
