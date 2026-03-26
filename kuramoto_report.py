import json
import os


def write_kuramoto_report(report_path, report_data):
    os.makedirs(os.path.dirname(report_path) or ".", exist_ok=True)
    serialized_data = json.dumps(report_data).replace("</", "<\\/")
    html = _build_template().replace("__KURAMOTO_REPORT_DATA__", serialized_data)
    with open(report_path, "w", encoding="utf-8") as report_file:
        report_file.write(html)


def _build_template():
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Gait Coordination Report</title>
  <style>
    :root {
      --bg: #f8f4ef;
      --panel: rgba(255, 255, 255, 0.78);
      --panel-strong: rgba(255, 255, 255, 0.92);
      --border: rgba(105, 83, 61, 0.12);
      --shadow: 0 20px 55px rgba(76, 57, 40, 0.12);
      --text: #2d261f;
      --muted: #6b6258;
      --title: #1f2b3d;
      --accent: #2f7f91;
      --healthy: #2fa56a;
      --alert: #cf5d83;
      --radius: 26px;
    }

    * { box-sizing: border-box; }
    html, body { min-height: 100%; }
    body {
      margin: 0;
      font-family: "Inter", "Segoe UI Variable", "Segoe UI", sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at 12% 14%, rgba(47, 127, 145, 0.10), transparent 28%),
        radial-gradient(circle at 84% 18%, rgba(47, 165, 106, 0.11), transparent 28%),
        radial-gradient(circle at 50% 100%, rgba(207, 93, 131, 0.08), transparent 30%),
        linear-gradient(180deg, #fcfaf7 0%, #f8f4ef 100%);
      overflow-x: hidden;
    }

    .shell {
      width: min(1680px, calc(100vw - 28px));
      margin: 14px auto 28px;
    }

    .hero,
    .card {
      background: linear-gradient(180deg, var(--panel-strong), var(--panel));
      border: 1px solid var(--border);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      backdrop-filter: blur(12px);
      position: relative;
      overflow: hidden;
    }

    .hero { padding: 28px 30px 24px; }
    .card { padding: 22px 24px 24px; }

    .hero::after,
    .card::after {
      content: "";
      position: absolute;
      inset: auto -70px -70px auto;
      width: 240px;
      height: 240px;
      background: radial-gradient(circle, rgba(63, 142, 252, 0.14), transparent 66%);
      pointer-events: none;
    }

    .eyebrow {
      color: var(--accent);
      font-size: 0.77rem;
      font-weight: 800;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      margin-bottom: 10px;
    }

    h1, h2, h3 { margin: 0; color: var(--title); }
    h1 {
      font-size: clamp(1.8rem, 3.1vw, 3rem);
      line-height: 1.02;
      max-width: 1080px;
    }

    .subtitle {
      margin: 12px 0 0;
      max-width: 1000px;
      color: var(--muted);
      line-height: 1.6;
      font-size: 1.02rem;
    }

    .metric-grid,
    .insight-grid,
    .callout-grid,
    .layout,
    .network-grid,
    .matrix-grid {
      display: grid;
      gap: 16px;
    }

    .metric-grid {
      margin-top: 22px;
      grid-template-columns: repeat(5, minmax(0, 1fr));
    }

    .layout {
      margin-top: 20px;
      grid-template-columns: 1.45fr 1fr;
      gap: 20px;
    }

    .metric-card,
    .insight-card,
    .callout,
    .network-panel,
    .matrix-panel {
      background: rgba(255, 255, 255, 0.66);
      border: 1px solid var(--border);
      border-radius: 22px;
      padding: 16px 18px;
    }

    .network-grid,
    .matrix-grid,
    .insight-grid,
    .callout-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 20px;
    }

    .metric-card small,
    .section-note,
    .legend-line,
    .trace-caption,
    .network-caption small {
      display: block;
      color: var(--muted);
      line-height: 1.5;
    }

    .metric-card strong,
    .insight-card strong {
      display: block;
      margin-top: 8px;
      color: var(--title);
      line-height: 1.05;
    }

    .metric-card strong { font-size: 1.7rem; }
    .insight-card strong { font-size: 1.1rem; }

    .card-head {
      display: flex;
      justify-content: space-between;
      gap: 18px;
      align-items: flex-start;
      flex-wrap: wrap;
      margin-bottom: 18px;
    }

    .card-head p,
    .insight-card p,
    .callout p {
      margin: 8px 0 0;
      color: var(--muted);
      line-height: 1.55;
      max-width: 780px;
    }

    .pill {
      padding: 10px 14px;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.74);
      border: 1px solid var(--border);
      font-size: 0.83rem;
      font-weight: 700;
      color: var(--title);
      white-space: nowrap;
    }

    .network-svg,
    .trace-svg,
    .order-svg {
      width: 100%;
      height: auto;
      display: block;
    }

    .network-caption strong { display: block; margin: 10px 0 6px; }

    .toggle-row {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin: 4px 0 18px;
    }

    .toolbar-row,
    .status-grid,
    .score-list {
      display: grid;
      gap: 14px;
    }

    .toolbar-row {
      grid-template-columns: 1.1fr 1fr;
      margin: 2px 0 18px;
      align-items: start;
    }

    .playback-panel,
    .status-panel {
      background: rgba(255, 255, 255, 0.68);
      border: 1px solid var(--border);
      border-radius: 20px;
      padding: 14px 16px;
    }

    .playback-row,
    .slider-row {
      display: flex;
      gap: 10px;
      align-items: center;
      flex-wrap: wrap;
    }

    .slider-row {
      margin-top: 12px;
    }

    .status-grid {
      grid-template-columns: repeat(3, minmax(0, 1fr));
      margin-top: 12px;
    }

    .status-box {
      background: rgba(255, 255, 255, 0.78);
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 12px 14px;
    }

    .status-box small,
    .score-row small {
      display: block;
      color: var(--muted);
      line-height: 1.4;
    }

    .status-box strong {
      display: block;
      margin-top: 6px;
      font-size: 1.22rem;
      color: var(--title);
    }

    .score-list {
      margin-top: 10px;
    }

    .score-row {
      display: grid;
      grid-template-columns: 92px 1fr 52px;
      gap: 10px;
      align-items: center;
    }

    .score-bar {
      height: 10px;
      border-radius: 999px;
      background: rgba(107, 98, 88, 0.12);
      overflow: hidden;
    }

    .score-fill {
      height: 100%;
      border-radius: inherit;
      background: linear-gradient(90deg, rgba(47,127,145,0.55), rgba(47,165,106,0.92));
    }

    .play-btn,
    .playback-select {
      border: 1px solid rgba(107, 98, 88, 0.16);
      background: rgba(255, 255, 255, 0.9);
      color: var(--title);
      padding: 10px 12px;
      border-radius: 12px;
      font-weight: 800;
      font: inherit;
    }

    .play-btn {
      cursor: pointer;
    }

    .frame-slider {
      flex: 1 1 220px;
      accent-color: #2f7f91;
    }

    .toggle-btn {
      border: 1px solid rgba(107, 98, 88, 0.16);
      background: rgba(255, 255, 255, 0.8);
      color: var(--muted);
      padding: 11px 14px;
      border-radius: 14px;
      font-weight: 800;
      letter-spacing: 0.02em;
      cursor: pointer;
      transition: all .22s ease;
    }

    .toggle-btn.active {
      color: var(--title);
      border-color: rgba(47, 127, 145, 0.25);
      background: linear-gradient(180deg, rgba(255,255,255,0.98), rgba(228,241,244,0.92));
      box-shadow: 0 10px 18px rgba(47, 127, 145, 0.08);
    }

    .heatmap {
      display: grid;
      grid-template-columns: 72px repeat(4, minmax(0, 1fr));
      gap: 8px;
      align-items: stretch;
    }

    .cell,
    .axis-label {
      min-height: 58px;
      border-radius: 16px;
      display: flex;
      align-items: center;
      justify-content: center;
      text-align: center;
      padding: 8px;
      line-height: 1.15;
      font-size: 0.86rem;
    }

    .axis-label {
      background: rgba(246, 242, 236, 0.92);
      border: 1px solid var(--border);
      color: var(--muted);
      font-weight: 800;
      min-height: 42px;
    }

    .cell {
      border: 1px solid rgba(255, 255, 255, 0.42);
      font-weight: 800;
      color: #1f2630;
      box-shadow: inset 0 1px 0 rgba(255,255,255,0.26);
    }

    .footer-note {
      margin-top: 18px;
      text-align: center;
      color: var(--muted);
      font-size: 0.92rem;
      line-height: 1.6;
    }

    @media (max-width: 1240px) {
      .metric-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
      .layout { grid-template-columns: 1fr; }
    }

    @media (max-width: 940px) {
      .metric-grid,
      .network-grid,
      .matrix-grid,
      .insight-grid,
      .callout-grid {
        grid-template-columns: 1fr;
      }
      .toolbar-row,
      .status-grid {
        grid-template-columns: 1fr;
      }
      .heatmap {
        grid-template-columns: 64px repeat(4, minmax(0, 1fr));
      }
    }
  </style>
</head>
<body>
  <div class="shell">
    <section class="hero">
      <div class="eyebrow">Gait Coordination Report</div>
      <h1>Reference and measured four-limb coordination</h1>
      <p class="subtitle" id="heroSubtitle"></p>
      <div class="metric-grid" id="metricGrid"></div>
    </section>

    <section class="layout">
      <article class="card">
        <div class="card-head">
          <div>
            <h2>Coordination overview</h2>
            <p>Switch between walk, trot, pace, bound, and stationary patterns. The left panel shows the selected reference pattern and the right panel shows the measured movement.</p>
          </div>
          <div class="pill" id="networkPill"></div>
        </div>
        <div class="toolbar-row">
          <div>
            <div class="toggle-row" id="templateToggleRow"></div>
            <div class="section-note" id="templateExplain"></div>
          </div>
          <div class="playback-panel">
            <div class="playback-row">
              <button class="play-btn" id="playPauseBtn" type="button">Pause</button>
              <button class="play-btn" id="stepBackBtn" type="button">Back</button>
              <button class="play-btn" id="stepForwardBtn" type="button">Forward</button>
              <select class="playback-select" id="speedSelect" aria-label="Playback speed">
                <option value="0.5">0.5x</option>
                <option value="1" selected>1x</option>
                <option value="1.5">1.5x</option>
                <option value="2">2x</option>
              </select>
            </div>
            <div class="slider-row">
              <input class="frame-slider" id="frameSlider" type="range" min="0" max="0" value="0" />
              <div class="pill" id="frameReadout"></div>
            </div>
          </div>
        </div>
        <div class="network-grid">
          <div class="network-panel">
            <svg class="network-svg" id="idealNetwork" viewBox="0 0 360 320" aria-label="Reference coordination network"></svg>
            <div class="network-caption">
              <strong id="idealNetworkTitle">Selected reference</strong>
              <small id="idealNetworkCaption"></small>
            </div>
          </div>
          <div class="network-panel">
            <svg class="network-svg" id="observedNetwork" viewBox="0 0 360 320" aria-label="Measured coordination network"></svg>
            <div class="network-caption">
              <strong>Measured movement</strong>
              <small id="observedNetworkCaption"></small>
            </div>
          </div>
        </div>
        <div class="status-grid">
          <div class="status-box">
            <small>Likely gait at this moment</small>
            <strong id="liveGaitLabel"></strong>
            <small id="liveGaitDetail"></small>
          </div>
          <div class="status-box">
            <small>Selected reference</small>
            <strong id="selectedTemplateLabel"></strong>
            <small id="selectedTemplateDetail"></small>
          </div>
          <div class="status-box">
            <small>Movement level</small>
            <strong id="movementLabel"></strong>
            <small id="movementDetail"></small>
          </div>
        </div>
        <div class="status-panel">
          <small>How closely each reference pattern matches this moment</small>
          <div class="score-list" id="scoreList"></div>
        </div>
      </article>

      <article class="card">
        <div class="card-head">
          <div>
            <h2>Interpretation</h2>
            <p>This panel highlights the main coordination patterns seen in the recording.</p>
          </div>
          <div class="pill" id="headlinePill"></div>
        </div>
        <div class="section-note" id="headlineText"></div>
        <div class="insight-grid" id="insightGrid"></div>
        <div class="callout-grid" id="calloutGrid"></div>
      </article>
    </section>

    <section class="card" style="margin-top: 20px;">
        <div class="card-head">
          <div>
            <h2>4x4 comparison</h2>
            <p>Switch between relative timing, locking strength, and coordination strength. The left panel follows the selected reference pattern; the right panel shows the measured movement.</p>
          </div>
          <div class="pill" id="matrixPill"></div>
        </div>
      <div class="toggle-row" id="matrixToggleRow"></div>
      <div class="matrix-grid">
        <div class="matrix-panel">
          <h3>Selected reference</h3>
          <div id="idealMatrix"></div>
        </div>
        <div class="matrix-panel">
          <h3>Measured movement</h3>
          <div id="observedMatrix"></div>
        </div>
      </div>
      <div class="legend-line" id="matrixLegend"></div>
    </section>

    <section class="layout" style="margin-top: 20px;">
      <article class="card">
        <div class="card-head">
          <div>
            <h2>Phase traces</h2>
          <p>Dashed traces show the selected reference pattern. Solid traces show the measured limb timing. The guide line stays synchronized with the playback above.</p>
          </div>
          <div class="pill" id="traceModePill">Measured solid / reference dashed</div>
        </div>
        <svg class="trace-svg" id="traceSvg" viewBox="0 0 920 330" aria-label="Phase trace comparison"></svg>
        <div class="trace-caption" id="traceCaption"></div>
      </article>

      <article class="card">
        <div class="card-head">
          <div>
            <h2>Whole-body coordination</h2>
          <p>`R1` asks whether all four paws are moving together as one group. `R2` asks whether the paws are organizing into two alternating groups, which is common in many quadruped gait patterns. The dashed guide changes with the selected reference pattern.</p>
          </div>
          <div class="pill" id="orderModePill">Measured vs reference</div>
        </div>
        <svg class="order-svg" id="orderSvg" viewBox="0 0 920 280" aria-label="Order parameter comparison"></svg>
        <div class="trace-caption" id="orderCaption"></div>
      </article>
    </section>

    <div class="footer-note">This HTML is a sampled overview of the full Kuramoto analysis. Use the exported CSV files when you need the full-resolution time series.</div>
  </div>
  <script>
    const report = __KURAMOTO_REPORT_DATA__;
    const templateIds = Object.keys(report.templates || {});
    const defaultTemplateId = report.reference_template_id || report.template_match.best_template_id || templateIds[0];
    const state = {
      matrixMetric: "phase",
      sampleIndex: 0,
      selectedTemplate: defaultTemplateId,
      isPlaying: true,
      playbackSpeed: 1,
      lastTimestamp: 0,
      idealNetwork: null,
      observedNetwork: null,
    };

    const matrixOptions = {
      phase: {
        label: "Phase Offset",
        key: "phase_matrix_rad",
        legend: "Each cell shows the average timing of the column paw relative to the row paw. Values near zero mean moving together; values near +/-pi mean alternating.",
        formatter: value => value === null ? "--" : `${(value / Math.PI).toFixed(2)} pi`,
      },
      lock: {
        label: "Phase Locking",
        key: "lock_matrix",
        legend: "Values range from 0 to 1. Higher values mean the timing relationship between the two paws stays more stable over time.",
        formatter: value => value === null ? "--" : value.toFixed(2),
      },
      coupling: {
        label: "Coordination Strength",
        key: "coupling_matrix",
        legend: "Positive values mean two paws tend to pull toward the same timing. Negative values mean they tend to stay in alternating timing.",
        formatter: value => value === null ? "--" : value.toFixed(3),
      },
    };

    const pawLabels = report.paw_labels;
    const pawFullLabels = report.paw_full_labels;
    const pawColors = report.paw_colors;
    const frames = report.observed.frames;

    function currentTemplate() {
      return report.templates[state.selectedTemplate] || report.templates[defaultTemplateId] || report.templates[templateIds[0]];
    }

    function templateLabel(templateId) {
      const template = report.templates[templateId];
      return template ? template.display_name : templateId.replace(/_/g, " ").replace(/\\b\\w/g, char => char.toUpperCase());
    }

    function clamp(value, min, max) {
      return Math.min(max, Math.max(min, value));
    }

    function lerp(a, b, t) {
      return a + (b - a) * t;
    }

    function hexToRgb(hex) {
      const clean = hex.replace("#", "");
      const full = clean.length === 3 ? clean.split("").map(char => char + char).join("") : clean;
      return {
        r: parseInt(full.slice(0, 2), 16),
        g: parseInt(full.slice(2, 4), 16),
        b: parseInt(full.slice(4, 6), 16),
      };
    }

    function mix(colorA, colorB, t) {
      const a = hexToRgb(colorA);
      const b = hexToRgb(colorB);
      return `rgb(${Math.round(lerp(a.r, b.r, t))}, ${Math.round(lerp(a.g, b.g, t))}, ${Math.round(lerp(a.b, b.b, t))})`;
    }

    function colorForPhase(value) {
      if (value === null) return "rgba(230, 225, 217, 0.9)";
      const normalized = clamp((value + Math.PI) / (2 * Math.PI), 0, 1);
      if (normalized < 0.5) return mix("#cf5d83", "#fff5ef", normalized / 0.5);
      return mix("#fff5ef", "#3f8efc", (normalized - 0.5) / 0.5);
    }

    function colorForLock(value) {
      if (value === null) return "rgba(230, 225, 217, 0.9)";
      return mix("#f7efe7", "#2fa56a", clamp(value, 0, 1));
    }

    function colorForCoupling(value, limit) {
      if (value === null) return "rgba(230, 225, 217, 0.9)";
      const normalized = clamp((value + limit) / (2 * limit || 1), 0, 1);
      if (normalized < 0.5) return mix("#cf5d83", "#fff7f4", normalized / 0.5);
      return mix("#fff7f4", "#2fa56a", (normalized - 0.5) / 0.5);
    }

    function textColorForBackground(background) {
      const match = background.match(/rgb\\((\\d+), (\\d+), (\\d+)\\)/);
      if (!match) return "#1f2630";
      const [, r, g, b] = match.map(Number);
      const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
      return luminance < 0.62 ? "#ffffff" : "#1f2630";
    }

    function buildMetricCards() {
      const summary = report.summary;
      const metrics = [
        {
          label: "Usable frames",
          value: `${(summary.valid_phase_fraction * 100).toFixed(1)}%`,
          note: `${summary.valid_phase_frame_count} of ${summary.total_frame_count} frames contained enough paw information to compare all four limbs. This HTML shows a sampled overview of those valid frames.`,
        },
        {
          label: "Alternating rhythm",
          value: summary.observed_order_2_mean.toFixed(2),
          note: "Higher values suggest the limbs are organizing into alternating groups rather than moving as one cluster.",
        },
        {
          label: "Diagonal pairing",
          value: summary.diagonal_lock_mean.toFixed(2),
          note: "Shows how consistently the diagonal limb pairs keep their timing relationship.",
        },
        {
          label: "Least stable pair",
          value: summary.weakest_pair.pair,
          note: `Stability score ${summary.weakest_pair.value.toFixed(2)}.`,
        },
        {
          label: "Rhythm spread",
          value: summary.observed_omega_std.toFixed(3),
          note: "Lower values mean the four paws are closer to sharing the same overall stepping rhythm.",
        },
      ];

      document.getElementById("metricGrid").innerHTML = metrics.map(metric => `
        <div class="metric-card">
          <small>${metric.label}</small>
          <strong>${metric.value}</strong>
          <small>${metric.note}</small>
        </div>
      `).join("");
    }

    function buildHero() {
      const meta = report.metadata;
      const summary = report.summary;
      const labelsLabel = meta.input_labels_dir || "pose labels";
      const videoLabel = meta.input_video_path || "video";
      const sampledCount = report.observed.frames.length;
      const isSampledView = sampledCount < summary.valid_phase_frame_count;
      const samplingNote = isSampledView
        ? `This HTML is a sampled overview showing ${sampledCount} evenly spaced valid phase frames out of ${summary.valid_phase_frame_count}. Use the exported CSV files for the full-resolution time series.`
        : `This HTML shows all ${sampledCount} valid phase frames available for the Kuramoto analysis.`;
      document.getElementById("heroSubtitle").textContent =
        `${summary.headline} Source files: ${videoLabel} and ${labelsLabel}. Generated on ${meta.generated_at}. ${samplingNote}`;
      document.getElementById("networkPill").textContent = isSampledView
        ? `Sampled view: ${sampledCount} of ${summary.valid_phase_frame_count} valid frames`
        : `Full valid view: ${sampledCount} frames`;
      document.getElementById("headlinePill").textContent = `Closest overall match: ${templateLabel(report.template_match.best_template_id)}`;
      document.getElementById("headlineText").textContent = summary.subheadline;
      document.getElementById("matrixPill").textContent = "4 x 4 reference vs measured";
      document.getElementById("traceCaption").textContent =
        "Solid traces show the measured limb timing. Dashed traces switch with the selected reference pattern so users can compare different gait styles.";
      document.getElementById("orderCaption").textContent =
        `Measured R1 is ${summary.observed_order_1_mean.toFixed(2)} and measured R2 is ${summary.observed_order_2_mean.toFixed(2)}. Higher R1 means the paws behave more like one shared group. Higher R2 means the paws behave more like two alternating groups. The dashed guide updates when you switch between walk, trot, pace, bound, and stationary reference patterns.`;
      document.getElementById("idealNetworkCaption").textContent =
        "This panel updates when you switch the reference pattern so you can compare the same recording against different gait styles.";
      document.getElementById("observedNetworkCaption").textContent =
        "This panel summarizes how the measured limb timing behaves across the recording.";
    }

    function buildInsights() {
      const summary = report.summary;
      const cycleValues = Object.values(summary.mean_cycle_frames).filter(value => value !== null && value !== undefined);
      const insights = [
        {
          label: "Best overall match",
          value: templateLabel(report.template_match.best_template_id),
          text: `Average match score ${report.template_match.overall_scores[report.template_match.best_template_id].toFixed(2)} across the recording.`,
        },
        {
          label: "Most stable pair",
          value: summary.strongest_pair.pair,
          text: `Stability score ${summary.strongest_pair.value.toFixed(2)}.`,
        },
        {
          label: "Least stable pair",
          value: summary.weakest_pair.pair,
          text: `Stability score ${summary.weakest_pair.value.toFixed(2)}.`,
        },
        {
          label: "Mean cycle length",
          value: cycleValues.length ? cycleValues.map(value => value.toFixed(1)).join(" / ") : "n/a",
          text: "Reported in frames for paws with enough repeated stepping cycles.",
        },
      ];

      document.getElementById("insightGrid").innerHTML = insights.map(item => `
        <div class="insight-card">
          <small>${item.label}</small>
          <strong>${item.value}</strong>
          <p>${item.text}</p>
        </div>
      `).join("");

      document.getElementById("calloutGrid").innerHTML = report.summary.callouts.map(text => `
        <div class="callout"><p>${text}</p></div>
      `).join("");
    }

    function buildTemplateToggles() {
      const row = document.getElementById("templateToggleRow");
      row.innerHTML = templateIds.map(templateId => `
        <button class="toggle-btn ${templateId === state.selectedTemplate ? "active" : ""}" data-template="${templateId}">${templateLabel(templateId)}</button>
      `).join("");
      row.querySelectorAll("button").forEach(button => {
        button.addEventListener("click", () => {
          state.selectedTemplate = button.dataset.template;
          refreshTemplateViews();
        });
      });
    }

    function updateTemplateCopy() {
      const template = currentTemplate();
      const selectedScore = ((report.template_match.sampled_scores[state.selectedTemplate] || [])[state.sampleIndex] || 0) * 100;
      document.getElementById("templateExplain").textContent =
        `${template.display_name}: ${template.description}`;
      document.getElementById("idealNetworkTitle").textContent = `${template.display_name} reference`;
      document.getElementById("idealNetworkCaption").textContent =
        `${template.description} The dashed traces and the left network use this pattern at the current playback frame.`;
      document.getElementById("traceCaption").textContent =
        `Solid traces show the measured movement. Dashed traces show the selected ${template.display_name.toLowerCase()} reference pattern over the same sampled frames.`;
      document.getElementById("orderCaption").textContent =
        `Solid lines show the measured recording. Dashed lines show the ${template.display_name.toLowerCase()} reference pattern. Higher R1 means the paws act more like one shared group, while higher R2 means they act more like two alternating groups.`;
      document.getElementById("orderModePill").textContent = `${template.display_name} dashed / measured solid`;
      document.getElementById("selectedTemplateLabel").textContent = template.display_name;
      document.getElementById("selectedTemplateDetail").textContent =
        `Match at this moment ${(selectedScore).toFixed(0)}%. ${template.description}`;
    }

    function updateScoreList() {
      const rows = templateIds
        .map(templateId => ({
          templateId,
          score: (report.template_match.sampled_scores[templateId] || [])[state.sampleIndex] || 0,
        }))
        .sort((a, b) => b.score - a.score);

      document.getElementById("scoreList").innerHTML = rows.map(row => `
        <div class="score-row">
          <small>${templateLabel(row.templateId)}</small>
          <div class="score-bar"><div class="score-fill" style="width:${(row.score * 100).toFixed(1)}%"></div></div>
          <small>${(row.score * 100).toFixed(0)}%</small>
        </div>
      `).join("");
    }

    function updateStatusPanels() {
      const liveTemplateId = report.template_match.sampled_labels[state.sampleIndex] || state.selectedTemplate;
      const liveConfidence = (report.template_match.sampled_confidence || [])[state.sampleIndex] || 0;
      const meanPawSpeed = (report.observed.mean_paw_speed_samples || [])[state.sampleIndex] || 0;
      const bodySpeed = (report.observed.body_speed_samples || [])[state.sampleIndex] || 0;

      document.getElementById("liveGaitLabel").textContent = templateLabel(liveTemplateId);
      document.getElementById("liveGaitDetail").textContent =
        `Closest match at this moment ${(liveConfidence * 100).toFixed(0)}%.`;
      document.getElementById("movementLabel").textContent = `${meanPawSpeed.toFixed(1)} px/frame`;
      document.getElementById("movementDetail").textContent =
        `Average paw motion at this moment. Body motion is ${bodySpeed.toFixed(1)} px/frame.`;

      updateTemplateCopy();
      updateScoreList();
    }

    function buildMatrixToggles() {
      const row = document.getElementById("matrixToggleRow");
      row.innerHTML = Object.entries(matrixOptions).map(([key, option]) => `
        <button class="toggle-btn ${key === state.matrixMetric ? "active" : ""}" data-metric="${key}">${option.label}</button>
      `).join("");
      row.querySelectorAll("button").forEach(button => {
        button.addEventListener("click", () => {
          state.matrixMetric = button.dataset.metric;
          buildMatrixToggles();
          renderMatrices();
        });
      });
    }

    function renderHeatmap(targetId, matrix, metricKey, sharedLimit = null) {
      const target = document.getElementById(targetId);
      const option = matrixOptions[metricKey];
      const numericValues = matrix.flat().filter(value => typeof value === "number" && Number.isFinite(value));
      const couplingLimit = sharedLimit === null
        ? Math.max(...numericValues.map(value => Math.abs(value)), 0.001)
        : sharedLimit;
      let html = '<div class="heatmap">';
      html += '<div class="axis-label"></div>';
      html += pawLabels.map(label => `<div class="axis-label">${label}</div>`).join("");
      for (let i = 0; i < pawLabels.length; i++) {
        html += `<div class="axis-label">${pawLabels[i]}</div>`;
        for (let j = 0; j < pawLabels.length; j++) {
          const value = i === j ? null : matrix[i][j];
          let background = "rgba(236, 230, 221, 0.95)";
          if (metricKey === "phase") background = colorForPhase(value);
          if (metricKey === "lock") background = colorForLock(value);
          if (metricKey === "coupling") background = colorForCoupling(value, couplingLimit);
          const textColor = textColorForBackground(background);
          html += `<div class="cell" style="background:${background}; color:${textColor};">${i === j ? "--" : option.formatter(value)}</div>`;
        }
      }
      html += "</div>";
      target.innerHTML = html;
    }

    function renderMatrices() {
      const option = matrixOptions[state.matrixMetric];
      const template = currentTemplate();
      const sharedLimit = state.matrixMetric === "coupling"
        ? Math.max(
            ...template[option.key].flat().map(value => Math.abs(value)),
            ...report.observed[option.key].flat().map(value => Math.abs(value)),
            0.001
          )
        : null;
      renderHeatmap("idealMatrix", template[option.key], state.matrixMetric, sharedLimit);
      renderHeatmap("observedMatrix", report.observed[option.key], state.matrixMetric, sharedLimit);
      document.getElementById("matrixLegend").textContent = option.legend;
      document.getElementById("matrixPill").textContent = `${template.display_name} vs measured`;
    }

    function buildPath(values, rowIndex, rowCount, width, height) {
      const left = 72;
      const right = width - 24;
      const top = 20;
      const bottom = height - 26;
      const chartHeight = bottom - top;
      const band = chartHeight / rowCount;
      const rowCenter = top + band * rowIndex + band / 2;
      const amplitude = Math.min(19, band * 0.34);
      return values.map((value, index) => {
        const x = left + (index / (values.length - 1 || 1)) * (right - left);
        const y = rowCenter - value * amplitude;
        return `${index === 0 ? "M" : "L"}${x.toFixed(2)} ${y.toFixed(2)}`;
      }).join(" ");
    }

    function renderTraceSvg() {
      const svg = document.getElementById("traceSvg");
      const width = 920;
      const height = 330;
      const template = currentTemplate();
      const observedColumns = pawLabels.map((_, index) => report.observed.wave_samples.map(row => row[index]));
      const idealColumns = pawLabels.map((_, index) => template.wave_samples.map(row => row[index]));
      let out = "";
      for (let i = 0; i < pawLabels.length; i++) {
        const y = 24 + ((height - 58) / pawLabels.length) * (i + 0.5);
        out += `<line x1="72" y1="${y.toFixed(2)}" x2="${(width - 24).toFixed(2)}" y2="${y.toFixed(2)}" stroke="rgba(107,98,88,0.15)" stroke-width="1"/>`;
        out += `<text x="16" y="${(y + 5).toFixed(2)}" fill="#6b6258" font-size="14" font-weight="800">${pawLabels[i]}</text>`;
        out += `<text x="16" y="${(y + 22).toFixed(2)}" fill="#8b8178" font-size="12">${pawFullLabels[i]}</text>`;
      }
      for (let i = 0; i < 6; i++) {
        const x = 72 + i * ((width - 96) / 5);
        out += `<line x1="${x.toFixed(2)}" y1="24" x2="${x.toFixed(2)}" y2="${(height - 30).toFixed(2)}" stroke="rgba(107,98,88,0.10)" stroke-width="1"/>`;
      }
      pawLabels.forEach((_, index) => {
        out += `<path d="${buildPath(idealColumns[index], index, pawLabels.length, width, height)}" fill="none" stroke="${pawColors[index]}" stroke-width="2.4" opacity="0.45" stroke-dasharray="9 7"/>`;
        out += `<path d="${buildPath(observedColumns[index], index, pawLabels.length, width, height)}" fill="none" stroke="${pawColors[index]}" stroke-width="3.4"/>`;
      });
      out += `<line id="traceCursor" x1="72" y1="24" x2="72" y2="${(height - 30).toFixed(2)}" stroke="rgba(31,43,61,0.44)" stroke-width="2" stroke-dasharray="6 6"/>`;
      out += `<text x="${(width - 28).toFixed(2)}" y="${(height - 8).toFixed(2)}" text-anchor="end" fill="#6b6258" font-size="12">time</text>`;
      svg.innerHTML = out;
    }

    function pathFromSeries(values, width, height, yMax) {
      const left = 62;
      const right = width - 20;
      const top = 18;
      const bottom = height - 28;
      return values.map((value, index) => {
        const x = left + (index / (values.length - 1 || 1)) * (right - left);
        const y = bottom - (value / yMax) * (bottom - top);
        return `${index === 0 ? "M" : "L"}${x.toFixed(2)} ${y.toFixed(2)}`;
      }).join(" ");
    }

    function renderOrderSvg() {
      const svg = document.getElementById("orderSvg");
      const width = 920;
      const height = 280;
      const template = currentTemplate();
      const r1 = report.observed.order_1_samples;
      const r2 = report.observed.order_2_samples;
      const templateR1 = template.order_1_samples;
      const templateR2 = template.order_2_samples;
      let out = "";
      for (let tick = 0; tick <= 5; tick++) {
        const y = 18 + tick * ((height - 46) / 5);
        out += `<line x1="62" y1="${y.toFixed(2)}" x2="${(width - 20).toFixed(2)}" y2="${y.toFixed(2)}" stroke="rgba(107,98,88,0.10)" stroke-width="1"/>`;
        out += `<text x="16" y="${(y + 4).toFixed(2)}" fill="#6b6258" font-size="12">${(1 - tick / 5).toFixed(1)}</text>`;
      }
      for (let i = 0; i < 6; i++) {
        const x = 62 + i * ((width - 82) / 5);
        out += `<line x1="${x.toFixed(2)}" y1="18" x2="${x.toFixed(2)}" y2="${(height - 28).toFixed(2)}" stroke="rgba(107,98,88,0.08)" stroke-width="1"/>`;
      }
      out += `<path d="${pathFromSeries(templateR1, width, height, 1)}" fill="none" stroke="#cf5d83" stroke-width="2.2" opacity="0.42" stroke-dasharray="9 7"/>`;
      out += `<path d="${pathFromSeries(templateR2, width, height, 1)}" fill="none" stroke="#2fa56a" stroke-width="2.2" opacity="0.5" stroke-dasharray="9 7"/>`;
      out += `<path d="${pathFromSeries(r1, width, height, 1)}" fill="none" stroke="#cf5d83" stroke-width="3"/>`;
      out += `<path d="${pathFromSeries(r2, width, height, 1)}" fill="none" stroke="#2fa56a" stroke-width="3"/>`;
      out += `<line id="orderCursor" x1="62" y1="18" x2="62" y2="${(height - 28).toFixed(2)}" stroke="rgba(31,43,61,0.42)" stroke-width="2" stroke-dasharray="6 6"/>`;
      out += `<text x="88" y="34" fill="#cf5d83" font-size="13" font-weight="800">Measured R1</text>`;
      out += `<text x="194" y="34" fill="#2fa56a" font-size="13" font-weight="800">Measured R2</text>`;
      out += `<text x="300" y="34" fill="#9a7d8a" font-size="13" font-weight="800">${template.display_name} guide</text>`;
      out += `<text x="${(width - 24).toFixed(2)}" y="${(height - 8).toFixed(2)}" text-anchor="end" fill="#6b6258" font-size="12">time</text>`;
      svg.innerHTML = out;
    }

    function networkStroke(value, limit) {
      if (Math.abs(value) < 1e-6) return "rgba(146, 137, 127, 0.18)";
      const t = clamp(Math.abs(value) / limit, 0, 1);
      return value >= 0 ? mix("#eaf7f0", "#2fa56a", t) : mix("#fff1f5", "#cf5d83", t);
    }

    function networkOpacity(value, limit) {
      return 0.18 + 0.72 * clamp(Math.abs(value) / limit, 0, 1);
    }

    function renderNetwork(targetId, matrix, thetaSamples) {
      const svg = document.getElementById(targetId);
      const nodePositions = [
        { x: 110, y: 86 },
        { x: 250, y: 86 },
        { x: 110, y: 236 },
        { x: 250, y: 236 },
      ];
      const links = [
        { a: 0, b: 1 },
        { a: 2, b: 3 },
        { a: 0, b: 2 },
        { a: 1, b: 3 },
        { a: 0, b: 3 },
        { a: 1, b: 2 },
      ];
      const limit = Math.max(...matrix.flat().map(value => Math.abs(value)), 0.001);
      let out = "";
      links.forEach((link, index) => {
        const p1 = nodePositions[link.a];
        const p2 = nodePositions[link.b];
        const value = matrix[link.a][link.b];
        out += `<path id="${targetId}-link-${index}" d="M${p1.x} ${p1.y} L${p2.x} ${p2.y}" stroke="${networkStroke(value, limit)}" stroke-opacity="${networkOpacity(value, limit)}" stroke-width="${(2.5 + 7 * clamp(Math.abs(value) / limit, 0, 1)).toFixed(2)}" stroke-linecap="round"/>`;
      });
      nodePositions.forEach((node, index) => {
        out += `
          <g transform="translate(${node.x} ${node.y})">
            <circle r="42" fill="#ffffff" stroke="rgba(107,98,88,0.14)" stroke-width="2"/>
            <circle r="34" fill="none" stroke="${pawColors[index]}" stroke-width="8" opacity="0.82"/>
            <line id="${targetId}-needle-${index}" x1="0" y1="0" x2="18" y2="-18" stroke="#3b4654" stroke-width="5" stroke-linecap="round"/>
            <circle r="5" fill="#3b4654"/>
            <text text-anchor="middle" x="0" y="66" fill="#1f2b3d" font-size="15" font-weight="800">${pawLabels[index]}</text>
            <text text-anchor="middle" x="0" y="83" fill="#7f756b" font-size="11">${pawFullLabels[index]}</text>
          </g>
        `;
      });
      svg.innerHTML = out;
      return { targetId, thetaSamples };
    }

    function updateNetworkNeedles(network, sampleIndex) {
      const sample = network && network.thetaSamples ? network.thetaSamples[sampleIndex] : null;
      if (!sample) return;
      sample.forEach((phase, index) => {
        const degrees = phase * 180 / Math.PI;
        const needle = document.getElementById(`${network.targetId}-needle-${index}`);
        if (needle) needle.setAttribute("transform", `rotate(${degrees.toFixed(1)})`);
      });
    }

    function updateCursors(sampleIndex) {
      const widthTrace = 920;
      const leftTrace = 72;
      const rightTrace = widthTrace - 24;
      const xTrace = leftTrace + (sampleIndex / (frames.length - 1 || 1)) * (rightTrace - leftTrace);
      const traceCursor = document.getElementById("traceCursor");
      if (traceCursor) {
        traceCursor.setAttribute("x1", xTrace.toFixed(2));
        traceCursor.setAttribute("x2", xTrace.toFixed(2));
      }

      const widthOrder = 920;
      const leftOrder = 62;
      const rightOrder = widthOrder - 20;
      const xOrder = leftOrder + (sampleIndex / (frames.length - 1 || 1)) * (rightOrder - leftOrder);
      const orderCursor = document.getElementById("orderCursor");
      if (orderCursor) {
        orderCursor.setAttribute("x1", xOrder.toFixed(2));
        orderCursor.setAttribute("x2", xOrder.toFixed(2));
      }
    }

    function renderNetworks() {
      const template = currentTemplate();
      state.idealNetwork = renderNetwork("idealNetwork", template.network_matrix, template.theta_samples);
      state.observedNetwork = renderNetwork("observedNetwork", report.observed.network_matrix, report.observed.theta_samples);
      updateNetworkNeedles(state.idealNetwork, state.sampleIndex);
      updateNetworkNeedles(state.observedNetwork, state.sampleIndex);
    }

    function updateFrameReadout() {
      const frameValue = frames[state.sampleIndex] || 0;
      const slider = document.getElementById("frameSlider");
      if (slider) slider.value = String(state.sampleIndex);
      document.getElementById("frameReadout").textContent = `Frame ${frameValue}`;
      const sampledCount = report.observed.frames.length;
      const validCount = report.summary.valid_phase_frame_count;
      document.getElementById("networkPill").textContent =
        `${currentTemplate().display_name} vs measured | sampled frame ${frameValue} | ${sampledCount}/${validCount} valid frames shown`;
    }

    function setSampleIndex(sampleIndex) {
      if (!frames.length) return;
      state.sampleIndex = ((sampleIndex % frames.length) + frames.length) % frames.length;
      updateNetworkNeedles(state.idealNetwork, state.sampleIndex);
      updateNetworkNeedles(state.observedNetwork, state.sampleIndex);
      updateCursors(state.sampleIndex);
      updateFrameReadout();
      updateStatusPanels();
    }

    function updatePlaybackButton() {
      document.getElementById("playPauseBtn").textContent = state.isPlaying ? "Pause" : "Play";
    }

    function bindPlaybackControls() {
      const slider = document.getElementById("frameSlider");
      slider.max = Math.max(frames.length - 1, 0);
      slider.addEventListener("input", () => {
        state.isPlaying = false;
        state.lastTimestamp = 0;
        updatePlaybackButton();
        setSampleIndex(Number(slider.value || 0));
      });

      document.getElementById("playPauseBtn").addEventListener("click", () => {
        state.isPlaying = !state.isPlaying;
        state.lastTimestamp = 0;
        updatePlaybackButton();
      });

      document.getElementById("stepBackBtn").addEventListener("click", () => {
        state.isPlaying = false;
        state.lastTimestamp = 0;
        updatePlaybackButton();
        setSampleIndex(state.sampleIndex - 1);
      });

      document.getElementById("stepForwardBtn").addEventListener("click", () => {
        state.isPlaying = false;
        state.lastTimestamp = 0;
        updatePlaybackButton();
        setSampleIndex(state.sampleIndex + 1);
      });

      document.getElementById("speedSelect").addEventListener("change", event => {
        state.playbackSpeed = Number(event.target.value || 1);
        state.lastTimestamp = 0;
      });
    }

    function refreshTemplateViews() {
      buildTemplateToggles();
      renderMatrices();
      renderTraceSvg();
      renderOrderSvg();
      renderNetworks();
      setSampleIndex(state.sampleIndex);
    }

    function animateNetworks() {
      function step(timestamp) {
        if (state.isPlaying && frames.length) {
          const frameInterval = 160 / Math.max(state.playbackSpeed, 0.1);
          if (!state.lastTimestamp || timestamp - state.lastTimestamp >= frameInterval) {
            setSampleIndex(state.sampleIndex + 1);
            state.lastTimestamp = timestamp;
          }
        }
        requestAnimationFrame(step);
      }
      requestAnimationFrame(step);
    }

    function init() {
      buildMetricCards();
      buildHero();
      buildInsights();
      buildTemplateToggles();
      buildMatrixToggles();
      bindPlaybackControls();
      updatePlaybackButton();
      refreshTemplateViews();
      updateCursors(0);
      animateNetworks();
    }

    init();
  </script>
</body>
</html>
"""
