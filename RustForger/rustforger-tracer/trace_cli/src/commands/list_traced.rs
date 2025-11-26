use anyhow::{Context, Result, ensure};
use std::path::Path;
use std::process::Command;
use std::collections::HashMap;

use crate::utils::fs::visit_rust_files;

/// List all files containing trace macros
pub fn run(dir: &Path, verbose: bool) -> Result<()> {
    ensure!(dir.exists(), "Directory does not exist: {}", dir.display());

    let search_results = search_trace_files(dir)
        .context("Failed to search for trace macros")?;

    if search_results.is_empty() {
        println!("no files with trace macros found in {}", dir.display());
        return Ok(());
    }

    let files_with_traces = group_results_by_file(search_results);
    display_results(&files_with_traces, verbose)?;

    Ok(())
}

/// Search for files containing trace macros using available tools
fn search_trace_files(dir: &Path) -> Result<Vec<(String, u32, String)>> {
    // Try tools in order of preference: ripgrep -> grep -> builtin
    try_ripgrep_search(dir)
        .or_else(|_| try_grep_search(dir))
        .or_else(|_| builtin_search(dir))
}

/// Try searching with ripgrep
fn try_ripgrep_search(dir: &Path) -> Result<Vec<(String, u32, String)>> {
    let output = Command::new("rg")
        .args(&[
            "--line-number",
            "--type", "rust",
            "--only-matching",
            r"#\[(rustforger_trace|trace)\]",
            ".",
        ])
        .current_dir(dir)
        .output()?;

    ensure!(output.status.success(), "ripgrep command failed");
    parse_search_output(&output.stdout, SearchFormat::Ripgrep)
}

/// Try searching with grep
fn try_grep_search(dir: &Path) -> Result<Vec<(String, u32, String)>> {
    let output = Command::new("grep")
        .args(&[
            "-rn",
            "--include=*.rs",
            r"#\[.*trace.*\]",
            ".",
        ])
        .current_dir(dir)
        .output()?;

    ensure!(output.status.success(), "grep command failed");
    parse_search_output(&output.stdout, SearchFormat::Grep)
}

/// Built-in search fallback
fn builtin_search(dir: &Path) -> Result<Vec<(String, u32, String)>> {
    let mut results = Vec::new();
    
    let mut file_processor = |file_path: &Path| -> Result<()> {
        if let Ok(content) = std::fs::read_to_string(file_path) {
            for (line_num, line) in content.lines().enumerate() {
                if line.contains("#[trace") || line.contains("#[rustforger_trace") {
                    results.push((
                        file_path.to_string_lossy().to_string(),
                        (line_num + 1) as u32,
                        line.trim().to_string(),
                    ));
                }
            }
        }
        Ok(())
    };
    
    visit_rust_files(dir, &mut file_processor)?;
    
    Ok(results)
}

/// Output format type
enum SearchFormat {
    Ripgrep,
    Grep,
}

/// Parse search tool output
fn parse_search_output(output: &[u8], format: SearchFormat) -> Result<Vec<(String, u32, String)>> {
    let output_str = String::from_utf8_lossy(output);
    let mut results = Vec::new();
    
    for line in output_str.lines() {
        if line.trim().is_empty() {
            continue;
        }
        
        let (file_path, line_num, content) = match format {
            SearchFormat::Ripgrep => parse_ripgrep_line(line)?,
            SearchFormat::Grep => parse_grep_line(line)?,
        };
        
        results.push((file_path, line_num, content));
    }
    
    Ok(results)
}

/// Parse ripgrep output line
fn parse_ripgrep_line(line: &str) -> Result<(String, u32, String)> {
    let parts: Vec<&str> = line.splitn(3, ':').collect();
    ensure!(parts.len() >= 3, "Invalid ripgrep output format");
    
    let file_path = parts[0].to_string();
    let line_num: u32 = parts[1].parse()
        .context("Failed to parse line number from ripgrep output")?;
    let content = parts[2].to_string();
    
    Ok((file_path, line_num, content))
}

/// Parse grep output line
fn parse_grep_line(line: &str) -> Result<(String, u32, String)> {
    let parts: Vec<&str> = line.splitn(3, ':').collect();
    ensure!(parts.len() >= 3, "Invalid grep output format");
    
    let file_path = parts[0].to_string();
    let line_num: u32 = parts[1].parse()
        .context("Failed to parse line number from grep output")?;
    let content = parts[2].to_string();
    
    Ok((file_path, line_num, content))
}

/// Group search results by file path
fn group_results_by_file(results: Vec<(String, u32, String)>) -> HashMap<String, Vec<(u32, String)>> {
    let mut grouped = HashMap::new();
    
    for (file_path, line_num, content) in results {
        grouped.entry(file_path)
            .or_insert_with(Vec::new)
            .push((line_num, content));
    }
    
    // Sort traces within each file by line number
    for traces in grouped.values_mut() {
        traces.sort_by_key(|(line_num, _)| *line_num);
    }
    
    grouped
}

/// Display search results
fn display_results(files_with_traces: &HashMap<String, Vec<(u32, String)>>, verbose: bool) -> Result<()> {
    let mut file_paths: Vec<_> = files_with_traces.keys().collect();
    file_paths.sort();
    
    let total_files = files_with_traces.len();
    let total_traces: usize = files_with_traces.values().map(|v| v.len()).sum();
    
    for file_path in &file_paths {
        let traces = &files_with_traces[*file_path];
        if verbose {
            display_verbose_file_info(file_path, traces);
        } else {
            display_simple_file_info(file_path, traces);
        }
    }
    
    display_summary(total_files, total_traces, verbose);
    
    Ok(())
}

/// Display detailed file information
fn display_verbose_file_info(file_path: &str, traces: &[(u32, String)]) {
    println!("{}", file_path);
    for (line_num, content) in traces {
        let function_info = extract_function_info(content);
        println!("    {}:{} {}", line_num, function_info, content);
    }
    println!();
}

/// Display simple file information
fn display_simple_file_info(file_path: &str, traces: &[(u32, String)]) {
    println!("{} ({} traces)", file_path, traces.len());
}

/// Display operation summary
fn display_summary(total_files: usize, total_traces: usize, verbose: bool) {
    println!("files with traces: {}", total_files);
    println!("total trace macros: {}", total_traces);
    
    if !verbose && total_files > 0 {
        println!("use --verbose for detailed line information");
    }
}

/// Extract function information from trace attribute line
fn extract_function_info(content: &str) -> String {
    // Simple heuristic to extract function name
    if content.contains("fn ") {
        if let Some(fn_start) = content.find("fn ") {
            let after_fn = &content[fn_start + 3..];
            if let Some(paren_pos) = after_fn.find('(') {
                return after_fn[..paren_pos].trim().to_string();
            }
        }
    }
    "function".to_string()
} 