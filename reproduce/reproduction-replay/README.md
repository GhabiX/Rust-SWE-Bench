# 🦀 RustBench Reproduction Replay

A comprehensive framework for replaying and analyzing Software Engineering agent trajectories on the **RustBench** dataset. This tool supports multiple AI agents including **OpenHands**, **SWE-agent**, and **RustAgent**, enabling systematic reproduction analysis and performance comparison by injecting test commands into agent trajectories and tracking output changes over time.

## ✨ Features

- **RustBench Integration**: Specialized support for RustBench dataset reproduction analysis
- **Multi-Agent Support**: Compatible with OpenHands, SWE-agent, and RustAgent trajectories
- **Reproduction Replay**: Execute agent trajectories step-by-step with reproduction test command injection
- **Output Analysis**: Track and analyze reproduction test results and output changes
- **Docker Integration**: Containerized execution environment for reproducible results
- **Performance Comparison**: Compare agent reproduction capabilities across different models and instances
- **Comprehensive Logging**: Detailed logging and result persistence for reproduction analysis

## 🏗️ Architecture

The RustBench Reproduction Replay system works by:

1. **Trajectory Extraction**: Parse agent trajectories from RustBench dataset to extract LLM call sequences
2. **Reproduction Command Injection**: Insert reproduction test commands after each agent action
3. **Replay Execution**: Execute modified trajectories in controlled Docker environments
4. **Reproduction Tracking**: Monitor and record reproduction test execution results
5. **Change Detection**: Only record outputs when reproduction results differ from previous rounds
6. **Analysis Generation**: Generate structured JSON reports for reproduction performance analysis

## 🛠️ Installation

### Prerequisites

- **Python 3.12+**
- **Docker** (installed and running)
- **Conda** (recommended for environment management)

### Setup Instructions

1. **Create Conda Environment**
   ```bash
   conda create -n replay python=3.12
   conda activate replay
   ```

2. **Install Dependencies**
   ```bash
   # Install OpenHands dependencies
   cd replay/dependencies/OpenHands && pip install . && cd -
   
   # Install SWE-agent dependencies
   cd replay/dependencies/SWE-agent && pip install -r requirements.txt && cd -
   
   # Install main dependencies
   pip install -r requirements.txt
   ```

## 🚀 Usage

### Command Line Interface

The main script provides a CLI interface using Typer:

```bash
python run.py --instance-id <ID> \
              --instance-method <METHOD> \
              --instance-model <MODEL> \
              --instance-traj-path <PATH> \
              --save-dir <OUTPUT_DIR> \
              --command <TEST_COMMAND>
```

### Parameters

- `--instance-id`: Unique identifier for the RustBench instance
- `--instance-method`: Agent method (`OpenHands`, `SWEAGENT`, or `RUSTAGENT`)
- `--instance-model`: Model name used by the agent
- `--instance-traj-path`: Path to the RustBench trajectory file
- `--save-dir`: Directory to save reproduction analysis results
- `--command`: Reproduction test command to execute after each trajectory step

### Example Usage

```bash
# Replay OpenHands trajectory on RustBench instance
python run.py --instance-id "rustbench-001" \
              --instance-method "OpenHands" \
              --instance-model "gpt-4" \
              --instance-traj-path "/path/to/rustbench_trajectory.json" \
              --save-dir "./reproduction_results" \
              --command "cargo test"

# Replay SWE-agent trajectory on RustBench with custom reproduction test
python run.py --instance-id "rustbench-002" \
              --instance-method "SWEAGENT" \
              --instance-model "claude-3" \
              --instance-traj-path "/path/to/rustbench_swe_traj.json" \
              --save-dir "./reproduction_results" \
              --command "cargo check && cargo test --quiet"
```

## 📊 Output Structure

Results are organized in the following structure:

```
save_dir/
├── {method}/
│   ├── {model}/
│   │   ├── {instance_id}/
│   │   │   ├── {instance_id}.json           # Final analysis results
│   │   │   ├── {instance_id}__*_output.traj # Raw trajectory output
│   │   │   └── {instance_id}__*_result.traj # Processed results
```

### Result Format

Each reproduction analysis produces a JSON file with the following structure:

```json
[
  {
    "round": "01",
    "command": "cargo test",
    "exit_code": 0,
    "output": "test result: ok. 15 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out"
  },
  {
    "round": "02",
    "command": "cargo test", 
    "exit_code": 1,
    "output": "test result: FAILED. 12 passed; 3 failed; 0 ignored; 0 measured; 0 filtered out"
  }
]
```

## 🔧 Configuration

### Environment Variables

The system supports proxy configuration through environment variables:

```bash
export http_proxy="http://proxy.example.com:8080"
export https_proxy="https://proxy.example.com:8080"
```

### Global Environment Setup

The following commands are automatically executed in all containers for RustBench compatibility:

- Rust warning suppression: `export RUSTFLAGS="-Awarnings"`
- Proxy configuration (if available)
- Cargo quiet mode: `alias cargo="cargo --quiet"`
- Git configuration for reproducible commits

## 🔍 Agent-Specific Features

### OpenHands Agent
- Direct function call execution from RustBench trajectories
- Docker container integration with Rust environment
- Real-time reproduction command execution and output capture

### SWE-agent
- Command extraction from RustBench trajectory requests
- Working directory recovery between reproduction test steps
- Git configuration and alias setup for Rust projects
- Internal command filtering (skip non-executable commands)

### RustAgent
- Uses OpenHands replay mechanism optimized for Rust
- Advanced Cargo warning removal and filtering
- RustBench-specific environment configuration
- Specialized handling of Rust compilation and test outputs

## 🧪 Advanced Usage

### Batch Processing

You can process multiple RustBench trajectories using shell scripts:

```bash
#!/bin/bash
for trajectory in rustbench_trajectories/*.json; do
    python run.py --instance-id "$(basename $trajectory .json)" \
                  --instance-method "OpenHands" \
                  --instance-model "gpt-4" \
                  --instance-traj-path "$trajectory" \
                  --save-dir "./rustbench_reproduction_results" \
                  --command "cargo test --quiet"
done
```

### Custom Reproduction Test Commands

The framework supports various Rust-specific reproduction test commands:

```bash
# Standard Rust testing
--command "cargo test --quiet"

# Compilation check + testing
--command "cargo check && cargo test"

# Specific test module
--command "cargo test integration_tests"

# Custom validation script
--command "bash validate_rustbench_solution.sh"

# Clippy linting + testing
--command "cargo clippy --quiet && cargo test"
```

## 🐛 Troubleshooting

### Common Issues

1. **Docker Permission Errors**
   ```bash
   sudo usermod -aG docker $USER
   # Then restart your session
   ```

2. **Missing Dependencies**
   ```bash
   pip install --upgrade -r requirements.txt
   ```

3. **Trajectory File Format Issues**
   - Ensure RustBench trajectory files are valid JSON
   - Check that required fields are present in trajectory data
   - Verify compatibility with your agent's trajectory format

4. **Container Timeout Issues**
   - Default timeout is 3600 seconds (1 hour)
   - Rust compilation may require longer timeouts for large projects
   - Modify timeout in source code if needed for complex RustBench instances

### Logging and Debugging

- Check trajectory output files (`*_output.traj`) for detailed execution logs
- Review result files (`*_result.traj`) for processed trajectory data
- Enable verbose logging by modifying the logger configuration
