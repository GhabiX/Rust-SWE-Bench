"""
A proxy agent. Process raw response into json format.
"""

import inspect
from typing import Any
import openai
from loguru import logger
from openai import BaseModel
from app.data_structures import MessageThread
from app.log import log_and_print
from app.model import common
from app.post_process import ExtractStatus, is_valid_json
from app.search.search_backend import SearchBackend
from app.utils import parse_function_invocation
import os


class API_CALLS(BaseModel):
    API_calls : list[str]
    bug_locations : list[dict[str, str]]

PROXY_PROMPT = """
You are a helpful assistant that retrieves API calls and bug locations from a text into JSON format.
The text will consist of two parts:
1. Do we need more context?
2. Where are the bug locations?
Extract API calls from question 1 (leave empty if not exist) and bug locations from question 2 (leave empty if not exist).

The API calls include:
search_macro(macro_name: str)
search_macro_in_file(macro_name: str, file_path: str)
search_function(function_name: str)
search_function_in_file(function_name: str, file_path: str)
search_method(method_name: str)
search_method_in_struct(method_name: str, struct_name: str)
search_method_in_trait(method_name: str, trait_name: str)
search_method_in_file(method_name: str, file_path: str)
search_struct_in_file(struct_name: str, file_path: str)
search_struct(struct_name: str)
search_trait_in_file(trait_name: str, file_path: str)
search_trait(trait_name: str)
search_code_in_file(code_str: str, file_path: str)
search_code(code_str: str)
get_code_around_line(file_path: str, line_number: int, window_size: int)

Provide your answer in JSON structure like this, you should ignore the argument placeholders in API calls.It is very important 
For example, search_code(code_str="str") should be search_code("str")
search_method_in_file("method_name", "path.to.file") should be search_method_in_file("method_name", "path/to/file")
Make sure each API call is written as a valid Python expression.

{
    "API_calls": ["api_call_1(args)", "api_call_2(args)", ...],
    "bug_locations": [{"file": "path/to/file", "function": "function_name", "intended_behavior": "This code should ..."}, {"file": "path/to/file", "struct": "struct_name", "method": "method_name", "intended_behavior": "..."}, ... ]
}
Note that for bug_locations, each dictionary should have "file", and then either "function" for free-standing functions, or "struct" and "method" for methods in structs, and "intended_behavior" describing what the code should do.
"""

def run_with_retries(text: str, retries=5) -> tuple[str | None, list[MessageThread]]:
    msg_threads = []
    for idx in range(1, retries + 1):
        logger.debug(
            "Trying to convert API calls/bug locations into json. Try {} of {}.",
            idx,
            retries,
        )

        res_text, new_thread = run(text)
        msg_threads.append(new_thread)

        # Find the start of the markdown code block for JSON
        # This effectively ignores any text that comes before it.
        start_marker = "```json"
        block_start_index = res_text.find(start_marker)

        if block_start_index != -1:
            # If the marker is found, slice the string from after the marker
            res_text = res_text[block_start_index + len(start_marker):]

        # Find the end of the markdown code block
        end_marker = "```"
        block_end_index = res_text.rfind(end_marker)
        
        if block_end_index != -1:
            # If the end marker is found, slice the string to get content inside
            res_text = res_text[:block_end_index]

        extract_status, data = is_valid_json(res_text)

        if extract_status != ExtractStatus.IS_VALID_JSON:
            logger.debug("Invalid json. Will retry.")
            continue

        valid, diagnosis = is_valid_response(data)
        if not valid:
            logger.debug(f"{diagnosis}. Will retry.")
            continue

        logger.debug("Extracted a valid json.")
        return res_text, msg_threads
    return None, msg_threads


def run(text: str) -> tuple[str, MessageThread]:
    """
    Run the agent to extract issue to json format.
    """

    msg_thread = MessageThread()
    msg_thread.add_system(PROXY_PROMPT)
    msg_thread.add_user(text)

    # client = openai.OpenAI(
    #     api_key=os.getenv("OPENAI_API_KEY"),
    #     base_url=os.getenv("OPENAI_BASE_URL"),
    # )
    # print("base_url", os.getenv("OPENAI_BASE_URL"))
    # for _ in range(3):
    #     try:
    #         completion = client.beta.chat.completions.parse(
    #             model=common.SELECTED_MODEL.name,
    #             messages=msg_thread.to_msg(),
    #             temperature=common.MODEL_TEMP,
    #             response_format=API_CALLS,
    #         )
    #         log_and_print(
    #             f"Raw model response: {completion.choices[0].message}"
    #         )
    #         res_text = completion.choices[0].message.parsed
    #         break
    #     except Exception as e:
    #         logger.debug(
    #             "Error when calling the model: {}. Retrying...",
    #             e,
    #         )
    #         res_text = None
    #         continue
    # if res_text is None:
    #     logger.debug("Failed to get a response from the model.")
    # res_text = res_text.model_dump_json(indent=4)
    # res_text, *_ = common.SELECTED_MODEL.call(
    #     msg_thread.to_msg(), response_format="json_object"
    # )
    res_text, *_ = common.SELECTED_MODEL.call(
        msg_thread.to_msg()
    )
    msg_thread.add_model(res_text, [])  # no tools

    return res_text, msg_thread


def is_valid_response(data: Any) -> tuple[bool, str]:
    if not isinstance(data, dict):
        return False, "Json is not a dict"

    if not data.get("API_calls"):
        bug_locations = data.get("bug_locations")
        if not isinstance(bug_locations, list) or not bug_locations:
            return False, "Both API_calls and bug_locations are empty"

        for loc in bug_locations:
            if loc.get("class") or loc.get("method") or loc.get("file"):
                continue
            return (
                False,
                "Bug location not detailed enough. Each location must contain at least a class or a method or a file.",
            )
    else:
        for api_call in data["API_calls"]:
            if not isinstance(api_call, str):
                return False, "Every API call must be a string"

            try:
                func_name, func_args = parse_function_invocation(api_call)
            except Exception:
                return False, "Every API call must be of form api_call(arg1, ..., argn)"

            function = getattr(SearchBackend, func_name, None)
            if function is None:
                return False, f"the API call '{api_call}' calls a non-existent function"

            # getfullargspec returns a wrapped function when the function defined
            # has a decorator. We unwrap it here.
            while "__wrapped__" in function.__dict__:
                function = function.__wrapped__

            arg_spec = inspect.getfullargspec(function)
            arg_names = arg_spec.args[1:]  # first parameter is self

            if len(func_args) != len(arg_names):
                return False, f"the API call '{api_call}' has wrong number of arguments"

    return True, "OK"
