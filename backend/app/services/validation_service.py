import ast
import io
import os
import re
import zipfile
from pathlib import Path
from typing import List, Tuple, Optional
from backend.app.core.config import settings
from backend.app.core.exceptions import JobSentinelException
from backend.app.core.logging import logger

# ---------------------------------------------------------------------------
# Multi-language configuration
# ---------------------------------------------------------------------------

SUPPORTED_LANGUAGES = {
    "python":     {"extensions": [".py"],                 "max_bytes": 10 * 1024 * 1024},
    "c":          {"extensions": [".c", ".h"],            "max_bytes": 10 * 1024 * 1024},
    "cpp":        {"extensions": [".cpp", ".cc", ".cxx", ".hpp", ".h"], "max_bytes": 10 * 1024 * 1024},
    "java":       {"extensions": [".java"],               "max_bytes": 10 * 1024 * 1024},
    "javascript": {"extensions": [".js"],                 "max_bytes": 10 * 1024 * 1024},
    "typescript": {"extensions": [".ts", ".tsx"],         "max_bytes": 10 * 1024 * 1024},
    "php":        {"extensions": [".php"],                "max_bytes": 10 * 1024 * 1024},
    "go":         {"extensions": [".go"],                 "max_bytes": 10 * 1024 * 1024},
    "rust":       {"extensions": [".rs"],                 "max_bytes": 10 * 1024 * 1024},
    "html":       {"extensions": [".html", ".htm"],       "max_bytes": 10 * 1024 * 1024},
    "css":        {"extensions": [".css"],                "max_bytes": 10 * 1024 * 1024},
}

def _format_size(size_bytes: int) -> str:
    """Formats bytes into human readable KB, MB, or GB string."""
    if size_bytes >= 1024 * 1024 * 1024:
        gb = size_bytes / (1024 * 1024 * 1024)
        return f"{gb:.1f} GB".replace(".0 GB", " GB")
    elif size_bytes >= 1024 * 1024:
        mb = size_bytes / (1024 * 1024)
        return f"{mb:.1f} MB".replace(".0 MB", " MB")
    else:
        return f"{size_bytes // 1024} KB"

MAX_INLINE_CODE_BYTES = 10 * 1024 * 1024                                       # 10 MB
MAX_ZIP_UPLOAD_BYTES = getattr(settings, "MAX_UPLOAD_SIZE_BYTES", 1024 * 1024 * 1024)       # 1 GB
MAX_EXTRACTED_TOTAL_BYTES = getattr(settings, "MAX_EXTRACTED_SIZE_BYTES", 2 * 1024 * 1024 * 1024) # 2 GB
MAX_ZIP_ENTRIES = 5000                                                         # Max 5000 files
MAX_INDIVIDUAL_FILE_BYTES = 1024 * 1024 * 1024                                # 1 GB per file
MAX_COMPRESSION_RATIO = 15.0                                                  # Max 15:1 compression ratio
MAX_REQUIREMENTS_BYTES = 100 * 1024                                           # 100 KB

ALLOWED_FILE_EXTENSIONS = {
    # Python
    ".py", ".pyw", ".pyi",
    # C / C++
    ".c", ".h", ".cpp", ".cc", ".cxx", ".hpp", ".hxx",
    # Java
    ".java", ".gradle", ".kts", ".properties",
    # JavaScript / TypeScript / Web frameworks
    ".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs", ".vue", ".svelte", ".map",
    # PHP
    ".php",
    # Go
    ".go",
    # Rust
    ".rs",
    # Web / markup / styles
    ".html", ".htm", ".css", ".scss", ".sass", ".less",
    # Data / config
    ".txt", ".json", ".csv", ".tsv",
    ".md", ".yaml", ".yml", ".toml", ".ini",
    ".cfg", ".dat", ".xml", ".sql", ".db",
    ".lock", ".example", ".mod", ".sum",
    # Images
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg", ".ico", ".webp",
    # Audio
    ".wav", ".mp3", ".ogg",
    # Fonts
    ".ttf", ".otf", ".woff", ".woff2",
}

EXCLUDED_DIR_NAMES = {
    ".git", ".venv", "venv", "env", "__pycache__",
    ".pytest_cache", ".idea", ".vscode"
}

EXCLUDED_FILE_EXTENSIONS = {
    ".pyc", ".pyo", ".pyd", ".ds_store"
}

def _is_excluded_archive_entry(norm_name: str) -> bool:
    """Checks if an archive entry belongs to git, venv, cache, or compiler bytecode."""
    parts = [p.lower() for p in norm_name.split("/")]
    if any(ex in parts for ex in EXCLUDED_DIR_NAMES):
        return True
    ext = os.path.splitext(norm_name)[1].lower()
    if ext in EXCLUDED_FILE_EXTENSIONS:
        return True
    lower = norm_name.lower()
    if lower.endswith(".ds_store") or lower.endswith("thumbs.db"):
        return True
    return False

DISALLOWED_FILE_EXTENSIONS = {
    ".exe", ".dll", ".so", ".dylib", ".bin",
    ".sh", ".bash", ".bat", ".cmd", ".ps1",
    ".msi", ".com", ".scr", ".pif", ".vbs",
    ".jar", ".class", ".pyc", ".pyo"
}

# Regex for safe requirements.txt package line: name followed by optional extras and versions
# Example: "requests>=2.28.0", "numpy==1.26.0", "scikit-learn[alldeps]~=1.3.0"
PACKAGE_NAME_REGEX = re.compile(
    r"^[a-zA-Z0-9_\-]+(\[[a-zA-Z0-9_,\-]+\])?(\s*([<>=!~]=?|[<>])\s*[a-zA-Z0-9_.\-*+]+(\s*,\s*([<>=!~]=?|[<>])\s*[a-zA-Z0-9_.\-*+]+)*)?$"
)


class JobValidationException(JobSentinelException):
    def __init__(self, message: str):
        super().__init__(message=f"Validation failed: {message}", status_code=422)


def validate_inline_code(code: str) -> str:
    """
    Validates inline Python code:
    - Checks length and non-emptiness.
    - Validates Python syntax using ast.parse.
    """
    if not code or not code.strip():
        raise JobValidationException("Python code content cannot be empty.")

    code_bytes = code.encode("utf-8")
    if len(code_bytes) > MAX_INLINE_CODE_BYTES:
        raise JobValidationException(
            f"Python code exceeds maximum allowed size of {MAX_INLINE_CODE_BYTES // 1024} KB."
        )

    try:
        ast.parse(code, filename="<inline_code>")
    except SyntaxError as e:
        raise JobValidationException(
            f"Python syntax error at line {e.lineno}, offset {e.offset}: {e.msg}"
        )

    return code


def validate_source_code(code: str, language: str) -> str:
    """
    Validates source code for any supported programming language.

    For Python: additionally validates AST syntax.
    For all others: validates size and non-emptiness only.
    Language must be a key in SUPPORTED_LANGUAGES.
    """
    lang = language.lower()
    if lang not in SUPPORTED_LANGUAGES:
        raise JobValidationException(
            f"Unsupported programming language '{language}'. "
            f"Supported languages: {sorted(SUPPORTED_LANGUAGES.keys())}"
        )

    if not code or not code.strip():
        raise JobValidationException(f"Source code for '{language}' cannot be empty.")

    max_bytes = SUPPORTED_LANGUAGES[lang]["max_bytes"]
    code_bytes = code.encode("utf-8")
    if len(code_bytes) > max_bytes:
        raise JobValidationException(
            f"Source code ({len(code_bytes) // 1024} KB) exceeds maximum allowed size of {max_bytes // 1024} KB."
        )

    # For Python: additionally validate AST syntax
    if lang == "python":
        try:
            ast.parse(code, filename="<inline_code>")
        except SyntaxError as e:
            raise JobValidationException(
                f"Python syntax error at line {e.lineno}, offset {e.offset}: {e.msg}"
            )

    return code


def validate_requirements_content(content: str) -> List[str]:
    """
    Validates requirements.txt content:
    - Rejects URLs, VCS dependencies, local path references, and flags.
    - Only permits valid package specifiers.
    """
    clean_packages = []
    lines = content.splitlines()

    for line_num, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        # Skip empty lines and comment lines
        if not line or line.startswith("#"):
            continue

        # Reject dangerous patterns in specific order
        lowered = line.lower()
        if line.startswith("-") or line.startswith("--"):
            raise JobValidationException(
                f"requirements.txt line {line_num}: Package manager command flags are not permitted ({line})."
            )
        if any(vcs in lowered for vcs in ["git+", "svn+", "hg+", "bzr+"]):
            raise JobValidationException(
                f"requirements.txt line {line_num}: VCS repository dependencies are not permitted ({line})."
            )
        if any(scheme in lowered for scheme in ["http://", "https://", "ftp://", "file://"]):
            raise JobValidationException(
                f"requirements.txt line {line_num}: Direct URL dependencies are not permitted ({line})."
            )
        if line.startswith((".", "/", "\\")) or ":\\" in line:
            raise JobValidationException(
                f"requirements.txt line {line_num}: Local filesystem path references are not permitted ({line})."
            )

        # Remove inline comments
        pkg_part = line.split("#")[0].strip()
        if not PACKAGE_NAME_REGEX.match(pkg_part):
            raise JobValidationException(
                f"requirements.txt line {line_num}: Invalid package specification format '{line}'."
            )

        clean_packages.append(pkg_part)

    return clean_packages


def detect_project_dependencies(source_dir: Path) -> List[str]:
    """Scans all Python files in source_dir and identifies external non-stdlib dependencies."""
    import sys
    stdlib = getattr(sys, "stdlib_module_names", set())
    imported_modules = set()
    local_modules = {p.stem for p in source_dir.glob("*.py")} | {p.name for p in source_dir.iterdir() if p.is_dir()}

    for py_file in source_dir.glob("**/*.py"):
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8", errors="ignore"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imported_modules.add(alias.name.split(".")[0])
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported_modules.add(node.module.split(".")[0])
        except Exception:
            pass

    external = sorted(list(imported_modules - stdlib - local_modules - {"_sentinel_runner", "sentinel_runner"}))
    return external


def validate_and_extract_zip(
    zip_bytes: bytes,
    target_extract_dir: Path,
    expected_entry_point: Optional[str] = "main.py"
) -> Tuple[List[str], Optional[str]]:
    """
    Performs comprehensive security inspection and extraction of a project ZIP:
    - Filters out unnecessary files (.git, .venv, __pycache__, .pyc).
    - Unwraps root directory prefixes when expected_entry_point is nested.
    - Path traversal, absolute path, and symlink prevention.
    - True streaming ZIP bomb defense (ratio + actual decompressed byte limits).
    - File extension whitelisting and blacklisting.
    - Validates expected entry_point if specified (AST check for .py files).
    - Auto-detects Python dependencies when appropriate and validates requirements.txt.
    Returns: (list_of_extracted_relative_paths, verified_entry_point)
    """
    if not zip_bytes:
        raise JobValidationException("Uploaded archive is empty.")

    if len(zip_bytes) > MAX_ZIP_UPLOAD_BYTES:
        raise JobValidationException(
            f"ZIP archive size ({_format_size(len(zip_bytes))}) exceeds limit of {_format_size(MAX_ZIP_UPLOAD_BYTES)}."
        )

    # Magic number check: PK\x03\x04 (standard) or PK\x05\x06 (empty ZIP EOCD)
    if not zip_bytes.startswith((b"PK\x03\x04", b"PK\x05\x06")):
        raise JobValidationException("Uploaded file is not a valid ZIP archive (missing PK magic header).")

    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except Exception as e:
        raise JobValidationException(f"Corrupt or invalid ZIP archive: {str(e)}")

    with zf:
        all_entries = zf.infolist()
        if not all_entries:
            raise JobValidationException("ZIP archive contains no entries.")

        # 1. Exclude unnecessary directories and files (.git, .venv, __pycache__, .pyc)
        infolist = [
            z for z in all_entries
            if not _is_excluded_archive_entry(z.filename.replace("\\", "/"))
        ]
        if not infolist:
            raise JobValidationException("ZIP archive contains no project files after excluding cache/venv files.")

        if len(infolist) > MAX_ZIP_ENTRIES:
            raise JobValidationException(
                f"Archive contains {len(infolist)} entries, exceeding limit of {MAX_ZIP_ENTRIES} files."
            )

        clean_entry_point: Optional[str] = (
            expected_entry_point.replace("\\", "/").strip().lstrip("/")
            if expected_entry_point and expected_entry_point.strip()
            else None
        )

        # Detect common root prefix containing the entry point (e.g. 'Maze (2)/Maze/')
        prefix_to_strip = ""
        if clean_entry_point:
            for z in infolist:
                norm = z.filename.replace("\\", "/").strip().lstrip("/")
                if norm == clean_entry_point or norm.endswith("/" + clean_entry_point):
                    if "/" in norm:
                        prefix_to_strip = norm[:-len(clean_entry_point)]
                    break

        total_uncompressed_bytes = 0
        extracted_files: List[str] = []
        entry_point_found = False

        # First pass: Full security validation of project members
        for zinfo in infolist:
            orig_name = zinfo.filename
            norm_name = orig_name.replace("\\", "/")

            # 1. Path traversal and absolute path protection
            if ".." in norm_name.split("/"):
                raise JobValidationException(f"Path traversal detected in archive entry: '{orig_name}'")
            if norm_name.startswith("/") or ":" in norm_name or "\x00" in norm_name:
                raise JobValidationException(f"Absolute or invalid drive path detected in archive entry: '{orig_name}'")

            # 2. Symlink detection
            is_symlink = False
            if hasattr(zinfo, "is_symlink") and zinfo.is_symlink():
                is_symlink = True
            elif (zinfo.external_attr >> 16) & 0o170000 == 0o120000:
                is_symlink = True

            if is_symlink:
                raise JobValidationException(f"Symbolic links are forbidden in archive: '{orig_name}'")

            # Skip directory records for size checks
            if norm_name.endswith("/"):
                continue

            # 3. File size and decompression limits (header pre-check)
            file_size = zinfo.file_size
            compress_size = zinfo.compress_size
            if file_size > MAX_INDIVIDUAL_FILE_BYTES:
                raise JobValidationException(
                    f"File '{orig_name}' ({_format_size(file_size)}) exceeds maximum file limit of {_format_size(MAX_INDIVIDUAL_FILE_BYTES)}."
                )

            total_uncompressed_bytes += file_size
            if total_uncompressed_bytes > MAX_EXTRACTED_TOTAL_BYTES:
                raise JobValidationException(
                    f"Total extracted size exceeds maximum allowed of {_format_size(MAX_EXTRACTED_TOTAL_BYTES)}."
                )

            # 4. Compression ratio check (zip bomb defense)
            if compress_size > 0:
                ratio = file_size / compress_size
                if ratio > MAX_COMPRESSION_RATIO and file_size > 50000:
                    raise JobValidationException(
                        f"Suspicious compression ratio ({ratio:.1f}:1) for file '{orig_name}' (potential zip bomb)."
                    )

            # 5. File extension checks
            ext = os.path.splitext(norm_name)[1].lower()
            if ext in DISALLOWED_FILE_EXTENSIONS:
                raise JobValidationException(f"Executable or disallowed file type detected: '{orig_name}'")

            if ext and ext not in ALLOWED_FILE_EXTENSIONS:
                raise JobValidationException(f"Disallowed file type with extension '{ext}' in entry '{orig_name}'")

        # Second pass: Streaming extraction with actual decompressed byte tracking
        target_extract_dir.mkdir(parents=True, exist_ok=True)
        real_extract_root = target_extract_dir.resolve()
        actual_total_bytes = 0
        chunk_size = 65536  # 64 KB chunks

        for zinfo in infolist:
            norm_name = zinfo.filename.replace("\\", "/").lstrip("/")
            if not norm_name or norm_name.endswith("/"):
                continue

            # Apply root prefix unwrapping if entry starts with it
            if prefix_to_strip and norm_name.startswith(prefix_to_strip):
                rel_dest = norm_name[len(prefix_to_strip):]
            else:
                rel_dest = norm_name

            if not rel_dest:
                continue

            dest_path = (target_extract_dir / rel_dest).resolve()
            try:
                dest_path.relative_to(real_extract_root)
            except ValueError:
                raise JobValidationException(f"Extracted file path escapes extraction root: '{rel_dest}'")

            dest_path.parent.mkdir(parents=True, exist_ok=True)
            if dest_path.is_symlink():
                raise JobValidationException(f"Symbolic link target rejected: '{rel_dest}'")

            actual_file_bytes = 0
            compress_size = zinfo.compress_size
            with zf.open(zinfo) as source_file, open(dest_path, "wb") as target_file:
                while True:
                    chunk = source_file.read(chunk_size)
                    if not chunk:
                        break
                    actual_file_bytes += len(chunk)
                    actual_total_bytes += len(chunk)
                    if actual_file_bytes > MAX_INDIVIDUAL_FILE_BYTES:
                        raise JobValidationException(
                            f"File '{rel_dest}' actual extracted size exceeds limit of {_format_size(MAX_INDIVIDUAL_FILE_BYTES)}."
                        )
                    if actual_total_bytes > MAX_EXTRACTED_TOTAL_BYTES:
                        raise JobValidationException(
                            f"Total actual extracted size exceeds maximum allowed of {_format_size(MAX_EXTRACTED_TOTAL_BYTES)}."
                        )
                    if compress_size > 0 and actual_file_bytes > 50000:
                        actual_ratio = actual_file_bytes / compress_size
                        if actual_ratio > MAX_COMPRESSION_RATIO:
                            raise JobValidationException(
                                f"Suspicious runtime compression ratio ({actual_ratio:.1f}:1) for '{rel_dest}' (potential zip bomb)."
                            )
                    target_file.write(chunk)

            extracted_files.append(rel_dest)
            if clean_entry_point and rel_dest == clean_entry_point:
                entry_point_found = True

        if clean_entry_point:
            if not entry_point_found:
                matching = [f for f in extracted_files if f.endswith("/" + clean_entry_point) or f == clean_entry_point]
                if len(matching) == 1:
                    clean_entry_point = matching[0]
                    entry_point_found = True

            if not entry_point_found:
                raise JobValidationException(
                    f"Specified entry-point file '{expected_entry_point}' was not found in the uploaded archive. "
                    f"Available files: {', '.join(extracted_files[:10])}{'...' if len(extracted_files) > 10 else ''}"
                )

            # Validate Python syntax ONLY when the entry point is a Python file
            if clean_entry_point.lower().endswith(".py"):
                entry_point_path = target_extract_dir / clean_entry_point
                try:
                    with open(entry_point_path, "r", encoding="utf-8", errors="replace") as ep_file:
                        ep_code = ep_file.read()
                    ast.parse(ep_code, filename=clean_entry_point)
                except SyntaxError as se:
                    raise JobValidationException(
                        f"Syntax error in entry-point '{clean_entry_point}' at line {se.lineno}: {se.msg}"
                    )
        else:
            # Auto-detect a reasonable entry point if main.py or app.py exists, else None
            for candidate in ("main.py", "app.py", "run.py"):
                if candidate in extracted_files:
                    clean_entry_point = candidate
                    break

        # Validate requirements.txt if present at root (or auto-detect for pure Python projects)
        req_path = target_extract_dir / "requirements.txt"
        if not req_path.exists():
            if clean_entry_point and clean_entry_point.lower().endswith(".py"):
                detected_deps = detect_project_dependencies(target_extract_dir)
                if detected_deps:
                    req_path.write_text("\n".join(detected_deps) + "\n", encoding="utf-8")
                    logger.info("Auto-detected dependencies for project: %s", detected_deps)
        else:
            if req_path.is_file():
                if req_path.stat().st_size > MAX_REQUIREMENTS_BYTES:
                    raise JobValidationException(f"requirements.txt exceeds maximum size of {MAX_REQUIREMENTS_BYTES // 1024} KB.")
                try:
                    with open(req_path, "r", encoding="utf-8") as rf:
                        req_content = rf.read()
                    validate_requirements_content(req_content)
                except UnicodeDecodeError:
                    raise JobValidationException("requirements.txt must be a valid UTF-8 encoded text file.")

        return extracted_files, clean_entry_point

