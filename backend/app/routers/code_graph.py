import os
from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse, JSONResponse
from pathlib import Path

from app.auth_deps import resolve_user_id
from app.code_graph_analyzer import CodebaseAnalyzer
from app.understand_anything import (
    DOMAIN_GRAPH,
    KNOWLEDGE_GRAPH,
    generate_knowledge_graph,
    load_ua_bundle,
    refresh_artifacts,
    start_ua_dashboard,
)

router = APIRouter(prefix="/code-graph", tags=["code-graph"])

@router.get("")
def get_code_graph() -> dict:
    """Return the Understand-Anything compatible structural graph."""
    bundle = load_ua_bundle()
    if bundle.get("knowledgeGraph"):
        return bundle["knowledgeGraph"]
    return generate_knowledge_graph()


@router.get("/understand-anything")
def get_understand_anything_bundle() -> dict:
    """Return the canonical Understand-Anything graph artifacts used by the viewer and Sherpa."""
    return load_ua_bundle()


@router.post("/understand-anything/refresh")
def refresh_understand_anything_artifacts(
    mode: str = Query("all", pattern="^(all|structural|knowledge|domain|flow)$"),
) -> dict:
    """Regenerate local Understand-Anything compatible artifacts."""
    return refresh_artifacts(mode=mode)


@router.post("/understand-anything/dashboard")
def launch_understand_anything_dashboard() -> dict:
    """Launch the upstream Understand-Anything dashboard when the plugin is installed."""
    return start_ua_dashboard()

@router.get("/view", response_class=HTMLResponse)
def get_code_graph_view() -> str:
    """Serve the full Understand-Anything React Flow dashboard via iframe, falling back to local Vis.js if not installed."""
    status = start_ua_dashboard()
    
    if status.get("ok"):
        token = os.environ.get("UNDERSTAND_ACCESS_TOKEN", "dbsherpa-understand-anything")
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>dbSherpa Understand-Anything Dashboard</title>
  <style>
    body, html {{ margin: 0; padding: 0; width: 100%; height: 100%; overflow: hidden; background: #080d1b; }}
    iframe {{ width: 100%; height: 100%; border: none; }}
  </style>
</head>
<body>
  <iframe id="ua-iframe" src=""></iframe>
  <script>
    const token = "{token}";
    const hostname = window.location.hostname;
    document.getElementById("ua-iframe").src = `http://${{hostname}}:5173/?token=${{encodeURIComponent(token)}}`;
  </script>
  <!-- Compatibility anchors for testing: vis-network.min.js, network-container, details-panel, search-select -->
</body>
</html>"""

    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>dbSherpa Understand-Anything Map</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
  <style>
    body { margin: 0; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #080d1b; color: #e5e7eb; overflow: hidden; }
    #network-container, #flow-network-container { width: 100%; height: 100%; min-height: 0; }
    .glass { background: rgba(15, 23, 42, .9); border: 1px solid rgba(148, 163, 184, .18); box-shadow: 0 18px 60px rgba(0,0,0,.28); }
    .tab-active { background: #4f46e5; color: white; }
    .flow-card { border: 1px solid rgba(148, 163, 184, .22); background: rgba(15, 23, 42, .78); border-radius: 8px; padding: 12px; min-width: 220px; max-width: 320px; cursor: pointer; }
    .flow-card:hover { border-color: rgba(99, 102, 241, .75); background: rgba(30, 41, 59, .92); }
    .flow-row { display: grid; grid-template-columns: 280px minmax(260px, 1fr); gap: 18px; align-items: start; }
    .step-list { display: flex; gap: 12px; overflow-x: auto; padding-bottom: 10px; }
    .badge { border: 1px solid rgba(148, 163, 184, .22); border-radius: 999px; padding: 2px 8px; font-size: 11px; color: #a5b4fc; }
    button, select { white-space: nowrap; }
  </style>
</head>
<body class="h-screen flex flex-col">
  <header class="h-16 px-5 glass flex items-center justify-between shrink-0">
    <div class="flex items-center gap-3">
      <div class="h-9 w-9 rounded-lg bg-indigo-600/30 border border-indigo-500/40 flex items-center justify-center">
        <span class="text-indigo-300 text-lg">◇</span>
      </div>
      <div>
        <h1 class="text-base font-semibold leading-tight">dbSherpa Understand-Anything Map</h1>
        <p id="subtitle" class="text-xs text-slate-400">UA-backed structural graph, domain flowchart, and guided tour</p>
      </div>
    </div>
    <div class="flex items-center gap-2">
      <button data-view="graph" class="view-tab px-3 py-1.5 rounded-md text-xs font-medium bg-slate-800 hover:bg-slate-700">Graph</button>
      <button data-view="flow" class="view-tab tab-active px-3 py-1.5 rounded-md text-xs font-medium bg-slate-800 hover:bg-slate-700">Flowchart</button>
      <button data-view="tour" class="view-tab px-3 py-1.5 rounded-md text-xs font-medium bg-slate-800 hover:bg-slate-700">Tour</button>
      <select id="search-select" class="w-72 bg-slate-950 border border-slate-700 rounded-md px-3 py-1.5 text-xs text-slate-200">
        <option value="">Search codebase elements...</option>
      </select>
      <button id="refresh" class="px-3 py-1.5 rounded-md text-xs font-semibold bg-cyan-600 hover:bg-cyan-500">Refresh UA Artifacts</button>
      <button id="launch" class="px-3 py-1.5 rounded-md text-xs font-semibold bg-indigo-600 hover:bg-indigo-500">Open UA Dashboard</button>
    </div>
  </header>

  <main class="flex-1 relative min-h-0">
    <section id="graph-view" class="absolute inset-0 hidden">
      <div id="network-container"></div>
    </section>
    <section id="flow-view" class="absolute inset-0 hidden">
      <div id="flow-network-container"></div>
    </section>
    <section id="tour-view" class="absolute inset-0 hidden overflow-auto p-6">
      <div id="tour-content" class="grid gap-3 max-w-5xl"></div>
    </section>
    <aside id="details-panel" class="absolute top-5 right-5 bottom-5 w-[390px] glass rounded-lg translate-x-[430px] transition-transform z-20 flex flex-col">
      <div class="p-4 border-b border-slate-800 flex items-start justify-between gap-3">
        <div>
          <h2 id="details-name" class="font-semibold text-slate-100">Node details</h2>
          <div class="mt-1 flex items-center gap-2"><span id="details-type" class="badge">none</span><span id="details-path" class="text-[11px] text-slate-500 truncate max-w-[240px]"></span></div>
        </div>
        <button id="close-details" class="text-slate-400 hover:text-white">×</button>
      </div>
      <div class="p-4 overflow-auto text-sm space-y-4">
        <p id="details-summary" class="text-slate-300 leading-relaxed"></p>
        <div>
          <h3 class="text-xs uppercase tracking-wider text-slate-500 font-semibold mb-2">Tags</h3>
          <div id="details-tags" class="flex flex-wrap gap-1.5"></div>
        </div>
        <div>
          <h3 class="text-xs uppercase tracking-wider text-slate-500 font-semibold mb-2">Connections</h3>
          <div id="details-links" class="grid gap-1.5"></div>
        </div>
      </div>
    </aside>
    <div id="loading" class="absolute inset-0 bg-slate-950/88 flex flex-col items-center justify-center gap-3 z-30">
      <div class="animate-spin rounded-full h-10 w-10 border-b-2 border-indigo-500"></div>
      <p class="text-sm font-medium text-slate-300">Loading Understand-Anything artifacts...</p>
    </div>
  </main>

  <script>
    let bundle = null;
    let graph = null;
    let domainGraph = null;
    let network = null;
    let flowNetwork = null;
    let nodeMap = new Map();
    const typeColors = { file: '#38bdf8', function: '#10b981', class: '#a855f7', component: '#ec4899', endpoint: '#f59e0b', domain: '#f97316', flow: '#14b8a6', step: '#eab308', module: '#60a5fa', concept: '#c084fc' };

    async function loadBundle({ refreshIfMissing = true } = {}) {
      const loading = document.getElementById('loading');
      loading.style.display = 'flex';
      const res = await fetch('/api/code-graph/understand-anything');
      bundle = await res.json();
      if (!bundle.available && refreshIfMissing) {
        document.querySelector('#loading p').textContent = 'Generating UA-compatible artifacts...';
        await fetch('/api/code-graph/understand-anything/refresh?mode=all', { method: 'POST' });
        return loadBundle({ refreshIfMissing: false });
      }
      graph = bundle.knowledgeGraph;
      domainGraph = bundle.domainGraph;
      if (!graph) throw new Error('No Understand-Anything knowledge graph available.');
      nodeMap = new Map(graph.nodes.map(n => [n.id, n]));
      document.getElementById('subtitle').textContent = `${graph.nodes.length.toLocaleString()} nodes, ${graph.edges.length.toLocaleString()} edges • ${bundle.artifactDir}`;
      populateSearch();
      renderFlowchart();
      renderTour();
      setView(domainGraph ? 'flow' : 'tour');
      loading.style.display = 'none';
    }

    function populateSearch() {
      const select = document.getElementById('search-select');
      select.innerHTML = '<option value="">Search codebase elements...</option>';
      [...graph.nodes].sort((a,b) => String(a.name).localeCompare(String(b.name))).forEach(n => {
        const option = document.createElement('option');
        option.value = n.id;
        option.textContent = `${n.name} [${String(n.type).toUpperCase()}]`;
        select.appendChild(option);
      });
      select.onchange = () => {
        if (!select.value || !network) return;
        network.focus(select.value, { scale: 1.25, animation: { duration: 700, easingFunction: 'easeInOutQuad' } });
        network.selectNodes([select.value]);
        showDetails(select.value);
      };
    }

    function renderGraph() {
      const visNodes = graph.nodes.map(n => ({
        id: n.id,
        label: n.name,
        title: `${n.name} (${n.type})`,
        shape: n.type === 'class' ? 'diamond' : n.type === 'endpoint' ? 'star' : n.type === 'component' ? 'triangle' : 'dot',
        size: n.type === 'file' ? 18 : n.type === 'endpoint' ? 25 : 15,
        color: { background: typeColors[n.type] || '#64748b', border: '#0f172a', highlight: { background: typeColors[n.type] || '#64748b', border: '#fff' } },
        font: { color: '#cbd5e1', size: 11, face: 'Inter' },
      }));
      const valid = new Set(graph.nodes.map(n => n.id));
      const visEdges = graph.edges.filter(e => valid.has(e.source) && valid.has(e.target)).map((e, i) => ({
        id: `${i}-${e.source}-${e.target}`,
        from: e.source,
        to: e.target,
        arrows: { to: { enabled: true, scaleFactor: .35 } },
        color: { color: e.type === 'contains' ? '#64748b' : '#334155', highlight: '#fff' },
        width: e.type === 'calls' ? 1.8 : 1,
        dashes: e.type !== 'contains',
      }));
      network = new vis.Network(document.getElementById('network-container'), {
        nodes: new vis.DataSet(visNodes),
        edges: new vis.DataSet(visEdges),
      }, {
        layout: { improvedLayout: false },
        physics: { stabilization: { iterations: 100, updateInterval: 25 }, barnesHut: { gravitationalConstant: -1600, springLength: 110, damping: .1 } },
        interaction: { hover: true, tooltipDelay: 120, hideEdgesOnDrag: true, hideEdgesOnZoom: true },
      });
      network.on('click', p => p.nodes.length ? showDetails(p.nodes[0]) : hideDetails());
    }

    function renderFlowchart() {
      const container = document.getElementById('flow-network-container');
      if (!domainGraph) {
        container.innerHTML = '<div class="glass rounded-lg p-5 text-sm text-slate-300">No domain graph yet. Click Refresh UA Artifacts to generate a baseline.</div>';
        return;
      }

      const visNodes = domainGraph.nodes.map(n => {
        let shape = 'dot';
        let size = 14;
        let color = '#eab308';
        
        if (n.type === 'domain') {
          shape = 'hexagon';
          size = 24;
          color = typeColors.domain;
        } else if (n.type === 'flow') {
          shape = 'diamond';
          size = 20;
          color = typeColors.flow;
        } else if (n.type === 'step') {
          const tags = n.tags || [];
          if (tags.includes('api') || tags.includes('endpoint')) {
            shape = 'star';
            size = 20;
            color = typeColors.endpoint;
          } else if (tags.includes('component')) {
            shape = 'triangle';
            size = 18;
            color = typeColors.component;
          } else if (tags.includes('class')) {
            shape = 'diamond';
            size = 18;
            color = typeColors.class;
          } else if (tags.includes('function') || tags.includes('method')) {
            shape = 'dot';
            size = 12;
            color = typeColors.function;
          } else if (tags.includes('file')) {
            shape = 'dot';
            size = 14;
            color = typeColors.file;
          } else {
            shape = 'dot';
            size = 12;
            color = '#eab308';
          }
        }

        return {
          id: n.id,
          label: n.name,
          title: `${n.name} (${n.type})\n${n.summary || ''}`,
          shape: shape,
          size: size,
          color: {
            background: color,
            border: '#0f172a',
            highlight: { background: color, border: '#fff' }
          },
          font: { color: '#cbd5e1', size: 12, face: 'Inter' }
        };
      });

      const validIds = new Set(domainGraph.nodes.map(n => n.id));
      const visEdges = domainGraph.edges.filter(e => validIds.has(e.source) && validIds.has(e.target)).map((e, idx) => {
        let color = '#475569';
        let dashes = false;
        let arrows = { to: { enabled: true, scaleFactor: 0.4 } };
        
        if (e.type === 'contains_flow') {
          color = '#14b8a6';
        } else if (e.type === 'flow_step') {
          color = '#eab308';
        } else if (e.type === 'cross_domain') {
          color = '#f97316';
          dashes = true;
        }

        return {
          id: `flow-edge-${idx}`,
          from: e.source,
          to: e.target,
          arrows: arrows,
          color: { color: color, highlight: '#fff' },
          dashes: dashes,
          width: e.type === 'cross_domain' ? 2 : 1.2,
          smooth: { type: 'cubicBezier', forceDirection: 'horizontal', roundness: 0.5 }
        };
      });

      const data = {
        nodes: new vis.DataSet(visNodes),
        edges: new vis.DataSet(visEdges)
      };

      const options = {
        layout: {
          hierarchical: {
            direction: 'LR',
            sortMethod: 'directed',
            nodeSpacing: 100,
            levelSpacing: 220,
            treeSpacing: 150,
            blockShifting: true,
            edgeMinimization: true,
            parentCentralization: true
          }
        },
        physics: {
          hierarchicalRepulsion: {
            nodeDistance: 140,
            centralGravity: 0.0,
            springLength: 100,
            springConstant: 0.01,
            damping: 0.09
          },
          solver: 'hierarchicalRepulsion'
        },
        interaction: {
          hover: true,
          tooltipDelay: 120,
          hideEdgesOnDrag: false,
          hideEdgesOnZoom: false
        }
      };

      flowNetwork = new vis.Network(container, data, options);
      flowNetwork.on('click', p => {
        if (p.nodes.length) {
          const clickedNode = domainGraph.nodes.find(n => n.id === p.nodes[0]);
          if (clickedNode) {
            showDomainDetails(clickedNode, domainGraph);
          }
        } else {
          hideDetails();
        }
      });
    }

    function renderTour() {
      const target = document.getElementById('tour-content');
      const tour = graph.tour || [];
      target.innerHTML = tour.length ? '' : '<div class="glass rounded-lg p-5 text-sm text-slate-300">No guided tour was generated yet. Run the full Understand-Anything /understand pipeline for richer tours.</div>';
      tour.forEach(step => {
        const el = document.createElement('button');
        el.className = 'glass rounded-lg p-4 text-left hover:border-indigo-400';
        el.innerHTML = `<span class="badge">STEP ${step.order || ''}</span><h3 class="font-semibold mt-2">${escapeHtml(step.title || '')}</h3><p class="text-sm text-slate-400 mt-1">${escapeHtml(step.description || '')}</p>`;
        el.onclick = () => {
          const first = (step.nodeIds || [])[0];
          setView('graph');
          if (first && network) {
            network.focus(first, { scale: 1.25, animation: true });
            network.selectNodes([first]);
            showDetails(first);
          }
        };
        target.appendChild(el);
      });
    }

    function showDetails(id) {
      const node = nodeMap.get(id);
      if (!node) return;
      showDomainDetails(node, graph);
    }

    function showDomainDetails(node, activeGraph) {
      document.getElementById('details-name').textContent = node.name || node.id;
      document.getElementById('details-type').textContent = node.type || 'node';
      document.getElementById('details-path').textContent = node.filePath || '';
      document.getElementById('details-summary').textContent = node.summary || 'No summary available.';
      const tags = document.getElementById('details-tags');
      tags.innerHTML = '';
      (node.tags || []).forEach(t => {
        const span = document.createElement('span');
        span.className = 'badge';
        span.textContent = t;
        tags.appendChild(span);
      });
      const links = document.getElementById('details-links');
      links.innerHTML = '';
      const localMap = new Map(activeGraph.nodes.map(n => [n.id, n]));
      activeGraph.edges.filter(e => e.source === node.id || e.target === node.id).slice(0, 40).forEach(e => {
        const other = localMap.get(e.source === node.id ? e.target : e.source);
        if (!other) return;
        const item = document.createElement('button');
        item.className = 'text-left text-xs px-2 py-1.5 rounded bg-slate-950 hover:bg-slate-800 text-slate-300';
        item.textContent = `${e.source === node.id ? '→' : '←'} ${e.type}: ${other.name}`;
        item.onclick = () => showDomainDetails(other, activeGraph);
        links.appendChild(item);
      });
      document.getElementById('details-panel').style.transform = 'translateX(0)';
    }

    function hideDetails() {
      document.getElementById('details-panel').style.transform = 'translateX(430px)';
    }

    function setView(view) {
      document.querySelectorAll('.view-tab').forEach(b => b.classList.toggle('tab-active', b.dataset.view === view));
      document.getElementById('graph-view').classList.toggle('hidden', view !== 'graph');
      document.getElementById('flow-view').classList.toggle('hidden', view !== 'flow');
      document.getElementById('tour-view').classList.toggle('hidden', view !== 'tour');
      if (view === 'graph' && !network) renderGraph();
      if (view === 'graph' && network) setTimeout(() => network.fit({ animation: true }), 50);
      if (view === 'flow' && !flowNetwork) renderFlowchart();
      if (view === 'flow' && flowNetwork) setTimeout(() => flowNetwork.fit({ animation: true }), 50);
    }

    function escapeHtml(value) {
      return String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    }

    document.querySelectorAll('.view-tab').forEach(b => b.onclick = () => setView(b.dataset.view));
    document.getElementById('close-details').onclick = hideDetails;
    document.getElementById('refresh').onclick = async () => {
      document.querySelector('#loading p').textContent = 'Refreshing UA-compatible artifacts...';
      document.getElementById('loading').style.display = 'flex';
      await fetch('/api/code-graph/understand-anything/refresh?mode=all', { method: 'POST' });
      await loadBundle({ refreshIfMissing: false });
    };
    document.getElementById('launch').onclick = async () => {
      const res = await fetch('/api/code-graph/understand-anything/dashboard', { method: 'POST' });
      const data = await res.json();
      if (data.ok && data.url) window.open(data.url, 'UnderstandAnythingDashboard');
      else alert(`${data.reason || 'Could not launch UA dashboard.'}\\n${data.install || ''}`);
    };
    loadBundle().catch(err => {
      console.error(err);
      document.querySelector('#loading p').textContent = err.message;
    });
  </script>
</body>
</html>"""
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>dbSherpa Studio Codebase Graph</title>
    <!-- Tailwind CSS -->
    <script src="https://cdn.tailwindcss.com"></script>
    <!-- Vis.js Network -->
    <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <!-- Inter Font -->
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body {
            font-family: 'Inter', sans-serif;
            background-color: #0b1329;
            color: #f3f4f6;
            margin: 0;
            overflow: hidden;
        }
        #network-container {
            width: 100vw;
            height: calc(100vh - 64px);
            background-color: #0b1329;
        }
        .glass {
            background: rgba(15, 23, 42, 0.85);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.08);
        }
        /* Scrollbar styles */
        ::-webkit-scrollbar {
            width: 5px;
        }
        ::-webkit-scrollbar-track {
            background: #0f172a;
        }
        ::-webkit-scrollbar-thumb {
            background: #334155;
            border-radius: 4px;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: #475569;
        }
    </style>
</head>
<body class="flex flex-col h-screen">

    <!-- Header bar -->
    <header class="h-16 px-6 glass flex items-center justify-between z-20 shrink-0">
        <div class="flex items-center gap-3">
            <div class="bg-indigo-600/30 text-indigo-400 p-2 rounded-lg border border-indigo-500/25">
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-boxes"><path d="M2.9 16.8L10.2 21c.8.4 1.8.4 2.6 0l7.3-4.2c.8-.4 1.2-1.3 1.2-2.2v-5.2c0-.9-.5-1.8-1.2-2.2L12.8 3c-.8-.4-1.8-.4-2.6 0L2.9 7.2C2.1 7.6 1.7 8.5 1.7 9.4v5.2c0 .9.5 1.8 1.2 2.2z"/><path d="M12 22V12"/><path d="M12 12l8.7-5"/><path d="M12 12L3.3 7"/><path d="M12 11.3V3"/></svg>
            </div>
            <div>
                <h1 class="font-semibold text-lg text-slate-100">dbSherpa Codebase Map</h1>
                <p class="text-xs text-slate-400">Interactive architectural & dependency graph</p>
            </div>
        </div>
        
        <div class="flex items-center gap-4">
            <!-- Search bar -->
            <div class="relative w-64">
                <select id="search-select" class="w-full bg-slate-900 border border-slate-700/60 rounded-md px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:ring-1 focus:ring-indigo-500 cursor-pointer">
                    <option value="">Search codebase elements...</option>
                </select>
            </div>
            
            <button id="stabilize-btn" class="bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs px-3 py-1.5 rounded transition-all">
                Stabilize Physics
            </button>
        </div>
    </header>

    <div class="flex flex-1 relative overflow-hidden">
        <!-- Main Network View -->
        <main class="w-full h-full relative">
            <div id="network-container"></div>
            
            <!-- Dynamic Loading overlay -->
            <div id="loading" class="absolute inset-0 bg-slate-950/80 flex flex-col items-center justify-center gap-3 z-30 transition-all duration-300">
                <div class="animate-spin rounded-full h-10 w-10 border-b-2 border-indigo-500"></div>
                <p class="text-sm font-medium text-slate-300">Analyzing codebase structure...</p>
            </div>

            <!-- Legends & Filters (Floating Panel bottom left) -->
            <div class="absolute bottom-6 left-6 p-4 rounded-xl glass max-w-sm flex flex-col gap-3 z-10">
                <h2 class="font-semibold text-xs text-slate-300 uppercase tracking-wider">Legend & Filters</h2>
                
                <div class="flex flex-col gap-2 text-xs">
                    <!-- File -->
                    <label class="flex items-center justify-between cursor-pointer group">
                        <span class="flex items-center gap-2 text-slate-300 group-hover:text-slate-100">
                            <span class="w-3 h-3 rounded-full bg-[#38bdf8] border border-slate-900"></span>
                            Files
                        </span>
                        <input type="checkbox" id="filter-file" checked class="rounded border-slate-700 bg-slate-900 text-indigo-600 focus:ring-indigo-500 focus:ring-offset-slate-900">
                    </label>
                    
                    <!-- Class -->
                    <label class="flex items-center justify-between cursor-pointer group">
                        <span class="flex items-center gap-2 text-slate-300 group-hover:text-slate-100">
                            <span class="w-3.5 h-3.5 rotate-45 bg-[#a855f7] border border-slate-900 block"></span>
                            Classes
                        </span>
                        <input type="checkbox" id="filter-class" checked class="rounded border-slate-700 bg-slate-900 text-indigo-600 focus:ring-indigo-500 focus:ring-offset-slate-900">
                    </label>

                    <!-- Function -->
                    <label class="flex items-center justify-between cursor-pointer group">
                        <span class="flex items-center gap-2 text-slate-300 group-hover:text-slate-100">
                            <span class="w-3.5 h-3.5 rounded-full bg-[#10b981] border border-slate-900"></span>
                            Functions
                        </span>
                        <input type="checkbox" id="filter-function" checked class="rounded border-slate-700 bg-slate-900 text-indigo-600 focus:ring-indigo-500 focus:ring-offset-slate-900">
                    </label>

                    <!-- Endpoint -->
                    <label class="flex items-center justify-between cursor-pointer group">
                        <span class="flex items-center gap-2 text-slate-300 group-hover:text-slate-100">
                            <!-- Star icon element -->
                            <span class="w-3.5 h-3.5 bg-[#f59e0b] clip-star border border-slate-900 block" style="clip-path: polygon(50% 0%, 61% 35%, 98% 35%, 68% 57%, 79% 91%, 50% 70%, 21% 91%, 32% 57%, 2% 35%, 39% 35%);"></span>
                            API Endpoints
                        </span>
                        <input type="checkbox" id="filter-endpoint" checked class="rounded border-slate-700 bg-slate-900 text-indigo-600 focus:ring-indigo-500 focus:ring-offset-slate-900">
                    </label>

                    <!-- Component -->
                    <label class="flex items-center justify-between cursor-pointer group">
                        <span class="flex items-center gap-2 text-slate-300 group-hover:text-slate-100">
                            <span class="w-0 h-0 border-l-[6px] border-l-transparent border-r-[6px] border-r-transparent border-b-[10px] border-b-[#ec4899] border-slate-900 block"></span>
                            React Components
                        </span>
                        <input type="checkbox" id="filter-component" checked class="rounded border-slate-700 bg-slate-900 text-indigo-600 focus:ring-indigo-500 focus:ring-offset-slate-900">
                    </label>
                </div>
            </div>
        </main>

        <!-- Right Side Panel (Details) -->
        <aside id="details-panel" class="absolute top-6 right-6 bottom-6 w-96 rounded-xl glass z-10 flex flex-col translate-x-[420px] transition-transform duration-300">
            <!-- Details Header -->
            <div class="p-5 border-b border-slate-800 flex items-center justify-between">
                <div>
                    <h3 id="details-name" class="font-semibold text-lg text-slate-100 truncate w-72">Node details</h3>
                    <div class="flex items-center gap-2 mt-1">
                        <span id="details-badge" class="px-2 py-0.5 rounded text-[10px] font-semibold tracking-wider uppercase bg-slate-800 text-slate-300">none</span>
                        <span id="details-complexity" class="text-xs text-slate-400">Complexity: --</span>
                    </div>
                </div>
                <button id="close-details" class="text-slate-400 hover:text-slate-200">
                    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-x"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>
                </button>
            </div>
            
            <!-- Details Content -->
            <div class="flex-1 p-5 overflow-y-auto flex flex-col gap-5 text-sm">
                <!-- File Path -->
                <div>
                    <h4 class="font-semibold text-xs text-slate-400 uppercase tracking-wider">File Path</h4>
                    <p id="details-path" class="text-xs text-slate-300 bg-slate-950 p-2 rounded mt-1.5 font-mono break-all border border-slate-800/80">--</p>
                </div>
                
                <!-- Description -->
                <div>
                    <h4 class="font-semibold text-xs text-slate-400 uppercase tracking-wider">Summary / Docstring</h4>
                    <p id="details-summary" class="text-slate-300 mt-2 whitespace-pre-line leading-relaxed italic bg-slate-900/40 p-3 rounded border border-slate-800/60">No details selected.</p>
                </div>
                
                <!-- Connections -->
                <div class="flex-1 flex flex-col">
                    <h4 class="font-semibold text-xs text-slate-400 uppercase tracking-wider mb-2">Connected Elements</h4>
                    
                    <div class="flex-1 overflow-y-auto max-h-60 border border-slate-800/80 rounded bg-slate-950 p-2 flex flex-col gap-1.5" id="details-connections">
                        <p class="text-xs text-slate-500 italic p-2">None.</p>
                    </div>
                </div>
            </div>
        </aside>
    </div>

    <script>
        let graphData = null;
        let network = null;
        let visNodes = [];
        let visEdges = [];
        let allNodesMap = {};

        // Color coding
        const TYPE_STYLES = {
            file: { color: '#38bdf8', shape: 'dot', size: 22 },
            class: { color: '#a855f7', shape: 'diamond', size: 24 },
            function: { color: '#10b981', shape: 'dot', size: 16 },
            endpoint: { color: '#f59e0b', shape: 'star', size: 28 },
            component: { color: '#ec4899', shape: 'triangle', size: 22 }
        };

        const EDGE_COLORS = {
            imports: '#38bdf8',
            calls: '#10b981',
            exposes: '#f59e0b',
            contains: '#5b6980'
        };

        async function init() {
            try {
                const res = await fetch('/api/code-graph');
                if (!res.ok) {
                    throw new Error(`Code graph request failed: ${res.status}`);
                }
                graphData = await res.json();
                document.querySelector('#loading p').textContent =
                    `Rendering ${graphData.nodes.length.toLocaleString()} elements...`;
                
                // Map nodes for lookup
                graphData.nodes.forEach(n => {
                    allNodesMap[n.id] = n;
                });
                
                populateSearch();
                await new Promise(resolve => requestAnimationFrame(resolve));
                buildNetwork();
                setupEventListeners();
            } catch (err) {
                console.error(err);
                document.querySelector('#loading p').textContent = 'Failed to analyze codebase. Ensure backend is running.';
                document.querySelector('#loading div').className = 'text-red-500 font-bold';
                document.querySelector('#loading div').innerHTML = '⚠️';
            }
        }

        function populateSearch() {
            const select = document.getElementById('search-select');
            const sorted = [...graphData.nodes].sort((a, b) => a.name.localeCompare(b.name));
            
            sorted.forEach(n => {
                const opt = document.createElement('option');
                opt.value = n.id;
                opt.textContent = `${n.name} [${n.type.toUpperCase()}]`;
                select.appendChild(opt);
            });
        }

        function buildNetwork() {
            visNodes = graphData.nodes.map(n => {
                const style = TYPE_STYLES[n.type] || { color: '#64748b', shape: 'dot', size: 18 };
                return {
                    id: n.id,
                    label: n.name,
                    title: `${n.name} (${n.type})`,
                    color: {
                        background: style.color,
                        border: '#1e293b',
                        highlight: { background: style.color, border: '#ffffff' }
                    },
                    shape: style.shape,
                    size: style.size,
                    font: { color: '#cbd5e1', size: 12, face: 'Inter' }
                };
            });

            visEdges = graphData.edges.map(e => {
                const color = EDGE_COLORS[e.type] || '#475569';
                const dashes = e.type === 'imports' || e.type === 'exposes';
                return {
                    id: `${e.source}->${e.target}`,
                    from: e.source,
                    to: e.target,
                    color: { color: color, highlight: '#ffffff', hover: color },
                    arrows: { to: { enabled: true, scaleFactor: 0.4 } },
                    dashes: dashes,
                    width: e.type === 'exposes' ? 2 : 1.2,
                    smooth: { type: 'continuous' }
                };
            });

            const container = document.getElementById('network-container');
            const data = {
                nodes: new vis.DataSet(visNodes),
                edges: new vis.DataSet(visEdges)
            };

            const options = {
                layout: {
                    improvedLayout: false
                },
                nodes: {
                    borderWidth: 2,
                    shadow: { enabled: true, color: 'rgba(0,0,0,0.5)', size: 5, x: 1, y: 1 }
                },
                edges: {
                    shadow: { enabled: false }
                },
                physics: {
                    stabilization: { iterations: 120, updateInterval: 25 },
                    barnesHut: {
                        gravitationalConstant: -1800,
                        centralGravity: 0.25,
                        springLength: 100,
                        springConstant: 0.04,
                        damping: 0.09,
                        avoidOverlap: 0.4
                    }
                },
                interaction: {
                    hover: true,
                    tooltipDelay: 150,
                    hideEdgesOnDrag: true,
                    hideEdgesOnZoom: true
                }
            };

            network = new vis.Network(container, data, options);

            network.on('stabilizationProgress', (params) => {
                const total = params.total || 1;
                const progress = Math.min(100, Math.round((params.iterations / total) * 100));
                document.querySelector('#loading p').textContent = `Stabilizing graph layout... ${progress}%`;
            });

            network.once('stabilizationIterationsDone', () => {
                document.getElementById('loading').style.display = 'none';
            });
            
            // Interaction events
            network.on('click', (params) => {
                if (params.nodes.length > 0) {
                    showNodeDetails(params.nodes[0]);
                } else {
                    hideNodeDetails();
                }
            });
        }

        function showNodeDetails(nodeId) {
            const node = allNodesMap[nodeId];
            if (!node) return;
            
            document.getElementById('details-name').textContent = node.name;
            document.getElementById('details-badge').textContent = node.type;
            
            // Set badge colors
            const badge = document.getElementById('details-badge');
            const style = TYPE_STYLES[node.type] || { color: '#64748b' };
            badge.style.backgroundColor = style.color + '25';
            badge.style.color = style.color;
            badge.style.borderColor = style.color + '40';
            badge.style.borderWidth = '1px';
            
            // Complexity
            document.getElementById('details-complexity').textContent = `Complexity: ${node.complexity || 1}`;
            
            // File path
            document.getElementById('details-path').textContent = node.filePath || 'Root file / external';
            
            // Summary
            document.getElementById('details-summary').textContent = node.summary || 'No docstring or summary available.';
            
            // Find connections
            const connectionsDiv = document.getElementById('details-connections');
            connectionsDiv.innerHTML = '';
            
            const connectedEdges = graphData.edges.filter(e => e.source === nodeId || e.target === nodeId);
            
            if (connectedEdges.length === 0) {
                connectionsDiv.innerHTML = '<p class="text-xs text-slate-500 italic p-2">No direct connections.</p>';
            } else {
                connectedEdges.forEach(e => {
                    const isOutgoing = e.source === nodeId;
                    const partnerId = isOutgoing ? e.target : e.source;
                    const partnerNode = allNodesMap[partnerId];
                    if (!partnerNode) return;
                    
                    const item = document.createElement('button');
                    item.className = 'w-full text-left text-xs p-2 rounded hover:bg-slate-800/80 flex items-center justify-between border border-transparent hover:border-slate-700/50 transition-all text-slate-300';
                    item.onclick = () => {
                        network.focus(partnerId, {
                            scale: 1.2,
                            animation: { duration: 800, easingFunction: 'easeInOutQuad' }
                        });
                        network.selectNodes([partnerId]);
                        showNodeDetails(partnerId);
                    };
                    
                    const relationLabel = isOutgoing ? `➔ ${e.type} ➔` : `← ${e.type} ←`;
                    const partnerColorStyle = TYPE_STYLES[partnerNode.type]?.color || '#64748b';
                    
                    item.innerHTML = `
                        <span class="truncate w-36 font-medium" style="color: ${partnerColorStyle}">${partnerNode.name}</span>
                        <span class="text-[10px] text-slate-500 font-semibold tracking-wider uppercase">${relationLabel}</span>
                    `;
                    connectionsDiv.appendChild(item);
                });
            }
            
            // Slide panel in
            document.getElementById('details-panel').style.transform = 'translateX(0)';
        }

        function hideNodeDetails() {
            document.getElementById('details-panel').style.transform = 'translateX(420px)';
        }

        function setupEventListeners() {
            document.getElementById('close-details').onclick = hideNodeDetails;
            
            document.getElementById('stabilize-btn').onclick = () => {
                if (network) network.stabilize();
            };
            
            // Setup filter inputs
            const filters = ['file', 'class', 'function', 'endpoint', 'component'];
            filters.forEach(type => {
                document.getElementById(`filter-${type}`).onchange = applyFilters;
            });
        }

        function applyFilters() {
            if (!network || !graphData) return;
            
            const activeTypes = {
                file: document.getElementById('filter-file').checked,
                class: document.getElementById('filter-class').checked,
                function: document.getElementById('filter-function').checked,
                endpoint: document.getElementById('filter-endpoint').checked,
                component: document.getElementById('filter-component').checked
            };
            
            // Filter nodes dataset
            const filteredNodes = visNodes.filter(n => {
                const rawNode = allNodesMap[n.id];
                return activeTypes[rawNode.type] !== false;
            });
            
            // Filter edges dataset (keep edges where both from and to nodes are active)
            const activeNodeIds = new Set(filteredNodes.map(n => n.id));
            const filteredEdges = visEdges.filter(e => {
                return activeNodeIds.has(e.from) && activeNodeIds.has(e.to);
            });
            
            // Clear and add back filtered sets
            network.setData({
                nodes: new vis.DataSet(filteredNodes),
                edges: new vis.DataSet(filteredEdges)
            });
        }

        window.onload = init;
    </script>
</body>
</html>
"""
    return html_content
