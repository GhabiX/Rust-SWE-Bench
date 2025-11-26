import re
from typing import Optional

from swebench.harness.constants import (
    NON_OSDK_CRATES,
    OSDK_CRATES,
)
from swebench.harness.utils import findCrate


def _base_single_module_test_commands(
        tests_changed: list[str],
        rust_flags: Optional[str] = None,
        rust_doc_flags: Optional[str] = None,
        features: Optional[list[str]] = None,
        use_all_features: bool = False,
        before: Optional[list[str]] = None,
):
    # generate specific str
    features_str = f'--features="{" ".join(features)}" ' if features else ""
    use_all_features_str = "--all-features " if use_all_features else ""
    # generate cmds
    cmds: list[str] = []
    if before:
        cmds.extend(before)
    if rust_flags:
        cmds.append(f'export RUSTFLAGS="{rust_flags}" ')
    if rust_doc_flags:
        cmds.append(f'export RUSTDOCFLAGS="{rust_doc_flags}"')
    test_names: Optional[list[str]] = []
    for test_path in tests_changed:
        match = re.match(r"tests/([\w\-]+)\.rs", test_path)
        if match:
            test_names.append(match.group(1))
        else:
            test_names = None
            break
    if test_names:
        cmds.extend(
            f"cargo test --no-fail-fast {features_str}{use_all_features_str}--test {test_name}"
            for test_name in test_names
        )
    else:
        cmds.append(f"cargo test --no-fail-fast {features_str}{use_all_features_str}")
    return cmds


def _base_multi_module_test_commands(
        tests_changed: list[str],
        rust_flags: Optional[str] = None,
        rust_doc_flags: Optional[str] = None,
        features: Optional[list[str]] = None,
        use_all_features: bool = False,
):
    submodule_tests: dict[str, Optional[list]] = {}
    for test_path in tests_changed:
        match = re.match(r"([\w\-]+)/tests/([\w\-]+)\.rs", test_path)
        # integration test  
        if match:
            submodule, test_name = match.group(1), match.group(2)
            if submodule not in submodule_tests:
                submodule_tests[submodule] = [test_name]
            elif isinstance(submodule_tests[submodule], list):
                submodule_tests[submodule].append(test_name)
        # other test
        else:
            submodule_tests[test_path.split("/")[0]] = None
    # generate specific str
    features_str = f'--features="{" ".join(features)}" ' if features else ""
    use_all_features_str = "--all-features " if use_all_features else ""
    # generate cmds
    cmds: list[str] = []
    if rust_flags:
        cmds.append(f'export RUSTFLAGS="{rust_flags}" ')
    if rust_doc_flags:
        cmds.append(f'export RUSTDOCFLAGS="{rust_doc_flags}"')
    for submodule, test_names in submodule_tests.items():
        cmds.append(f"cd ./{submodule}")
        if isinstance(test_names, list):
            cmds.extend(
                f"cargo test --no-fail-fast {features_str}{use_all_features_str}--test {test_name}"
                for test_name in test_names
            )
        else:
            cmds.append(
                f"cargo test --no-fail-fast {features_str}{use_all_features_str}"
            )
        cmds.append(f"cd ../")
    return cmds


def make_arrow_rs_test_cmds(
        instance, specs, env_name, repo_directory, base_commit, test_patch, tests_changed
):
    # ban cargo test warnning
    # cmds = ['export RUSTFLAGS="-Awarnings"']
    
    return _base_single_module_test_commands(
        tests_changed=tests_changed,
        rust_flags="-Awarnings",
        use_all_features=True
    )


def make_asterinas_test_cmds(
        instance, specs, env_name, repo_directory, base_commit, test_patch, tests_changed
):
    cmds = []
    test_crates = findCrate(tests_changed)
    print(test_crates)
    if instance["instance_id"] == "asterinas__asterinas-1073":
        cmds.append(
            "make run AUTO_TEST=syscall ENABLE_KVM=1 BOOT_PROTOCOL=linux-efi-handover64 RELEASE=0"
        )
        cmds.append(
            "make run AUTO_TEST=syscall SYSCALL_TEST_DIR=/exfat  ENABLE_KVM=0 BOOT_PROTOCOL=multiboot2 RELEASE=1"
        )
        return cmds
    for test_crate in test_crates:
        if test_crate in NON_OSDK_CRATES:
            cmds.append(f"cd /{env_name}/{test_crate} ")
            cmds.append(f"cargo test --no-fail-fast --all-features")
            cmds.append(f"cd ..")
        if test_crate in OSDK_CRATES:
            cmds.append(f"cd /{env_name}/{test_crate} ")
            cmds.append("cargo osdk test ")
            cmds.append(f"cd ..")
        if test_crate == "test/apps":
            cmds.append("make run AUTO_TEST=test")
    return cmds


def make_tokio_test_cmds(
        instance, specs, env_name, repo_directory, base_commit, test_patch, tests_changed
):
    # add allow lint deny
    options = [
        "-Awarnings",
        "-Aunused_must_use",
        "-Aundropped_manually_drops",
        "-Ainvalid_doc_attributes",
        "-Auseless_deprecated",
        "-Aintra_doc_link_resolution_failure",
        "-Alet_underscore_lock",
        "-Arenamed_and_removed_lints",
        "-Abroken_intra_doc_links",
    ]
    return _base_multi_module_test_commands(
        tests_changed=tests_changed,
        rust_flags=" ".join(options),
        use_all_features=True
    )


def make_crossbeam_test_cmds(
        instance, specs, env_name, repo_directory, base_commit, test_patch, tests_changed
):
    return _base_multi_module_test_commands(
        tests_changed=tests_changed,
        rust_flags="-Awarnings",
    )


def make_hyper_test_cmds(
        instance, specs, env_name, repo_directory, base_commit, test_patch, tests_changed
):
    version = float(instance["version"])
    if version > 1.0:
        features = ['full', 'ffi', 'tracing']
        rust_flags = '-A warnings --cfg hyper_unstable_tracing --cfg hyper_unstable_ffi'
        rust_doc_flags = rust_flags
        before = [
            r"""lint_check_config="\n[lints.rust.unexpected_cfgs]\nlevel = \"warn\"\ncheck-cfg = ['cfg(hyper_unstable_tracing)', 'cfg(hyper_unstable_ffi)']\n" """,
            r"""grep -q '\[lints\.rust\.unexpected_cfgs\]' ./Cargo.toml || echo -e "$lint_check_config" >> ./Cargo.toml""",
        ]
    else:
        features = ['full', 'ffi']
        rust_flags = '-A warnings --cfg hyper_unstable_ffi'
        rust_doc_flags = rust_flags
        before = [
            r"cargo clean",
            r"""lint_check_config="\n[lints.rust.unexpected_cfgs]\nlevel = \"warn\"\ncheck-cfg = ['cfg(hyper_unstable_ffi)']\n" """,
            r"""grep -q '\[lints\.rust\.unexpected_cfgs\]' ./Cargo.toml || echo -e "$lint_check_config" >> ./Cargo.toml""",
            r"""
            find . -name "*.rs" -type f | while read file; do
                sed -i 's/deny(warnings)/allow(warnings)/g' "$file"
            done
            """,
        ]
    return _base_single_module_test_commands(
        tests_changed=tests_changed,
        rust_flags=rust_flags,
        rust_doc_flags=rust_doc_flags,
        features=features,
        before=before,
    )


MAP_REPO_TO_TESTS = {
    "apache/arrow-rs": make_arrow_rs_test_cmds,
    "asterinas/asterinas": make_asterinas_test_cmds,
    "tokio-rs/tokio": make_tokio_test_cmds,
    "crossbeam-rs/crossbeam": make_crossbeam_test_cmds,
    "hyperium/hyper": make_hyper_test_cmds
}


def make_test_cmds(
        instance, specs, env_name, repo_directory, base_commit, test_patch, tests_changed
):
    repo = instance["repo"]
    if repo not in MAP_REPO_TO_TESTS:
        test_cmd = specs.get("test_cmd", None)
        if test_cmd is None:
            return None
        elif isinstance(test_cmd,str):
            return [test_cmd]
        elif isinstance(test_cmd,list):
            return test_cmd
        else:
            raise ValueError(f"Unsupported test commands")
    return MAP_REPO_TO_TESTS[repo](
        instance,
        specs,
        env_name,
        repo_directory,
        base_commit,
        test_patch,
        tests_changed,
    )
