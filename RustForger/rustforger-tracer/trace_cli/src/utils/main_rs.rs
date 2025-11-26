use anyhow::{Context, Result};
use std::path::Path;
use std::fs;

/// Automatically integrate trace initialization into main.rs
pub fn integrate_trace_initialization(project_root: &Path) -> Result<bool> {
    let main_rs_path = project_root.join("src").join("main.rs");
    
    if !main_rs_path.exists() {
        // No main.rs file found, skip integration
        return Ok(false);
    }

    let content = fs::read_to_string(&main_rs_path)
        .with_context(|| format!("Failed to read main.rs: {}", main_rs_path.display()))?;

    // Check if trace integration already exists
    if is_trace_already_integrated(&content) {
        return Ok(false); // Already integrated
    }

    // Attempt to automatically integrate trace initialization
    let modified_content = auto_integrate_trace(&content)?;
    
    // Write back the modified content
    fs::write(&main_rs_path, modified_content)
        .with_context(|| format!("Failed to write modified main.rs: {}", main_rs_path.display()))?;

    Ok(true)
}

/// Check if trace integration already exists in the file
fn is_trace_already_integrated(content: &str) -> bool {
    content.contains("mod trace_config") && 
    content.contains("trace_config::init_tracing")
}

/// Automatically integrate trace initialization into main.rs content
fn auto_integrate_trace(content: &str) -> Result<String> {
    let lines: Vec<&str> = content.lines().collect();
    let mut result_lines = Vec::new();
    let mut trace_mod_added = false;
    let mut main_fn_modified = false;
    
    // Check if mod trace_config already exists
    let mod_already_exists = lines.iter().any(|line| line.trim() == "mod trace_config;");
    if mod_already_exists {
        trace_mod_added = true;
    }
    
    // Find the best position to insert mod trace_config
    let mod_insert_position = if trace_mod_added { 
        usize::MAX // Don't insert if already exists
    } else { 
        find_mod_insert_position(&lines) 
    };
    
    let mut i = 0;
    while i < lines.len() {
        let line = lines[i];
        let trimmed = line.trim();
        
        // Insert mod trace_config at the determined position
        if !trace_mod_added && i == mod_insert_position {
            // Add a blank line if previous line is not blank and is a use statement
            if i > 0 && !lines[i-1].trim().is_empty() && lines[i-1].trim().starts_with("use ") {
                result_lines.push("".to_string());
            }
            result_lines.push("mod trace_config;".to_string());
            result_lines.push("".to_string());
            trace_mod_added = true;
        }

        // Check if this is the main function line
        if is_main_function_line(trimmed) && !main_fn_modified {
            // Add the main function line first
            result_lines.push(line.to_string());
            
            // If opening brace is on the same line
            if line.contains('{') {
                let indent = "    ";
                result_lines.push(format!("{}// Initialize trace system automatically", indent));
                result_lines.push(format!("{}trace_config::init_tracing_ignore_errors();", indent));
                result_lines.push("".to_string());
                main_fn_modified = true;
            } else {
                // Find and add lines until we find the opening brace
                let mut j = i + 1;
                while j < lines.len() {
                    let next_line = lines[j];
                    result_lines.push(next_line.to_string());
                    
                    if next_line.trim().contains('{') {
                        // Found opening brace, now add the trace initialization
                        let indent = "    "; // Standard 4-space indentation for function body
                        result_lines.push(format!("{}// Initialize trace system automatically", indent));
                        result_lines.push(format!("{}trace_config::init_tracing_ignore_errors();", indent));
                        result_lines.push("".to_string());
                        main_fn_modified = true;
                        break;
                    }
                    j += 1;
                }
                
                // Skip the lines we've already processed
                i = j;
            }
        } else {
            // Regular line, just add it
            result_lines.push(line.to_string());
        }
        
        i += 1;
    }

    // If we didn't add mod trace_config yet, add it at the top
    if !trace_mod_added {
        let mut final_lines = vec!["mod trace_config;".to_string(), "".to_string()];
        final_lines.extend(result_lines);
        result_lines = final_lines;
    }

    if !main_fn_modified {
        anyhow::bail!("Could not automatically modify main function. Please add trace_config::init_tracing_ignore_errors(); manually at the beginning of main().");
    }

    Ok(result_lines.join("\n"))
}

/// Find the best position to insert mod trace_config
fn find_mod_insert_position(lines: &[&str]) -> usize {
    let mut last_use_line = None;
    let mut first_non_use_line = None;
    
    for (i, line) in lines.iter().enumerate() {
        let trimmed = line.trim();
        
        if trimmed.starts_with("use ") {
            last_use_line = Some(i);
        } else if !trimmed.is_empty() && !trimmed.starts_with("//") {
            if last_use_line.is_some() && first_non_use_line.is_none() {
                first_non_use_line = Some(i);
                break;
            } else if last_use_line.is_none() {
                // No use statements found, insert at the beginning of non-comment content
                first_non_use_line = Some(i);
                break;
            }
        }
    }
    
    // Return position after last use statement or before first non-use item
    if let Some(last_use) = last_use_line {
        if let Some(first_non_use) = first_non_use_line {
            first_non_use
        } else {
            last_use + 1
        }
    } else if let Some(first_non_use) = first_non_use_line {
        first_non_use
    } else {
        0 // Insert at the beginning if no suitable position found
    }
}

/// Check if a line contains the main function declaration
fn is_main_function_line(line: &str) -> bool {
    // More precise main function detection
    let line = line.trim();
    
    // Look for various main function patterns
    if line.starts_with("fn main(") || 
       line.starts_with("fn main()") ||
       (line.contains("fn main") && (line.contains("()") || line.contains("("))) {
        return true;
    }
    
    // Handle attributed main functions like #[rustforger_trace] fn main()
    if line.starts_with("#[") && line.contains("fn main") {
        return true;
    }
    
    false
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_simple_main_integration() {
        let input = r#"use std::io;

fn main() {
    println!("Hello, world!");
}"#;

        let result = auto_integrate_trace(input).unwrap();
        assert!(result.contains("mod trace_config;"));
        assert!(result.contains("trace_config::init_tracing_ignore_errors();"));
    }

    #[test]
    fn test_already_integrated() {
        let input = r#"use std::io;

mod trace_config;

fn main() {
    trace_config::init_tracing_ignore_errors();
    println!("Hello, world!");
}"#;

        assert!(is_trace_already_integrated(input));
    }

    #[test]
    fn test_main_with_attributes() {
        let input = r#"use clap::Parser;

#[derive(Parser)]
struct Cli {
    args: Vec<String>,
}

#[rustforger_trace]
fn main() {
    let cli = Cli::parse();
    println!("{:#?}", cli.args);
}"#;

        let result = auto_integrate_trace(input).unwrap();
        assert!(result.contains("mod trace_config;"));
        assert!(result.contains("trace_config::init_tracing_ignore_errors();"));
    }

    #[test]
    fn test_clap_derive_parser_integration() {
        let input = r#"use clap::Parser;
#[derive(Parser)]
struct Cli {
    /// Args
    #[arg(value_name = "ARG", num_args = 2..)]
    args: Vec<String>,
}

fn main() {
    let cli = Cli::parse();
    println!("{:#?}", cli.args);
}"#;

        let result = auto_integrate_trace(input).unwrap();
        assert!(result.contains("mod trace_config;"));
        assert!(result.contains("trace_config::init_tracing_ignore_errors();"));
        // Ensure #[derive(Parser)] stays with struct Cli
        assert!(result.contains("#[derive(Parser)]\nstruct Cli"));
        // Ensure mod trace_config comes after use statements but before attributes
        let lines: Vec<&str> = result.lines().collect();
        let use_line_idx = lines.iter().position(|&line| line.starts_with("use ")).unwrap();
        let mod_line_idx = lines.iter().position(|&line| line.trim() == "mod trace_config;").unwrap();
        let derive_line_idx = lines.iter().position(|&line| line.starts_with("#[derive(Parser)]")).unwrap();
        
        // mod trace_config should come after use but before derive
        assert!(mod_line_idx > use_line_idx);
        assert!(mod_line_idx < derive_line_idx);
    }

    #[test]
    fn test_no_duplicate_mod_trace_config() {
        let input = r#"use clap::Parser;

mod trace_config;

#[derive(Parser)]
struct Cli {
    /// Args
    #[arg(value_name = "ARG", num_args = 2..)]
    args: Vec<String>,
}

fn main() {
    let cli = Cli::parse();
    println!("{:#?}", cli.args);
}"#;

        let result = auto_integrate_trace(input).unwrap();
        assert!(result.contains("mod trace_config;"));
        assert!(result.contains("trace_config::init_tracing_ignore_errors();"));
        
        // Ensure there's only one mod trace_config declaration
        let mod_count = result.matches("mod trace_config;").count();
        assert_eq!(mod_count, 1, "Should have exactly one mod trace_config declaration, found {}", mod_count);
    }
} 