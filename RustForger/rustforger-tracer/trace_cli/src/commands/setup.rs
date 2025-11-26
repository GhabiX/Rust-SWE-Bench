use anyhow::{Context, Result, ensure};
use std::path::{Path, PathBuf};
use std::fs;

use crate::utils::fs::find_cargo_toml;
use crate::utils::cargo::{DependencyType, update_cargo_toml_with_deps, display_dependency_summary};
use crate::utils::config::{PropagationConfig, create_trace_config_file};
use crate::utils::main_rs::integrate_trace_initialization;

/// Setup tracing dependencies for a project
pub fn run(
    project_dir: &Path, 
    trace_tool_path: Option<&Path>, 
    force: bool, 
    trace_output: Option<&Path>,
    propagate: bool
) -> Result<()> {
    let cargo_toml_path = find_cargo_toml(project_dir)?;
    
    let trace_tool_root = resolve_trace_tool_path(project_dir, trace_tool_path)?;
    validate_trace_tool_path(&trace_tool_root)?;
    let relative_paths = calculate_relative_paths(&cargo_toml_path, &trace_tool_root)?;
    
    update_cargo_toml(&cargo_toml_path, &relative_paths, force)?;
    
    let project_root = cargo_toml_path.parent().context("Failed to get project directory")?;
    let propagation_config = if propagate { 
        Some(PropagationConfig::enabled()) 
    } else { 
        None 
    };
    create_trace_config_file(project_root, trace_output, propagation_config.as_ref())?;

    // Attempt to automatically integrate trace initialization into main.rs
    match integrate_trace_initialization(project_root) {
        Ok(true) => {
            // Successfully integrated - no output needed
        },
        Ok(false) => {
            // Already exists or no main.rs - no output needed
        },
        Err(e) => {
            println!("Could not automatically modify main.rs: {}", e);
            println!("Please manually add the following to your main.rs:");
            println!("   1. Add `mod trace_config;` after your use statements");
            println!("   2. Add `trace_config::init_tracing_ignore_errors();` at the beginning of main()");
        }
    }

    Ok(())
}

/// Resolve trace tool path (auto-detect if not provided)
fn resolve_trace_tool_path(project_dir: &Path, trace_tool_path: Option<&Path>) -> Result<PathBuf> {
    if let Some(path) = trace_tool_path {
        // If user specified path, use absolute path or canonicalized path
        if path.is_absolute() {
            return Ok(path.to_path_buf());
        } else {
            // Resolve path relative to current working directory
            return std::env::current_dir()
                .context("Unable to get current working directory")?
                .join(path)
                .canonicalize()
                .context("Unable to canonicalize specified trace tool path");
        }
    }
    
    auto_detect_trace_tool_path(project_dir)
}

/// Auto-detect trace tool path
fn auto_detect_trace_tool_path(project_dir: &Path) -> Result<PathBuf> {
    // First try searching from current executable location
    if let Ok(current_exe) = std::env::current_exe() {
        if let Some(search_path) = current_exe.parent() {
            if let Some(found_path) = search_upward_for_trace_tool(search_path) {
                return Ok(found_path);
            }
        }
    }

    // Try searching from current working directory
    if let Ok(cwd) = std::env::current_dir() {
        if let Some(found_path) = search_upward_for_trace_tool(&cwd) {
            return Ok(found_path);
        }
    }

    // Try searching upward from project directory
    if let Some(found_path) = search_upward_for_trace_tool(project_dir) {
        return Ok(found_path);
    }

    // Try common relative locations and possible project names
    let potential_names = ["rust_tracer", "trace_tool", "tracing_tool", "trace"];
    let potential_patterns = [
        "../{}", "../../{}", "../../../{}", "./{}",
        "../*/", "../../*/", "../../../*/"
    ];
    
    for name in &potential_names {
        for pattern in &potential_patterns {
            let search_pattern = if pattern.ends_with("*/") {
                // For wildcard patterns, search for directories containing necessary components
                let parent_pattern = pattern.trim_end_matches("*/");
                let parent_path = project_dir.join(parent_pattern);
                if let Ok(entries) = fs::read_dir(&parent_path) {
                    for entry in entries.flatten() {
                        if entry.file_type().map(|ft| ft.is_dir()).unwrap_or(false) {
                            let candidate = entry.path();
                            if is_trace_tool_root(&candidate) {
                                return candidate.canonicalize()
                                    .context("Unable to canonicalize candidate path");
                            }
                        }
                    }
                }
                continue;
            } else {
                project_dir.join(pattern.replace("{}", name))
            };
            
            if is_trace_tool_root(&search_pattern) {
                return search_pattern.canonicalize()
                    .context("Unable to canonicalize candidate path");
            }
        }
    }

    anyhow::bail!("Unable to auto-detect trace tool path. Please specify manually using --trace-tool-path.")
}

/// Search upward for trace tool root
fn search_upward_for_trace_tool(mut search_path: &Path) -> Option<PathBuf> {
    for _ in 0..15 { // Increase search depth
        if is_trace_tool_root(search_path) {
            return Some(search_path.to_path_buf());
        }
        
        search_path = search_path.parent()?;
    }
    None
}

/// Check if path is trace tool root directory
fn is_trace_tool_root(path: &Path) -> bool {
    let required_components = ["trace_runtime", "trace_macro", "trace_common"];
    let has_all_components = required_components
        .iter()
        .all(|component| path.join(component).is_dir());
    
    // Additional check: ensure workspace Cargo.toml exists
    let has_workspace_cargo = path.join("Cargo.toml").exists();
    
    has_all_components && has_workspace_cargo
}

/// Validate trace tool path structure
fn validate_trace_tool_path(trace_tool_path: &Path) -> Result<()> {
    ensure!(trace_tool_path.exists(), "Trace tool path does not exist: {}", trace_tool_path.display());

    let required_components = ["trace_runtime", "trace_macro", "trace_common"];
    for component in &required_components {
        let component_path = trace_tool_path.join(component);
        ensure!(component_path.is_dir(), 
               "Missing required component '{}' in trace tool path: {}", 
               component, trace_tool_path.display());
    }

    // Validate workspace Cargo.toml exists
    let workspace_cargo = trace_tool_path.join("Cargo.toml");
    ensure!(workspace_cargo.exists(), 
           "Missing workspace Cargo.toml in trace tool path: {}", 
           trace_tool_path.display());

    Ok(())
}

/// Calculate relative paths for dependencies
fn calculate_relative_paths(cargo_toml_path: &Path, trace_tool_root: &Path) -> Result<RelativePaths> {
    let _project_dir = cargo_toml_path.parent()
        .context("Unable to get project directory")?;

    let trace_tool_canonical = trace_tool_root.canonicalize()
        .context("Unable to canonicalize trace tool path")?;

    // Always use absolute paths to avoid dependency resolution issues
    // This ensures reliable path resolution across different project hierarchies
    let absolute_base = trace_tool_canonical.clone();

    let paths = RelativePaths {
        trace_runtime: absolute_base.join("trace_runtime"),
        trace_common: absolute_base.join("trace_common"),
    };

    Ok(paths)
}

#[derive(Debug)]
struct RelativePaths {
    trace_runtime: PathBuf,
    trace_common: PathBuf,
}

/// Update Cargo.toml with trace dependencies
fn update_cargo_toml(cargo_toml_path: &Path, paths: &RelativePaths, force: bool) -> Result<()> {
    // Define dependencies to add
    let dependencies = [
        ("trace_runtime", DependencyType::Path(&paths.trace_runtime)),
        ("trace_common", DependencyType::Path(&paths.trace_common)),
        ("serde_json", DependencyType::Version("1.0")),
    ];

    let stats = update_cargo_toml_with_deps(cargo_toml_path, &dependencies, force)?;
    display_dependency_summary(&stats);
    Ok(())
} 