from enum import Enum
from pathlib import Path
from typing import TypedDict

# Constants - Evaluation Log Directories
BASE_IMAGE_BUILD_DIR = Path("logs/build_images/base")
ENV_IMAGE_BUILD_DIR = Path("logs/build_images/env")
INSTANCE_IMAGE_BUILD_DIR = Path("logs/build_images/instances")
RUN_EVALUATION_LOG_DIR = Path("logs/run_evaluation")

NON_OSDK_CRATES = [
    "osdk",
    "ostd/libs/align_ext",
    "ostd/libs/id-alloc",
    "ostd/libs/linux-bzimage/builder",
    "ostd/libs/linux-bzimage/boot-params",
    "ostd/libs/ostd-macros",
    "ostd/libs/ostd-test",
    "kernel/libs/cpio-decoder",
    "kernel/libs/int-to-c-enum",
    "kernel/libs/int-to-c-enum/derive",
    "kernel/libs/aster-rights",
    "kernel/libs/aster-rights-proc",
    "kernel/libs/keyable-arc",
    "kernel/libs/typeflags",
    "kernel/libs/typeflags-util",
    "kernel/libs/atomic-integer-wrapper",
]

OSDK_CRATES = [
    "osdk/test-kernel",
    "ostd",
    "ostd/libs/linux-bzimage/setup",
    "kernel",
    "kernel/comps/block",
    "kernel/comps/console",
    "kernel/comps/framebuffer",
    "kernel/comps/input",
    "kernel/comps/network",
    "kernel/comps/softirq",
    "kernel/comps/time",
    "kernel/comps/virtio",
    "kernel/libs/aster-util",
    "kernel/libs/aster-bigtcp",
]


# Constants - Task Instance Class
class SWEbenchInstance(TypedDict):
    repo: str
    instance_id: str
    base_commit: str
    patch: str
    test_patch: str
    problem_statement: str
    hints_text: str
    created_at: str
    updated_at: str
    version: str
    FAIL_TO_PASS: str
    PASS_TO_PASS: str
    environment_setup_commit: str


# Constants - Test Types, Statuses, Commands
FAIL_TO_PASS = "FAIL_TO_PASS"
FAIL_TO_FAIL = "FAIL_TO_FAIL"
PASS_TO_PASS = "PASS_TO_PASS"
PASS_TO_FAIL = "PASS_TO_FAIL"


class ResolvedStatus(Enum):
    NO = "RESOLVED_NO"
    PARTIAL = "RESOLVED_PARTIAL"
    FULL = "RESOLVED_FULL"


class TestStatus(Enum):
    FAILED = "FAILED"
    PASSED = "PASSED"
    SKIPPED = "SKIPPED"
    ERROR = "ERROR"


# TEST_PYTEST = "pytest --no-header -rA --tb=no -p no:cacheprovider"
# TEST_PYTEST_VERBOSE = "pytest -rA --tb=long -p no:cacheprovider"

TEST_CARGO = "cargo test --no-fail-fast --all-features"

# Constants - Installation Specifications
SPECS_RUSTLINGS = {}

SPECS_SERDE = {
    k:{
        "rustc": "nightly",
        "test_cmd": TEST_CARGO,
    }
    for k in ["1.21","1.20","1.19",]
    
    }

SPECS_SERDE.update({
    k: {
        "rustc": "nightly",
        "test_cmd": "cd test_suite && cargo test --features unstable",
        # "pre_install": [
        #     "cargo clean"
        # ]
    }
    for k in ["1.18","1.17","1.16"]
    }
)

SPECS_PROC_MACRO2 = {
    k:{
        "rustc": "1.81.0",
        "test_cmd": TEST_CARGO,
    }
    for k in ["1.0","0.4","0.3","0.2","0.1"]

}

SPECS_BITFLAGS = {
    k: {"rustc": "1.81.0", "test_cmd": TEST_CARGO}
    for k in ["2.5", "2.4", "2.3", "2.2", "2.1", "2.0", "1.2"]
}
SPECS_BITFLAGS.update(
    {
        k: {
            "rustc": "1.81.0",
            "test_cmd": TEST_CARGO,
            #     "pre_install":[
            #         "cargo upgrade"
            # ]
            "pre_install": [
                r"""sed -i '/\[dependencies\]/a serde = { version = "1.0.210", features = ["derive"] }' Cargo.toml""",
                r"""sed -i 's/serde_json = "1.0"/serde_json = "1.0.69"/' Cargo.toml""",
                r"""sed -i 's/default = \[\]/default = ["derive"]/' Cargo.toml""",
                r"""sed -i '/example_generated = \[\]/i derive = ["serde/derive"]' Cargo.toml""",
            ],
        }
        for k in ["1.3"]
    }
)

SPECS_ARROW = {
    k: {
        "rustc": "1.81.0",
        "test_cmd": TEST_CARGO,
        "pre_install": [
            r"""git submodule update --init""",
        ],
        "env_setup": ["pip install pyarrow"],
    }
    for k in ["53.3","53.2", "53.0", "52.2", "52.1", "52.0", "51.0", "50.0"]
}
SPECS_ARROW.update(
    {
        k: {
            "rustc": "1.81.0",
            "test_cmd": TEST_CARGO,
            "env_setup": [
                r"""sed -i 's/ahash = { version = "0.8"/ahash = { version = "0.8.8"/' ./arrow/Cargo.toml""",
                r"""sed -i 's/proc-macro2 = { version = "=1\.0\.[0-9]\+"/proc-macro2 = { version = "=1.0.75"/' ./arrow-flight/gen/Cargo.toml""",
            ],
            "pre_install": [
                r"""sed -i 's/ahash = { version = "0.8"/ahash = { version = "0.8.8"/' ./arrow/Cargo.toml""",
                r"""sed -i 's/proc-macro2 = { version = "=1\.0\.[0-9]\+"/proc-macro2 = { version = "=1.0.75"/' ./arrow-flight/gen/Cargo.toml""",
                r"""git submodule update --init""",
            ],
        }
        for k in ["49.0", "48.0", "47.0"]
    }
)
SPECS_ARROW.update(
    {
        k: {
            "rustc": "1.81.0",
            "test_cmd": TEST_CARGO,
            "env_setup": [
                r"""sed -i 's/proc-macro2 = { version = "=1\.0\.[0-9]\+"/proc-macro2 = { version = "=1.0.75"/' ./arrow-flight/gen/Cargo.toml""",
            ],
            "pre_install": [
                r"""sed -i 's/proc-macro2 = { version = "=1\.0\.[0-9]\+"/proc-macro2 = { version = "=1.0.75"/' ./arrow-flight/gen/Cargo.toml""",
                r"""git submodule update --init""",
            ],
        }
        for k in ["46.0", "45.0", "40.0", "39.0", "38.0", "37.0", "36.0", "35.0"]
    }
)
SPECS_ARROW.update(
    {
        k: {
            "rustc": "1.81.0",
            "test_cmd": TEST_CARGO,
            "env_setup": [
                r"""sed -i 's/proc-macro2 = { version = "=1\.0\.[0-9]\+"/proc-macro2 = { version = "=1.0.75"/' ./arrow-flight/Cargo.toml""",
            ],
            "pre_install": [
                r"""sed -i 's/proc-macro2 = { version = "=1\.0\.[0-9]\+"/proc-macro2 = { version = "=1.0.75"/' ./arrow-flight/Cargo.toml""",
                r"""git submodule update --init""",
            ],
        }
        for k in [
            "34.0",
            "33.0",
            "32.0",
            "31.0",
            "30.0",
            "29.0",
            "28.0",
            "27.0",
            "26.0",
            "25.0",
            "24.0",
            "21.0",
            "20.0",
            "19.0",
            "18.0",
            "17.0",
            "16.0",
            "15.0",
            "14.0",
            "13.0",
            "11.1",
            "11.0",
            "10.0",
            "9.0",
            "8.0",
            "7.0",
        ]
    }
)
SPECS_ARROW.update(
    {
        k: {
            "rustc": "1.81.0",
            "test_cmd": TEST_CARGO,
            "env_setup": [
                r"""sed -i 's/proc-macro2 = "=1\.0\.[0-9]\+"/proc-macro2 = "=1.0.75"/' ./arrow-flight/Cargo.toml""",
            ],
            "pre_install": [
                r"""sed -i 's/proc-macro2 = "=1\.0\.[0-9]\+"/proc-macro2 = "=1.0.75"/' ./arrow-flight/Cargo.toml""",
                r"""git submodule update --init""",
            ],
        }
        for k in ["0.8", "0.6", "0.3"]
    }
)

SPECS_ASTERINAS = {
    k: {
        "rustc": "1.81.0",
        "test_cmd": TEST_CARGO,
        "image_tag": "0.8.3",
        "pre_install": [
            r"""
            git fetch origin pull/1666/head:pr-1666
            git checkout main
            git cherry-pick -X theirs pr-1666
            git branch -D pr-1666
            sed -i 's/multiboot2 = "0.20.2"/multiboot2 = "0.23.1"/' ostd/Cargo.toml
            """
        ],
        # env level
        "env_setup": [
            r"""
            git fetch origin pull/1666/head:pr-1666
            git checkout main
            git cherry-pick -X theirs pr-1666
            git branch -D pr-1666
            """
        ],
    }
    for k in ["0.8"]
}

SPECS_ASTERINAS.update(
    {
        k: {
            "rustc": "1.81.0",
            "test_cmd": TEST_CARGO,
            "image_tag": "0.9.4",
            "env_setup": [
                "git fetch origin pull/1666/head:pr-1666",
                "git checkout main",
                "git cherry-pick -X theirs pr-1666",
                # "git cherry-pick pr-1666",
                "git branch -D pr-1666",
            ],
            "pre_install": [
                # r"""sed -i 's/channel = "nightly-[0-9]\{4\}-[0-9]\{2\}-[0-9]\{2\}"/channel = "nightly-2024-10-12"/' rust-toolchain.toml"""
                # "git fetch origin pull/1666/head:pr-1666",
                # "git checkout main",
                # "git cherry-pick pr-1666",
                # "git branch -D pr-1666"
            ],
        }
        for k in ["0.9"]
    }
)

SPECS_ASTERINAS.update(
    {
        k: {
            "rustc": "1.81.0",
            "test_cmd": TEST_CARGO,
            "image_tag": "0.7.0",
            # repo level
            "pre_install": [
                r"""
            git fetch origin pull/1666/head:pr-1666
            git checkout main
            git cherry-pick -X theirs pr-1666
            git branch -D pr-1666
            sed -i 's/multiboot2 = "0.20.2"/multiboot2 = "0.23.1"/' ostd/Cargo.toml
            """
            ],
            # env level
            "env_setup": [
                r"""
            git fetch origin pull/1666/head:pr-1666
            git checkout main
            git cherry-pick -X theirs pr-1666
            git branch -D pr-1666
            sed -i 's/multiboot2 = "0.20.2"/multiboot2 = "0.23.1"/' ostd/Cargo.toml

            """
            ],
        }
        for k in ["0.7"]
    }
)
SPECS_ASTERINAS.update(
    {
        k: {
            "rustc": "1.81.0",
            "test_cmd": TEST_CARGO,
            "image_tag": "0.6.2",
            # repo level
            "pre_install": [
                r"""
            git fetch origin pull/1666/head:pr-1666
            git checkout main
            git cherry-pick -X theirs pr-1666
            git branch -D pr-1666
            sed -i 's/channel = "nightly-2024-06-20"/channel = "nightly-2024-11-29"/' rust-toolchain.toml
            sed -i 's/multiboot2 = "0.20.2"/multiboot2 = "0.23.1"/' ostd/Cargo.toml
            sed -i 's/target_arch == "x86_64-unknown-none"/target_arch == "x86_64-unknown-linux-gnu"/' ostd/libs/linux-bzimage/setup/build.rs
            cargo update -p unwinding
            sed '/^\[target\.x86_64-unknown-none\.dependencies\]$/d' ostd/libs/linux-bzimage/setup/Cargo.toml
            """
            ],
            # env level
            "env_setup": [
                r"""
            git fetch origin pull/1666/head:pr-1666
            git checkout main
            git cherry-pick -X theirs pr-1666
            git branch -D pr-1666
            sed -i 's/channel = "nightly-2024-06-20"/channel = "nightly-2024-11-29"/' rust-toolchain.toml
            sed -i 's/multiboot2 = "0.20.2"/multiboot2 = "0.23.1"/' ostd/Cargo.toml
            sed -i 's/target_arch == "x86_64-unknown-none"/target_arch == "x86_64-unknown-linux-gnu"/' ostd/libs/linux-bzimage/setup/build.rs
            cargo update -p unwinding
            """
            ],
        }
        for k in ["0.6"]
    }
)
SPECS_ASTERINAS.update(
    {
        k: {
            "rustc": "1.81.0",
            "test_cmd": TEST_CARGO,
            "image_tag": "0.5.1",
            "pre_install": [
                r"""
            # sed -i 's/channel = "nightly-2024-06-20"/channel = "nightly-2024-11-29"/' rust-toolchain.toml
            # sed -i 's/multiboot2 = "0.20.2"/multiboot2 = "0.23.1"/' ostd/Cargo.toml
            # cargo update -p unwinding

            """
            ],
            # env level
            "env_setup": [
                r"""
# export CFLAGS="-DSECOMP FILTER FLAG WAIT KILLABLE RECV=32 -DMFD NOEXEC SEAL=8 -DMFD EXEC=16 -DNF NETDEV EGRESS=1"
# echo $CFLAGS

            """
            ],
        }
        for k in ["0.5"]
    }
)
SPECS_ASTERINAS.update(
    {
        k: {
            "rustc": "1.81.0",
            "test_cmd": TEST_CARGO,
            "image_tag": "0.4.2",
            # #repo level
            "pre_install": [
                r"""
                # git fetch origin pull/1666/head:pr-1666
                # git checkout main
                # git cherry-pick -X theirs pr-1666
                # git branch -D pr-1666
                sed -i 's/channel = "nightly-[0-9]\{4\}-[0-9]\{2\}-[0-9]\{2\}"/channel = "nightly-2024-11-29"/' rust-toolchain.toml
                sed -i 's/multiboot2 = "[0-9]*\.[0-9]*\.[0-9]*"/multiboot2 = "0.23.1"/' framework/aster-frame/Cargo.toml
                sed -i 's/x86_64 = "[0-9]*\.[0-9]*\.[0-9]*"/x86_64 = "0.14.13"/' kernel/Cargo.toml
                cargo update -p unwinding
        
                """
            ],
            # env level
            "env_setup": [
                r"""
                # git fetch origin pull/1666/head:pr-1666
                # git checkout main
                # git cherry-pick -X theirs pr-1666
                # git branch -D pr-1666
                # sed -i 's/channel = "nightly-[0-9]\{4\}-[0-9]\{2\}-[0-9]\{2\}"/channel = "nightly-2024-11-29"/' rust-toolchain.toml
                # sed -i 's/channel = "nightly-[0-9]\{4\}-[0-9]\{2\}-[0-9]\{2\}"/channel = "nightly-2024-11-29"/' rust-toolchain.toml
                sed -i 's/multiboot2 = "[0-9]*\.[0-9]*\.[0-9]*"/multiboot2 = "0.23.1"/' framework/aster-frame/Cargo.toml
                # sed -i 's/x86_64 = "[0-9]*\.[0-9]*\.[0-9]*"/x86_64 = "0.14.13"/' kernel/Cargo.toml
                # sed -i 's#multiboot2 = "[0-9]*\.[0-9]*\.[0-9]*"#multiboot2 = {path="multiboot2-multiboot2-v0.16.0/multiboot2-multiboot2-v0.16.0/multiboot2"}#' framework/aster-frame/Cargo.toml

                """
            ],
        }
        for k in ["0.4"]
    }
)
SPECS_ASTERINAS.update(
    {
        k: {
            "rustc": "1.81.0",
            "test_cmd": TEST_CARGO,
            "image_tag": "0.2.2",
            # #repo level
            # "pre_install":[
            #     r"""
            #     sed -i 's/channel = "nightly-2024-06-20"/channel = "nightly-2024-10-12"/' rust-toolchain.toml
            #     """
            # ],
            # #env level
            # "env_setup":[
            #     r"""sed -i 's/channel = "nightly-2024-06-20"/channel = "nightly-2024-10-12"/' rust-toolchain.toml"""
            # ]
        }
        for k in ["0.2"]
    }
)
SPECS_ASTERINAS.update(
    {
        k: {
            "rustc": "1.81.0",
            "test_cmd": TEST_CARGO,
            "image_tag": "0.1.1",
            # #repo level
            # "pre_install":[
            #     r"""
            #     sed -i 's/channel = "nightly-2024-06-20"/channel = "nightly-2024-10-12"/' rust-toolchain.toml
            #     """
            # ],
            # #env level
            # "env_setup":[
            #     r"""sed -i 's/channel = "nightly-2024-06-20"/channel = "nightly-2024-10-12"/' rust-toolchain.toml"""
            # ]
        }
        for k in ["0.1"]
    }
)

SPECS_TOKIO = {
    k: {
        "rustc": "1.81.0",
        "pre_install": [
            r"sed -i 's/#!\[deny(unused_must_use)\]/#![warn(unused_must_use)]/' ./tokio/src/lib.rs",
        ],
    }
    for k in [
        "1.9",
        "1.8",
        "1.7",
        "1.6",
        "1.5",
        "1.41",
        "1.40",
        "1.4",
        "1.39",
        "1.38",
        "1.37",
        "1.36",
        "1.35",
        "1.34",
        "1.33",
        "1.32",
        "1.31",
        "1.3",
        "1.29",
        "1.28",
        "1.26",
        "1.25",
        "1.24",
        "1.23",
        "1.22",
        "1.21",
        "1.20",
        "1.17",
        "1.16",
        "1.15",
        "1.14",
        "1.12",
        "1.11",
        "1.1",
        "1.0",
        "0.3",
    ]
}

SPECS_TOKIO.update(
    {
        k: {
            "rustc": "1.81.0",
            "pre_install": [
                r"sed -i 's/#!\[deny(unused_must_use)\]/#![warn(unused_must_use)]/' ./tokio/src/lib.rs",
                "set +e",
                r"sed -E -i 's/nightly-2019[a-zA-Z0-9_\-]+/1.81.0/' ./rust-toolchain",
                'sed -i \'s/security-framework = "0.2"/security-framework = "3.0.0-beta.2"/\' ./tokio-tls/Cargo.toml',
                "set -e",
            ],
        }
        for k in ["0.2"]
    }
)

SPECS_SPIN = {
    k: {
        "rustc": "1.81.0",
        "test_cmd": "make test-unit test-integration",
        "pre_install": [
            "cargo update",
        ],
        "env_setup": [
            "rustup target add wasm32-wasip1 && rustup target add wasm32-unknown-unknown",
            "rustup target add wasm32-wasi",
            "cargo update",
            "apt update",
            "apt install -y pkg-config libssl-dev",
            "export PKG_CONFIG_PATH=/usr/lib/x86_64-linux-gnu/pkgconfig:${PKG_CONFIG_PATH:-}",
        ],
    }
    for k in ["3.2"]
}

SPECS_SYSINFO = {
    k: {
        "rustc": "1.74",
        "test_cmd": "cargo test --no-fail-fast",
        "pre_install": [],
        "env_setup": [],
    }
    for k in [
        "0.8",
        "0.6",
        "0.30",
        "0.32",
        "0.31",
        "0.29",
        "0.28",
        "0.27",
        "0.26",
        "0.24",
        "0.23",
        "0.22",
        "0.21",
        "0.2",
        "0.18",
        "0.17",
        "0.16",
        "0.15",
        "0.14",
        "0.13",
        "0.11",
        "0.10",
    ]
}


SPECS_REGEX = {
    k: {
        "rustc": "1.81.0",
        "test_cmd": "./test",
    }
    for k in ["1.2", "1.3", "1.4", "1.5", "1.6", "1.7", "1.8", "1.9", "1.10"]
}

SPECS_REGEX.update(
    {
        k: {"rustc": "1.24.1", "test_cmd": TEST_CARGO}
        for k in ["0.1", "0.2", "1.0", "1.1"]
    }
)

SPECS_SYN = {
    k: {
        "rustc": "1.81.0",
        "test_cmd": TEST_CARGO,
        "pre_install": [
            "apt update",
            "apt install -y pkg-config libssl-dev",
            "export PKG_CONFIG_PATH=/usr/lib/x86_64-linux-gnu/pkgconfig:${PKG_CONFIG_PATH:-}",
        ],
    }
    for k in ["1.0", "2.0"]
}

SPECS_RAYON = {
    k: {
        "rustc": "nightly",
        "test_cmd": "cargo test --all --no-fail-fast --all-features",
    }
    for k in ["1.6"]
}

SPECS_INDEXMAP = {
    k: {"rustc": "1.81.0", "test_cmd": TEST_CARGO}
    for k in ["2.2", "1.8", "1.6", "1.4", "1.2", "1.1", "0.4", "0.3", "0.2"]
}

SPECS_CROSSBEAM = {
    k: {
        "rustc": "nightly",
    }
    for k in ["0.8", "0.7", "0.6", "0.5", "0.4", "0.3", "0.2", "0.1"]
}


SPECS_RAND = {
    k: {
        "rustc": "1.81.0",
        "test_cmd": r"""export RUSTFLAGS="-Awarnings -Auseless_deprecated" && cargo test --all --no-fail-fast""",
    }
    for k in ["0.9", "0.8", "0.7", "0.6", "0.5"]
}

SPECS_LOG = {
    k: {
        "rustc": "1.81.0",
        "test_cmd": r"""export RUSTFLAGS="-Awarnings" && cargo test --all --no-fail-fast --all-features""",
    }
    for k in ["0.4", "0.3"]
}

SPECS_HYPER = {
    k: {
        "rustc": "1.81.0",
    }
    for k in ["1.5", "1.4", "1.3", "1.2", "1.1", "1.0"]
}

SPECS_DENO = {
    k: {
        "rustc": "1.83.0",
        "pre_install": [
            r"""
apt install -y lsb-release wget software-properties-common gnupg
git submodule update --init --recursive
wget https://apt.llvm.org/llvm.sh
chmod +x llvm.sh
./llvm.sh 17
apt install --install-recommends -y cmake libglib2.0-dev
apt install -y protobuf-compiler
apt-get update
apt-get install -y python3
ln -sf "$(which python3)" /usr/bin/python
            """
        ],
        "test_cmd": r"""
cargo test -vv
target/debug/deno test -A --unstable --lock=tools/deno.lock.json --config tests/config/deno.json tests/unit
"""
    }
    for k in ["2.1"]
}

# Constants - Task Instance Instllation Environment
MAP_REPO_VERSION_TO_SPECS = {
    # "rust-lang/rustlings": SPECS_RUSTLINGS,
    # "serde-rs/serde": SPECS_SERDE,
    # "bitflags/bitflags": SPECS_BITFLAGS,
    # "apache/arrow-rs": SPECS_ARROW,
    # "asterinas/asterinas": SPECS_ASTERINAS,
    # "fermyon/spin": SPECS_SPIN,
    # "GuillaumeGomez/sysinfo": SPECS_SYSINFO,
    # "rayon-rs/rayon": SPECS_RAYON,
    # "rust-lang/regex": SPECS_REGEX,
    # "dtolnay/syn": SPECS_SYN,
    # "rust-random/rand": SPECS_RAND,
    # "rust-lang/log": SPECS_LOG,
    # "tokio-rs/tokio": SPECS_TOKIO,
    # "indexmap-rs/indexmap": SPECS_INDEXMAP,
    # "crossbeam-rs/crossbeam": SPECS_CROSSBEAM,
    # "hyperium/hyper": SPECS_HYPER,
    # "denoland/deno": SPECS_DENO,
    # "dtolnay/proc-macro2": SPECS_PROC_MACRO2,
}

# Constants - Repository Specific Installation Instructions
MAP_REPO_TO_INSTALL = {}

# Constants - Task Instance Requirements File Paths
MAP_REPO_TO_REQS_PATHS = {
    "bitflags/bitflags": "Cargo.toml",
    "apache/arrow-rs": "Cargo.toml",
    "asterinas/asterinas": "Cargo.toml",
    "tokio-rs/tokio": "Cargo.toml",
    "fermyon/spin": "Cargo.toml",
    "GuillaumeGomez/sysinfo": "Cargo.toml",
    "rayon-rs/rayon": "Cargo.toml",
    "rust-lang/regex": "Cargo.toml",
    "dtolnay/syn": "Cargo.toml",
    "rust-random/rand": "Cargo.toml",
    "rust-lang/log": "Cargo.toml",
    "indexmap-rs/indexmap": "Cargo.toml",
    "crossbeam-rs/crossbeam": "Cargo.toml",
    "hyperium/hyper": "Cargo.toml",
    "dtoinay/proc-macro2": "Cargo.toml",
}

# Constants - Task Instance environment.yml File Paths
MAP_REPO_TO_ENV_YML_PATHS = {
    "matplotlib/matplotlib": ["environment.yml"],
    "pydata/xarray": ["ci/requirements/environment.yml", "environment.yml"],
}

# Constants - Evaluation Keys
KEY_INSTANCE_ID = "instance_id"
KEY_MODEL = "model_name_or_path"
KEY_PREDICTION = "model_patch"

# Constants - Logging
APPLY_PATCH_FAIL = ">>>>> Patch Apply Failed"
APPLY_PATCH_PASS = ">>>>> Applied Patch"
INSTALL_FAIL = ">>>>> Init Failed"
INSTALL_PASS = ">>>>> Init Succeeded"
INSTALL_TIMEOUT = ">>>>> Init Timed Out"
RESET_FAILED = ">>>>> Reset Failed"
TESTS_ERROR = ">>>>> Tests Errored"
TESTS_FAILED = ">>>>> Some Tests Failed"
TESTS_PASSED = ">>>>> All Tests Passed"
TESTS_TIMEOUT = ">>>>> Tests Timed Out"


# Constants - Patch Types
class PatchType(Enum):
    PATCH_GOLD = "gold"
    PATCH_PRED = "pred"
    PATCH_PRED_TRY = "pred_try"
    PATCH_PRED_MINIMAL = "pred_minimal"
    PATCH_PRED_MINIMAL_TRY = "pred_minimal_try"
    PATCH_TEST = "test"

    def __str__(self):
        return self.value


# Constants - Miscellaneous
NON_TEST_EXTS = [
    ".json",
    ".png",
    "csv",
    ".txt",
    ".md",
    ".jpg",
    ".jpeg",
    ".pkl",
    ".yml",
    ".yaml",
    ".toml",
]
SWE_BENCH_URL_RAW = "https://raw.githubusercontent.com/"
USE_X86 = {}
