import json
import os


def write_gait_review_report(report_path, report_data):
    os.makedirs(os.path.dirname(report_path) or ".", exist_ok=True)
    serialized_data = json.dumps(report_data).replace("</", "<\\/")
    html = _build_template().replace("__GAIT_REVIEW_REPORT_DATA__", serialized_data)
    with open(report_path, "w", encoding="utf-8") as report_file:
        report_file.write(html)


def _build_template():
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Gait Review Report</title>
  <style>
    :root {
      --bg: #f6f3ef;
      --panel: rgba(255, 255, 255, 0.86);
      --panel-strong: rgba(255, 255, 255, 0.95);
      --border: rgba(88, 74, 60, 0.12);
      --shadow: 0 18px 42px rgba(63, 49, 35, 0.10);
      --text: #2b241d;
      --muted: #6a6259;
      --title: #1d2a3a;
      --accent: #2f7f91;
      --good: #2fa56a;
      --warn: #d67a44;
      --soft: #efe8df;
      --radius: 24px;
    }

    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Inter", "Segoe UI Variable", "Segoe UI", sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at 12% 18%, rgba(47, 127, 145, 0.10), transparent 28%),
        radial-gradient(circle at 88% 14%, rgba(47, 165, 106, 0.10), transparent 28%),
        linear-gradient(180deg, #fbf8f4 0%, #f6f3ef 100%);
    }

    .shell {
      width: min(1600px, calc(100vw - 26px));
      margin: 14px auto 28px;
    }

    .hero,
    .card {
      background: linear-gradient(180deg, var(--panel-strong), var(--panel));
      border: 1px solid var(--border);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      backdrop-filter: blur(12px);
    }

    .hero {
      padding: 28px 30px 24px;
    }

    .card {
      padding: 22px 24px 24px;
      margin-top: 20px;
    }

    .eyebrow {
      color: var(--accent);
      font-size: 0.78rem;
      font-weight: 800;
      letter-spacing: 0.13em;
      text-transform: uppercase;
      margin-bottom: 10px;
    }

    h1, h2, h3 {
      margin: 0;
      color: var(--title);
    }

    h1 {
      font-size: clamp(1.9rem, 3vw, 3rem);
      line-height: 1.02;
      max-width: 1040px;
    }

    p {
      margin: 10px 0 0;
      color: var(--muted);
      line-height: 1.6;
    }

    .metric-grid,
    .card-grid,
    .bout-grid,
    .chart-grid {
      display: grid;
      gap: 16px;
    }

    .metric-grid {
      margin-top: 22px;
      grid-template-columns: repeat(5, minmax(0, 1fr));
    }

    .card-grid,
    .chart-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .metric-card,
    .mini-card,
    .bout-card {
      background: rgba(255, 255, 255, 0.70);
      border: 1px solid var(--border);
      border-radius: 20px;
      padding: 16px 18px;
    }

    .metric-card small,
    .mini-card small,
    .table-note,
    .subnote {
      display: block;
      color: var(--muted);
      line-height: 1.45;
    }

    .metric-card strong,
    .mini-card strong,
    .bout-card strong {
      display: block;
      margin-top: 8px;
      color: var(--title);
      line-height: 1.05;
    }

    .metric-card strong { font-size: 1.7rem; }
    .mini-card strong { font-size: 1.15rem; }

    .card-head {
      display: flex;
      justify-content: space-between;
      gap: 18px;
      align-items: flex-start;
      flex-wrap: wrap;
      margin-bottom: 16px;
    }

    .pill {
      padding: 10px 14px;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.75);
      border: 1px solid var(--border);
      font-size: 0.84rem;
      font-weight: 800;
      color: var(--title);
      white-space: nowrap;
    }

    .bout-grid {
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }

    .badge {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 12px;
      border-radius: 999px;
      background: rgba(47, 127, 145, 0.10);
      color: var(--accent);
      font-weight: 800;
      font-size: 0.84rem;
      margin-bottom: 12px;
    }

    .label-bar {
      margin-top: 12px;
      height: 12px;
      border-radius: 999px;
      background: rgba(106, 98, 89, 0.12);
      overflow: hidden;
    }

    .label-fill {
      height: 100%;
      border-radius: inherit;
      background: linear-gradient(90deg, rgba(47,127,145,0.58), rgba(47,165,106,0.92));
    }

    .meta-grid {
      display: grid;
      gap: 8px;
      margin-top: 12px;
    }

    .meta-row {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      padding-top: 8px;
      border-top: 1px solid rgba(88, 74, 60, 0.08);
      font-size: 0.94rem;
    }

    .meta-row span:first-child {
      color: var(--muted);
    }

    .meta-row span:last-child {
      font-weight: 700;
    }

    .clip-link {
      display: inline-block;
      margin-top: 14px;
      text-decoration: none;
      color: white;
      background: linear-gradient(90deg, #2f7f91, #2fa56a);
      padding: 10px 14px;
      border-radius: 12px;
      font-weight: 800;
    }

    .table-wrap {
      overflow-x: auto;
      border: 1px solid var(--border);
      border-radius: 18px;
      background: rgba(255, 255, 255, 0.68);
    }

    table {
      width: 100%;
      border-collapse: collapse;
      min-width: 880px;
    }

    th,
    td {
      padding: 12px 14px;
      text-align: left;
      border-bottom: 1px solid rgba(88, 74, 60, 0.08);
      vertical-align: top;
      font-size: 0.93rem;
    }

    th {
      font-size: 0.82rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--muted);
      background: rgba(246, 242, 236, 0.9);
      position: sticky;
      top: 0;
    }

    tr:last-child td {
      border-bottom: none;
    }

    .stack-list {
      display: grid;
      gap: 12px;
      margin-top: 6px;
    }

    .stack-row {
      display: grid;
      grid-template-columns: 120px 1fr 56px;
      gap: 12px;
      align-items: center;
    }

    .stack-track {
      height: 12px;
      border-radius: 999px;
      background: rgba(106, 98, 89, 0.12);
      overflow: hidden;
    }

    .stack-fill {
      height: 100%;
      border-radius: inherit;
      background: linear-gradient(90deg, rgba(214,122,68,0.72), rgba(47,165,106,0.92));
    }

    .chart-svg {
      width: 100%;
      height: auto;
      display: block;
      background: rgba(255,255,255,0.58);
      border: 1px solid var(--border);
      border-radius: 18px;
    }

    @media (max-width: 1240px) {
      .metric-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
      .bout-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .card-grid,
      .chart-grid { grid-template-columns: 1fr; }
    }

    @media (max-width: 900px) {
      .metric-grid,
      .bout-grid { grid-template-columns: 1fr; }
      .stack-row { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <div class="shell">
    <section class="hero">
      <div class="eyebrow">Bout And Stride Review</div>
      <h1>Locomotion summarized over gait bouts instead of single frames</h1>
      <p id="heroText"></p>
      <div class="metric-grid" id="metricGrid"></div>
    </section>

    <section class="card">
      <div class="card-head">
        <div>
          <h2>Bout Overview</h2>
          <p>Each bout groups neighboring strides into a larger locomotion segment. This makes the report easier to interpret than frame-by-frame labels alone.</p>
        </div>
        <div class="pill" id="boutPill"></div>
      </div>
      <div class="card-grid">
        <div class="mini-card">
          <small>Pattern balance across bouts</small>
          <strong id="patternHeadline"></strong>
          <div class="stack-list" id="patternList"></div>
        </div>
        <div class="mini-card">
          <small>How to read this report</small>
          <strong>Focus on stable bouts first</strong>
          <p>Longer bouts with more strides, stronger match fractions, and available clip links are the best starting point for manual review and biological interpretation.</p>
          <p class="subnote" id="clipNote"></p>
        </div>
      </div>
      <div class="bout-grid" id="boutGrid"></div>
    </section>

    <section class="card">
      <div class="card-head">
        <div>
          <h2>Stride Summary</h2>
          <p>These summaries compress stride-by-stride variability into easier-to-read views while still preserving access to the detailed stride table below.</p>
        </div>
        <div class="pill">Stride-level review</div>
      </div>
      <div class="chart-grid">
        <div>
          <svg class="chart-svg" id="lengthChart" viewBox="0 0 720 320" aria-label="Stride length by bout"></svg>
          <div class="table-note">Mean stride length by bout. Error bars show within-bout variability.</div>
        </div>
        <div>
          <svg class="chart-svg" id="speedChart" viewBox="0 0 720 320" aria-label="Stride speed by bout"></svg>
          <div class="table-note">Mean stride speed by bout. Error bars show within-bout variability.</div>
        </div>
      </div>
    </section>

    <section class="card">
      <div class="card-head">
        <div>
          <h2>Bout Table</h2>
          <p>Use this table when you want exact start and end frames, dominant bout labels, and direct links to validation clips.</p>
        </div>
        <div class="pill">Validation-ready</div>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Bout</th>
              <th>Frames</th>
              <th>Seconds</th>
              <th>Strides</th>
              <th>Dominant pattern</th>
              <th>Match</th>
              <th>Stride length</th>
              <th>Stride speed</th>
              <th>Clip</th>
            </tr>
          </thead>
          <tbody id="boutTableBody"></tbody>
        </table>
      </div>
    </section>

    <section class="card">
      <div class="card-head">
        <div>
          <h2>Stride Table</h2>
          <p>This table keeps the stride-level numbers available for closer inspection without forcing the whole report to stay at frame-level granularity.</p>
        </div>
        <div class="pill" id="stridePill"></div>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Stride</th>
              <th>Bout</th>
              <th>Frames</th>
              <th>Seconds</th>
              <th>Pattern</th>
              <th>Match</th>
              <th>Stride length</th>
              <th>Stride speed</th>
              <th>Step length</th>
              <th>Step width</th>
            </tr>
          </thead>
          <tbody id="strideTableBody"></tbody>
        </table>
      </div>
    </section>
  </div>

  <script>
    const report = __GAIT_REVIEW_REPORT_DATA__;

    function fmtNumber(value, digits = 2) {
      if (value === null || value === undefined || Number.isNaN(value)) return "n/a";
      return Number(value).toFixed(digits);
    }

    function fmtPct(value) {
      if (value === null || value === undefined || Number.isNaN(value)) return "n/a";
      return `${(Number(value) * 100).toFixed(0)}%`;
    }

    function buildMetricCards() {
      const summary = report.summary;
      const metrics = [
        { label: "Qualified bouts", value: summary.total_bouts, note: `${summary.total_strides} strides were assigned to bout-level review.` },
        { label: "Locomotion time", value: `${fmtNumber(summary.total_locomotion_seconds, 1)} s`, note: "Sum of bout durations after grouping neighboring strides." },
        { label: "Median bout length", value: `${fmtNumber(summary.median_bout_seconds, 1)} s`, note: "Half of the bouts are shorter than this and half are longer." },
        { label: "Mean stride length", value: fmtNumber(summary.mean_stride_length, 1), note: "Average across strides assigned to reviewed bouts." },
        { label: "Mean stride speed", value: fmtNumber(summary.mean_stride_speed, 2), note: "Average body speed during those strides." },
      ];

      document.getElementById("metricGrid").innerHTML = metrics.map(metric => `
        <div class="metric-card">
          <small>${metric.label}</small>
          <strong>${metric.value}</strong>
          <small>${metric.note}</small>
        </div>
      `).join("");
    }

    function buildHeader() {
      const meta = report.metadata;
      document.getElementById("heroText").textContent =
        `Source video: ${meta.input_video_path || "video"} | pose labels: ${meta.input_labels_dir || "labels"} | generated on ${meta.generated_at}.`;
      document.getElementById("boutPill").textContent = `${report.summary.total_bouts} reviewed bouts`;
      document.getElementById("stridePill").textContent = `${report.strides.length} strides listed`;
      document.getElementById("clipNote").textContent =
        report.summary.clips_exported > 0
          ? `${report.summary.clips_exported} validation clips were exported for manual review.`
          : "No validation clips were exported.";
    }

    function buildPatternBalance() {
      const counts = report.summary.dominant_pattern_counts || {};
      const entries = Object.entries(counts).sort((a, b) => b[1] - a[1]);
      document.getElementById("patternHeadline").textContent =
        entries.length ? `${entries[0][0]} is the most common bout label` : "No dominant bout labels were available";
      document.getElementById("patternList").innerHTML = entries.map(([label, count]) => {
        const fraction = report.summary.total_bouts > 0 ? count / report.summary.total_bouts : 0;
        return `
          <div class="stack-row">
            <small>${label}</small>
            <div class="stack-track"><div class="stack-fill" style="width:${(fraction * 100).toFixed(1)}%"></div></div>
            <small>${count}</small>
          </div>
        `;
      }).join("");
    }

    function buildBoutCards() {
      document.getElementById("boutGrid").innerHTML = report.bouts.map(bout => `
        <div class="bout-card">
          <div class="badge">${bout.bout_id} · ${bout.dominant_label}</div>
          <strong>${bout.stride_count} strides across ${fmtNumber(bout.duration_seconds, 1)} s</strong>
          <small>Frames ${bout.start_frame} to ${bout.end_frame}</small>
          <div class="label-bar"><div class="label-fill" style="width:${(bout.dominant_fraction * 100).toFixed(1)}%"></div></div>
          <small>Dominant pattern agreement ${fmtPct(bout.dominant_fraction)} · mean confidence ${fmtPct(bout.mean_template_confidence)}</small>
          <div class="meta-grid">
            <div class="meta-row"><span>Stride length</span><span>${fmtNumber(bout.mean_stride_length, 1)}</span></div>
            <div class="meta-row"><span>Stride speed</span><span>${fmtNumber(bout.mean_stride_speed, 2)}</span></div>
            <div class="meta-row"><span>Step length</span><span>${fmtNumber(bout.mean_step_length, 1)}</span></div>
            <div class="meta-row"><span>Step width</span><span>${fmtNumber(bout.mean_step_width, 1)}</span></div>
          </div>
          ${bout.clip_relpath ? `<a class="clip-link" href="${bout.clip_relpath}" target="_blank" rel="noopener noreferrer">Open validation clip</a>` : ""}
        </div>
      `).join("");
    }

    function buildBoutTable() {
      document.getElementById("boutTableBody").innerHTML = report.bouts.map(bout => `
        <tr>
          <td>${bout.bout_id}</td>
          <td>${bout.start_frame} - ${bout.end_frame}</td>
          <td>${fmtNumber(bout.duration_seconds, 2)}</td>
          <td>${bout.stride_count}</td>
          <td>${bout.dominant_label}</td>
          <td>${fmtPct(bout.dominant_fraction)}</td>
          <td>${fmtNumber(bout.mean_stride_length, 1)}</td>
          <td>${fmtNumber(bout.mean_stride_speed, 2)}</td>
          <td>${bout.clip_relpath ? `<a href="${bout.clip_relpath}" target="_blank" rel="noopener noreferrer">clip</a>` : "n/a"}</td>
        </tr>
      `).join("");
    }

    function buildStrideTable() {
      document.getElementById("strideTableBody").innerHTML = report.strides.map(stride => `
        <tr>
          <td>${stride.stride_id}</td>
          <td>${stride.bout_id || "n/a"}</td>
          <td>${stride.start_frame} - ${stride.end_frame}</td>
          <td>${fmtNumber(stride.duration_seconds, 2)}</td>
          <td>${stride.dominant_label}</td>
          <td>${fmtPct(stride.dominant_fraction)}</td>
          <td>${fmtNumber(stride.stride_length, 1)}</td>
          <td>${fmtNumber(stride.stride_speed, 2)}</td>
          <td>${fmtNumber(stride.step_length, 1)}</td>
          <td>${fmtNumber(stride.step_width, 1)}</td>
        </tr>
      `).join("");
    }

    function buildBoutMetricChart(targetId, valueKey, errorKey, title) {
      const svg = document.getElementById(targetId);
      const width = 720;
      const height = 320;
      const left = 68;
      const right = width - 24;
      const top = 28;
      const bottom = height - 42;
      const bouts = report.bouts;
      const values = bouts.map(bout => Number(bout[valueKey] || 0));
      const errors = bouts.map(bout => Number(bout[errorKey] || 0));
      const yMax = Math.max(...values.map((value, idx) => value + errors[idx]), 1);
      const plotWidth = right - left;
      const plotHeight = bottom - top;
      const band = plotWidth / Math.max(bouts.length, 1);
      let out = "";

      for (let tick = 0; tick <= 4; tick++) {
        const y = bottom - tick * (plotHeight / 4);
        const label = (yMax * tick / 4).toFixed(1);
        out += `<line x1="${left}" y1="${y.toFixed(2)}" x2="${right}" y2="${y.toFixed(2)}" stroke="rgba(106,98,89,0.10)" stroke-width="1"/>`;
        out += `<text x="16" y="${(y + 4).toFixed(2)}" fill="#6a6259" font-size="12">${label}</text>`;
      }

      bouts.forEach((bout, idx) => {
        const cx = left + band * idx + band / 2;
        const barWidth = Math.min(34, band * 0.48);
        const value = values[idx];
        const error = errors[idx];
        const barHeight = (value / yMax) * plotHeight;
        const y = bottom - barHeight;
        const errTop = bottom - ((value + error) / yMax) * plotHeight;
        const errBottom = bottom - (Math.max(0, value - error) / yMax) * plotHeight;
        out += `<rect x="${(cx - barWidth / 2).toFixed(2)}" y="${y.toFixed(2)}" width="${barWidth.toFixed(2)}" height="${barHeight.toFixed(2)}" rx="10" fill="rgba(47,127,145,0.78)"/>`;
        out += `<line x1="${cx.toFixed(2)}" y1="${errTop.toFixed(2)}" x2="${cx.toFixed(2)}" y2="${errBottom.toFixed(2)}" stroke="#1d2a3a" stroke-width="2"/>`;
        out += `<line x1="${(cx - 8).toFixed(2)}" y1="${errTop.toFixed(2)}" x2="${(cx + 8).toFixed(2)}" y2="${errTop.toFixed(2)}" stroke="#1d2a3a" stroke-width="2"/>`;
        out += `<line x1="${(cx - 8).toFixed(2)}" y1="${errBottom.toFixed(2)}" x2="${(cx + 8).toFixed(2)}" y2="${errBottom.toFixed(2)}" stroke="#1d2a3a" stroke-width="2"/>`;
        out += `<text x="${cx.toFixed(2)}" y="${(bottom + 18).toFixed(2)}" text-anchor="middle" fill="#6a6259" font-size="12">${bout.bout_id}</text>`;
      });

      out += `<text x="${left}" y="18" fill="#1d2a3a" font-size="14" font-weight="800">${title}</text>`;
      svg.innerHTML = out;
    }

    function init() {
      buildMetricCards();
      buildHeader();
      buildPatternBalance();
      buildBoutCards();
      buildBoutTable();
      buildStrideTable();
      buildBoutMetricChart("lengthChart", "mean_stride_length", "std_stride_length", "Stride length by bout");
      buildBoutMetricChart("speedChart", "mean_stride_speed", "std_stride_speed", "Stride speed by bout");
    }

    init();
  </script>
</body>
</html>
"""
