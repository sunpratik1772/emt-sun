from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from app.code_graph_analyzer import CodebaseAnalyzer


UA_DIR_NAME = ".understand-anything"
KNOWLEDGE_GRAPH = "knowledge-graph.json"
DOMAIN_GRAPH = "domain-graph.json"
META_FILE = "meta.json"
CONFIG_FILE = "config.json"


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def ua_dir(root: Path | None = None) -> Path:
    return (root or project_root()) / UA_DIR_NAME


def graph_path(file_name: str, root: Path | None = None) -> Path:
    return ua_dir(root) / file_name


def load_json_file(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {
            "error": f"Invalid JSON in {path.name}: {exc}",
            "path": str(path),
        }


def _get_git_commit_hash(root: Path) -> str:
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(root),
            capture_output=True,
            text=True,
            check=False
        )
        if res.returncode == 0:
            return res.stdout.strip()
    except Exception:
        pass
    return "0000000000000000000000000000000000000000"


def _complexity_label(value: Any) -> str:
    if isinstance(value, str):
        lowered = value.lower()
        if lowered in {"simple", "moderate", "complex"}:
            return lowered
        return "moderate"
    if isinstance(value, (int, float)):
        if value <= 3:
            return "simple"
        if value <= 8:
            return "moderate"
        return "complex"
    return "moderate"


def _node_to_ua(node: dict[str, Any]) -> dict[str, Any]:
    node_type = node.get("type") or "concept"
    if node_type == "component":
        node_type = "function"
    elif node_type not in {
        "file", "function", "class", "module", "concept",
        "config", "document", "service", "table", "endpoint",
        "pipeline", "schema", "resource", "domain", "flow", "step",
        "article", "entity", "topic", "claim", "source"
    }:
        node_type = "concept"
        
    return {
        "id": str(node.get("id")),
        "type": node_type,
        "name": str(node.get("name") or node.get("id")),
        "filePath": node.get("filePath"),
        "summary": node.get("summary") or "",
        "tags": node.get("tags") or [node_type],
        "complexity": _complexity_label(node.get("complexity")),
    }


def _edge_to_ua(edge: dict[str, Any]) -> dict[str, Any]:
    edge_type = str(edge.get("type") or "related").lower()
    if edge_type not in {
        "imports", "exports", "contains", "inherits", "implements",
        "calls", "subscribes", "publishes", "middleware",
        "reads_from", "writes_to", "transforms", "validates",
        "depends_on", "tested_by", "configures",
        "related", "similar_to",
        "deploys", "serves", "provisions", "triggers",
        "migrates", "documents", "routes", "defines_schema",
        "contains_flow", "flow_step", "cross_domain",
        "cites", "contradicts", "builds_on", "exemplifies", "categorized_under", "authored_by"
    }:
        edge_type = "related"
        
    return {
        "source": str(edge.get("source")),
        "target": str(edge.get("target")),
        "type": edge_type,
        "direction": edge.get("direction") or "forward",
        "weight": float(edge.get("weight") or 1.0),
        "description": edge.get("description") or "",
    }


def _build_layers(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    layer_specs = [
        ("api", "API", lambda n: n["type"] == "endpoint" or "router" in str(n.get("filePath", ""))),
        ("ui", "UI", lambda n: "frontend/" in str(n.get("filePath", "")) or n["type"] == "component"),
        ("backend", "Backend", lambda n: "backend/" in str(n.get("filePath", ""))),
        ("docs-config", "Docs & Config", lambda n: n["type"] == "file" and str(n.get("filePath", "")).split(".")[-1] in {"md", "json", "yaml", "yml", "css", "html"}),
    ]
    assigned: set[str] = set()
    layers: list[dict[str, Any]] = []
    for layer_id, name, predicate in layer_specs:
        ids = [n["id"] for n in nodes if n["id"] not in assigned and predicate(n)]
        if ids:
            assigned.update(ids)
            layers.append({
                "id": layer_id,
                "name": name,
                "description": f"{name} elements inferred from the local codebase.",
                "nodeIds": ids,
            })
    remaining = [n["id"] for n in nodes if n["id"] not in assigned]
    if remaining:
        layers.append({
            "id": "other",
            "name": "Other",
            "description": "Elements not assigned to a stronger architectural layer.",
            "nodeIds": remaining,
        })
    return layers


def generate_knowledge_graph(root: Path | None = None) -> dict[str, Any]:
    root = root or project_root()
    analyzer = CodebaseAnalyzer(str(root))
    raw = analyzer.run_analysis()
    nodes = [_node_to_ua(n) for n in raw.get("nodes", []) if n.get("id")]
    valid_ids = {n["id"] for n in nodes}
    edges = [
        _edge_to_ua(e)
        for e in raw.get("edges", [])
        if e.get("source") in valid_ids and e.get("target") in valid_ids
    ]
    graph = {
        "version": "1.0.0",
        "project": {
            "name": raw.get("project", {}).get("name") or root.name,
            "description": "Understand-Anything compatible graph generated for dbSherpa Studio.",
            "languages": raw.get("project", {}).get("languages") or ["Python", "TypeScript", "JavaScript", "HTML", "CSS"],
            "frameworks": raw.get("project", {}).get("frameworks") or ["FastAPI", "React"],
            "analyzedAt": raw.get("project", {}).get("analyzedAt") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "gitCommitHash": _get_git_commit_hash(root)
        },
        "nodes": nodes,
        "edges": edges,
        "layers": _build_layers(nodes),
        "tour": _build_tour(nodes),
        "generatedBy": "dbsherpa-understand-anything-adapter",
        "schemaVersion": "understand-anything-compatible",
    }
    return graph


def _build_tour(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    interesting = [
        n for n in nodes
        if n["type"] in {"endpoint", "component", "class", "function"} and n.get("summary")
    ][:8]
    return [
        {
            "order": idx + 1,
            "title": f"Step {idx + 1}: {node['name']}",
            "description": node.get("summary") or f"Explore {node['name']}.",
            "nodeIds": [node["id"]],
        }
        for idx, node in enumerate(interesting)
    ]


def generate_domain_graph(knowledge_graph: dict[str, Any] | None = None, root: Path | None = None) -> dict[str, Any]:
    root = root or project_root()
    graph = knowledge_graph or generate_knowledge_graph(root)
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    by_id = {n["id"]: n for n in nodes if isinstance(n, dict) and n.get("id")}

    # Define standard logical domains in the project
    DOMAINS_DEFINITION = [
        {
            "id": "domain:auth",
            "type": "domain",
            "name": "Authentication & Users",
            "summary": "Manage user login, registration, authorization, session state, and security policies.",
            "tags": ["domain", "security", "auth"],
            "complexity": "moderate",
            "domainMeta": {
                "entities": ["user", "session", "token"],
                "businessRules": ["Requires valid credentials or OAuth token.", "Session tokens must be validated on protected routes."],
            },
            "keywords": ["auth", "user"],
            "flows": [
                {
                    "id": "flow:auth:session",
                    "type": "flow",
                    "name": "User Session Management",
                    "summary": "Login, logout, and token exchange for JWT/OAuth authentication.",
                    "tags": ["flow", "session"],
                    "complexity": "moderate",
                    "domainMeta": {"entryPoint": "/api/auth/login", "entryType": "api"},
                    "keywords": ["login", "logout", "callback", "token", "session"]
                },
                {
                    "id": "flow:auth:profile",
                    "type": "flow",
                    "name": "User Accounts & Profiles",
                    "summary": "Manage user profile details and access permissions.",
                    "tags": ["flow", "profile"],
                    "complexity": "simple",
                    "domainMeta": {"entryPoint": "/api/user/me", "entryType": "api"},
                    "keywords": ["user", "profile", "register"]
                }
            ]
        },
        {
            "id": "domain:workflows",
            "type": "domain",
            "name": "Workflow Design & Library",
            "summary": "Design, build, validate, configure, and template runnable automation workflows.",
            "tags": ["domain", "workflows", "templates"],
            "complexity": "complex",
            "domainMeta": {
                "entities": ["workflow", "draft", "template", "step"],
                "businessRules": ["Workflows must pass validation before execution.", "Drafts can be promoted to saved workflows."],
            },
            "keywords": ["workflow", "automation", "library", "draft"],
            "flows": [
                {
                    "id": "flow:workflows:crud",
                    "type": "flow",
                    "name": "Workflow Lifecycle Management",
                    "summary": "Create, edit, validate, and retrieve workflow definitions and drafts.",
                    "tags": ["flow", "editor"],
                    "complexity": "complex",
                    "domainMeta": {"entryPoint": "/api/workflows", "entryType": "api"},
                    "keywords": ["workflow", "draft", "validate"]
                },
                {
                    "id": "flow:workflows:library",
                    "type": "flow",
                    "name": "Shared Templates Library",
                    "summary": "Access and publish to the shared reusable workflow template catalog.",
                    "tags": ["flow", "templates"],
                    "complexity": "moderate",
                    "domainMeta": {"entryPoint": "/api/library", "entryType": "api"},
                    "keywords": ["library", "template"]
                },
                {
                    "id": "flow:workflows:automations",
                    "type": "flow",
                    "name": "Automations Configuration",
                    "summary": "Manage hooks, triggers, and automated rules for event-driven workflows.",
                    "tags": ["flow", "automations"],
                    "complexity": "moderate",
                    "domainMeta": {"entryPoint": "/api/automations", "entryType": "api"},
                    "keywords": ["automation", "trigger"]
                }
            ]
        },
        {
            "id": "domain:execution",
            "type": "domain",
            "name": "Execution Engine & Scheduler",
            "summary": "Execute workflows asynchronously, manage run logs, scheduler tasks, and process outputs.",
            "tags": ["domain", "execution", "scheduler"],
            "complexity": "complex",
            "domainMeta": {
                "entities": ["run", "log", "task", "job"],
                "businessRules": ["Executions are logged for auditability.", "Scheduled tasks trigger based on cron definitions."],
            },
            "keywords": ["run", "execute", "scheduler", "query", "run_log"],
            "flows": [
                {
                    "id": "flow:execution:run",
                    "type": "flow",
                    "name": "Workflow Execution & Logging",
                    "summary": "Synchronous and asynchronous execution of workflows and log capture.",
                    "tags": ["flow", "run"],
                    "complexity": "complex",
                    "domainMeta": {"entryPoint": "/api/run", "entryType": "api"},
                    "keywords": ["run", "execute", "log", "query"]
                },
                {
                    "id": "flow:execution:scheduler",
                    "type": "flow",
                    "name": "Scheduled Task Management",
                    "summary": "Define, list, and trigger scheduled recurring automation jobs.",
                    "tags": ["flow", "scheduler"],
                    "complexity": "moderate",
                    "domainMeta": {"entryPoint": "/api/scheduler", "entryType": "api"},
                    "keywords": ["schedule", "scheduler", "cron"]
                }
            ]
        },
        {
            "id": "domain:intelligence",
            "type": "domain",
            "name": "AI Copilot & Code Intelligence",
            "summary": "AI assistant for workflow generation, chat support, and codebase structure mapping/visualization.",
            "tags": ["domain", "ai", "intelligence"],
            "complexity": "complex",
            "domainMeta": {
                "entities": ["chat", "prompt", "knowledge graph", "domain graph"],
                "businessRules": ["Copilot recommendations are advisory.", "Code graph updates incrementally on refresh."],
            },
            "keywords": ["copilot", "code_graph", "code-graph", "understand", "analyzer"],
            "flows": [
                {
                    "id": "flow:intelligence:copilot",
                    "type": "flow",
                    "name": "Interactive Copilot Assistant",
                    "summary": "Get chat-based workspace assistance and code generation context.",
                    "tags": ["flow", "copilot"],
                    "complexity": "complex",
                    "domainMeta": {"entryPoint": "Sherpa agent", "entryType": "agent"},
                    "keywords": ["copilot", "chat", "assist"]
                },
                {
                    "id": "flow:intelligence:analysis",
                    "type": "flow",
                    "name": "Codebase Structure Mapping",
                    "summary": "Analyze files and endpoints to generate interactive dependency maps.",
                    "tags": ["flow", "code-graph"],
                    "complexity": "moderate",
                    "domainMeta": {"entryPoint": "/api/code-graph/view", "entryType": "api"},
                    "keywords": ["code-graph", "code_graph", "understand", "analyzer"]
                }
            ]
        },
        {
            "id": "domain:infrastructure",
            "type": "domain",
            "name": "System Infrastructure & Core",
            "summary": "Core database access, request context, FastAPI configuration, and app initialization.",
            "tags": ["domain", "infrastructure", "core"],
            "complexity": "moderate",
            "domainMeta": {
                "entities": ["database", "connection", "router", "middleware"],
                "businessRules": ["Database connections pool automatically.", "Unhandled errors log to system metrics."],
            },
            "keywords": ["database", "server", "main", "deps", "config"],
            "flows": [
                {
                    "id": "flow:infrastructure:db",
                    "type": "flow",
                    "name": "Database Operations",
                    "summary": "Database connectivity, schemas migration, and transaction helper scopes.",
                    "tags": ["flow", "database"],
                    "complexity": "moderate",
                    "domainMeta": {"entryPoint": "Database Connection Pool", "entryType": "system"},
                    "keywords": ["database", "db", "sql", "migration"]
                },
                {
                    "id": "flow:infrastructure:lifecycle",
                    "type": "flow",
                    "name": "Application Setup & Core",
                    "summary": "FastAPI application start, middleware injection, and root router mounting.",
                    "tags": ["flow", "lifecycle"],
                    "complexity": "simple",
                    "domainMeta": {"entryPoint": "server.py", "entryType": "file"},
                    "keywords": ["server", "main", "deps", "config"]
                }
            ]
        }
    ]

    domain_nodes = []
    flow_nodes = []
    flow_map = {} # flow_id -> list of node dictionaries

    # Build initial lists of domains and flows
    for dom in DOMAINS_DEFINITION:
        domain_nodes.append({
            "id": dom["id"],
            "type": "domain",
            "name": dom["name"],
            "summary": dom["summary"],
            "tags": dom["tags"],
            "complexity": dom["complexity"],
            "domainMeta": dom["domainMeta"]
        })
        for fl in dom["flows"]:
            flow_nodes.append({
                "id": fl["id"],
                "type": "flow",
                "name": fl["name"],
                "summary": fl["summary"],
                "tags": fl["tags"],
                "complexity": fl["complexity"],
                "domainMeta": fl["domainMeta"]
            })
            flow_map[fl["id"]] = []

    # Map nodes to flows dynamically
    for node in nodes:
        node_type = node.get("type", "")
        if node_type not in {"endpoint", "component", "function", "class", "file"}:
            continue
        
        # Skip files that are not Python/JS/TS/CSS/HTML code or Markdown docs
        if node_type == "file":
            filepath = str(node.get("filePath", ""))
            if not any(filepath.endswith(ext) for ext in (".py", ".ts", ".tsx", ".js", ".jsx", ".css", ".html", ".md")):
                continue

        name = str(node.get("name", "")).lower()
        filepath = str(node.get("filePath", "")).lower()
        tags = [t.lower() for t in node.get("tags", [])]

        best_flow_id = None
        best_score = 0

        # Score matching flows
        for dom in DOMAINS_DEFINITION:
            for fl in dom["flows"]:
                score = 0
                for kw in fl["keywords"]:
                    if kw in name:
                        score += 5
                    if kw in filepath:
                        score += 3
                    if kw in tags:
                        score += 2
                if score > best_score:
                    best_score = score
                    best_flow_id = fl["id"]

        # Default fallbacks if no strong match
        if best_score == 0:
            if "auth" in filepath or "user" in filepath:
                best_flow_id = "flow:auth:profile"
            elif "workflows" in filepath or "automation" in filepath or "library" in filepath or "draft" in filepath:
                best_flow_id = "flow:workflows:crud"
            elif "run" in filepath or "execute" in filepath or "scheduler" in filepath or "query" in filepath:
                best_flow_id = "flow:execution:run"
            elif "copilot" in filepath or "code_graph" in filepath or "understand" in filepath:
                best_flow_id = "flow:intelligence:copilot"
            elif "database" in filepath or "db" in filepath:
                best_flow_id = "flow:infrastructure:db"
            else:
                best_flow_id = "flow:infrastructure:lifecycle"

        if best_flow_id in flow_map:
            flow_map[best_flow_id].append(node)

    # Process steps and generate steps & edges
    step_nodes = []
    step_edges = []

    for flow_id, matched_nodes in flow_map.items():
        # Sort matched nodes to have a clean logical order:
        # 1. endpoints (API entry points)
        # 2. components (UI entry points)
        # 3. classes
        # 4. functions
        # 5. files / others
        def sort_key(n):
            nt = n.get("type", "")
            if nt == "endpoint":
                return 0
            if nt == "component":
                return 1
            if nt == "class":
                return 2
            if nt == "function":
                return 3
            return 4

        matched_nodes.sort(key=sort_key)

        for idx, node in enumerate(matched_nodes, start=1):
            step_id = f"step:{node['id']}"
            step_nodes.append({
                "id": step_id,
                "type": "step",
                "name": node.get("name") or f"Step {idx}",
                "filePath": node.get("filePath"),
                "summary": node.get("summary") or f"Code step: {node.get('name')}",
                "tags": ["step"] + list(node.get("tags") or [])[:3],
                "complexity": node.get("complexity") or "moderate",
            })
            step_edges.append({
                "source": flow_id,
                "target": step_id,
                "type": "flow_step",
                "direction": "forward",
                "weight": idx,
                "description": f"Flow Step {idx}",
            })

    # Domain relationships and structural flow nesting edges
    domain_edges = []
    for dom in DOMAINS_DEFINITION:
        for fl in dom["flows"]:
            domain_edges.append({
                "source": dom["id"],
                "target": fl["id"],
                "type": "contains_flow",
                "direction": "forward",
                "weight": 1
            })

    # Inter-domain transitions
    domain_edges.extend([
        {"source": "domain:auth", "target": "domain:workflows", "type": "cross_domain", "direction": "forward", "weight": 1, "description": "Authenticates user for workflow modifications."},
        {"source": "domain:workflows", "target": "domain:execution", "type": "cross_domain", "direction": "forward", "weight": 1, "description": "Sends saved workflows for execution."},
        {"source": "domain:intelligence", "target": "domain:workflows", "type": "cross_domain", "direction": "forward", "weight": 1, "description": "AI agent recommends or constructs workflows."},
        {"source": "domain:infrastructure", "target": "domain:auth", "type": "cross_domain", "direction": "forward", "weight": 1, "description": "Provides database user profiles storage."},
        {"source": "domain:infrastructure", "target": "domain:execution", "type": "cross_domain", "direction": "forward", "weight": 1, "description": "Persists query log captures."}
    ])

    domain_graph_nodes = domain_nodes + flow_nodes + step_nodes
    domain_graph_edges = domain_edges + step_edges

    return {
        "version": "1.0.0",
        "project": {
            "name": graph.get("project", {}).get("name", root.name),
            "description": "Understand-Anything compatible domain flowchart for dbSherpa Studio.",
            "languages": graph.get("project", {}).get("languages") or ["Python", "TypeScript", "JavaScript", "HTML", "CSS"],
            "frameworks": graph.get("project", {}).get("frameworks") or ["FastAPI", "React"],
            "analyzedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "gitCommitHash": _get_git_commit_hash(root)
        },
        "nodes": domain_graph_nodes,
        "edges": domain_graph_edges,
        "layers": [
            {
                "id": "domain-layer",
                "name": "Domains",
                "description": "Business domains and their process flows.",
                "nodeIds": [n["id"] for n in domain_graph_nodes],
            }
        ],
        "tour": [],
        "generatedBy": "dbsherpa-understand-anything-adapter",
        "schemaVersion": "understand-anything-compatible",
    }


def refresh_artifacts(mode: str = "all", root: Path | None = None) -> dict[str, Any]:
    root = root or project_root()
    out_dir = ua_dir(root)
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    knowledge_graph = load_json_file(graph_path(KNOWLEDGE_GRAPH, root))
    if mode in {"all", "structural", "knowledge"} or not knowledge_graph:
        knowledge_graph = generate_knowledge_graph(root)
        graph_path(KNOWLEDGE_GRAPH, root).write_text(json.dumps(knowledge_graph, indent=2), encoding="utf-8")
        written.append(KNOWLEDGE_GRAPH)
    if mode in {"all", "domain", "flow"}:
        domain_graph = generate_domain_graph(knowledge_graph, root)
        graph_path(DOMAIN_GRAPH, root).write_text(json.dumps(domain_graph, indent=2), encoding="utf-8")
        written.append(DOMAIN_GRAPH)
    meta = {
        "projectRoot": str(root),
        "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": "dbsherpa-understand-anything-adapter",
    }
    graph_path(META_FILE, root).write_text(json.dumps(meta, indent=2), encoding="utf-8")
    if not graph_path(CONFIG_FILE, root).exists():
        graph_path(CONFIG_FILE, root).write_text(json.dumps({"autoUpdate": False, "outputLanguage": "en"}, indent=2), encoding="utf-8")
    return {
        "ok": True,
        "mode": mode,
        "written": written,
        "artifactDir": str(out_dir),
    }


def load_ua_bundle(root: Path | None = None) -> dict[str, Any]:
    root = root or project_root()
    knowledge = load_json_file(graph_path(KNOWLEDGE_GRAPH, root))
    domain = load_json_file(graph_path(DOMAIN_GRAPH, root))
    return {
        "available": bool(knowledge),
        "artifactDir": str(ua_dir(root)),
        "knowledgeGraph": knowledge,
        "domainGraph": domain,
        "meta": load_json_file(graph_path(META_FILE, root)),
        "config": load_json_file(graph_path(CONFIG_FILE, root)),
    }


def find_plugin_root() -> Path | None:
    home = Path.home()
    candidates = [
        os.environ.get("CLAUDE_PLUGIN_ROOT"),
        str(home / ".understand-anything-plugin"),
        str(home / ".codex/understand-anything/understand-anything-plugin"),
        str(home / ".opencode/understand-anything/understand-anything-plugin"),
        str(home / ".pi/understand-anything/understand-anything-plugin"),
        str(home / "understand-anything/understand-anything-plugin"),
    ]
    for raw in candidates:
        if not raw:
            continue
        candidate = Path(raw).expanduser()
        if (candidate / "packages/dashboard").exists() and (candidate / "package.json").exists():
            return candidate
    return None


def start_ua_dashboard(root: Path | None = None) -> dict[str, Any]:
    root = root or project_root()
    plugin_root = find_plugin_root()
    if not plugin_root:
        return {
            "ok": False,
            "reason": "Understand-Anything plugin root not found.",
            "install": "curl -fsSL https://raw.githubusercontent.com/Lum1104/Understand-Anything/main/install.sh | bash -s codex",
        }
    dashboard_dir = plugin_root / "packages/dashboard"
    token = os.environ.get("UNDERSTAND_ACCESS_TOKEN", "dbsherpa-understand-anything")
    log_path = Path("/tmp/dbsherpa-understand-anything-dashboard.log")
    cmd = ["npx", "vite", "--host", "127.0.0.1"]
    env = {
        **os.environ,
        "GRAPH_DIR": str(root),
        "UNDERSTAND_ACCESS_TOKEN": token,
        "BROWSER_OPEN": "false",
    }
    with log_path.open("a", encoding="utf-8") as log:
        subprocess.Popen(cmd, cwd=str(dashboard_dir), env=env, stdout=log, stderr=log)
    return {
        "ok": True,
        "url": f"http://127.0.0.1:5173/?token={token}",
        "pluginRoot": str(plugin_root),
        "log": str(log_path),
    }
