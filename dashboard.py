# dashboard.py
import cv2
import numpy as np
import pandas as pd
from collections import deque, defaultdict
import logging

logger = logging.getLogger(__name__)

class Dashboard:
    """A clean dashboard focusing on pose, ROI, and gait analysis visualization."""
    def __init__(self, config, video_height, fps=30):
        self.config = config
        self.width = config.DASHBOARD_WIDTH
        self.video_height = video_height
        self.fps = fps

        # --- Colors & Font ---
        self.colors = config.BEHAVIOR_COLORS
        self.font = cv2.FONT_HERSHEY_SIMPLEX
        self.font_scale, self.title_scale = 0.5, 0.6
        self.line_spacing, self.section_spacing = 15, 10
        self.text_color, self.placeholder_color = (255, 255, 255), (180, 180, 180)
        self.bg_color = (20, 20, 20)

        # --- Data History for Graphs & Plots ---
        graph_window_frames = int(fps * config.GRAPH_WINDOW_SECONDS)
        self.speed_history = deque(maxlen=graph_window_frames)
        self.posture_history = deque(maxlen=graph_window_frames)
        self.stride_length_history = deque(maxlen=10)
        self.stride_speed_history = deque(maxlen=10)
        
        hildebrand_window_frames = int(fps * config.HILDEBRAND_WINDOW_SECONDS)
        self.hildebrand_history = defaultdict(lambda: {
            paw: deque(maxlen=hildebrand_window_frames) for paw in config.PAW_ORDER_HILDEBRAND
        })

    def _draw_title(self, p, y, t):
        cv2.putText(p, t, (15, y), self.font, self.title_scale, self.text_color, 1, cv2.LINE_AA)
        return y + self.line_spacing + self.section_spacing

    def _update_histories(self, stats):
        """Updates the data deques for real-time graphs."""
        self.speed_history.append(stats.get('speed_mean', 0))
        self.posture_history.append(stats.get('posture_mean', 0))

        if new_stride := stats.get('newly_completed_stride'):
            self.stride_length_history.append(new_stride.get('stride_length', 0))
            self.stride_speed_history.append(new_stride.get('stride_speed', 0))
        
        for animal in stats.get('animals_on_frame', []):
            track_id = animal['track_id']
            if self.config.PAW_ORDER_HILDEBRAND:
                for paw in self.config.PAW_ORDER_HILDEBRAND:
                    self.hildebrand_history[track_id][paw].append(animal.get(f'{paw}_phase', 'unknown'))

    def _draw_live_metrics(self, p, y, animals):
        """Displays live pose metrics for each detected animal."""
        y = self._draw_title(p, y, "Live Animal Metrics")
        if not animals:
            cv2.putText(p, "No animals detected.", (20, y), self.font, self.font_scale, self.placeholder_color, 1)
            return y + self.line_spacing

        for animal in animals[:self.config.MAX_LIST_ITEMS]:
            cv2.putText(p, f"ID {animal['track_id']}", (20, y), self.font, self.font_scale, self.text_color, 1)
            y += self.line_spacing
            metrics = {
                "Elong": animal.get('elongation', np.nan),
                "Angle": animal.get('body_angle_deg', np.nan),
                "Turn": animal.get('turning_speed_deg_per_frame', np.nan)
            }
            metric_text = ", ".join([f"{k}: {v:.1f}" if pd.notna(v) else f"{k}: N/A" for k, v in metrics.items()])
            cv2.putText(p, metric_text, (25, y), self.font, 0.4, self.text_color, 1)
            y += self.line_spacing
        return y + self.section_spacing

    def _draw_list_section(self, p, y, title, data, placeholder):
        """Draws a simple list of key-value pairs, used for ROI stats."""
        y = self._draw_title(p, y, title)
        if not data:
            cv2.putText(p, placeholder, (20, y), self.font, self.font_scale, self.placeholder_color, 1)
            return y + self.line_spacing
        
        items = sorted(data.items())
        for i, (key, val) in enumerate(items[:self.config.MAX_LIST_ITEMS]):
            text = f"{key}: {val}"
            cv2.putText(p, text, (20, y), self.font, self.font_scale, self.text_color, 1)
            y += self.line_spacing
        return y + self.section_spacing

    def _draw_hildebrand_gait_diagram(self, p, y, animals):
        """Visualizes the stance/swing phase of each paw over time."""
        y = self._draw_title(p, y, "Hildebrand Gait Diagram")
        if not self.config.PAW_ORDER_HILDEBRAND:
            cv2.putText(p, "Gait analysis disabled.", (20, y), self.font, self.font_scale, self.placeholder_color, 1)
            return y + self.line_spacing

        active_ids = {a['track_id'] for a in animals}
        if not active_ids:
            cv2.putText(p, "No animals for gait plot.", (20, y), self.font, self.font_scale, self.placeholder_color, 1)
            return y + self.line_spacing

        h, w, origin = 14, self.width - 40, (20, y)
        for i, track_id in enumerate(sorted(list(active_ids))[:2]):
            cv2.putText(p, f"ID {track_id}", (origin[0], y - 5), self.font, 0.4, self.text_color, 1)
            for j, paw in enumerate(self.config.PAW_ORDER_HILDEBRAND):
                paw_history = self.hildebrand_history[track_id][paw]
                if not paw_history: continue
                y_pos, bar_start_x, bar_w = y + j * (h + 2), origin[0] + 60, w - 60
                cv2.putText(p, paw.replace(" Paw", ""), (origin[0], y_pos + 10), self.font, 0.4, self.text_color, 1)
                for k, phase in enumerate(paw_history):
                    color = self.colors.get(phase, (50, 50, 50))
                    x1 = bar_start_x + int(k * (bar_w / len(paw_history)))
                    x2 = bar_start_x + int((k + 1) * (bar_w / len(paw_history)))
                    cv2.rectangle(p, (x1, y_pos), (x2, y_pos + h), color, -1)
            y += len(self.config.PAW_ORDER_HILDEBRAND) * (h + 2) + 10
        return y + self.section_spacing

    def _draw_graph(self, p, y, title, history, color, is_bar=False, max_len=None):
        """Draws a generic line or bar graph for a given data history."""
        y = self._draw_title(p, y, title)
        h, w, origin = 50, self.width - 40, (20, y)
        cv2.rectangle(p, origin, (origin[0] + w, origin[1] + h), (40, 40, 40), -1)
        
        pts = list(history)
        if len(pts) > 1:
            max_val = max(pts) if max(pts) > 0 else 1.0
            num_points = len(pts)
            if is_bar:
                bar_w = w / (max_len or num_points)
                for i, val in enumerate(pts):
                    p1 = (origin[0] + int(i * bar_w), origin[1] + h)
                    p2 = (origin[0] + int((i + 1) * bar_w - 1), origin[1] + h - int((val / max_val) * h))
                    cv2.rectangle(p, p1, p2, color, -1)
            else:
                line_len = max_len or num_points
                if line_len > 1:
                    pts_coords = [(origin[0] + int(i * (w / (line_len - 1))), origin[1] + h - int((val / max_val) * h)) for i, val in enumerate(pts)]
                    cv2.polylines(p, [np.array(pts_coords)], isClosed=False, color=color, thickness=1, lineType=cv2.LINE_AA)
        return y + h + self.section_spacing

    def update_and_draw(self, canvas, stats, frame_number):
        """Main drawing function to create and attach the dashboard panel."""
        panel = np.full((self.video_height, self.width, 3), self.bg_color, dtype=np.uint8)
        self._update_histories(stats)

        # --- Draw all sections onto the panel ---
        y = 15
        cv2.putText(panel, f"Frame: {frame_number}", (15, y + 10), self.font, self.title_scale, self.text_color, 1)
        y += 40

        # Split dashboard into two columns for a balanced layout
        col1_y, col2_y = y, y
        col1_panel, col2_panel = panel[:, :self.width // 2], panel[:, self.width // 2:]

        # --- Column 1: Live metrics, gait, and pose graphs ---
        col1_y = self._draw_live_metrics(col1_panel, col1_y, stats.get('animals_on_frame', []))
        col1_y = self._draw_hildebrand_gait_diagram(col1_panel, col1_y, stats.get('animals_on_frame', []))
        col1_y = self._draw_graph(col1_panel, col1_y, "Body Speed (px/f)", self.speed_history, (75, 180, 255), max_len=int(self.fps * self.config.GRAPH_WINDOW_SECONDS))
        self._draw_graph(col1_panel, col1_y, "Posture Variability (px)", self.posture_history, (255, 200, 100), max_len=int(self.fps * self.config.GRAPH_WINDOW_SECONDS))

        # --- Column 2: ROI stats and stride graphs ---
        roi_stats = stats.get('roi_stats', {})
        col2_y = self._draw_list_section(col2_panel, col2_y, "ROI Total Time (s)", {k: f"{v['time_s']:.1f}" for k, v in roi_stats.items()}, "No ROI data.")
        col2_y = self._draw_list_section(col2_panel, col2_y, "ROI Entries", {k: v['entries'] for k, v in roi_stats.items()}, "No ROI entries.")
        col2_y = self._draw_graph(col2_panel, col2_y, "Stride Lengths (px)", self.stride_length_history, (100, 255, 100), is_bar=True, max_len=10)
        self._draw_graph(col2_panel, col2_y, "Stride Speeds (px/f)", self.stride_speed_history, (100, 200, 255), is_bar=True, max_len=10)

        canvas[:, -self.width:] = panel
        return canvas