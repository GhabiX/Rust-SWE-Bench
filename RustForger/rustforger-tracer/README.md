# trace_cli

A robust command-line tool for automatic function tracing in Rust projects with intelligent error handling and recovery capabilities.

## Key Features

- **Complete Workflow**: `run-flow` command executes setup, instrumentation, execution, and cleanup in a single robust pipeline
- **Intelligent Function Discovery**: Provides smart function name suggestions when target functions are not found
- **Panic-Safe Tracing**: Preserves trace data even when instrumented code panics during execution
- **Automatic Recovery**: Built-in backup and restoration system ensures project integrity
- **Brief Trace Reports**: Generates concise, tree-structured trace summaries for quick analysis

## Installation

```bash
cargo build --release --bin trace_cli
```

## Core Command: run-flow

The `run-flow` command provides a complete tracing workflow with automatic cleanup and error recovery:

```bash
trace_cli run-flow \
    --test-project ./my_project \
    --instrument "src/main.rs:main,helper" \
    --output trace_output.json \
    --exec "cargo run -- --input data.txt" \
    --clean
```

**Parameters:**
- `--test-project` - Project directory where the executable runs
- `--target-project` - Additional projects to instrument (optional)
- `--instrument` - Instrumentation specs: `"file_path:function1,function2"` or `"file_path:*"` for all functions
- `--output` - Trace output file path
- `--exec` - Command to execute after instrumentation
- `--clean` - Automatically restore original files after execution
- `--propagate` - Enable deep call tracing
- `--force` - Overwrite existing configurations

**Workflow Steps:**
1. **Setup**: Configures dependencies and trace infrastructure
2. **Instrument**: Adds tracing annotations to specified functions
3. **Execute**: Runs the command with trace environment configured
4. **Verify**: Validates trace output and displays brief report
5. **Cleanup**: Restores original files (if `--clean` specified)

## Robustness Features

### Panic-Safe Execution

The tool distinguishes between execution failures and runtime panics:

```bash
# Even if your code panics, trace data is preserved
trace_cli run-flow --test-project . --instrument "src/lib.rs:*" --exec "cargo test" --output traces.json
```

Output when panic occurs:
```
Note: Program exited with runtime error (this may be expected for testing)
Runtime error details:
thread 'main' panicked at 'assertion failed', src/lib.rs:42:5
Trace output verification successful: traces.json (1337 bytes)
```

### Intelligent Function Discovery

When a function name is not found, the tool provides smart suggestions using similarity algorithms:

```bash
trace_cli instrument -f src/main.rs -n "mian"  # typo in "main"
```

Output:
```
Error: Function 'mian' not found in file

Available functions in this file:

Standalone functions:
  - main
  - setup_logger
  - parse_args

Methods in Config:
  - Config::new
  - Config::load
  - Config::validate

Use the exact function name from above with --function parameter.
For methods, use the full qualified name like 'TypeName::method_name'.
```

### Automatic Backup and Recovery

The tool automatically creates backups when using `--clean`:

```bash
# Creates .rs.bak files before modification
trace_cli run-flow --clean --test-project . --instrument "src/lib.rs:process" --exec "cargo test"
```

If any step fails:
```
Warning: File restoration failed: Permission denied
Backup files (.rs.bak) are preserved for manual recovery
```

### Brief Trace Reports

Automatically displays concise trace summaries:

```
Trace Preview (3 entries, showing first 3)
main (src/main.rs:10) [14:32:15]
  in:  {"args": ["--input", "data.txt"]}
  out: Ok(())
  ├─ parse_config (src/config.rs:25)
  │  ├─ read_file (src/io.rs:15)
  │  └─ validate_schema (src/config.rs:45)
  └─ process_data (src/processor.rs:30)
     ├─ load_dataset (src/data.rs:20)
     └─ compute_metrics (src/compute.rs:18)
        └─ ... (max depth reached)
```

## Command Reference

### Individual Commands

```bash
# Setup project dependencies
trace_cli setup --propagate

# Instrument specific functions
trace_cli instrument -f src/main.rs -n main --propagate

# Instrument all functions in a file
trace_cli instrument -f src/lib.rs --all

# List traced functions
trace_cli list-traced --verbose

# Remove tracing annotations
trace_cli revert src/

# Clean all tracing artifacts
trace_cli clean
```

### Propagation Tracing

Enable deep call tracing for comprehensive analysis:

```bash
trace_cli run-flow \
    --test-project . \
    --instrument "src/main.rs:*" \
    --propagate \
    --max-depth 5 \
    --exclude "std::" "tokio::" \
    --user-code-only \
    --exec "cargo run" \
    --output deep_trace.json
```

## Error Handling

The tool provides graceful error handling:

- **Missing Functions**: Smart suggestions with similarity matching
- **Build Failures**: Detailed error context with recovery suggestions  
- **Permission Issues**: Preserves backups for manual recovery
- **Panic Recovery**: Continues trace collection even after runtime panics
- **Dependency Conflicts**: Automatic dependency resolution with conflict reporting

## Output Format

Trace files contain structured JSON with call trees:

```json
{
  "timestamp_utc": "2024-01-01T10:00:00Z",
  "thread_id": "ThreadId(1)",
  "root_node": {
    "name": "main",
    "file": "src/main.rs",
    "line": 10,
    "children": [...]
  },
  "inputs": {...},
  "output": {...}
}
```

## Examples

**Complete testing workflow:**
```bash
trace_cli run-flow \
    --test-project ./my_app \
    --instrument "src/main.rs:main" "src/lib.rs:*" \
    --propagate --max-depth 3 \
    --exec "cargo test --release" \
    --output test_traces.json \
    --clean
```

**Debug specific function:**
```bash
trace_cli run-flow \
    --test-project . \
    --instrument "src/buggy.rs:problematic_function" \
    --propagate \
    --exec "cargo run -- --debug" \
    --output debug_trace.json
```

**Performance analysis:**
```bash
trace_cli run-flow \
    --test-project ./benchmark \
    --instrument "src/compute.rs:*" \
    --propagate --user-code-only \
    --exec "cargo run --release -- --benchmark" \
    --output perf_trace.json \
    --clean
```

