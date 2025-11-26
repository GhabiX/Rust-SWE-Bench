# Constants - Task Instance Version File
MAP_REPO_TO_VERSION_PATHS = {
    "dbt-labs/dbt-core": ["core/dbt/version.py", "core/dbt/__init__.py"],
    "django/django": ["django/__init__.py"],
    "huggingface/transformers": ["src/transformers/__init__.py"],
    "marshmallow-code/marshmallow": ["src/marshmallow/__init__.py"],
    "mwaskom/seaborn": ["seaborn/__init__.py"],
    "pallets/flask": ["src/flask/__init__.py", "flask/__init__.py"],
    "psf/requests": ["requests/__version__.py", "requests/__init__.py"],
    "pyca/cryptography": [
        "src/cryptography/__about__.py",
        "src/cryptography/__init__.py",
    ],
    "pylint-dev/astroid": ["astroid/__pkginfo__.py", "astroid/__init__.py"],
    "pylint-dev/pylint": ["pylint/__pkginfo__.py", "pylint/__init__.py"],
    "pytest-dev/pytest": ["src/_pytest/_version.py", "_pytest/_version.py"],
    "pyvista/pyvista": ["pyvista/_version.py", "pyvista/__init__.py"],
    "Qiskit/qiskit": ["qiskit/VERSION.txt"],
    "scikit-learn/scikit-learn": ["sklearn/__init__.py"],
    "sphinx-doc/sphinx": ["sphinx/__init__.py"],
    "sympy/sympy": ["sympy/release.py", "sympy/__init__.py"],
    "rust-lang/rustlings": ["Cargo.toml"],
    "serde-rs/serde": ["serde/Cargo.toml"],
    "bitflags/bitflags": ["Cargo.toml"],
    "apache/arrow-rs": ["Cargo.toml", "arrow/Cargo.toml"],
    "asterinas/asterinas": ["VERSION", "Cargo.toml"],
    "tokio-rs/tokio": ["Cargo.toml", "tokio/Cargo.toml"],
    "fermyon/spin": ["Cargo.toml"],
    "GuillaumeGomez/sysinfo": ["Cargo.toml"],
    "rayon-rs/rayon": ["Cargo.toml"],
    "rust-lang/regex": ["Cargo.toml"],
    "dtolnay/syn": ["Cargo.toml"],
    "serde-rs/json": ["Cargo.toml"],
    "rust-random/rand": ["Cargo.toml"],
    "rust-lang/log": ["Cargo.toml"],
    "indexmap-rs/indexmap":["Cargo.toml"],
    "crossbeam-rs/crossbeam":["Cargo.toml"],
    "hyperium/hyper":["Cargo.toml"],
    "denoland/deno":["Releases.md"],
    "dtolnay/proc-macro2":["Cargo.toml"],
}

# Cosntants - Task Instance Version Regex Pattern
MAP_REPO_TO_VERSION_PATTERNS = {
    k: [r'version\s*=\s*"(\d+\.\d+\.\d+)"']
    for k in [
        "rust-lang/rustlings",
        "serde-rs/serde",
        "bitflags/bitflags",
        "apache/arrow-rs",
        "fermyon/spin",
        "GuillaumeGomez/sysinfo",
        "rust-lang/regex",
        "dtolnay/syn",
        "serde-rs/json",
        "rayon-rs/rayon",
        "dtolnay/proc-macro2"
    ]
}

MAP_REPO_TO_VERSION_PATTERNS.update(
    {k: [r"\d+\.\d+\.\d+"] for k in ["asterinas/asterinas"]}
)

MAP_REPO_TO_VERSION_PATTERNS.update(
    {k: [r'version\s*=\s*"(.*)"'] for k in ["tokio-rs/tokio", "rust-random/rand", "hyperium/hyper"]}
)

MAP_REPO_TO_VERSION_PATTERNS.update(
    {k: [r'(\d+\.\d+\.\d+)'] for k in ["denoland/deno"]}
)


SWE_BENCH_URL_RAW = "https://raw.githubusercontent.com/"
