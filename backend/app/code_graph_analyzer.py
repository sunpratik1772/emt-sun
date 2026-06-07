import os
import ast
import re
import time
from pathlib import Path
from typing import Dict, List, Any, Set, Tuple

class CodebaseAnalyzer:
    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir).resolve()
        self.nodes: List[Dict[str, Any]] = []
        self.edges: List[Dict[str, Any]] = []
        
        # Track all processed files to build import map
        self.files_index: Dict[str, Path] = {}  # relative path -> absolute path
        self.python_module_map: Dict[str, str] = {}  # module_path (e.g. app.routers.workflows) -> rel_file_path
        
        # Track defined symbols to resolve calls
        self.functions_index: Dict[str, List[Tuple[str, str]]] = {}  # name -> list of (node_id, rel_file_path)
        self.classes_index: Dict[str, List[Tuple[str, str]]] = {}    # name -> list of (node_id, rel_file_path)

    def should_ignore(self, path: Path) -> bool:
        ignore_dirs = {
            ".git", "node_modules", "__pycache__", ".venv", "venv", 
            "dist", "build", ".run", "scratch", ".understand-anything",
            ".gemini", "tests", "test_reports", "copilot_chats.db"
        }
        for part in path.parts:
            if part in ignore_dirs:
                return True

        # Ignore disabled/inactive Studio node spec files
        if "backend" in path.parts and "engine" in path.parts and "nodes" in path.parts:
            stem = path.stem
            if stem not in ("__init__", "mcp_common"):
                try:
                    from engine.node_availability import is_agent_visible_type
                    from engine.registry import NODE_SPECS
                    if stem in NODE_SPECS and not is_agent_visible_type(stem):
                        return True
                except Exception:
                    pass

        return False

    def scan_files(self):
        """First pass: find and index all source files."""
        for root, dirs, files in os.walk(self.root_dir):
            # Prune directories in-place to prevent os.walk from entering ignored directories
            dirs[:] = [d for d in dirs if not self.should_ignore(Path(root) / d)]
            
            root_path = Path(root)
            if self.should_ignore(root_path):
                continue
                
            for file in files:
                file_path = root_path / file
                if self.should_ignore(file_path):
                    continue
                    
                suffix = file_path.suffix
                if suffix in (".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".json", ".md"):
                    rel_path = file_path.relative_to(self.root_dir).as_posix()
                    self.files_index[rel_path] = file_path
                    
                    if suffix == ".py":
                        # Map relative path within backend to python module path
                        # e.g., backend/app/routers/workflows.py -> app.routers.workflows
                        try:
                            backend_path = file_path.relative_to(self.root_dir / "backend")
                            module_parts = list(backend_path.parent.parts)
                            if backend_path.stem != "__init__":
                                module_parts.append(backend_path.stem)
                            module_name = ".".join(module_parts)
                            self.python_module_map[module_name] = rel_path
                        except ValueError:
                            # Not under backend
                            pass

    def compute_python_complexity(self, node: ast.AST) -> int:
        complexity = 1
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.For, ast.While, ast.AsyncFor, ast.ExceptHandler, ast.Try, ast.IfExp)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
        return complexity

    def parse_python_file(self, rel_path: str, file_path: Path):
        file_id = f"file:{rel_path}"
        try:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(file_path))
        except Exception as e:
            # Fallback node if parsing fails
            self.nodes.append({
                "id": file_id,
                "type": "file",
                "name": file_path.name,
                "filePath": rel_path,
                "summary": f"Python source file (unable to parse: {str(e)})",
                "tags": ["python", "error"],
                "complexity": 1
            })
            return

        docstring = ast.get_docstring(tree) or ""
        self.nodes.append({
            "id": file_id,
            "type": "file",
            "name": file_path.name,
            "filePath": rel_path,
            "summary": docstring or f"Python module: {file_path.name}",
            "tags": ["python"],
            "complexity": 1
        })

        # Track import statements to resolve references later
        imports_in_file: List[Tuple[str, str]] = []  # (imported_name, resolved_rel_path)
        
        # First walk to map defined classes & functions
        file_classes = []
        file_functions = []
        
        # Try to scan for APIRouter prefix
        router_prefix = ""
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "router":
                        if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and node.value.func.id == "APIRouter":
                            for kw in node.value.keywords:
                                if kw.arg == "prefix" and isinstance(kw.value, ast.Constant):
                                    router_prefix = str(kw.value.value)

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                class_id = f"class:{rel_path}:{node.name}"
                class_summary = ast.get_docstring(node) or f"Class representing {node.name}"
                self.nodes.append({
                    "id": class_id,
                    "type": "class",
                    "name": node.name,
                    "filePath": rel_path,
                    "summary": class_summary,
                    "tags": ["python", "class"],
                    "complexity": 1
                })
                self.edges.append({
                    "source": file_id,
                    "target": class_id,
                    "type": "contains",
                    "direction": "forward",
                    "weight": 1
                })
                
                # Index the class
                if node.name not in self.classes_index:
                    self.classes_index[node.name] = []
                self.classes_index[node.name].append((class_id, rel_path))
                
                # Map methods inside class
                for subnode in node.body:
                    if isinstance(subnode, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        method_id = f"function:{rel_path}:{node.name}.{subnode.name}"
                        method_summary = ast.get_docstring(subnode) or ""
                        complexity = self.compute_python_complexity(subnode)
                        
                        self.nodes.append({
                            "id": method_id,
                            "type": "function",
                            "name": f"{node.name}.{subnode.name}",
                            "filePath": rel_path,
                            "summary": method_summary or f"Method {subnode.name} on class {node.name}",
                            "tags": ["python", "method"],
                            "complexity": complexity
                        })
                        self.edges.append({
                            "source": class_id,
                            "target": method_id,
                            "type": "contains",
                            "direction": "forward",
                            "weight": 1
                        })

            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_id = f"function:{rel_path}:{node.name}"
                func_summary = ast.get_docstring(node) or ""
                complexity = self.compute_python_complexity(node)
                
                self.nodes.append({
                    "id": func_id,
                    "type": "function",
                    "name": node.name,
                    "filePath": rel_path,
                    "summary": func_summary or f"Function {node.name}",
                    "tags": ["python", "function"],
                    "complexity": complexity
                })
                self.edges.append({
                    "source": file_id,
                    "target": func_id,
                    "type": "contains",
                    "direction": "forward",
                    "weight": 1
                })
                
                # Index the function
                if node.name not in self.functions_index:
                    self.functions_index[node.name] = []
                self.functions_index[node.name].append((func_id, rel_path))

                # Check if it exposes an API endpoint (FastAPI decorator)
                for decorator in node.decorator_list:
                    # Check for router decorators: @router.get, etc.
                    is_endpoint = False
                    method = ""
                    path_val = ""
                    
                    if isinstance(decorator, ast.Call):
                        func = decorator.func
                        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                            if func.value.id in ("router", "app"):
                                is_endpoint = True
                                method = func.attr.upper()
                        elif isinstance(func, ast.Name) and func.id in ("get", "post", "delete", "put", "patch"):
                            is_endpoint = True
                            method = func.id.upper()
                            
                        # Extract the path (first arg)
                        if is_endpoint and len(decorator.args) > 0:
                            first_arg = decorator.args[0]
                            if isinstance(first_arg, ast.Constant):
                                path_val = str(first_arg.value)
                                
                    if is_endpoint and method and path_val:
                        # Combine with APIRouter prefix
                        combined_path = router_prefix + path_val if router_prefix else path_val
                        # Ensure /api is prefixed if it's not already, since server.py mounts routers at /api
                        if not combined_path.startswith("/api") and not combined_path.startswith("http"):
                            # Special case: docs router has prefix docs but inside server.py it is app.include_router(docs_routes.router, prefix="/api")
                            # If the router prefix already contains docs, combined path might be like "/docs" or "/docs/{filename}"
                            if combined_path.startswith("/"):
                                combined_path = "/api" + combined_path
                            else:
                                combined_path = "/api/" + combined_path
                        
                        endpoint_id = f"endpoint:{method}:{combined_path}"
                        self.nodes.append({
                            "id": endpoint_id,
                            "type": "endpoint",
                            "name": f"{method} {combined_path}",
                            "summary": func_summary or f"FastAPI Endpoint: {method} {combined_path}",
                            "tags": ["api", method.lower()],
                            "complexity": complexity
                        })
                        self.edges.append({
                            "source": func_id,
                            "target": endpoint_id,
                            "type": "exposes",
                            "direction": "forward",
                            "weight": 2
                        })

            # Handle imports in this file
            elif isinstance(node, ast.Import):
                for name in node.names:
                    # Resolve simple import e.g., `import app.routers.workflows`
                    target_rel = self.python_module_map.get(name.name)
                    if target_rel:
                        self.edges.append({
                            "source": file_id,
                            "target": f"file:{target_rel}",
                            "type": "imports",
                            "direction": "forward",
                            "weight": 1
                        })
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    # Resolve module path, e.g. `from app.database import init_db`
                    module_name = node.module
                    if node.level > 0:
                        # Relative import e.g. `from .database import ...`
                        # Resolve relative to current module path
                        try:
                            backend_path = file_path.relative_to(self.root_dir / "backend")
                            parent_parts = list(backend_path.parent.parts)
                            # Remove parts based on level
                            for _ in range(node.level - 1):
                                if parent_parts:
                                    parent_parts.pop()
                            module_name = ".".join(parent_parts) + "." + node.module
                        except Exception:
                            pass
                            
                    target_rel = self.python_module_map.get(module_name)
                    if not target_rel:
                        # Try exact match or relative fallback
                        # e.g., if module name is "database"
                        for m_key, m_val in self.python_module_map.items():
                            if m_key.endswith(module_name):
                                target_rel = m_val
                                break
                                
                    if target_rel:
                        self.edges.append({
                            "source": file_id,
                            "target": f"file:{target_rel}",
                            "type": "imports",
                            "direction": "forward",
                            "weight": 1
                        })

    def parse_frontend_file(self, rel_path: str, file_path: Path):
        file_id = f"file:{rel_path}"
        suffix = file_path.suffix
        tags = ["javascript"] if suffix in (".js", ".jsx") else ["typescript"]
        if suffix in (".jsx", ".tsx"):
            tags.append("react")
            
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception as e:
            self.nodes.append({
                "id": file_id,
                "type": "file",
                "name": file_path.name,
                "filePath": rel_path,
                "summary": f"Frontend source file (unable to read: {str(e)})",
                "tags": tags + ["error"],
                "complexity": 1
            })
            return

        self.nodes.append({
            "id": file_id,
            "type": "file",
            "name": file_path.name,
            "filePath": rel_path,
            "summary": f"Frontend source file: {file_path.name}",
            "tags": tags,
            "complexity": 1
        })

        # Resolve relative frontend imports
        # Looks for: `import X from 'path'` or `import 'path'`
        import_pattern = re.compile(r"import\s+(?:[\w\s{},*]+\s+from\s+)?['\"]([^'\"]+)['\"]")
        lines = content.splitlines()
        for line in lines:
            match = import_pattern.search(line)
            if match:
                import_ref = match.group(1)
                if import_ref.startswith("."):  # Relative import
                    # Resolve path relative to current folder
                    parent_dir = file_path.parent
                    resolved_path = (parent_dir / import_ref).resolve()
                    
                    # Try suffixes
                    found_rel = None
                    for ext in (".tsx", ".ts", ".jsx", ".js", "/index.tsx", "/index.ts", "/index.jsx", "/index.js"):
                        check_path = resolved_path.with_name(resolved_path.name + ext) if not ext.startswith("/") else Path(str(resolved_path) + ext)
                        try:
                            if check_path.exists():
                                found_rel = check_path.relative_to(self.root_dir).as_posix()
                                break
                        except ValueError:
                            pass
                            
                    if found_rel:
                        self.edges.append({
                            "source": file_id,
                            "target": f"file:{found_rel}",
                            "type": "imports",
                            "direction": "forward",
                            "weight": 1
                        })

        # Parse simple component declarations
        # e.g., export default function DashboardHome()
        component_pattern = re.compile(r"export\s+(?:default\s+)?function\s+([A-Za-z0-9_]+)")
        arrow_pattern = re.compile(r"export\s+const\s+([A-Za-z0-9_]+)\s*=\s*\([^)]*\)\s*=>")
        
        components_found = set()
        for line in lines:
            c_match = component_pattern.search(line)
            if c_match:
                components_found.add(c_match.group(1))
            a_match = arrow_pattern.search(line)
            if a_match:
                components_found.add(a_match.group(1))
                
        for comp in components_found:
            # Skip common utility helper names
            if comp in ("request", "fetchJson", "workflowToCard"):
                continue
            comp_id = f"component:{rel_path}:{comp}"
            self.nodes.append({
                "id": comp_id,
                "type": "component",
                "name": comp,
                "filePath": rel_path,
                "summary": f"React component {comp}",
                "tags": tags + ["component"],
                "complexity": 1
            })
            self.edges.append({
                "source": file_id,
                "target": comp_id,
                "type": "contains",
                "direction": "forward",
                "weight": 1
            })

    def run_analysis(self) -> Dict[str, Any]:
        """Perform scan, index, and full parsing."""
        start_time = time.time()
        self.scan_files()
        
        for rel_path, abs_path in self.files_index.items():
            if abs_path.suffix == ".py":
                self.parse_python_file(rel_path, abs_path)
            elif abs_path.suffix in (".js", ".ts", ".jsx", ".tsx"):
                self.parse_frontend_file(rel_path, abs_path)
            else:
                # Basic node for other configuration or doc files
                self.nodes.append({
                    "id": f"file:{rel_path}",
                    "type": "file",
                    "name": abs_path.name,
                    "filePath": rel_path,
                    "summary": f"Resource/Config file: {abs_path.name}",
                    "tags": [abs_path.suffix.lstrip(".")],
                    "complexity": 1
                })

        duration = time.time() - start_time
        
        # Deduplicate nodes by ID
        unique_nodes = []
        seen_nodes = set()
        for node in self.nodes:
            node_id = node.get("id")
            if node_id not in seen_nodes:
                seen_nodes.add(node_id)
                unique_nodes.append(node)
                
        # Deduplicate edges by source+target+type
        unique_edges = []
        seen_edges = set()
        for edge in self.edges:
            edge_key = (edge.get("source"), edge.get("target"), edge.get("type"))
            if edge_key not in seen_edges:
                seen_edges.add(edge_key)
                unique_edges.append(edge)

        project_meta = {
            "name": "emt-sun",
            "description": "Codebase Knowledge Graph generated statically by dbSherpa Code Analyzer.",
            "languages": ["Python", "TypeScript", "JavaScript", "HTML", "CSS"],
            "frameworks": ["FastAPI", "React"],
            "analyzedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "durationSeconds": round(duration, 3)
        }
        
        return {
            "project": project_meta,
            "nodes": unique_nodes,
            "edges": unique_edges
        }

if __name__ == "__main__":
    import json
    analyzer = CodebaseAnalyzer(os.getcwd())
    res = analyzer.run_analysis()
    print(f"Analysis complete. Found {len(res['nodes'])} nodes, {len(res['edges'])} edges.")
