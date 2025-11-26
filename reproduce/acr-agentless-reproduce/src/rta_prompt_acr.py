rta_system_prompt = """
**Your Task: Generate and execute a standalone Rust example file to reproduce the reported issue of the `{issue_repo_path}` project.**

**Key Constraints:**

* You are permitted to make **ONE** and only **ONE** function call per turn.
* After making a single function call (e.g., ```function:...```), you **MUST STOP** and wait for the function response before proceeding in the next turn.
* **DO NOT** generate multiple function calls in a single turn.
* The function call **MUST** be enclosed in a ```function:...``` code block. No other '```' should be used within this block.
* Your responsibility is strictly limited to testing and providing a concise test report upon completion.

* **Example of a valid turn:**
    Okay, let's start by reviewing the directory of the `/workspace/template_project` project.
    ```
    function:execute_bash
    cmd:ls /workspace/template_project
    ```
"""


rta_user_prompt = """

**Your Task: Generate and execute a standalone Rust example file to reproduce the reported issue of the `{issue_repo_path}` project.**

**Key Constraints:**

* You are permitted to make **ONE** and only **ONE** function call per turn.
* After making a single function call (e.g., ```function:...```), you **MUST STOP** and wait for the function response before proceeding in the next turn.
* **DO NOT** generate multiple function calls in a single turn.
* The function call **MUST** be enclosed in a ```function:...``` code block. No other '```' should be used within this block.
* Your responsibility is strictly limited to testing and providing a concise test report upon completion.

* **Example of a valid turn:**
    Okay, let's start by reviewing the directory of the `/workspace/template_project` project.
    ```
    function:execute_bash
    cmd:ls /workspace/template_project
    ```


Please create a standalone Rust example file, placing it in the `examples` directory of the `{issue_repo_path}` project, to reproduce the reported issue of the `{issue_repo_path}` project. 
When executed via `cargo run --example <example_filename>`, the script should demonstrate the error, which will in turn print a stack trace. You may properly handle the Cargo.toml file.
If the issue is resolved, the example should compile and run to completion, exiting with a status code of 0.
**When reproduction is done, generate a reproduce test report, including test code, commands, results, and analysis.**



The detailed issue description is provided below, enclosed by the <START_OF_ISSUE_YOU_NEED_TO_REPRODUCE> and <END_OF_ISSUE_YOU_NEED_TO_REPRODUCE> tags.

---

### function Definitions

1.  **`execute_bash`**
    * **Purpose:** Executes shell commands.
    * **Format:**
        ```
        function:execute_bash 
        cmd:<your_command_here>
        ```
    * **Details:**
        * `cmd:` is followed by the specific command to be executed (e.g., `pwd && ls`).
        * This function can leverage a wide range of Unix/GNU tools.

2.  **`str_replace`**
    * **Purpose:** Replaces a specific string segment in an existing file.
    * **Format:**
        ```
        function:str_replace 
        file_path:<path_to_file>
        old_str:
        <exact_string_to_be_replaced>
        new_str:
        <replacement_string>
        ```
    * **Details:**
        * `file_path:` specifies the absolute path to the file that needs modification.
        * `old_str:` must be followed by a newline, and then the *exact* string segment to be replaced.
        * `new_str:` must be followed by a newline, and then the new string segment that will replace the `old_str`.
        * **Crucial:**
            * The `old_str` must uniquely match *exactly one* segment in the target file. If `old_str` matches zero or multiple locations, the operation will fail and return an error.
            * It is critical that `old_str` is an *exact literal match* of the code segment you intend to replace, including all indentation, spacing, newlines, and any special characters or placeholders. Any mismatch will result in a failure to find and replace the intended segment.

3.  **`new_file`**
    * **Purpose:** Creates a new file with specified content or overwrites an existing file.
    * **Format:**
        ```
        function:new_file 
        file_path:<path_to_new_or_existing_file>
        new_str:
        <content_to_be_written_to_the_file>
        ```
    * **Details:**
        * `file_path:` specifies the absolute path where the file will be created or overwritten.
        * `new_str:` must be followed by a newline, and then the entire content to be written into the file.
        * If the file specified by `file_path` already exists, its current content will be completely replaced by `new_str`.
        * If the file does not exist, it will be created with the content provided in `new_str`.
        

4.  **`test_report`**    
- **Purpose:** Returns a test report upon completion of assigned responsibilities, including test code, commands, results, and analysis.
- **Format:**
    ```
    function:test_report
    test_cmd: <commands_used_for_testing>
    test_file_path: <path_to_the_test_file>
    test_analysis: <analysis_of_the_test_results>
    reproduce_success: <True/False>
    ```
- **Details:**
    - `test_cmd:` must be followed by a newline, and then the commands or instructions used to execute the test. This could include compilation commands, execution commands, or specific tool invocations.
    - `test_file_path:` must be followed by a newline, and then the path to the test file.
    - `test_analysis:` must be followed by a newline, and then a brief analysis or interpretation of the test results, explaining what the outcome means, identifying any issues, or confirming success.
    - `reproduce_success:` the result of reproduce the issue (e.g., "True" if the issue is reproduced, "False" if it is not reproduced).

---

### function Usage Examples:

**`execute_bash` function Usage & Demo:**

* **Traverse project structure:**
    ```
    function:execute_bash 
    cmd:ls -la /workspace/tokio-rs__tokio__0.1
    ```
    ```
    function:execute_bash 
    cmd:ls -R /workspace/tokio-rs__tokio__0.1/sub_module
    ```

* **Search for relative code (using `grep`):**
    ```
    function:execute_bash 
    cmd:grep -n "fn try_reserve" /workspace/tokio-rs__tokio__0.1/sub_module/.../main.rs
    ```
    ```
    function:execute_bash 
    cmd:grep -A 10 "impl<T> Sender<T>" /workspace/tokio-rs__tokio__0.1/.../main.rs
    ```
    *(Self-correction: Ensure grep paths are valid or illustrative placeholders. The `...` implies deeper paths)*

* **Create a new Cargo project and modify its `Cargo.toml`:**
    ```
    function:execute_bash 
    cmd:cd /workspace && cargo new reproduce_proj && cd reproduce_proj && cargo add --path "../tokio-rs__tokio__0.1/submodule" --features "full"
    ```

**`str_replace` function Usage & Demo:**

```
function:str_replace 
file_path:/workspace/tokio-rs__tokio__0.1/src/main.rs
old_str:
    println!("Old greeting");
new_str:
    println!("New, improved greeting!");
```

**`new_file` function Usage & Demo:**

```
function:new_file 
file_path:/workspace/tokio-rs__tokio__0.1/src/new_module.rs
new_str:
// This is a new Rust module.

pub fn new_function() {{
    println!("Hello from the new module!");
}}

struct NewStruct {{
    id: i32,
}}
```

---

<START_OF_ISSUE_YOU_NEED_TO_REPRODUCE>


{issue_description}


<END_OF_ISSUE_YOU_NEED_TO_REPRODUCE>
"""
