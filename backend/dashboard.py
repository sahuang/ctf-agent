"""Tiny built-in dashboard for live coordinator and solver inspection."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import parse_qs, urlparse

logger = logging.getLogger(__name__)


DASHBOARD_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>CTF Agent Dashboard</title>
  <style>
    :root {
      --paper: #f4efe6;
      --ink: #171717;
      --muted: #6f665d;
      --panel: rgba(255, 252, 247, 0.88);
      --line: rgba(23, 23, 23, 0.12);
      --accent: #d85f2d;
      --good: #1f7a45;
      --bad: #a12e2f;
      --shadow: 0 18px 40px rgba(23, 23, 23, 0.08);
    }

    * { box-sizing: border-box; }
    body {
      margin: 0;
      color: var(--ink);
      font-family: "IBM Plex Sans", "Avenir Next", "Segoe UI", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(216, 95, 45, 0.14), transparent 32%),
        radial-gradient(circle at top right, rgba(31, 122, 69, 0.10), transparent 28%),
        linear-gradient(180deg, #f8f3ea 0%, #efe7dc 100%);
    }

    header { padding: 28px 24px 12px; }

    h1 {
      margin: 0;
      font-family: "IBM Plex Mono", "SFMono-Regular", monospace;
      font-size: 28px;
      letter-spacing: 0.03em;
      text-transform: uppercase;
    }

    .subhead {
      margin-top: 8px;
      color: var(--muted);
      max-width: 780px;
    }

    main {
      padding: 0 24px 28px;
      display: grid;
      grid-template-columns: 1.6fr 1fr;
      gap: 18px;
    }

    .stack {
      display: grid;
      gap: 18px;
    }

    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 20px;
      box-shadow: var(--shadow);
      backdrop-filter: blur(10px);
      overflow: hidden;
    }

    .panel h2 {
      margin: 0;
      padding: 16px 18px 0;
      font-size: 15px;
      letter-spacing: 0.05em;
      text-transform: uppercase;
    }

    .panel-body { padding: 16px 18px 18px; }

    .summary-grid {
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 12px;
    }

    .summary-card {
      padding: 14px;
      border-radius: 16px;
      background: linear-gradient(180deg, rgba(255,255,255,0.75), rgba(255,255,255,0.45));
      border: 1px solid var(--line);
    }

    .label {
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }

    .value {
      margin-top: 8px;
      font-size: 28px;
      font-weight: 700;
    }

    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }

    th, td {
      padding: 10px 8px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
    }

    th {
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }

    .badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 3px 10px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      background: rgba(23, 23, 23, 0.06);
    }

    .badge.running { color: var(--accent); background: rgba(216, 95, 45, 0.12); }
    .badge.solved, .badge.won { color: var(--good); background: rgba(31, 122, 69, 0.14); }
    .badge.error, .badge.cancelled { color: var(--bad); background: rgba(161, 46, 47, 0.12); }
    .badge.pending, .badge.pulled, .badge.unsolved { color: var(--muted); }

    .swarm-list {
      display: grid;
      gap: 14px;
    }

    .swarm-card {
      border: 1px solid var(--line);
      border-radius: 18px;
      overflow: hidden;
      background: rgba(255,255,255,0.45);
    }

    .swarm-head {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      padding: 14px 16px;
      border-bottom: 1px solid var(--line);
      background: rgba(216, 95, 45, 0.05);
    }

    .swarm-title {
      font-size: 18px;
      font-weight: 700;
    }

    .swarm-meta {
      margin-top: 4px;
      color: var(--muted);
      font-size: 13px;
    }

    .solver-grid {
      display: grid;
      gap: 10px;
      padding: 14px 16px 16px;
    }

    .solver-card {
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 12px;
      background: rgba(255,255,255,0.72);
    }

    .solver-top {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: start;
    }

    .solver-name {
      font-family: "IBM Plex Mono", "SFMono-Regular", monospace;
      font-size: 13px;
      font-weight: 700;
    }

    .solver-meta {
      margin-top: 8px;
      color: var(--muted);
      font-size: 13px;
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }

    .solver-findings {
      margin-top: 10px;
      padding: 10px;
      border-radius: 10px;
      background: rgba(23, 23, 23, 0.04);
      font-family: "IBM Plex Mono", "SFMono-Regular", monospace;
      font-size: 12px;
      white-space: pre-wrap;
      word-break: break-word;
      max-height: 160px;
      overflow: auto;
    }

    .trace-actions { margin-top: 10px; }

    button {
      border: 0;
      border-radius: 999px;
      padding: 9px 14px;
      background: var(--ink);
      color: white;
      font-weight: 700;
      cursor: pointer;
    }

    button.secondary {
      background: transparent;
      color: var(--ink);
      border: 1px solid var(--line);
    }

    form {
      display: grid;
      gap: 10px;
    }

    textarea, pre {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 12px;
      background: rgba(255,255,255,0.7);
      color: var(--ink);
      font-family: "IBM Plex Mono", "SFMono-Regular", monospace;
      font-size: 12px;
    }

    textarea {
      min-height: 110px;
      resize: vertical;
    }

    pre {
      min-height: 280px;
      max-height: 680px;
      overflow: auto;
      white-space: pre-wrap;
      word-break: break-word;
      margin: 0;
    }

    .event-log {
      display: grid;
      gap: 8px;
      max-height: 300px;
      overflow: auto;
    }

    .event {
      padding: 10px;
      border-radius: 12px;
      background: rgba(23, 23, 23, 0.04);
      font-size: 13px;
    }

    .event time {
      color: var(--muted);
      display: block;
      margin-bottom: 4px;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }

    .muted { color: var(--muted); }

    @media (max-width: 1100px) {
      main { grid-template-columns: 1fr; }
      .summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    }

    @media (max-width: 720px) {
      header, main { padding-left: 14px; padding-right: 14px; }
      .summary-grid { grid-template-columns: 1fr; }
      .solver-top, .swarm-head { flex-direction: column; }
    }
  </style>
</head>
<body>
  <header>
    <h1>CTF Agent Control Room</h1>
    <div class="subhead">Live challenge and solver visibility for the coordinator loop. This page polls local runtime state, lets you inspect solver traces, and can send operator messages into the running coordinator.</div>
  </header>

  <main>
    <section class="stack">
      <div class="panel">
        <h2>Overview</h2>
        <div class="panel-body">
          <div class="summary-grid" id="summary"></div>
        </div>
      </div>

      <div class="panel">
        <h2>Challenges</h2>
        <div class="panel-body">
          <table>
            <thead>
              <tr>
                <th>Challenge</th>
                <th>Status</th>
                <th>Category</th>
                <th>Value</th>
                <th>Flag</th>
                <th>Running</th>
                <th>Pulled</th>
              </tr>
            </thead>
            <tbody id="challenge-table"></tbody>
          </table>
        </div>
      </div>

      <div class="panel">
        <h2>Active Swarms</h2>
        <div class="panel-body">
          <div class="swarm-list" id="swarms"></div>
        </div>
      </div>
    </section>

    <aside class="stack">
      <div class="panel">
        <h2>Confirmed Flags</h2>
        <div class="panel-body">
          <div class="event-log" id="results"></div>
        </div>
      </div>

      <div class="panel">
        <h2>Operator Message</h2>
        <div class="panel-body">
          <form id="msg-form">
            <textarea id="msg-input" placeholder="Send a message to the running coordinator"></textarea>
            <div style="display:flex; gap:10px; align-items:center;">
              <button type="submit">Send Message</button>
              <span class="muted" id="msg-status"></span>
            </div>
          </form>
        </div>
      </div>

      <div class="panel">
        <h2>Trace Viewer</h2>
        <div class="panel-body">
          <div class="muted" id="trace-title" style="margin-bottom:10px;">Select a solver trace.</div>
          <pre id="trace-output">No trace selected.</pre>
        </div>
      </div>

      <div class="panel">
        <h2>Recent Events</h2>
        <div class="panel-body">
          <div class="event-log" id="events"></div>
        </div>
      </div>
    </aside>
  </main>

  <script>
    const summaryEl = document.getElementById("summary");
    const challengeTableEl = document.getElementById("challenge-table");
    const swarmsEl = document.getElementById("swarms");
    const resultsEl = document.getElementById("results");
    const eventsEl = document.getElementById("events");
    const traceTitleEl = document.getElementById("trace-title");
    const traceOutputEl = document.getElementById("trace-output");
    const msgFormEl = document.getElementById("msg-form");
    const msgInputEl = document.getElementById("msg-input");
    const msgStatusEl = document.getElementById("msg-status");

    function escapeHtml(value) {
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;");
    }

    function badge(status) {
      const cls = String(status || "unknown").replaceAll("_", "-");
      return `<span class="badge ${cls}">${escapeHtml(status || "unknown")}</span>`;
    }

    function fmtMoney(value) {
      return `$${Number(value || 0).toFixed(2)}`;
    }

    function fmtTime(ts) {
      return new Date(ts * 1000).toLocaleTimeString();
    }

    function renderSummary(state) {
      const cards = [
        ["Challenges", state.summary.total_challenges],
        ["Solved", state.summary.solved_challenges],
        ["Unsolved", state.summary.unsolved_challenges],
        ["Active Swarms", state.summary.active_swarms],
        ["Total Cost", fmtMoney(state.summary.total_cost_usd)],
      ];
      summaryEl.innerHTML = cards.map(([label, value]) => `
        <div class="summary-card">
          <div class="label">${escapeHtml(label)}</div>
          <div class="value">${escapeHtml(value)}</div>
        </div>
      `).join("");
    }

    function renderChallenges(challenges) {
      challengeTableEl.innerHTML = challenges.map((challenge) => `
        <tr>
          <td><strong>${escapeHtml(challenge.name)}</strong></td>
          <td>${badge(challenge.status)}</td>
          <td>${escapeHtml(challenge.category || "-")}</td>
          <td>${escapeHtml(challenge.value ?? "-")}</td>
          <td>${escapeHtml(challenge.flag || "-")}</td>
          <td>${challenge.running ? "yes" : "no"}</td>
          <td>${challenge.pulled ? "yes" : "no"}</td>
        </tr>
      `).join("");
    }

    function renderSwarms(swarms) {
      if (!swarms.length) {
        swarmsEl.innerHTML = `<div class="muted">No active or retained swarms yet.</div>`;
        return;
      }

      swarmsEl.innerHTML = swarms.map((swarm) => `
        <article class="swarm-card">
          <div class="swarm-head">
            <div>
              <div class="swarm-title">${escapeHtml(swarm.challenge)}</div>
              <div class="swarm-meta">
                ${badge(swarm.cancelled ? "cancelled" : "running")}
                ${swarm.winner ? `<span style="margin-left:8px;">Winner: <strong>${escapeHtml(swarm.winner)}</strong></span>` : ""}
              </div>
            </div>
            <div class="swarm-meta">Started ${escapeHtml(new Date(swarm.started_at * 1000).toLocaleTimeString())}</div>
          </div>
          <div class="solver-grid">
            ${swarm.agents.map((agent) => `
              <div class="solver-card">
                <div class="solver-top">
                  <div>
                    <div class="solver-name">${escapeHtml(agent.model_spec)}</div>
                    <div class="solver-meta">
                      <span>${badge(agent.status)}</span>
                      <span>${escapeHtml(agent.provider)} / ${escapeHtml(agent.model_id)}</span>
                    </div>
                  </div>
                  <div class="solver-meta">
                    <span>steps ${escapeHtml(agent.step_count)}</span>
                    <span>${fmtMoney(agent.cost_usd)}</span>
                  </div>
                </div>
                <div class="solver-meta">
                  <span>tokens ${escapeHtml(agent.total_tokens)}</span>
                  ${agent.flag ? `<span>flag ${escapeHtml(agent.flag)}</span>` : ""}
                  ${agent.trace_path ? `<span>trace ready</span>` : ""}
                </div>
                <div class="solver-findings">${escapeHtml(agent.findings || "No findings yet.")}</div>
                <div class="trace-actions">
                  <button class="secondary" onclick="loadTrace(${JSON.stringify(swarm.challenge)}, ${JSON.stringify(agent.model_spec)})">View Trace</button>
                </div>
              </div>
            `).join("")}
          </div>
        </article>
      `).join("");
    }

    function renderEvents(events) {
      if (!events.length) {
        eventsEl.innerHTML = `<div class="muted">No events yet.</div>`;
        return;
      }
      eventsEl.innerHTML = events.map((event) => `
        <div class="event">
          <time>${escapeHtml(fmtTime(event.ts))} · ${escapeHtml(event.kind)}</time>
          <div>${escapeHtml(event.message)}</div>
        </div>
      `).join("");
    }

    function renderResults(results) {
      const entries = Object.entries(results || {});
      if (!entries.length) {
        resultsEl.innerHTML = `<div class="muted">No confirmed flags yet.</div>`;
        return;
      }
      resultsEl.innerHTML = entries.map(([challenge, data]) => `
        <div class="event">
          <time>${escapeHtml(challenge)}</time>
          <div>${escapeHtml((data && data.flag) || "no flag recorded")}</div>
        </div>
      `).join("");
    }

    async function refresh() {
      const res = await fetch("/api/state");
      const state = await res.json();
      renderSummary(state);
      renderChallenges(state.challenges);
      renderSwarms(state.swarms);
      renderResults(state.results);
      renderEvents(state.events);
    }

    async function loadTrace(challenge, model) {
      traceTitleEl.textContent = `${challenge} / ${model}`;
      traceOutputEl.textContent = "Loading trace...";
      const url = `/api/trace?challenge=${encodeURIComponent(challenge)}&model=${encodeURIComponent(model)}&last_n=80`;
      const res = await fetch(url);
      const payload = await res.json();
      traceOutputEl.textContent = payload.text || "Trace unavailable.";
    }

    msgFormEl.addEventListener("submit", async (event) => {
      event.preventDefault();
      const message = msgInputEl.value.trim();
      if (!message) return;
      msgStatusEl.textContent = "sending...";
      const res = await fetch("/api/msg", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({message}),
      });
      const payload = await res.json();
      msgStatusEl.textContent = payload.queued ? "queued" : "failed";
      if (payload.queued) {
        msgInputEl.value = "";
        refresh();
      }
    });

    refresh();
    setInterval(refresh, 3000);
    window.loadTrace = loadTrace;
  </script>
</body>
</html>
"""


@dataclass
class DashboardEvent:
    ts: float
    kind: str
    message: str


@dataclass
class DashboardState:
    events: list[DashboardEvent] = field(default_factory=list)
    max_events: int = 200

    def add_event(self, kind: str, message: str) -> None:
        self.events.append(DashboardEvent(ts=time.time(), kind=kind, message=message[:1000]))
        if len(self.events) > self.max_events:
            self.events = self.events[-self.max_events:]


def _read_trace_lines(path: str, last_n: int) -> list[str]:
    return Path(path).read_text().splitlines()[-last_n:]


def build_state_snapshot(deps, poller, cost_tracker, dashboard: DashboardState) -> dict:
    known_challenges = poller.known_challenges | set(deps.challenge_dirs) | set(deps.results) | set(deps.swarms)
    challenges = []
    for name in sorted(known_challenges):
        meta = deps.challenge_metas.get(name)
        task = deps.swarm_tasks.get(name)
        running = bool(task and not task.done())
        solved = name in poller.known_solved or name in deps.results
        if solved:
            status = "solved"
        elif running:
            status = "running"
        elif name in deps.challenge_dirs:
            status = "pulled"
        else:
            status = "unsolved"

        challenges.append(
            {
                "name": name,
                "status": status,
                "category": getattr(meta, "category", ""),
                "value": getattr(meta, "value", None),
                "flag": deps.results.get(name, {}).get("flag"),
                "running": running,
                "pulled": name in deps.challenge_dirs,
            }
        )

    swarms = []
    for challenge_name in sorted(deps.swarms):
        swarm = deps.swarms[challenge_name]
        swarm_status = swarm.get_status()
        task = deps.swarm_tasks.get(challenge_name)
        swarm_status["agents"] = [swarm_status["agents"][spec] for spec in swarm.model_specs]
        if not task or task.done():
            for agent in swarm_status["agents"]:
                if agent["status"] == "running":
                    agent["status"] = "finished"
        swarms.append(swarm_status)

    return {
        "summary": {
            "total_challenges": len(poller.known_challenges),
            "solved_challenges": len(poller.known_solved),
            "unsolved_challenges": max(0, len(poller.known_challenges) - len(poller.known_solved)),
            "active_swarms": sum(1 for task in deps.swarm_tasks.values() if not task.done()),
            "total_cost_usd": round(cost_tracker.total_cost_usd, 4),
            "total_tokens": cost_tracker.total_tokens,
        },
        "challenges": challenges,
        "swarms": swarms,
        "results": deps.results,
        "events": [
            {"ts": event.ts, "kind": event.kind, "message": event.message}
            for event in reversed(dashboard.events[-50:])
        ],
    }


def build_trace_payload(deps, challenge_name: str, model_spec: str, last_n: int = 80) -> dict:
    swarm = deps.swarms.get(challenge_name)
    if not swarm:
        return {"text": f"No swarm running for {challenge_name}"}
    solver = swarm.solvers.get(model_spec)
    if not solver:
        return {"text": f"No solver for {model_spec}"}
    trace_path = getattr(getattr(solver, "tracer", None), "path", "")
    if not trace_path:
        return {"text": "No trace file available yet."}

    path = Path(trace_path)
    if not path.exists():
        return {"text": f"Trace file not found: {trace_path}"}

    try:
        lines = _read_trace_lines(trace_path, last_n)
    except Exception as e:
        return {"text": f"Could not read trace: {e}"}

    rendered = []
    for line in lines:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            rendered.append(line)
            continue

        event_type = event.get("type", "?")
        step = event.get("step")
        if event_type == "tool_call":
            rendered.append(f"step {step} CALL {event.get('tool')}: {event.get('args')}")
        elif event_type == "tool_result":
            rendered.append(f"step {step} RESULT {event.get('tool')}: {event.get('result')}")
        elif event_type == "usage":
            rendered.append(
                "usage: "
                f"in={event.get('input_tokens', 0)} "
                f"out={event.get('output_tokens', 0)} "
                f"cached={event.get('cache_read_tokens', 0)} "
                f"cost=${event.get('cost_usd', 0):.4f}"
            )
        else:
            rendered.append(json.dumps(event, ensure_ascii=False))

    return {"text": "\n".join(rendered) if rendered else "Trace file is empty."}


async def start_dashboard_server(
    deps,
    poller,
    cost_tracker,
    dashboard: DashboardState,
    port: int = 0,
    host: str = "0.0.0.0",
) -> asyncio.Server:
    async def _reply(writer: asyncio.StreamWriter, status: str, content_type: str, body: bytes) -> None:
        writer.write(
            (
                f"HTTP/1.1 {status}\r\n"
                f"Content-Type: {content_type}\r\n"
                f"Content-Length: {len(body)}\r\n"
                "Cache-Control: no-store\r\n"
                "Connection: close\r\n\r\n"
            ).encode()
            + body
        )
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    async def _handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            request_line = await asyncio.wait_for(reader.readline(), timeout=5)
            headers: dict[str, str] = {}
            while True:
                line = await asyncio.wait_for(reader.readline(), timeout=5)
                if line in (b"\r\n", b"\n", b""):
                    break
                if b":" in line:
                    key, value = line.decode().split(":", 1)
                    headers[key.strip().lower()] = value.strip()

            parts = request_line.decode("utf-8", errors="replace").strip().split()
            method = parts[0] if len(parts) >= 1 else ""
            target = parts[1] if len(parts) >= 2 else "/"
            parsed = urlparse(target)
            params = parse_qs(parsed.query)
            content_length = int(headers.get("content-length", "0"))
            body = b""
            if content_length > 0:
                body = await asyncio.wait_for(reader.read(content_length), timeout=5)

            if method == "GET" and parsed.path in ("/", "/index.html"):
                return await _reply(writer, "200 OK", "text/html; charset=utf-8", DASHBOARD_HTML.encode())

            if method == "GET" and parsed.path == "/api/state":
                payload = json.dumps(build_state_snapshot(deps, poller, cost_tracker, dashboard)).encode()
                return await _reply(writer, "200 OK", "application/json; charset=utf-8", payload)

            if method == "GET" and parsed.path == "/api/trace":
                challenge = params.get("challenge", [""])[0]
                model = params.get("model", [""])[0]
                last_n = int(params.get("last_n", ["80"])[0])
                payload = json.dumps(build_trace_payload(deps, challenge, model, last_n)).encode()
                return await _reply(writer, "200 OK", "application/json; charset=utf-8", payload)

            if method == "GET" and parsed.path == "/health":
                return await _reply(writer, "200 OK", "application/json; charset=utf-8", b'{"ok":true}')

            if method == "POST" and parsed.path in ("/api/msg", "/msg"):
                try:
                    data = json.loads(body.decode()) if body else {}
                    message = data.get("message", "")
                except (json.JSONDecodeError, UnicodeDecodeError):
                    message = body.decode("utf-8", errors="replace")
                deps.operator_inbox.put_nowait(message)
                dashboard.add_event("operator_message", message)
                payload = json.dumps({"queued": message[:200]}).encode()
                return await _reply(writer, "200 OK", "application/json; charset=utf-8", payload)

            return await _reply(writer, "404 Not Found", "text/plain; charset=utf-8", b"not found")
        except Exception as e:
            logger.warning("Dashboard request failed: %s", e)
            try:
                await _reply(writer, "500 Internal Server Error", "text/plain; charset=utf-8", b"internal error")
            except Exception:
                pass

    server = await asyncio.start_server(_handle, host=host, port=port)
    sock = server.sockets[0].getsockname() if server.sockets else (host, port)
    deps.msg_port = int(sock[1])
    logger.info("Dashboard listening on http://%s:%s", host, deps.msg_port)
    return server
