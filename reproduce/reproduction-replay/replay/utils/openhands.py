"""
OpenHands utility functions for function call parsing and trajectory processing.

This module provides utilities for working with OpenHands (formerly OpenDevin) agent
function calls and trajectory data. It handles parsing and serialization of function
calls in the OpenHands format, as well as extracting different components from
trajectory strings.

The module integrates with OpenHands' codeact agent function calling system and
provides a consistent interface for processing agent interactions and tool usage.

Key Features:
    - Function call parsing from string format to structured data
    - Function call serialization from structured data to string format
    - Trajectory parsing to extract function calls and natural language
    - Integration with OpenHands tool system

Functions:
    openhands_function_call_loads: Parse function call string to name and arguments
    openhands_function_call_dumps: Serialize function name and arguments to string
    openhands_traj_extract_function_call: Extract function call blocks from trajectory
    openhands_traj_extract_natural_language: Extract natural language from trajectory

Dependencies:
    - OpenHands codeact agent function calling system
    - OpenHands LLM function call converter
"""

import json
import re
from typing import Dict
from typing import Optional
from typing import Tuple


from openhands.agenthub.codeact_agent.function_calling import get_tools
from openhands.llm.fn_call_converter import convert_non_fncall_messages_to_fncall_messages

from replay.utils.dependency import dependency_list

# Verify that OpenHands (Mope   nHands) is available as a dependency
assert "OpenHands" in dependency_list(full_path=False)

# Cache the OpenHands tools for function call processing
_openhands_tools = get_tools()


def openhands_function_call_loads(
    call_string: str,
) -> Tuple[Optional[str], Optional[Dict]]:
    """
    Parse a function call string into a function name and arguments dictionary.

    This function takes a string containing an OpenHands-formatted function call
    and converts it into structured data using the OpenHands function call converter.
    It handles the conversion from natural language or XML-like function call format
    to a standardized function name and arguments dictionary.

    Args:
        call_string: The string containing the function call, which may be in
                    natural language or XML-like format (e.g., "<function=name>...")

    Returns:
        A tuple containing:
        - function_name (Optional[str]): The extracted function name, or None if parsing fails
        - arguments (Optional[Dict]): The extracted arguments dictionary, or None if parsing fails

    Examples:
        >>> name, args = openhands_function_call_loads("<function=test><parameter=arg>value</parameter></function>")
        >>> print(name)  # "test"
        >>> print(args)  # {"arg": "value"}

        >>> name, args = openhands_function_call_loads("invalid function call")
        >>> print(name, args)  # None None

    Note:
        This function uses OpenHands' built-in converter which may modify the input
        by wrapping it in a message format before processing.
    """
    try:
        # Convert the call string into OpenHands function call format
        # Wrap in assistant message format as required by the converter
        function = convert_non_fncall_messages_to_fncall_messages(
            [
                {
                    "role": "assistant",
                    "content": call_string,
                }
            ],
            _openhands_tools,  # Use cached OpenHands tools
        )[
            -1  # Get the last (most recent) message
        ]["tool_calls"][
            -1  # Get the last (most recent) tool call
        ]["function"]

        # Extract function name and parse JSON arguments
        return function["name"], json.loads(function["arguments"])
    except:
        # Return None values if any step fails (invalid format, JSON parsing error, etc.)
        return None, None


def openhands_function_call_dumps(
    function_name: str,
    function_args: Dict[str, str],
) -> str:
    """
    Serialize a function name and arguments dictionary into OpenHands XML-like string format.

    This function converts structured function call data back into the OpenHands
    XML-like string format used for agent communication. It creates a properly
    formatted function call block with parameters.

    Args:
        function_name: The name of the function to call
        function_args: Dictionary of function arguments where keys are parameter names
                      and values are parameter values (will be converted to strings)

    Returns:
        A formatted string representing the function call in OpenHands XML format

    Examples:
        >>> call_str = openhands_function_call_dumps("test", {"arg1": "value1", "arg2": "value2"})
        >>> print(call_str)
        <function=test>
        <parameter=arg1>value1</parameter>
        <parameter=arg2>value2</parameter>
        </function>

        >>> # Long values get formatted on separate lines for readability
        >>> long_value = "a" * 150
        >>> call_str = openhands_function_call_dumps("process", {"content": long_value})
        >>> print(call_str)
        <function=process>
        <parameter=content>
        aaa...aaa
        </parameter>
        </function>

    Note:
        Values longer than 100 characters are formatted on separate lines for
        better readability, while shorter values are kept inline.
    """
    result = f"<function={function_name}>\n"
    for key, val in function_args.items():
        key, val = str(key), str(val)  # Ensure both key and value are strings
        result += f"<parameter={key}>"
        if len(val) > 100:
            # Format long values on separate lines for better readability
            result += f"\n{val}\n"
        else:
            # Keep short values inline
            result += val
        result += "</parameter>\n"
    result += "</function>\n"
    return result


def openhands_traj_extract_function_call(
    traj: str,
) -> str:
    """
    Extract the function call block from an OpenHands trajectory string.

    This function uses regex to find and extract function call blocks from
    trajectory strings. It looks for the OpenHands XML-like function call format
    and returns the complete function call block including all parameters.

    Args:
        traj: The trajectory string that may contain function call blocks
              mixed with other content

    Returns:
        The extracted function call block as a string, including the opening
        <function=...> tag and closing </function> tag

    Raises:
        AttributeError: If no function call block is found in the trajectory
                       (when re.search returns None)

    Examples:
        >>> traj = "Some text <function=test><parameter=arg>value</parameter></function> more text"
        >>> extracted = openhands_traj_extract_function_call(traj)
        >>> print(extracted)
        <function=test><parameter=arg>value</parameter></function>

        >>> traj = "No function calls here"
        >>> extracted = openhands_traj_extract_function_call(traj)  # Will raise AttributeError

    Note:
        This function assumes there is exactly one function call block in the
        trajectory. If multiple blocks exist, only the first one is returned.
    """
    function_calling_regex = r"<function=.*>.*</function>"
    # Use DOTALL flag to match across newlines within function blocks
    return re.search(function_calling_regex, traj, re.DOTALL).group(0).strip()


def openhands_traj_extract_natural_language(
    traj: str,
) -> str:
    """
    Extract the natural language part from an OpenHands trajectory string.

    This function removes all function call blocks from the trajectory string,
    leaving only the natural language content (explanations, reasoning, etc.).
    It's useful for analyzing the agent's thought process separate from its actions.

    Args:
        traj: The trajectory string that may contain both natural language
              and function call blocks

    Returns:
        The trajectory string with all function call blocks removed,
        with leading and trailing whitespace stripped

    Examples:
        >>> traj = "I need to test something <function=test><parameter=arg>value</parameter></function> now done"
        >>> natural = openhands_traj_extract_natural_language(traj)
        >>> print(natural)
        I need to test something  now done

        >>> traj = "Pure natural language without any function calls"
        >>> natural = openhands_traj_extract_natural_language(traj)
        >>> print(natural)
        Pure natural language without any function calls

        >>> traj = "<function=only_function><parameter=x>y</parameter></function>"
        >>> natural = openhands_traj_extract_natural_language(traj)
        >>> print(natural)
        (empty string)

    Note:
        Multiple function call blocks will all be removed from the trajectory.
        The function uses regex substitution with DOTALL flag to handle
        multi-line function blocks properly.
    """
    function_calling_regex = r"<function=.*>.*</function>"
    # Remove all function call blocks using regex substitution
    # DOTALL flag ensures newlines within function blocks are matched
    natural_language = re.sub(function_calling_regex, "", traj, flags=re.DOTALL)
    return natural_language.strip()


if __name__ == "__main__":
    # Test example for demonstrating function call parsing
    TEXT = """
    [TEST BEGIN]
    <function=test>
        <parameter=arg>test</parameter>
    </function>
    [TEST FINISH]
"""
    # Demonstrate the parsing functionality
    print(openhands_function_call_loads(TEXT))
