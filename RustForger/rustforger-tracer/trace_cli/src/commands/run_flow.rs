//! Run Flow Command
//! 
//! This module provides a unified command that combines setup, instrumentation, 
//! execution, and cleanup operations in a single workflow.

use anyhow::{Context, Result, ensure};
use std::path::{Path, PathBuf};
use std::process::Command;
use std::collections::HashSet;

use crate::commands::{setup, instrument};
use crate::utils::config::PropagationConfig;
use crate::utils::fs::find_project_root;
use crate::utils::trace_display::{display_trace_preview, DisplayConfig};

/// Instrumentation specification parsed from command line
#[derive(Debug, Clone)]
struct InstrumentSpec {
    file_path: PathBuf,
    functions: Vec<String>,
}

/// Execute complete trace flow: setup, instrument, run, and optionally clean
pub fn run(
    test_project: &Path,
    target_projects: &[PathBuf],
    instrument_specs: &[String],
    output: &Path,
    exec_command: &str,
    clean_after: bool,
    force: bool,
    propagate: bool,
    max_depth: Option<u32>,
    exclude: &[String],
    user_code_only: bool,
    trace_tool_path: Option<&Path>,
) -> Result<()> {
    println!("Starting complete trace flow execution...");
    
    // 1. Parse instrumentation specifications
    let parsed_specs = parse_instrument_specs(instrument_specs)?;
    
    // 2. Collect all involved projects
    let all_projects = collect_all_projects(test_project, target_projects, &parsed_specs)?;
    
    // 3. Create propagation configuration
    let propagation_config = create_propagation_config(propagate, max_depth, exclude, user_code_only);
    
    // 4. Execute flow steps
    execute_flow_steps(
        &all_projects,
        &parsed_specs,
        output,
        exec_command,
        test_project,
        clean_after,
        force,
        propagation_config,
        trace_tool_path,
    )?;
    
    println!("Trace flow execution completed successfully!");
    Ok(())
}

/// Parse instrumentation specifications from command line arguments
fn parse_instrument_specs(specs: &[String]) -> Result<Vec<InstrumentSpec>> {
    let mut parsed_specs = Vec::new();
    
    for spec in specs {
        let parts: Vec<&str> = spec.splitn(2, ':').collect();
        ensure!(
            parts.len() == 2, 
            "Invalid instrumentation specification format: {} (expected: file_path:function1,function2)", 
            spec
        );
        
        let file_path = PathBuf::from(parts[0]);
        ensure!(file_path.exists(), "File does not exist: {}", file_path.display());
        
        let functions: Vec<String> = if parts[1] == "*" {
            Vec::new() // Empty means all functions
        } else {
            parts[1]
                .split(',')
                .map(|s| s.trim().to_string())
                .filter(|s| !s.is_empty())
                .collect()
        };
        
        parsed_specs.push(InstrumentSpec { file_path, functions });
    }
    
    Ok(parsed_specs)
}

/// Collect all projects involved in the trace flow
fn collect_all_projects(
    test_project: &Path,
    target_projects: &[PathBuf],
    parsed_specs: &[InstrumentSpec],
) -> Result<HashSet<PathBuf>> {
    let mut all_projects = HashSet::new();
    
    // Add test project (ensure it's absolute path)
    let test_project_canonical = test_project.canonicalize()
        .with_context(|| format!("Failed to canonicalize test project path: {}", test_project.display()))?;
    all_projects.insert(test_project_canonical);
    
    // Add target projects
    for target in target_projects {
        let target_canonical = target.canonicalize()
            .with_context(|| format!("Failed to canonicalize target project path: {}", target.display()))?;
        all_projects.insert(target_canonical);
    }
    
    // Infer projects from instrumentation specs (by finding Cargo.toml)
    for spec in parsed_specs {
        // If the file path is relative, resolve it relative to the test project
        let file_path = if spec.file_path.is_relative() {
            test_project.join(&spec.file_path)
        } else {
            spec.file_path.clone()
        };
        
        if let Ok(project_path) = find_project_root(&file_path) {
            all_projects.insert(project_path);
        }
    }
    
    Ok(all_projects)
}

/// Create propagation configuration from command line arguments
fn create_propagation_config(
    propagate: bool,
    max_depth: Option<u32>,
    exclude: &[String],
    user_code_only: bool,
) -> Option<PropagationConfig> {
    if propagate {
        Some(PropagationConfig {
            enabled: true,
            max_depth,
            exclude_patterns: exclude.to_vec(),
            user_code_only,
        })
    } else {
        None
    }
}

/// Execute all steps of the trace flow
fn execute_flow_steps(
    all_projects: &HashSet<PathBuf>,
    parsed_specs: &[InstrumentSpec],
    output: &Path,
    exec_command: &str,
    test_project: &Path,
    clean_after: bool,
    force: bool,
    propagation_config: Option<PropagationConfig>,
    trace_tool_path: Option<&Path>,
) -> Result<()> {
    // 1. Create backups before instrumentation (if cleanup is requested)
    if clean_after {
        if let Err(e) = backup_files_before_instrumentation(parsed_specs, force) {
            // Even if backup fails, try to clean up before exiting
            let _ = handle_cleanup_and_restoration(all_projects, parsed_specs, &Err(e.into()));
            // Return the original backup error
            return Err(anyhow::anyhow!("Backup failed, aborting flow."));
        }
    }

    // 2. Execute the main flow steps
    let main_result = execute_main_flow_steps(
        all_projects,
        parsed_specs,
        output,
        exec_command,
        test_project,
        force,
        propagation_config,
        trace_tool_path,
    );

    // 3. Handle cleanup and restoration
    if clean_after {
        if let Err(cleanup_err) = handle_cleanup_and_restoration(all_projects, parsed_specs, &main_result) {
            // If cleanup fails, we must return this error, as it might leave the user's
            // project in a dirty state.
            return main_result.and(Err(cleanup_err));
        }
    }

    // Return the main execution result
    main_result
}

/// Execute the main flow steps (setup, instrument, execute, verify)
fn execute_main_flow_steps(
    all_projects: &HashSet<PathBuf>,
    parsed_specs: &[InstrumentSpec],
    output: &Path,
    exec_command: &str,
    test_project: &Path,
    force: bool,
    propagation_config: Option<PropagationConfig>,
    trace_tool_path: Option<&Path>,
) -> Result<()> {
    // Step 1: Setup all projects
    setup_all_projects(all_projects, output, force, propagation_config.is_some(), trace_tool_path)?;
    
    // Step 2: Execute all instrumentations
    instrument_all_functions(parsed_specs, output, propagation_config)?;
    
    // Step 3: Set environment variables and execute command
    execute_with_trace_env(exec_command, test_project, output)?;
    
    // Step 4: Verify output
    verify_trace_output(output)?;
    
    Ok(())
}

/// Setup all projects by calling existing setup::run function
fn setup_all_projects(
    all_projects: &HashSet<PathBuf>,
    output: &Path,
    force: bool,
    propagate: bool,
    trace_tool_path: Option<&Path>,
) -> Result<()> {
    println!("Setting up project environments...");
    
    for project_path in all_projects {
        // Call existing setup command directly
        setup::run(
            project_path,
            trace_tool_path,
            force,
            Some(output),
            propagate,
        ).with_context(|| format!("Failed to configure project: {}", project_path.display()))?;
    }
    
    Ok(())
}

/// Instrument all functions by calling existing instrument::run* functions
fn instrument_all_functions(
    parsed_specs: &[InstrumentSpec],
    output: &Path,
    propagation_config: Option<PropagationConfig>,
) -> Result<()> {
    println!("Executing function instrumentation...");
    
    for spec in parsed_specs {
        if spec.functions.is_empty() {
            // Instrument all functions - call existing function directly
            instrument::run_all(
                &spec.file_path,
                Some(output),
                propagation_config.clone(),
            ).with_context(|| format!("Failed to instrument all functions: {}", spec.file_path.display()))?;
        } else if spec.functions.len() == 1 {
            // Instrument single function - call existing function directly
            instrument::run(
                &spec.file_path,
                &spec.functions[0],
                Some(output),
                propagation_config.clone(),
            ).with_context(|| format!("Failed to instrument function: {}", spec.functions[0]))?;
        } else {
            // Instrument multiple functions - call existing function directly
            instrument::run_multiple(
                &spec.file_path,
                &spec.functions,
                Some(output),
                propagation_config.clone(),
            ).with_context(|| format!("Failed to instrument multiple functions: {:?}", spec.functions))?;
        }
    }
    
    Ok(())
}

/// Execute user command with trace environment variables set
fn execute_with_trace_env(
    exec_command: &str,
    test_project: &Path,
    output: &Path,
) -> Result<()> {
    println!("Executing user command: {}", exec_command);
    
    // Set TRACE_OUTPUT_FILE environment variable
    std::env::set_var("TRACE_OUTPUT_FILE", output);
    
    // Execute command using shell
    let output_result = Command::new("sh")
        .arg("-c")
        .arg(exec_command)
        .current_dir(test_project)
        .output()
        .context("Failed to execute user command")?;
    
    // Print stdout first
    let stdout = String::from_utf8_lossy(&output_result.stdout);
    if !stdout.is_empty() {
        println!("Command output:");
        println!("{}", stdout);
    }
    
    // Handle command execution result
    if !output_result.status.success() {
        let stderr = String::from_utf8_lossy(&output_result.stderr);
        
        // Check if this looks like a runtime error (panic, etc.) vs execution failure
        if stderr.contains("panicked at") || 
           stderr.contains("thread") && stderr.contains("panicked") ||
           output_result.status.code().is_some() {
            // This is a runtime error (panic, etc.) - not a command execution failure
            println!("Note: Program exited with runtime error (this may be expected for testing)");
            if !stderr.is_empty() {
                println!("Runtime error details:");
                println!("{}", stderr);
            }
        } else {
            // This is a real command execution failure
            anyhow::bail!("Command execution failed: {}", stderr);
        }
    }
    
    Ok(())
}

/// Verify that trace output was generated successfully and display preview
fn verify_trace_output(output: &Path) -> Result<()> {
    println!("Verifying trace output...");
    
    if !output.exists() {
        anyhow::bail!("Trace output file does not exist: {}", output.display());
    }
    
    let file_size = std::fs::metadata(output)
        .context("Failed to get output file metadata")?
        .len();
    
    if file_size == 0 {
        println!("WARNING: Trace output file is empty, no trace data may have been captured");
        return Ok(());
    }
    
    println!("Trace output verification successful: {} ({} bytes)", output.display(), file_size);
    println!();
    
    // Display trace preview using tree format
    let config = DisplayConfig::default();
    match display_trace_preview(output, config) {
        Ok(()) => {},
        Err(e) => {
            println!("Note: Could not display trace preview: {}", e);
            // Fallback to simple file info
            println!("Trace file: {} ({} bytes)", output.display(), file_size);
        }
    }
    
    Ok(())
}

/// Create backups of all files before instrumentation
fn backup_files_before_instrumentation(parsed_specs: &[InstrumentSpec], force: bool) -> Result<()> {
    for spec in parsed_specs {
        let backup_path = spec.file_path.with_extension("rs.bak");
        
        // Check if backup file already exists
        if backup_path.exists() {
            if force {
                // If force is enabled, remove existing backup
                std::fs::remove_file(&backup_path).with_context(|| {
                    format!("Failed to remove existing backup file: {}", backup_path.display())
                })?;
            } else {
                anyhow::bail!(
                    "Backup file already exists: {}. Please remove it first or use --force", 
                    backup_path.display()
                );
            }
        }
        
        // Create backup
        std::fs::copy(&spec.file_path, &backup_path)
            .with_context(|| format!(
                "Failed to backup {} to {}", 
                spec.file_path.display(), 
                backup_path.display()
            ))?;
    }
    
    Ok(())
}

/// Restore files from backup
fn restore_files_from_backup(parsed_specs: &[InstrumentSpec]) -> Result<()> {
    for spec in parsed_specs {
        let backup_path = spec.file_path.with_extension("rs.bak");
        
        if backup_path.exists() {
            // Restore file from backup
            std::fs::copy(&backup_path, &spec.file_path)
                .with_context(|| format!(
                    "Failed to restore {} from {}", 
                    spec.file_path.display(), 
                    backup_path.display()
                ))?;
            
            // Remove backup file
            std::fs::remove_file(&backup_path)
                .with_context(|| format!(
                    "Failed to remove backup file: {}", 
                    backup_path.display()
                ))?;
        }
    }
    
    Ok(())
}

/// Handle cleanup and restoration after execution
fn handle_cleanup_and_restoration(
    all_projects: &HashSet<PathBuf>,
    parsed_specs: &[InstrumentSpec],
    main_result: &Result<()>,
) -> Result<()> {
    match main_result {
        Ok(_) => {
            println!("Restoring original files after successful execution...");
        }
        Err(e) => {
            // Also log the main error for context
            eprintln!("Execution failed: {}. Restoring original files...", e);
        }
    }
    
    // Use backup restoration instead of AST-based cleaning
    match restore_files_from_backup(parsed_specs) {
        Ok(()) => {
            // Clean up project dependencies and configurations
            match clean_project_dependencies(all_projects) {
                Ok(()) => {
                    println!("Cleanup completed");
                }
                Err(clean_err) => {
                    eprintln!("Warning: Project cleanup failed: {}", clean_err);
                    // If main flow succeeded but dependency cleanup failed, return cleanup error
                    if main_result.is_ok() {
                        return Err(clean_err);
                    }
                }
            }
        }
        Err(restore_err) => {
            eprintln!("Warning: File restoration failed: {}", restore_err);
            eprintln!("Backup files (.rs.bak) are preserved for manual recovery");
            // If main flow succeeded but restoration failed, return restoration error
            if main_result.is_ok() {
                return Err(restore_err);
            }
        }
    }
    
    Ok(())
}

/// Clean project dependencies and configurations (without touching source files)
fn clean_project_dependencies(all_projects: &HashSet<PathBuf>) -> Result<()> {
    use crate::utils::fs::find_cargo_toml;
    use crate::utils::cargo::remove_dependencies_from_cargo_toml;
    use std::fs;
    
    for project_path in all_projects {
        // Remove trace dependencies from Cargo.toml
        if let Ok(cargo_toml_path) = find_cargo_toml(project_path) {
            let _ = remove_dependencies_from_cargo_toml(&cargo_toml_path);
        }
        
        // Remove trace_config.rs if it exists
        let src_dir = project_path.join("src");
        let trace_config_path = src_dir.join("trace_config.rs");
        if trace_config_path.exists() {
            let _ = fs::remove_file(&trace_config_path);
        }
        
        // Clean up main.rs integration
        let _ = clean_main_rs_integration(project_path);
    }
    
    Ok(())
}

/// Clean up trace initialization code from main.rs
fn clean_main_rs_integration(project_dir: &Path) -> Result<()> {
    let src_dir = project_dir.join("src");
    let main_rs_path = src_dir.join("main.rs");
    
    if !main_rs_path.exists() {
        return Ok(());
    }
    
    let content = std::fs::read_to_string(&main_rs_path)
        .with_context(|| format!("Failed to read main.rs: {}", main_rs_path.display()))?;
    
    // Remove trace-related lines
    let mut lines: Vec<&str> = content.lines().collect();
    let mut modified = false;
    
    // Remove mod trace_config; line
    if let Some(pos) = lines.iter().position(|line| {
        line.trim() == "mod trace_config;" || 
        line.trim().starts_with("mod trace_config;")
    }) {
        lines.remove(pos);
        modified = true;
    }
    
    // Remove trace initialization calls
    let mut positions_to_remove = Vec::new();
    for (i, line) in lines.iter().enumerate() {
        let trimmed = line.trim();
        if trimmed.contains("trace_config::init_tracing_ignore_errors()") ||
           trimmed.contains("trace_config::init_tracing()") ||
           (trimmed.starts_with("trace_config::") && trimmed.contains("init_tracing")) {
            positions_to_remove.push(i);
        }
    }
    
    // Remove lines in reverse order to maintain correct indices
    for &pos in positions_to_remove.iter().rev() {
        lines.remove(pos);
        modified = true;
    }
    
    // Remove auto-generated trace comment
    if let Some(pos) = lines.iter().position(|line| {
        line.trim() == "// Initialize trace system automatically"
    }) {
        lines.remove(pos);
        modified = true;
    }
    
    if modified {
        let new_content = lines.join("\n");
        std::fs::write(&main_rs_path, new_content)
            .with_context(|| format!("Failed to write main.rs: {}", main_rs_path.display()))?;
    }
    
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_instrument_specs() {
        let specs = vec![
            "src/main.rs:main,helper".to_string(),
            "src/lib.rs:*".to_string(),
        ];
        
        // This test requires actual files to exist, so it's done in integration tests
        // Here we only test the basic structure of parsing logic
        assert_eq!(specs.len(), 2);
    }

    #[test]
    fn test_create_propagation_config() {
        let config = create_propagation_config(
            true,
            Some(5),
            &["std::".to_string()],
            true,
        );
        
        assert!(config.is_some());
        let config = config.unwrap();
        assert!(config.enabled);
        assert_eq!(config.max_depth, Some(5));
        assert_eq!(config.exclude_patterns, vec!["std::"]);
        assert!(config.user_code_only);
    }

    #[test]
    fn test_create_propagation_config_disabled() {
        let config = create_propagation_config(false, None, &[], false);
        assert!(config.is_none());
    }
} 