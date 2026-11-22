"""
ProjectAnalyzer: Analyzes extracted ZIP project directories to detect languages,
frameworks, project structure, databases, entry points, and dependencies.

SECURITY: Never reads or exposes secret values from config files or .env files.
Only inspects dependency/package names in manifests, structural markers, and
non-secret metadata.
"""
import json
import os
import re
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

logger = logging.getLogger("jobsentinel.project_analyzer")

# ---------------------------------------------------------------------------
# Language → file extensions mapping
# ---------------------------------------------------------------------------
LANGUAGE_EXTENSIONS: Dict[str, List[str]] = {
    "python":     [".py", ".pyw", ".pyi"],
    "javascript": [".js", ".mjs", ".cjs", ".jsx"],
    "typescript": [".ts", ".tsx", ".mts"],
    "java":       [".java"],
    "c":          [".c", ".h"],
    "cpp":        [".cpp", ".cc", ".cxx", ".hpp", ".hxx"],
    "go":         [".go"],
    "rust":       [".rs"],
    "php":        [".php"],
    "html":       [".html", ".htm"],
    "css":        [".css", ".scss", ".sass", ".less"],
    "sql":        [".sql"],
}

# Reverse map: extension → language
_EXT_TO_LANG: Dict[str, str] = {}
for _lang, _exts in LANGUAGE_EXTENSIONS.items():
    for _ext in _exts:
        _EXT_TO_LANG[_ext] = _lang

# ---------------------------------------------------------------------------
# Config / manifest filenames to detect
# ---------------------------------------------------------------------------
KNOWN_CONFIG_FILES = [
    "package.json",
    "package-lock.json",
    "requirements.txt",
    "pyproject.toml",
    "Pipfile",
    "pom.xml",
    "build.gradle",
    "Cargo.toml",
    "go.mod",
    "composer.json",
    "CMakeLists.txt",
    "Dockerfile",
    "docker-compose.yml",
    ".env.example",
]

# ---------------------------------------------------------------------------
# Framework detection rules (verified via manifest / source evidence)
# ---------------------------------------------------------------------------
# (config_file, search_pattern_in_file, framework_name)
FRAMEWORK_RULES = [
    # JavaScript / TypeScript (via package.json)
    ("package.json", r'"react"\s*:', "React"),
    ("package.json", r'"next"\s*:', "Next.js"),
    ("package.json", r'"express"\s*:', "Express"),
    ("package.json", r'"@angular/core"\s*:', "Angular"),
    ("package.json", r'"vue"\s*:', "Vue"),
    ("package.json", r'"nuxt"\s*:', "Nuxt.js"),
    ("package.json", r'"svelte"\s*:', "Svelte"),
    ("package.json", r'"@nestjs/core"\s*:', "NestJS"),
    ("package.json", r'"main"\s*:|"scripts"\s*:', "Node.js"),
    # Python (via requirements.txt)
    ("requirements.txt", r'\bflask\b', "Flask"),
    ("requirements.txt", r'\bdjango\b', "Django"),
    ("requirements.txt", r'\bfastapi\b', "FastAPI"),
    # Python (via pyproject.toml)
    ("pyproject.toml", r'\bflask\b', "Flask"),
    ("pyproject.toml", r'\bdjango\b', "Django"),
    ("pyproject.toml", r'\bfastapi\b', "FastAPI"),
    # Python (via Pipfile)
    ("Pipfile", r'\bflask\b', "Flask"),
    ("Pipfile", r'\bdjango\b', "Django"),
    ("Pipfile", r'\bfastapi\b', "FastAPI"),
    # Java (pom.xml / build.gradle → Spring Boot)
    ("pom.xml", r'spring-boot', "Spring Boot"),
    ("build.gradle", r'spring-boot|org\.springframework\.boot', "Spring Boot"),
    # PHP (composer.json → Laravel / Symfony)
    ("composer.json", r'"laravel/framework"', "Laravel"),
    ("composer.json", r'"symfony/', "Symfony"),
    # Go modules
    ("go.mod", r'github\.com/gin-gonic/gin', "Gin"),
    ("go.mod", r'github\.com/labstack/echo', "Echo"),
]

FRONTEND_FRAMEWORKS = {"React", "Next.js", "Angular", "Vue", "Nuxt.js", "Svelte"}
BACKEND_FRAMEWORKS = {"Flask", "Django", "FastAPI", "Express", "Spring Boot", "Laravel", "Symfony", "NestJS", "Echo", "Gin"}

# Max files to include in the tree (avoid huge output)
MAX_TREE_FILES = 500
# Max depth for the file tree
MAX_TREE_DEPTH = 6


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------
@dataclass
class ProjectAnalysis:
    project_name: str
    total_files: int
    total_size_bytes: int
    languages: List[str]
    frameworks: List[str]
    config_files: List[str]
    frontend_dir: Optional[str]
    backend_dir: Optional[str]
    database_dir: Optional[str]
    project_type: str
    file_tree: Dict[str, Any]
    entry_points: Dict[str, str]
    dependencies: Dict[str, List[str]]
    security_status: str
    analysis_status: str
    databases: List[str] = field(default_factory=list)
    config_file_paths: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------
class ProjectAnalyzer:
    """Analyzes an extracted project directory and returns a ProjectAnalysis."""

    def __init__(self, project_dir: Path, project_name: Optional[str] = None):
        self.project_dir = Path(project_dir)
        self.project_name = project_name or self.project_dir.name

    def analyze(self) -> ProjectAnalysis:
        """Run the full analysis pipeline."""
        logger.info("Starting project analysis for: %s", self.project_dir)

        all_files = self._collect_files()
        total_files = len(all_files)
        total_size = sum(f.stat().st_size for f in all_files if f.exists())

        languages = self._detect_languages(all_files)
        config_files_found, config_file_paths = self._detect_config_files()
        frameworks = self._detect_frameworks(config_files_found, all_files)
        frontend_dir, backend_dir, database_dir = self._detect_project_structure(all_files)
        databases = self._detect_databases(all_files, config_files_found)
        project_type = self._classify_project_type(
            languages, frameworks, frontend_dir, backend_dir
        )
        file_tree = self._build_file_tree()
        entry_points = self._detect_entry_points(all_files, languages, frameworks)
        dependencies = self._extract_dependencies(config_files_found)

        logger.info(
            "Analysis complete: %d files, langs=%s, frameworks=%s, dbs=%s, type=%s",
            total_files, languages, frameworks, databases, project_type
        )

        return ProjectAnalysis(
            project_name=self.project_name,
            total_files=total_files,
            total_size_bytes=total_size,
            languages=languages,
            frameworks=frameworks,
            config_files=config_files_found,
            frontend_dir=frontend_dir,
            backend_dir=backend_dir,
            database_dir=database_dir,
            project_type=project_type,
            file_tree=file_tree,
            entry_points=entry_points,
            dependencies=dependencies,
            security_status="CLEAN",
            analysis_status="COMPLETED",
            databases=databases,
            config_file_paths=config_file_paths,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _collect_files(self) -> List[Path]:
        """Return a flat list of all files in the project directory."""
        result: List[Path] = []
        try:
            for root, dirs, files in os.walk(self.project_dir):
                dirs[:] = [
                    d for d in dirs
                    if d not in {"__pycache__", "node_modules", ".git", ".venv", "venv", "env", "dist", "build", ".tox", ".pytest_cache"}
                ]
                for fname in files:
                    result.append(Path(root) / fname)
        except Exception as exc:
            logger.warning("Error collecting files: %s", exc)
        return result

    def _detect_languages(self, all_files: List[Path]) -> List[str]:
        """Detect programming languages by scanning file extensions."""
        found: set = set()
        for fp in all_files:
            ext = fp.suffix.lower()
            lang = _EXT_TO_LANG.get(ext)
            if lang:
                found.add(lang)
        return sorted(found)

    def _detect_config_files(self) -> Tuple[List[str], List[str]]:
        """Return unique config basenames and all relative config paths found."""
        found_names: List[str] = []
        found_paths: List[str] = []
        known_set = set(KNOWN_CONFIG_FILES)

        for root, dirs, files in os.walk(self.project_dir):
            dirs[:] = [d for d in sorted(dirs) if d not in {"node_modules", ".git", ".venv", "venv", "__pycache__"}]
            for fname in sorted(files):
                if fname in known_set:
                    rel = (Path(root) / fname).relative_to(self.project_dir).as_posix()
                    found_paths.append(rel)
                    if fname not in found_names:
                        found_names.append(fname)

        # Preserve canonical order for found_names
        ordered_names = [cfg for cfg in KNOWN_CONFIG_FILES if cfg in found_names]
        return ordered_names, found_paths

    def _safe_read(self, path: Path, max_bytes: int = 65536) -> str:
        """Read a text file safely, returning empty string on error. Never reads .env files."""
        if path.name == ".env" or path.name.startswith(".env.") and path.name != ".env.example":
            return ""
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                return fh.read(max_bytes)
        except Exception:
            return ""

    def _find_all_files(self, filename: str) -> List[Path]:
        """Find all occurrences of a filename in the project tree."""
        matches: List[Path] = []
        for root, dirs, files in os.walk(self.project_dir):
            dirs[:] = [d for d in sorted(dirs) if d not in {"node_modules", ".git", ".venv", "venv", "__pycache__"}]
            if filename in files:
                matches.append(Path(root) / filename)
        return matches

    def _detect_frameworks(self, config_files_found: List[str], all_files: List[Path]) -> List[str]:
        """Detect frameworks strictly from actual manifest / file evidence."""
        detected: set = set()
        file_cache: Dict[str, List[str]] = {}

        for cfg_name, pattern, framework in FRAMEWORK_RULES:
            if cfg_name not in config_files_found:
                continue
            if cfg_name not in file_cache:
                file_cache[cfg_name] = [self._safe_read(p) for p in self._find_all_files(cfg_name)]
            for content in file_cache[cfg_name]:
                if re.search(pattern, content, re.IGNORECASE):
                    detected.add(framework)
                    break

        # Keep Node.js only if Express/NestJS/server JS exists OR no frontend-only framework exclusively owns package.json
        # Wait: if a package.json has Express or a backend JS entry without React/Vue/Angular/Next, Node.js is appropriate.
        # If React AND Express are both present, keep React, Express, and Node.js or keep specific frameworks.
        frontend_only = {"React", "Next.js", "Angular", "Vue", "Nuxt.js", "Svelte"}
        if (frontend_only & detected) and "Express" not in detected and "NestJS" not in detected:
            # Check if there is a separate server JS file or second package.json with main/server
            has_server_js = any(
                fp.name in {"server.js", "app.js", "server.ts", "app.ts"}
                for fp in all_files
            )
            if not has_server_js:
                detected.discard("Node.js")

        return sorted(detected)

    def _analyze_directory_role(self, dir_path: Path) -> Dict[str, bool]:
        """
        Inspect actual files inside `dir_path` to verify whether it truly contains
        frontend, backend, or database technology. Never trust directory names alone!
        """
        roles = {"frontend": False, "backend": False, "database": False}
        dir_files: List[Path] = []
        for root, dirs, files in os.walk(dir_path):
            dirs[:] = [d for d in dirs if d not in {"node_modules", ".git", ".venv", "venv", "__pycache__"}]
            for fname in files:
                dir_files.append(Path(root) / fname)

        if not dir_files:
            return roles

        exts = {f.suffix.lower() for f in dir_files}
        names = {f.name for f in dir_files}

        # Check package.json inside this directory
        pkg_jsons = [f for f in dir_files if f.name == "package.json"]
        pkg_has_frontend = False
        pkg_has_backend = False
        for pj in pkg_jsons:
            txt = self._safe_read(pj)
            if re.search(r'"(react|next|vue|nuxt|@angular/core|svelte|vite)"\s*:', txt, re.IGNORECASE):
                pkg_has_frontend = True
            if re.search(r'"(express|@nestjs/core|koa|fastify|hapi)"\s*:', txt, re.IGNORECASE):
                pkg_has_backend = True

        # Frontend evidence: frontend frameworks in package.json, or JSX/TSX/Vue/Svelte/HTML/CSS files
        if pkg_has_frontend or (exts & {".jsx", ".tsx", ".vue", ".svelte"}) or (
            (".html" in exts or ".htm" in exts or ".css" in exts)
            and not (exts & {".py", ".java", ".go", ".rs", ".php", ".c", ".cpp"})
            and not pkg_has_backend
        ):
            roles["frontend"] = True

        # Backend evidence: Python/Java/Go/Rust/PHP/C/C++ files or manifests, or Express/NestJS
        backend_exts = {".py", ".java", ".go", ".rs", ".php", ".c", ".cpp", ".cc", ".cxx"}
        backend_manifests = {"requirements.txt", "pyproject.toml", "Pipfile", "pom.xml", "build.gradle", "Cargo.toml", "go.mod", "composer.json"}
        if (exts & backend_exts) or (names & backend_manifests) or pkg_has_backend:
            roles["backend"] = True

        # Database evidence: .sql, .db, .sqlite files
        if exts & {".sql", ".db", ".sqlite", ".sqlite3"}:
            roles["database"] = True

        return roles

    def _detect_project_structure(self, all_files: List[Path]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Detect frontend, backend, and database directories by inspecting actual files
        inside directories (not blindly trusting folder names).
        Supports both root-level splits (frontend/, backend/) and single-root-wrapped
        archives (my-project/frontend/, my-project/backend/).
        """
        frontend_dir: Optional[str] = None
        backend_dir: Optional[str] = None
        database_dir: Optional[str] = None

        try:
            top_entries = [
                p for p in sorted(self.project_dir.iterdir(), key=lambda x: x.name.lower())
                if not p.name.startswith(".") and p.name not in {"__pycache__", "node_modules", ".venv", "venv"}
            ]
        except Exception:
            return None, None, None

        top_dirs = [p for p in top_entries if p.is_dir()]
        top_files = [p for p in top_entries if p.is_file()]

        # If archive has a single root wrapper directory (e.g. my-project/) and no files at root,
        # inspect its immediate subdirectories as the logical project root dirs.
        candidate_dirs = top_dirs
        prefix = ""
        if len(top_dirs) == 1 and not top_files:
            inner_dirs = [
                p for p in sorted(top_dirs[0].iterdir(), key=lambda x: x.name.lower())
                if p.is_dir() and not p.name.startswith(".") and p.name not in {"__pycache__", "node_modules", ".venv", "venv"}
            ]
            if inner_dirs:
                candidate_dirs = inner_dirs
                prefix = top_dirs[0].name + "/"

        # Inspect candidate directories and verify via actual file contents
        fe_preferred = {"frontend", "client", "web", "ui"}
        be_preferred = {"backend", "server", "api", "service", "services"}
        db_preferred = {"database", "db", "migrations", "schemas"}

        dir_roles: List[Tuple[Path, Dict[str, bool]]] = [
            (d, self._analyze_directory_role(d)) for d in candidate_dirs
        ]

        # Pass 1: prefer conventional names ONLY when verified by actual project files
        for d, roles in dir_roles:
            nl = d.name.lower()
            rel = prefix + d.name
            if nl in fe_preferred and roles["frontend"] and frontend_dir is None:
                frontend_dir = rel
            if nl in be_preferred and roles["backend"] and backend_dir is None:
                backend_dir = rel
            if nl in db_preferred and roles["database"] and database_dir is None:
                database_dir = rel

        # Pass 2: fallback to any verified directory (e.g. go-service/, src/, public/)
        for d, roles in dir_roles:
            rel = prefix + d.name
            if roles["frontend"] and not roles["backend"] and frontend_dir is None:
                frontend_dir = rel
            elif roles["backend"] and not roles["frontend"] and backend_dir is None:
                backend_dir = rel
            if roles["database"] and not roles["frontend"] and not roles["backend"] and database_dir is None:
                database_dir = rel

        # Pass 3: if still none found for database, accept any dir with .sql files
        if database_dir is None:
            for d, roles in dir_roles:
                if roles["database"]:
                    database_dir = prefix + d.name
                    break

        return frontend_dir, backend_dir, database_dir

    def _detect_databases(self, all_files: List[Path], config_files_found: List[str]) -> List[str]:
        """Detect database technologies from dependencies, docker-compose, and SQL files."""
        dbs: set = set()

        # Check Python manifests
        for cfg in ("requirements.txt", "pyproject.toml", "Pipfile"):
            if cfg in config_files_found:
                for p in self._find_all_files(cfg):
                    txt = self._safe_read(p).lower()
                    if any(k in txt for k in ("psycopg2", "asyncpg", "pg8000")):
                        dbs.add("PostgreSQL")
                    if any(k in txt for k in ("pymysql", "mysqlclient", "mysql-connector")):
                        dbs.add("MySQL")
                    if "pymongo" in txt:
                        dbs.add("MongoDB")
                    if "redis" in txt:
                        dbs.add("Redis")

        # Check package.json
        if "package.json" in config_files_found:
            for p in self._find_all_files("package.json"):
                txt = self._safe_read(p).lower()
                if '"pg"' in txt or '"postgres"' in txt:
                    dbs.add("PostgreSQL")
                if '"mysql"' in txt or '"mysql2"' in txt:
                    dbs.add("MySQL")
                if '"sqlite3"' in txt or '"better-sqlite3"' in txt:
                    dbs.add("SQLite")
                if '"mongodb"' in txt or '"mongoose"' in txt:
                    dbs.add("MongoDB")
                if '"redis"' in txt or '"ioredis"' in txt:
                    dbs.add("Redis")

        # Check docker-compose.yml service images (never reads passwords/env values)
        if "docker-compose.yml" in config_files_found:
            for p in self._find_all_files("docker-compose.yml"):
                txt = self._safe_read(p).lower()
                if re.search(r'image:\s*postgres', txt):
                    dbs.add("PostgreSQL")
                if re.search(r'image:\s*(mysql|mariadb)', txt):
                    dbs.add("MySQL")
                if re.search(r'image:\s*mongo', txt):
                    dbs.add("MongoDB")
                if re.search(r'image:\s*redis', txt):
                    dbs.add("Redis")

        # Check .sql files
        sql_files = [f for f in all_files if f.suffix.lower() == ".sql"]
        if sql_files and not dbs:
            for sf in sql_files[:5]:
                txt = self._safe_read(sf, max_bytes=8192).lower()
                if "serial" in txt or "jsonb" in txt:
                    dbs.add("PostgreSQL")
                elif "auto_increment" in txt or "innodb" in txt:
                    dbs.add("MySQL")
                elif "autoincrement" in txt:
                    dbs.add("SQLite")
            if not dbs:
                dbs.add("SQL")

        return sorted(dbs)

    def _classify_project_type(
        self,
        languages: List[str],
        frameworks: List[str],
        frontend_dir: Optional[str],
        backend_dir: Optional[str],
    ) -> str:
        """Classify the overall project type as a human-readable string."""
        has_frontend = bool(frontend_dir) or any(f in frameworks for f in FRONTEND_FRAMEWORKS)
        has_backend  = bool(backend_dir)  or any(f in frameworks for f in BACKEND_FRAMEWORKS)

        if has_frontend and has_backend:
            return "Full-Stack Application"

        if has_frontend:
            if "React" in frameworks:
                return "React Application"
            if "Vue" in frameworks:
                return "Vue Application"
            if "Angular" in frameworks:
                return "Angular Application"
            if "Next.js" in frameworks:
                return "Next.js Application"
            return "Frontend Application"

        if "python" in languages:
            if "Flask" in frameworks:
                return "Flask Application"
            if "Django" in frameworks:
                return "Django Application"
            if "FastAPI" in frameworks:
                return "FastAPI Application"
            return "Python Application"

        if "java" in languages:
            if "Spring Boot" in frameworks:
                return "Spring Boot Application"
            return "Java Application"

        if "cpp" in languages:
            return "C++ Application"

        if "c" in languages:
            return "C Application"

        if "javascript" in languages or "typescript" in languages:
            if "Express" in frameworks:
                return "Express.js Application"
            if "NestJS" in frameworks:
                return "NestJS Application"
            return "Node.js Application"

        if "go" in languages:
            return "Go Application"

        if "rust" in languages:
            return "Rust Application"

        if "php" in languages:
            if "Laravel" in frameworks:
                return "Laravel Application"
            return "PHP Application"

        if "html" in languages:
            return "Static Web Page"

        if languages:
            return f"{languages[0].capitalize()} Application"

        return "Unknown Project"

    def _build_file_tree(self) -> Dict[str, Any]:
        """Build a nested dict representing the project file structure."""
        tree: Dict[str, Any] = {}
        file_count = 0

        for root, dirs, files in os.walk(self.project_dir):
            dirs[:] = [
                d for d in sorted(dirs)
                if d not in {"__pycache__", "node_modules", ".git", ".venv", "venv", "env", "dist", "build", ".pytest_cache"}
            ]

            rel_root = Path(root).relative_to(self.project_dir)
            depth = len(rel_root.parts)
            if depth >= MAX_TREE_DEPTH:
                continue

            node = tree
            for part in rel_root.parts:
                node = node.setdefault(part, {})

            for fname in sorted(files):
                if file_count >= MAX_TREE_FILES:
                    node["..."] = "(truncated)"
                    return tree
                node[fname] = "file"
                file_count += 1

        return tree

    def _detect_entry_points(self, all_files: List[Path], languages: List[str], frameworks: List[str]) -> Dict[str, str]:
        """Detect likely entry point files for each language/component."""
        entry_points: Dict[str, str] = {}

        # Common Python entry points
        for candidate in ["main.py", "app.py", "run.py", "server.py", "manage.py", "wsgi.py", "asgi.py"]:
            for fp in all_files:
                if fp.name == candidate:
                    rel = fp.relative_to(self.project_dir).as_posix()
                    if "python" not in entry_points:
                        entry_points["python"] = rel
                    break

        # JavaScript / TypeScript entry points
        for candidate in ["index.js", "app.js", "server.js", "main.js", "App.jsx", "index.jsx", "index.ts", "app.ts", "server.ts", "main.ts", "App.tsx"]:
            for fp in all_files:
                if fp.name == candidate:
                    rel = fp.relative_to(self.project_dir).as_posix()
                    lang_key = "typescript" if fp.suffix in (".ts", ".tsx") else "javascript"
                    if lang_key not in entry_points:
                        entry_points[lang_key] = rel
                    break

        # C / C++
        for candidate in ["main.cpp", "main.cc", "main.cxx"]:
            for fp in all_files:
                if fp.name == candidate:
                    entry_points["cpp"] = fp.relative_to(self.project_dir).as_posix()
                    break
        if "cpp" in languages and "cpp" not in entry_points:
            for fp in all_files:
                if fp.suffix.lower() in (".cpp", ".cc", ".cxx"):
                    entry_points["cpp"] = fp.relative_to(self.project_dir).as_posix()
                    break

        for fp in all_files:
            if fp.name == "main.c":
                entry_points["c"] = fp.relative_to(self.project_dir).as_posix()
                break

        # Java
        for fp in all_files:
            if fp.suffix == ".java" and fp.stem in ("Main", "Application", "App"):
                entry_points["java"] = fp.relative_to(self.project_dir).as_posix()
                break

        # Go
        for fp in all_files:
            if fp.name == "main.go":
                entry_points["go"] = fp.relative_to(self.project_dir).as_posix()
                break

        # Rust
        for fp in all_files:
            if fp.relative_to(self.project_dir).as_posix() in ("src/main.rs", "main.rs"):
                entry_points["rust"] = fp.relative_to(self.project_dir).as_posix()
                break

        # PHP
        for candidate in ["index.php", "main.php", "artisan"]:
            for fp in all_files:
                if fp.name == candidate:
                    entry_points["php"] = fp.relative_to(self.project_dir).as_posix()
                    break
            if "php" in entry_points:
                break

        # HTML
        for fp in all_files:
            if fp.name == "index.html":
                entry_points["html"] = fp.relative_to(self.project_dir).as_posix()
                break

        # Dockerfile
        docker_files = self._find_all_files("Dockerfile")
        if docker_files:
            entry_points["docker"] = docker_files[0].relative_to(self.project_dir).as_posix()

        return entry_points

    def _extract_dependencies(self, config_files_found: List[str]) -> Dict[str, List[str]]:
        """Extract dependency package names from manifests. Never exposes secret values."""
        deps: Dict[str, List[str]] = {}

        # requirements.txt (across all dirs)
        if "requirements.txt" in config_files_found:
            pkgs: List[str] = []
            for path in self._find_all_files("requirements.txt"):
                content = self._safe_read(path)
                for line in content.splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and not line.startswith("-"):
                        pkg = re.split(r"[>=<!@;]", line)[0].strip()
                        if pkg and pkg not in pkgs:
                            pkgs.append(pkg)
            if pkgs:
                deps["python"] = pkgs[:50]

        # package.json (only package names from dependencies/devDependencies)
        if "package.json" in config_files_found:
            prod_all: List[str] = []
            dev_all: List[str] = []
            for path in self._find_all_files("package.json"):
                try:
                    data = json.loads(self._safe_read(path))
                    for k in (data.get("dependencies") or {}).keys():
                        if k not in prod_all:
                            prod_all.append(k)
                    for k in (data.get("devDependencies") or {}).keys():
                        if k not in dev_all:
                            dev_all.append(k)
                except Exception:
                    pass
            if prod_all:
                deps["node"] = prod_all[:50]
            if dev_all:
                deps["node_dev"] = dev_all[:50]

        # pyproject.toml
        if "pyproject.toml" in config_files_found and "python" not in deps:
            for path in self._find_all_files("pyproject.toml"):
                content = self._safe_read(path)
                pkgs = re.findall(r'"([a-zA-Z0-9_\-]+)\s*[>=<~]', content)
                if pkgs:
                    deps["python"] = list(dict.fromkeys(pkgs))[:50]
                    break

        # pom.xml (extract artifactId names only)
        if "pom.xml" in config_files_found:
            for path in self._find_all_files("pom.xml"):
                content = self._safe_read(path)
                artifacts = re.findall(r'<artifactId>([^<]+)</artifactId>', content)
                if artifacts:
                    deps["java"] = list(dict.fromkeys(artifacts))[:50]
                    break

        # Cargo.toml
        if "Cargo.toml" in config_files_found:
            for path in self._find_all_files("Cargo.toml"):
                content = self._safe_read(path)
                pkgs = re.findall(r'^([a-zA-Z0-9_\-]+)\s*=', content, re.MULTILINE)
                pkgs = [p for p in pkgs if p not in {"name", "version", "edition", "authors", "description"}]
                if pkgs:
                    deps["rust"] = pkgs[:50]
                    break

        # go.mod
        if "go.mod" in config_files_found:
            go_pkgs: List[str] = []
            for path in self._find_all_files("go.mod"):
                content = self._safe_read(path)
                pkgs = re.findall(r'^\s+([^\s]+)\s+v', content, re.MULTILINE)
                for p in pkgs:
                    if p not in go_pkgs:
                        go_pkgs.append(p)
            if go_pkgs:
                deps["go"] = go_pkgs[:50]

        return deps

    # ------------------------------------------------------------------
    # Static factory for convenience
    # ------------------------------------------------------------------
    @staticmethod
    def analyze_directory(project_dir: Path, project_name: Optional[str] = None) -> ProjectAnalysis:
        """Convenience wrapper: create analyzer and run."""
        analyzer = ProjectAnalyzer(project_dir, project_name=project_name)
        return analyzer.analyze()
