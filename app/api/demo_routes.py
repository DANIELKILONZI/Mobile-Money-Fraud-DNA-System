"""Demo routes — seed data and serve the interactive graph visualization."""

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.core.storage import store
from app.graph.builder import graph_manager
from app.models.entities import Transaction
from app.services.reputation import reputation_manager

demo_router = APIRouter(tags=["Demo"])

# ── Fixed IDs used by the demo scenario ──────────────────────────────────────

DEMO_CLEAN_USER = "USER_CLEAN_001"
DEMO_RING_USERS = ["USER_A", "USER_B", "USER_C", "USER_D", "USER_E"]
DEMO_STRUCTURING_USER = "USER_STRUCT_001"
DEMO_MERCHANT = "MERCH_DEMO_001"
DEMO_DEVICE_SHARED = "DEV_SHARED_001"
DEMO_DEVICE_CLEAN = "DEV_CLEAN_001"


def _add_tx(
    tx_id: str,
    sender: str,
    receiver: str,
    amount: float,
    receiver_type: str = "user",
    device_id: str | None = None,
    ts: datetime | None = None,
) -> None:
    ts = ts or datetime.now(timezone.utc)
    store.get_or_create_user(sender)
    if receiver_type == "merchant":
        store.get_or_create_merchant(receiver, "general")
    else:
        store.get_or_create_user(receiver)
    if device_id:
        store.get_or_create_device(device_id)

    tx = Transaction(
        tx_id=tx_id,
        sender_id=sender,
        receiver_id=receiver,
        amount=amount,
        timestamp=ts,
        device_id=device_id,
    )
    store.add_transaction(tx)
    graph_manager.add_transaction(tx, receiver_type=receiver_type)


@demo_router.post("/demo/seed", status_code=201)
def seed_demo() -> dict[str, Any]:
    """
    Seed the in-memory store with a ready-made demo scenario:

    * **USER_CLEAN_001** — normal user, low risk, stable reputation
    * **USER_A … USER_E** — 5-node circular fraud ring (USER_A is the entry point)
    * **USER_STRUCT_001** — structuring user sending 6 small transfers
    * All nodes share realistic amounts and device assignments

    Call this once before a demo, then query:
    - `GET /risk/user/USER_CLEAN_001` → LOW risk
    - `GET /risk/user/USER_A`         → HIGH risk + fraud_story + alert
    - `GET /graph/suspicious-cluster/USER_A` → the fraud ring visualized
    """
    # Wipe existing demo state first so seeding is idempotent
    for uid in [DEMO_CLEAN_USER, DEMO_STRUCTURING_USER, *DEMO_RING_USERS]:
        store.users.pop(uid, None)
    store.merchants.pop(DEMO_MERCHANT, None)
    store.devices.pop(DEMO_DEVICE_SHARED, None)
    store.devices.pop(DEMO_DEVICE_CLEAN, None)

    tx_to_remove = [
        tx_id for tx_id, tx in store.transactions.items()
        if tx.sender_id in {DEMO_CLEAN_USER, DEMO_STRUCTURING_USER, *DEMO_RING_USERS}
        or tx.receiver_id in {DEMO_CLEAN_USER, DEMO_STRUCTURING_USER, *DEMO_RING_USERS, DEMO_MERCHANT}
    ]
    for tx_id in tx_to_remove:
        store.transactions.pop(tx_id, None)

    for uid in [DEMO_CLEAN_USER, DEMO_STRUCTURING_USER, *DEMO_RING_USERS]:
        reputation_manager._history.pop(uid, None)
        reputation_manager._long_term.pop(uid, None)

    # ── Clean user ────────────────────────────────────────────────────────────
    _add_tx("DEMO_TX_C1", DEMO_CLEAN_USER, DEMO_MERCHANT, 1200.0, "merchant", DEMO_DEVICE_CLEAN)
    _add_tx("DEMO_TX_C2", DEMO_CLEAN_USER, DEMO_MERCHANT, 850.0,  "merchant", DEMO_DEVICE_CLEAN)
    _add_tx("DEMO_TX_C3", DEMO_CLEAN_USER, DEMO_MERCHANT, 500.0,  "merchant", DEMO_DEVICE_CLEAN)

    # ── Fraud ring: 5-node cycle  A→B→C→D→E→A ────────────────────────────────
    ring = DEMO_RING_USERS
    for i, (src, dst) in enumerate(zip(ring, ring[1:] + ring[:1])):
        _add_tx(f"DEMO_TX_RING_{i}", src, dst, 10_000.0, "user", DEMO_DEVICE_SHARED)

    # Extra transactions to raise centrality and activate patterns
    _add_tx("DEMO_TX_A1", "USER_A", DEMO_MERCHANT, 3_000.0, "merchant", DEMO_DEVICE_SHARED)
    _add_tx("DEMO_TX_A2", "USER_A", "USER_B",      5_500.0, "user",     DEMO_DEVICE_SHARED)
    _add_tx("DEMO_TX_A3", "USER_B", "USER_A",      4_800.0, "user",     DEMO_DEVICE_SHARED)

    # ── Structuring user: 6 small transfers in a short burst ─────────────────
    for i in range(6):
        _add_tx(
            f"DEMO_TX_STR_{i}",
            DEMO_STRUCTURING_USER,
            DEMO_MERCHANT,
            round(450 + i * 30, 2),
            "merchant",
            DEMO_DEVICE_SHARED,
        )

    return {
        "status": "seeded",
        "demo_users": {
            "clean_user": DEMO_CLEAN_USER,
            "fraud_ring_entry": "USER_A",
            "ring_members": DEMO_RING_USERS,
            "structuring_user": DEMO_STRUCTURING_USER,
        },
        "demo_endpoints": {
            "step_1_clean":      f"/risk/user/{DEMO_CLEAN_USER}",
            "step_2_suspicious": "/risk/user/USER_A",
            "step_3_cluster":    "/graph/suspicious-cluster/USER_A",
            "visualization":     "/demo",
        },
        "pitch_line": (
            "This is not one bad actor. This is a coordinated fraud ring."
        ),
    }


# ── D3.js visualization ───────────────────────────────────────────────────────

_DEMO_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Fraud DNA — Live Graph Intelligence</title>
<script src="https://d3js.org/d3.v7.min.js"></script>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'Segoe UI', system-ui, sans-serif;
    background: #0d0d0d;
    color: #e0e0e0;
    display: flex;
    height: 100vh;
    overflow: hidden;
  }
  #sidebar {
    width: 340px;
    min-width: 280px;
    background: #141414;
    border-right: 1px solid #2a2a2a;
    display: flex;
    flex-direction: column;
    padding: 20px;
    overflow-y: auto;
    gap: 16px;
  }
  #graph-area {
    flex: 1;
    position: relative;
  }
  svg {
    width: 100%;
    height: 100%;
  }
  h1 { font-size: 1.1rem; color: #fff; letter-spacing: 0.5px; }
  h2 { font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px; color: #888; margin-bottom: 6px; }
  .card {
    background: #1e1e1e;
    border: 1px solid #2a2a2a;
    border-radius: 8px;
    padding: 14px;
  }
  .badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  .HIGH   { background: rgba(239,68,68,0.15); color: #ef4444; border: 1px solid #ef4444; }
  .MEDIUM { background: rgba(249,115,22,0.15); color: #f97316; border: 1px solid #f97316; }
  .LOW    { background: rgba(34,197,94,0.15);  color: #22c55e; border: 1px solid #22c55e; }
  .UNKNOWN{ background: rgba(156,163,175,0.15); color: #9ca3af; border: 1px solid #9ca3af; }
  .metric { display: flex; justify-content: space-between; align-items: center; margin-top: 8px; }
  .metric-label { font-size: 0.78rem; color: #888; }
  .metric-value { font-size: 0.85rem; font-weight: 600; color: #e0e0e0; }
  #story-chain {
    font-size: 0.78rem;
    color: #a3a3a3;
    line-height: 1.7;
    white-space: pre-wrap;
    word-break: break-all;
  }
  #story-summary { font-size: 0.82rem; color: #d4d4d4; line-height: 1.5; }
  #alert-box {
    display: none;
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 0.8rem;
    font-weight: 600;
    border: 1px solid #ef4444;
    background: rgba(239,68,68,0.1);
    color: #ef4444;
  }
  #node-tooltip {
    position: absolute;
    background: #1e1e1e;
    border: 1px solid #3a3a3a;
    border-radius: 8px;
    padding: 10px 14px;
    pointer-events: none;
    font-size: 0.78rem;
    line-height: 1.6;
    display: none;
    z-index: 10;
    max-width: 220px;
  }
  .controls {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }
  button {
    flex: 1;
    padding: 7px 12px;
    border: 1px solid #3a3a3a;
    border-radius: 6px;
    background: #1e1e1e;
    color: #e0e0e0;
    font-size: 0.78rem;
    cursor: pointer;
    transition: border-color 0.15s, background 0.15s;
  }
  button:hover { border-color: #ef4444; background: rgba(239,68,68,0.08); }
  button.active { border-color: #ef4444; color: #ef4444; }
  #loading {
    position: absolute;
    top: 50%; left: 50%;
    transform: translate(-50%, -50%);
    color: #555;
    font-size: 0.9rem;
  }
  .legend { display: flex; gap: 12px; flex-wrap: wrap; }
  .legend-item { display: flex; align-items: center; gap: 6px; font-size: 0.72rem; color: #888; }
  .legend-dot { width: 10px; height: 10px; border-radius: 50%; }
</style>
</head>
<body>

<div id="sidebar">
  <div>
    <h1>🧬 Fraud DNA</h1>
    <p style="font-size:0.72rem;color:#555;margin-top:4px;">Graph Intelligence Layer</p>
  </div>

  <div class="card">
    <h2>Inspect Node</h2>
    <div style="display:flex;gap:6px;margin-top:6px;">
      <input id="node-input" type="text" value="USER_A"
        style="flex:1;background:#111;border:1px solid #333;border-radius:5px;
               padding:5px 8px;color:#e0e0e0;font-size:0.78rem;outline:none;"/>
      <button id="load-btn" style="flex:0 0 auto;padding:5px 10px;" onclick="loadNode()">Load</button>
    </div>
    <div style="margin-top:8px;" class="controls">
      <button onclick="loadNode('USER_CLEAN_001')">Clean user</button>
      <button onclick="loadNode('USER_A')" class="active">Fraud ring</button>
    </div>
  </div>

  <!-- Risk card -->
  <div class="card" id="risk-card" style="display:none;">
    <h2>Risk Profile</h2>
    <div class="metric">
      <span class="metric-label">Entity</span>
      <span class="metric-value" id="p-entity">—</span>
    </div>
    <div class="metric">
      <span class="metric-label">Risk Score</span>
      <span class="metric-value" id="p-score">—</span>
    </div>
    <div class="metric">
      <span class="metric-label">Risk Level</span>
      <span id="p-level">—</span>
    </div>
    <div class="metric">
      <span class="metric-label">Reputation Trend</span>
      <span class="metric-value" id="p-trend">—</span>
    </div>
    <div class="metric">
      <span class="metric-label">Long-term Score</span>
      <span class="metric-value" id="p-longterm">—</span>
    </div>
  </div>

  <!-- Alert -->
  <div id="alert-box"></div>

  <!-- Fraud Story -->
  <div class="card" id="story-card" style="display:none;">
    <h2>Fraud Story</h2>
    <p id="story-summary"></p>
    <div style="margin-top:10px;">
      <div style="font-size:0.72rem;color:#555;text-transform:uppercase;letter-spacing:1px;">Chain</div>
      <div id="story-chain" style="margin-top:4px;"></div>
    </div>
    <div style="margin-top:10px;">
      <div style="font-size:0.72rem;color:#555;text-transform:uppercase;letter-spacing:1px;">Pattern</div>
      <div id="story-pattern" style="margin-top:4px;font-size:0.8rem;color:#f97316;font-weight:600;"></div>
    </div>
    <div style="margin-top:10px;" id="story-device-row" style="display:none;">
      <div style="font-size:0.72rem;color:#555;text-transform:uppercase;letter-spacing:1px;">Device Link</div>
      <div id="story-device" style="margin-top:4px;font-size:0.78rem;color:#a3a3a3;"></div>
    </div>
  </div>

  <!-- Legend -->
  <div class="card">
    <h2>Legend</h2>
    <div class="legend" style="margin-top:6px;">
      <div class="legend-item"><div class="legend-dot" style="background:#ef4444;"></div>HIGH risk</div>
      <div class="legend-item"><div class="legend-dot" style="background:#f97316;"></div>MEDIUM risk</div>
      <div class="legend-item"><div class="legend-dot" style="background:#22c55e;"></div>LOW risk</div>
      <div class="legend-item"><div class="legend-dot" style="background:#6b7280;"></div>UNKNOWN</div>
    </div>
    <p style="font-size:0.7rem;color:#555;margin-top:8px;">Edge thickness = transaction volume</p>
  </div>

  <div style="font-size:0.68rem;color:#333;text-align:center;padding-bottom:4px;">
    Mobile Money Fraud DNA System
  </div>
</div>

<div id="graph-area">
  <div id="loading">Loading graph…</div>
  <div id="node-tooltip"></div>
  <svg id="graph-svg"></svg>
</div>

<script>
const COLOR = { HIGH: '#ef4444', MEDIUM: '#f97316', LOW: '#22c55e', UNKNOWN: '#6b7280' };

function show(id) { document.getElementById(id).style.display = ''; }
function hide(id) { document.getElementById(id).style.display = 'none'; }

async function loadNode(nodeId) {
  nodeId = nodeId || document.getElementById('node-input').value.trim();
  if (!nodeId) return;
  document.getElementById('node-input').value = nodeId;

  // Clear previous
  hide('risk-card'); hide('story-card'); hide('alert-box');
  d3.select('#graph-svg').selectAll('*').remove();
  document.getElementById('loading').textContent = 'Loading…';
  show('loading');

  // Parallel fetch: risk + cluster
  const [riskResp, clusterResp] = await Promise.all([
    fetch(`/risk/user/${encodeURIComponent(nodeId)}`),
    fetch(`/graph/suspicious-cluster/${encodeURIComponent(nodeId)}?depth=2`),
  ]);

  hide('loading');

  if (!riskResp.ok) {
    document.getElementById('loading').textContent =
      `User "${nodeId}" not found. Run POST /demo/seed first, then try USER_A or USER_CLEAN_001.`;
    show('loading');
    return;
  }

  const risk    = await riskResp.json();
  const cluster = clusterResp.ok ? await clusterResp.json() : null;

  // Populate risk card
  document.getElementById('p-entity').textContent  = risk.entity_id;
  document.getElementById('p-score').textContent   = risk.risk_score.toFixed(4);
  const levelEl = document.getElementById('p-level');
  levelEl.innerHTML = `<span class="badge ${risk.risk_level}">${risk.risk_level}</span>`;
  const rep = risk.reputation;
  document.getElementById('p-trend').textContent   = rep ? rep.trend : '—';
  document.getElementById('p-longterm').textContent = rep ? rep.long_term_score.toFixed(4) : '—';
  show('risk-card');

  // Alert
  if (risk.alert) {
    const ab = document.getElementById('alert-box');
    ab.textContent = `⚠ ${risk.alert.alert_type.replace(/_/g,' ')} — severity: ${risk.alert.severity}`;
    show('alert-box');
  }

  // Fraud story
  if (risk.fraud_story) {
    const s = risk.fraud_story;
    document.getElementById('story-summary').textContent = s.summary || '';
    document.getElementById('story-chain').textContent   = (s.chain || []).join('\\n');
    document.getElementById('story-pattern').textContent = s.pattern || '';
    const devRow = document.getElementById('story-device-row');
    if (s.device_link) {
      document.getElementById('story-device').textContent = s.device_link;
      devRow.style.display = '';
    } else {
      devRow.style.display = 'none';
    }
    show('story-card');
  }

  // Draw graph
  if (cluster) drawGraph(cluster);
}

function drawGraph(data) {
  const container = document.getElementById('graph-area');
  const W = container.clientWidth;
  const H = container.clientHeight;

  const svg = d3.select('#graph-svg').attr('viewBox', `0 0 ${W} ${H}`);

  // Arrowhead marker
  svg.append('defs').append('marker')
    .attr('id', 'arrow')
    .attr('viewBox', '0 -5 10 10')
    .attr('refX', 22).attr('refY', 0)
    .attr('markerWidth', 6).attr('markerHeight', 6)
    .attr('orient', 'auto')
    .append('path').attr('d', 'M0,-5L10,0L0,5').attr('fill', '#555');

  const maxTx = d3.max(data.edges, e => e.tx_count || 1) || 1;

  const simulation = d3.forceSimulation(data.nodes)
    .force('link', d3.forceLink(data.edges)
      .id(d => d.id)
      .distance(d => 80 + (d.tx_count || 1) * 4))
    .force('charge', d3.forceManyBody().strength(-320))
    .force('center', d3.forceCenter(W / 2, H / 2))
    .force('collision', d3.forceCollide(32));

  // Edges
  const link = svg.append('g').selectAll('line')
    .data(data.edges).join('line')
    .attr('stroke', '#3a3a3a')
    .attr('stroke-width', d => 1 + ((d.tx_count || 1) / maxTx) * 5)
    .attr('marker-end', 'url(#arrow)');

  // Edge labels (total_amount)
  const edgeLabel = svg.append('g').selectAll('text')
    .data(data.edges).join('text')
    .attr('fill', '#555')
    .attr('font-size', '9px')
    .attr('text-anchor', 'middle')
    .text(d => d.total_amount ? `$${(d.total_amount/1000).toFixed(1)}k` : '');

  // Node groups
  const node = svg.append('g').selectAll('g')
    .data(data.nodes).join('g')
    .call(d3.drag()
      .on('start', (event, d) => { if (!event.active) simulation.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
      .on('drag',  (event, d) => { d.fx = event.x; d.fy = event.y; })
      .on('end',   (event, d) => { if (!event.active) simulation.alphaTarget(0); d.fx = null; d.fy = null; }));

  // Glow ring for center node
  node.filter(d => d.is_center)
    .append('circle')
    .attr('r', 22)
    .attr('fill', 'none')
    .attr('stroke', d => COLOR[d.risk_level] || COLOR.UNKNOWN)
    .attr('stroke-width', 2)
    .attr('stroke-dasharray', '4 3')
    .attr('opacity', 0.5);

  node.append('circle')
    .attr('r', d => d.is_center ? 18 : 13)
    .attr('fill', d => COLOR[d.risk_level] || COLOR.UNKNOWN)
    .attr('fill-opacity', 0.85)
    .attr('stroke', '#0d0d0d')
    .attr('stroke-width', 2);

  node.append('text')
    .attr('text-anchor', 'middle')
    .attr('dy', '0.35em')
    .attr('fill', '#fff')
    .attr('font-size', d => d.is_center ? '8px' : '7px')
    .attr('font-weight', d => d.is_center ? '700' : '400')
    .text(d => d.id.length > 10 ? d.id.slice(0, 10) + '…' : d.id);

  // Tooltip
  const tooltip = document.getElementById('node-tooltip');
  node
    .on('mouseover', (event, d) => {
      tooltip.innerHTML = `
        <strong>${d.id}</strong><br/>
        Type: ${d.type}<br/>
        Risk: <span style="color:${COLOR[d.risk_level]}">${d.risk_level}</span><br/>
        Score: ${(d.risk_score || 0).toFixed(4)}
      `;
      tooltip.style.display = 'block';
    })
    .on('mousemove', (event) => {
      const rect = container.getBoundingClientRect();
      tooltip.style.left = (event.clientX - rect.left + 14) + 'px';
      tooltip.style.top  = (event.clientY - rect.top  - 10) + 'px';
    })
    .on('mouseout', () => { tooltip.style.display = 'none'; });

  simulation.on('tick', () => {
    link
      .attr('x1', d => d.source.x).attr('y1', d => d.source.y)
      .attr('x2', d => d.target.x).attr('y2', d => d.target.y);
    edgeLabel
      .attr('x', d => (d.source.x + d.target.x) / 2)
      .attr('y', d => (d.source.y + d.target.y) / 2 - 5);
    node.attr('transform', d => `translate(${d.x},${d.y})`);
  });
}

// Auto-load on page open
window.addEventListener('load', () => loadNode('USER_A'));
</script>
</body>
</html>
"""


@demo_router.get("/demo", response_class=HTMLResponse, include_in_schema=False)
def demo_page() -> HTMLResponse:
    """Serve the interactive force-directed fraud graph visualization."""
    return HTMLResponse(content=_DEMO_HTML)
