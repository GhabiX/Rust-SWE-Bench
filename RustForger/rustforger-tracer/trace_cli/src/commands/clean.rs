use anyhow::{Context, Result};
use std::path::Path;
use std::fs;

use crate::commands::revert;
use crate::utils::fs::find_cargo_toml;
use crate::utils::cargo::{remove_dependencies_from_cargo_toml, display_removal_summary};

/// Clean all tracing instrumentation and remove dependencies
pub fn run(project_dir: &Path) -> Result<()> {
    // Step 1: Revert all tracing instrumentation in the project
    revert::run(project_dir)
        .with_context(|| format!("Failed to revert tracing instrumentation: {}", project_dir.display()))?;
    
    // Step 2: Remove trace dependencies from Cargo.toml
    let cargo_toml_path = find_cargo_toml(project_dir)
        .context("Could not find Cargo.toml file")?;
    
    let stats = remove_dependencies_from_cargo_toml(&cargo_toml_path)
        .context("Failed to remove dependencies")?;
    
    // Only show summary if dependencies were actually removed
    if stats.added.len() > 0 {
        display_removal_summary(&stats);
    }
    
    // Step 3: Remove trace_config.rs if it exists
    remove_trace_config_file(project_dir)?;
    
    // Step 4: Clean up main.rs integration (optional)
    clean_main_rs_integration(project_dir)?;
    
    Ok(())
}

/// Remove trace_config.rs file if it exists
fn remove_trace_config_file(project_dir: &Path) -> Result<()> {
    let src_dir = project_dir.join("src");
    let trace_config_path = src_dir.join("trace_config.rs");
    
    if trace_config_path.exists() {
        fs::remove_file(&trace_config_path)
            .with_context(|| format!("Failed to remove trace config file: {}", trace_config_path.display()))?;
        println!("Removed: {}", trace_config_path.display());
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
    
    let content = fs::read_to_string(&main_rs_path)
        .with_context(|| format!("Failed to read main.rs: {}", main_rs_path.display()))?;
    
    // Remove trace-related lines
    let mut lines: Vec<&str> = content.lines().collect();
    let mut modified = false;
    let mut changes = Vec::<String>::new();
    
    // Remove mod trace_config; line
    if let Some(pos) = lines.iter().position(|line| {
        line.trim() == "mod trace_config;" || 
        line.trim().starts_with("mod trace_config;")
    }) {
        lines.remove(pos);
        modified = true;
        changes.push("mod trace_config;".to_string());
    }
    
    // Remove trace initialization call - handle various formats
    let mut positions_to_remove = Vec::new();
    
    // Find all lines that contain trace initialization calls
    for (i, line) in lines.iter().enumerate() {
        let trimmed = line.trim();
        if trimmed.contains("trace_config::init_tracing_ignore_errors()") ||
           trimmed.contains("trace_config::init_tracing()") ||
           (trimmed.starts_with("trace_config::") && (trimmed.contains("init_tracing"))) {
            positions_to_remove.push(i);
        }
    }
    
    // Remove lines in reverse order to maintain correct indices
    for &pos in positions_to_remove.iter().rev() {
        lines.remove(pos);
        modified = true;
    }
    
    if !positions_to_remove.is_empty() {
        changes.push(format!("{} trace initialization calls", positions_to_remove.len()));
    }
    
    // Remove auto-generated trace comment
    if let Some(pos) = lines.iter().position(|line| {
        line.trim() == "// Initialize trace system automatically"
    }) {
        lines.remove(pos);
        modified = true;
    }
    
    // Remove any empty lines that might have been left behind after trace code removal
    let mut final_lines = Vec::new();
    let mut prev_empty = false;
    
    for line in lines {
        let current_empty = line.trim().is_empty();
        
        // Skip multiple consecutive empty lines, but keep single empty lines
        if current_empty && prev_empty {
            continue;
        }
        
        final_lines.push(line);
        prev_empty = current_empty;
    }
    
    if modified {
        let new_content = final_lines.join("\n");
        fs::write(&main_rs_path, new_content)
            .with_context(|| format!("Failed to write main.rs: {}", main_rs_path.display()))?;
        
        // Only show what was actually removed
        if !changes.is_empty() {
            println!("Removed from main.rs: {}", changes.join(", "));
        }
    }
    
    Ok(())
} 