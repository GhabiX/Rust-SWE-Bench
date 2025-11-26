import os
from typing import Optional, Union, Callable

from func_timeout import func_timeout
from func_timeout.exceptions import FunctionTimedOut
from ghapi.all import GhApi
from fastcore.net import HTTP403ForbiddenError


def gh_tree(api: GhApi, owner: str, repo: str, commit: str = "HEAD", **kwargs):
    return api.git.get_tree(owner, repo, commit, recursive=True, **kwargs)["tree"]


class GithubApiPool:

    def __init__(self, tokens: Union[str, list]):
        if isinstance(tokens, str):
            self.apis = [GhApi(token=token) for token in tokens.split(",") if token]
        elif isinstance(tokens, list):
            self.apis = [GhApi(token=token) for token in tokens]
        else:
            raise ValueError("tokens must be a str or list")

    def call(self, *args, method: Callable, timeout: Optional[float] = None, **kwargs):
        while True:
            try:
                return func_timeout(timeout, method, args=(self.fetch(), *args,), kwargs=kwargs)
            except HTTP403ForbiddenError:
                print(f"403 Forbidden: Access denied, switching to next available API.")
                self._rotate()
            except FunctionTimedOut:
                print(f"Connection timed out. Retrying...")
                self._rotate()
            except (SystemError, KeyboardInterrupt):
                raise
            except Exception as e:
                print(f"Unexpected error {e}. Retrying...")
                self._rotate()

    def _rotate(self):
        if not self.apis:
            raise RuntimeError("No GitHub API available")
        self.apis.append(self.apis.pop(0))
        print(f"Rotated to {self.apis[0]}...")

    def fetch(self):
        if not self.apis:
            raise RuntimeError("No GitHub API available")
        return self.apis[0]


class RepoArchitecture:

    def __init__(self, name: Optional[str] = None, parent=None):
        self.name = name
        self.parent: Optional[RepoArchitecture] = parent
        self.files: set[str] = set()
        self.dirs: dict[str, RepoArchitecture] = dict()
        self.is_module: bool = False

    def find_dir(self, paths: list[str], create_dir: bool = True):
        current = self
        for path in paths:
            if path in current.dirs:
                current = current.dirs[path]
            else:
                if create_dir:
                    current.dirs[path] = RepoArchitecture(path, current)
                    current = current.dirs[path]
                else:
                    raise RuntimeError(f"Path: {path} is not a directory")
        return current

    def find_module(self, paths: list[str]):
        module = self.find_dir(paths)
        while module is not None and not module.is_module:
            module = module.parent
        assert module is not None
        return module

    def get_full_path(self):
        current, path = self.parent, self.name
        while current:
            if current.name:
                path = f"{current.name}/{path}"
            current = current.parent
        return path


def get_repo_arch(
        pool: GithubApiPool, owner: str, repo: str, commit: Optional[str] = None
) -> RepoArchitecture:
    root = RepoArchitecture()

    for item in pool.call(owner, repo, commit, method=gh_tree, timeout=5):
        item_type, item_path = item["type"], item["path"]
        paths = item_path.split("/")

        if item_type == "tree":
            root.find_dir(paths)

        elif item["type"] == "blob":
            paths = item["path"].split("/")
            paths, name = paths[:-1], paths[-1]
            arch = root.find_dir(paths)
            if name == "Cargo.toml":
                arch.is_module = True
            elif name.endswith(".rs"):
                arch.files.add(name)

    return root


def get_cargo_test_cmd(
        root: RepoArchitecture, tests: list[str], flags: Optional[str] = None
) -> list[str]:
    try:
        submodule_test_dict = dict()
        for test_path in tests:
            # assert .rs file
            if not test_path.endswith(".rs"):
                continue
            test_segments = test_path.split("/")
            test_dir, test_file, test_name = test_segments[:-1], test_segments[-1], test_segments[-1].removesuffix(".rs")
            # find nearest cargo submodule
            module_path = root.find_module(test_dir).get_full_path()
            # init submodule tests
            if module_path not in submodule_test_dict:
                submodule_test_dict[module_path] = list()
            # try integration test
            if f"{module_path}/tests/{test_file}" == test_path:
                if isinstance(submodule_test_dict[module_path], list):
                    submodule_test_dict[module_path].append(
                        f'cargo test --no-fail-fast --all-features --test "{test_name}"'
                    )
            # try bin test
            elif f"{module_path}/src/bin/{test_file}" == test_path:
                if isinstance(submodule_test_dict[module_path], list):
                    submodule_test_dict[module_path].append(
                        f'cargo test --no-fail-fast --all-features --bin "{test_name}"'
                    )
            # try example test
            elif f"{module_path}/examples/{test_file}" == test_path:
                if isinstance(submodule_test_dict[module_path], list):
                    submodule_test_dict[module_path].append(
                        f'cargo test --no-fail-fast --all-features --example "{test_name}"'
                    )
            # try bench test
            elif f"{module_path}/benches/{test_file}" == test_path:
                if isinstance(submodule_test_dict[module_path], list):
                    submodule_test_dict[module_path].append(
                        f'cargo test --no-fail-fast --all-features --bench "{test_name}"'
                    )
            # test all
            else:
                submodule_test_dict[module_path] = None
        cmds = list()
        if flags:
            cmds.append(f'export RUSTFLAGS="{flags}"')
            cmds.append(f'export RUSTDOCFLAGS="{flags}"')
        for module_path in submodule_test_dict:
            if module_path:
                cmds.append(f'cd "{module_path}"')
            if submodule_test_dict[module_path]:
                cmds.extend(submodule_test_dict[module_path])
            else:
                cmds.append(f"cargo test --no-fail-fast --all-features")
            if module_path:
                cmds.append(f'cd {"../" * (module_path.count("/") + 1)}')
        return cmds
    except AssertionError:
        return None


def get_cargo_test_cmd_wo_features(
        root: RepoArchitecture, tests: list[str], flags: Optional[str] = None
) -> list[str]:
    try:
        submodule_test_dict = dict()
        for test_path in tests:
            # assert .rs file
            if not test_path.endswith(".rs"):
                continue
            test_segments = test_path.split("/")
            test_dir, test_file, test_name = test_segments[:-1], test_segments[-1], test_segments[-1].removesuffix(".rs")
            # find nearest cargo submodule
            module_path = root.find_module(test_dir).get_full_path()
            # init submodule tests
            if module_path not in submodule_test_dict:
                submodule_test_dict[module_path] = list()
            # try integration test
            if f"{module_path}/tests/{test_file}" == test_path:
                if isinstance(submodule_test_dict[module_path], list):
                    submodule_test_dict[module_path].append(
                        f'cargo test --no-fail-fast --test "{test_name}"'
                    )
            # try bin test
            elif f"{module_path}/src/bin/{test_file}" == test_path:
                if isinstance(submodule_test_dict[module_path], list):
                    submodule_test_dict[module_path].append(
                        f'cargo test --no-fail-fast --bin "{test_name}"'
                    )
            # try example test
            elif f"{module_path}/examples/{test_file}" == test_path:
                if isinstance(submodule_test_dict[module_path], list):
                    submodule_test_dict[module_path].append(
                        f'cargo test --no-fail-fast --example "{test_name}"'
                    )
            # try bench test
            elif f"{module_path}/benches/{test_file}" == test_path:
                if isinstance(submodule_test_dict[module_path], list):
                    submodule_test_dict[module_path].append(
                        f'cargo test --no-fail-fast --bench "{test_name}"'
                    )
            # test all
            else:
                submodule_test_dict[module_path] = None
        cmds = list()
        if flags:
            cmds.append(f'export RUSTFLAGS="{flags}"')
            cmds.append(f'export RUSTDOCFLAGS="{flags}"')
        for module_path in submodule_test_dict:
            if module_path:
                cmds.append(f'cd "{module_path}"')
            if submodule_test_dict[module_path]:
                cmds.extend(submodule_test_dict[module_path])
            else:
                cmds.append(f"cargo test --no-fail-fast")
            if module_path:
                cmds.append(f'cd {"../" * (module_path.count("/") + 1)}')
        return cmds
    except AssertionError:
        return None


def test_bitflags():
    test_cases = [
        ["tests/basic.rs"],
        ["tests/basic.rs", "tests/compile-fail/redefined.rs"],
        [
            "tests/basic.rs",
            "tests/compile-fail/redefined.rs",
            "tests/compile-fail/trait/custom_impl.rs",
        ],
        [
            "tests/basic.rs",
            "tests/compile-fail/redefined.rs",
            "tests/compile-fail/trait/custom_impl.rs",
            "tests/smoke-test/src/main.rs",
        ],
        [
            "tests/basic.rs",
            "tests/compile-fail/redefined.rs",
            "tests/compile-fail/trait/custom_impl.rs",
            "tests/smoke-test/src/main.rs",
            "src/lib.rs",
        ]
    ]
    root = get_repo_arch(GithubApiPool(tokens=os.environ["GITHUB_TOKENS"]), "bitflags", "bitflags",
                         "dc971042c8132a5381ab3e2165983ee7f9d44c63")
    for test_case in test_cases:
        print(get_cargo_test_cmd(root, test_case))


def test_arrow():
    test_cases = [
        ["arrow-flight/tests/flight_sql_client.rs"],
        [
            "arrow-flight/tests/flight_sql_client.rs",
            "arrow-flight/examples/server.rs",
        ],
        [
            "arrow-flight/tests/flight_sql_client.rs",
            "arrow-flight/examples/server.rs",
            "testing/data/csv/README.md",
        ]
    ]
    root = get_repo_arch(GithubApiPool(tokens=os.environ["GITHUB_TOKENS"]), "apache", "arrow-rs",
                         "9ffa06543be51613ea1f509e63f6e7405b7d9989")
    for test_case in test_cases:
        print(get_cargo_test_cmd(root, test_case))


def test_repo():
    test_bitflags()
    test_arrow()


def test_rate():
    pool = GithubApiPool(tokens=os.environ["GITHUB_TOKENS"])
    cnt = 0
    while True:
        pool.call("bitflags", "bitflags", method=gh_tree, timeout=3)
        print(f"Count: {cnt}")
        cnt += 1


if __name__ == "__main__":
    # test_repo()
    test_rate()
