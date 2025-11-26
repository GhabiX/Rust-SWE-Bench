import json
import re
from collections import defaultdict
from collections.abc import Generator
from copy import deepcopy
from pathlib import Path
from typing import TypeAlias

from loguru import logger
from tenacity import retry, stop_after_attempt

from app.agents.agent_common import InvalidLLMResponse
from app.data_structures import MessageThread, ReproResult
from app.log import print_acr, print_reproducer
from app.model.gpt import common
from app.task import Task
from app.repo_utils.repository_structure import get_git_repo_structure_from_url

SYSTEM_PROMPT = (
    "You are an experienced software engineer responsible for reproducing given issues."
)

INITIAL_REQUEST = (
    "Please try to write a standalone rust test file to reproduce the issue."
    "Put the file in a code block.\n\n"
    "The file would be put in the bin directory of the project and compiled and executed using \"cargo run --bin <filename>\"."
    "The test should panic or fail when the issue is present, and the panci message should include a stack trace of the issue."
    "The script should exit successfully (without panicking) when the issue is fixed.\n\n"
    "Please use the following function to print the stack trace, so that the line numbers "
    "of the statements are shown clearly:\n"
    "\n"
    "fn print_stacktrace(e: &dyn std::error::Error) {\n"
    "    eprintln!(\"Error: {}\", e);\n"
    "    let backtrace = std::backtrace::Backtrace::capture();\n"
    "    eprintln!(\"Stack trace:\\n{:?}\", backtrace);\n"
    "}\n"
    "\n"
    "When the issue is present, the script should panic with a descriptive message, and the"
    "stack trace should be printed using the `print_stacktrace` function. When the issue "
    "is fixed, the script should exit successfully without panicking.\n"
    # "In order to run the test, the script must have the main function.\n"
)

class NoReproductionStep(RuntimeError):
    """Raised when issue statement does not contain steps for reproduction."""

    pass


TestHandle: TypeAlias = str


class TestAgent:
    def __init__(self, task: Task, task_dir: str) -> None:
        self.task = task
        self.task_dir = task_dir

        self._request_idx: int = -1
        self._responses: dict[TestHandle, str] = {}
        self._tests: dict[TestHandle, str] = {}
        self._feedbacks: dict[TestHandle, list[str]] = defaultdict(list)
        self._history: list[TestHandle] = []
        self._non_repro_history: list[TestHandle] = []

    def write_reproducing_test_without_feedback(
        self, retries: int = 1
    ) -> tuple[TestHandle, str, ReproResult]:
        return self._write_reproducing_test(num_feedbacks=1, retries=retries)

    def write_reproducing_test_with_feedback(
        self, max_feedbacks: int = 1, retries: int = 1
    ) -> tuple[TestHandle, str, ReproResult]:
        return self._write_reproducing_test(
            num_feedbacks=max_feedbacks, retries=retries
        )

    def add_feedback(self, handle: TestHandle, feedback: str) -> None:
        if handle not in self._tests:
            raise ValueError("patch {} does not exist", handle)

        self._feedbacks[handle].append(feedback)

    def _write_reproducing_test(
        self, num_feedbacks: int, retries: int
    ) -> tuple[TestHandle, str, ReproResult]:

        for _ in range(retries):
            response = ""
            test_content = self.task.task_id
            true_test, repro_result = self.task.execute_reproducer(test_content)

            if repro_result.reproduced:
                response = "Reproducing test passed."
                test_content = f"Reproducing test content for task {self.task.task_id}"
                handle = self._register_reproducing_test(response, true_test)
                print_acr(str(repro_result))
                return (handle, true_test, repro_result)
            handle = self._register_non_reproducing_test(
                response, true_test, repro_result
            )
            print_acr(str(repro_result))
            return(handle, true_test, repro_result)

        raise InvalidLLMResponse(
            f"Failed to write a reproducing test in {retries} attempts"
        )

    @classmethod
    def _issue_has_reproduction_steps(
        cls, issue_statement: str
    ) -> tuple[bool, MessageThread]:
        prefix_thread = MessageThread()

        prefix_thread.add_system(SYSTEM_PROMPT)

        prefix_thread.add_user(f"Here is an issue:\n\n{issue_statement}")

        key = "has-reproducible-example"
        prefix_thread.add_user(
            "Tell me whether the issue contains a reproducible example. Your"
            " answer should take the following Json format:\n"
            "```\n"
            "{\n"
            f'    "{key}": ...\n'
            "}\n"
            "```\n"
            f'where "{key}" should be either `true` or `false`.'
        )

        @retry(stop=stop_after_attempt(1))
        def query_and_parse():
            # response, *_ = common.SELECTED_MODEL.call(
            #     prefix_thread.to_msg(), response_format="json_object"
            # )
            response, *_ = common.SELECTED_MODEL.call(
                prefix_thread.to_msg()
            )
            print(response)
            result = json.loads(response)[key]

            if not isinstance(result, bool):
                raise InvalidLLMResponse

            thread = deepcopy(prefix_thread)
            thread.add_model(response)

            return result, thread

        return query_and_parse()

    def _select_feedback_handles(self, max_num_feedbacks: int) -> list[TestHandle]:
        if 0 <= max_num_feedbacks <= len(self._history):
            return self._history[-max_num_feedbacks:]
        elif max_num_feedbacks <= len(self._history) + len(self._non_repro_history):
            num_non_repro = max_num_feedbacks - len(self._history)
            return [
                *self._non_repro_history[-num_non_repro:],
                *self._history,
            ]
        else:
            return [*self._non_repro_history, *self._history]

    def _write_test(
        self, history_handles: list[TestHandle] | None = None
    ) -> tuple[str, str | None, MessageThread]:
        history_handles = history_handles or []
        repo = self.task.repo_name
        url = "https://github.com/"+repo+".git"
        structure = get_git_repo_structure_from_url(url)
        quest_location=(
        f"""
        Please try to write a bash script to reproduce the issue.
        Put the script in a ```bash code block.

        The script should run from the root directory of a Rust workspace and include the following steps:
        - Locate a suitable 'bin' directory in the project (default to 'bin/' in the workspace root unless the project structure suggests a specific crate's 'bin/' directory).
        - Write the reproducer code to 'bin/reproducer.rs' in the chosen directory.
        - Compile and run the reproducer using 'cargo run --bin reproducer'.
        - If the issue is present, the script should exit with a non-zero code, print a descriptive error message, and include the stack trace from the Rust reproducer's `print_stacktrace` function.
        - If the issue is fixed, the script should exit successfully with a zero code.
        Here is the directory structure of the project:
        {structure}
        """
        )
        thread = self._construct_init_thread()
        if any(handle in self._feedbacks for handle in history_handles):
            thread.add_user(quest_location)
        for handle in history_handles:
            if feedbacks := self._feedbacks.get(handle, []):
                thread.add_model(self._responses[handle], [])
                for feedback in feedbacks:
                    thread.add_user(feedback)
            else:
                logger.warning("test {} does not have a feedback; skipping", handle)

        thread.add_user(quest_location)
        # thread.add_user("Please try again.")
        if not history_handles:
            print_acr(quest_location)

        response, *_ = common.SELECTED_MODEL.call(thread.to_msg())

        return response, self.convert_response_to_test(response), thread

    def _construct_init_thread(self) -> MessageThread:
        thread = MessageThread()
        thread.add_system(SYSTEM_PROMPT)

        prompt = f"Here is an issue:\n\n{self.task.get_issue_statement()}"
        thread.add_user(prompt)

        return thread

    def _register_reproducing_test(
        self, response: str, test_content: str
    ) -> TestHandle:
        handle = str(self._request_idx)

        assert handle not in self._responses
        assert handle not in self._feedbacks
        assert handle not in self._tests
        assert handle not in self._history

        self._responses[handle] = response
        self._tests[handle] = test_content
        self._history.append(handle)

        return handle

    def _register_non_reproducing_test(
        self, response: str, test_content: str, repro_result: ReproResult
    ) -> TestHandle:
        handle = str(self._request_idx)

        assert handle not in self._responses
        assert handle not in self._feedbacks
        assert handle not in self._tests
        assert handle not in self._non_repro_history

        self._responses[handle] = response
        self._tests[handle] = test_content
        self._non_repro_history.append(handle)
        self._feedbacks[handle].append(self._feedback_from_repro_result(repro_result))

        return handle

    def _feedback_from_repro_result(self, repro_result: ReproResult) -> str:
        return (
            "This test did not reproduce the issue.\n"
            "\n"
            f"The test execution exited with code {repro_result.returncode}.\n"
            "\n"
            f"Standard output: {repro_result.stdout}\n"
            "\n"
            f"Standard error: {repro_result.stderr}"
        )

    @classmethod
    def convert_response_to_test(cls, response: str) -> str | None:
        blocks = extract_markdown_code_blocks(response)

        if len(blocks) == 1:
            return blocks[0]
        elif len(blocks) == 2 and blocks[0].startswith("```bash"):
            return blocks[0]
        else:
            return None

    def save_test(self, handle: TestHandle) -> None:
        Path(self.task_dir, f"reproducer_{handle}.py").write_text(self._tests[handle])


def generator(
    issue_statement: str,
) -> Generator[tuple[str, MessageThread, bool], str | None, None]:
    prefix_thread = MessageThread()
    prefix_thread.add_system(SYSTEM_PROMPT)
    # issue_statement = task.get_issue_statement()
    prompt = f"Here is an issue:\n\n{issue_statement}"
    prefix_thread.add_user(prompt)
    # print_acr(prompt, "reproducer test generation")
    prefix_thread.add_user(INITIAL_REQUEST)

    # prefix_thread.add_user(quest_location)

    print_acr(INITIAL_REQUEST, "reproducer test generation")

    threads = []

    index = 1
    thread = deepcopy(prefix_thread)
    while True:
        response, *_ = common.SELECTED_MODEL.call(prefix_thread.to_msg())

        thread.add_model(response, [])
        print_reproducer(response, desc=f"Try {index}")

        index += 1

        threads.append(thread)

        code_blocks, = extract_markdown_code_blocks(response)

        if len(code_blocks) != 1:
            _ = yield "", thread, False

            new_prompt = (
                f"Expected 1 code block, got {len(code_blocks)}. Please try again."
            )
        else:
            test_content = code_blocks[0]
            evaluation_msg = yield test_content, thread, True

            assert evaluation_msg is not None

            new_prompt = f"The issue reproduction is incorrect. {evaluation_msg} Please try again."

        thread.add_user(new_prompt)


def extract_markdown_code_blocks(content: str) -> list[str]:
    lines = content.splitlines(keepends=True)

    in_code_block = False
    start_pattern = r"\s*```\w*\s*"
    end_pattern = r"\s*```\s*"

    start, end = -1, -1
    intervals = []

    for idx, line in enumerate(lines):
        if (not in_code_block) and re.match(start_pattern, line):
            in_code_block = True
            start = idx + 1
        elif in_code_block and re.match(end_pattern, line):
            in_code_block = False
            end = idx
            intervals.append((start, end))

    res = ["".join(lines[start:end]) for start, end in intervals]
    return res
