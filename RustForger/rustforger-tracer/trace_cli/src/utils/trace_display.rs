use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::Path;

/// Configuration for trace display
#[derive(Debug, Clone)]
pub struct DisplayConfig {
    /// Maximum number of trace entries to display
    pub max_entries: usize,
    /// Maximum depth of call tree to display
    pub max_depth: usize,
    /// Maximum number of children to show per node
    pub max_children_per_node: usize,
    /// Whether to show input/output values
    pub show_values: bool,
    /// Maximum length of displayed values
    pub max_value_length: usize,
}

impl Default for DisplayConfig {
    fn default() -> Self {
        Self {
            max_entries: 30,
            max_depth: 10,
            max_children_per_node: 10,
            show_values: true,
            max_value_length: 200,
        }
    }
}

/// Represents a function call node in the trace tree
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CallNode {
    pub name: String,
    pub file: String,
    pub line: u32,
    pub children: Vec<CallNode>,
}

/// Complete trace data for a function call
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CallData {
    pub timestamp_utc: String,
    pub thread_id: String,
    pub root_node: CallNode,
    pub inputs: serde_json::Value,
    pub output: serde_json::Value,
}

/// Display trace data in a compact tree format
pub fn display_trace_preview(trace_file: &Path, config: DisplayConfig) -> Result<()> {
    let content = std::fs::read_to_string(trace_file)
        .with_context(|| format!("Failed to read trace file: {}", trace_file.display()))?;
    
    let trace_data: Vec<CallData> = serde_json::from_str(&content)
        .with_context(|| "Failed to parse trace JSON data")?;
    
    if trace_data.is_empty() {
        println!("Trace Preview: No trace data found");
        return Ok(());
    }
    
    // Display header
    let total_entries = trace_data.len();
    let showing_entries = std::cmp::min(config.max_entries, total_entries);
    
    println!("Trace Preview ({} entries, showing first {})", total_entries, showing_entries);
    
    // Group by thread for better organization
    let mut thread_groups: HashMap<String, Vec<&CallData>> = HashMap::new();
    for call_data in trace_data.iter().take(showing_entries) {
        thread_groups.entry(call_data.thread_id.clone())
            .or_default()
            .push(call_data);
    }
    
    // Display each thread's traces
    for (thread_id, calls) in thread_groups {
        if calls.len() == 1 {
            display_single_call(calls[0], &config, "");
        } else {
            println!("Thread {} ({} calls)", thread_id, calls.len());
            for (i, call) in calls.iter().enumerate() {
                let prefix = if i == calls.len() - 1 { "  └─" } else { "  ├─" };
                display_single_call(call, &config, prefix);
            }
        }
    }
    
    if total_entries > showing_entries {
        println!("... {} more entries omitted", total_entries - showing_entries);
    }
    
    Ok(())
}

/// Display a single function call with its tree structure
fn display_single_call(call_data: &CallData, config: &DisplayConfig, prefix: &str) {
    // Extract timestamp (show only time part)
    let time_str = extract_time_from_timestamp(&call_data.timestamp_utc);
    
    // Display root function
    let location = format_location(&call_data.root_node.file, call_data.root_node.line);
    println!("{}{} {} [{}]", 
             prefix, 
             call_data.root_node.name, 
             location, 
             time_str);
    
    // Display input/output if enabled
    if config.show_values {
        display_values(&call_data.inputs, &call_data.output, config, &format!("{}  ", prefix));
    }
    
    // Display call tree
    if !call_data.root_node.children.is_empty() {
        display_call_tree(&call_data.root_node.children, config, 1, &format!("{}  ", prefix));
    }
}

/// Display the call tree recursively
fn display_call_tree(children: &[CallNode], config: &DisplayConfig, depth: usize, prefix: &str) {
    if depth > config.max_depth {
        println!("{}└─ ... (max depth reached)", prefix);
        return;
    }
    
    let display_count = std::cmp::min(config.max_children_per_node, children.len());
    
    for (i, child) in children.iter().take(display_count).enumerate() {
        let is_last = i == display_count - 1 && display_count == children.len();
        let child_prefix = if is_last { "└─" } else { "├─" };
        let location = format_location(&child.file, child.line);
        
        println!("{}{} {} {}", prefix, child_prefix, child.name, location);
        
        // Recursively display children
        if !child.children.is_empty() {
            let next_prefix = if is_last {
                format!("{}   ", prefix)
            } else {
                format!("{}│  ", prefix)
            };
            display_call_tree(&child.children, config, depth + 1, &next_prefix);
        }
    }
    
    // Show omitted children count
    if children.len() > display_count {
        let omitted = children.len() - display_count;
        println!("{}└─ ... ({} more children omitted)", prefix, omitted);
    }
}

/// Display input and output values in a compact format
fn display_values(inputs: &serde_json::Value, output: &serde_json::Value, config: &DisplayConfig, prefix: &str) {
    // Display inputs
    if !inputs.is_null() && !is_empty_object(inputs) {
        let input_str = format_value(inputs, config.max_value_length);
        println!("{}in:  {}", prefix, input_str);
    }
    
    // Display output
    if !output.is_null() {
        let output_str = format_value(output, config.max_value_length);
        println!("{}out: {}", prefix, output_str);
    }
}

/// Format a JSON value for compact display
fn format_value(value: &serde_json::Value, max_length: usize) -> String {
    let formatted = match value {
        serde_json::Value::String(s) => {
            if s.starts_with("<unserializable:") || s.starts_with("<debug:") {
                // Extract type name from unserializable placeholders
                extract_type_from_placeholder(s)
            } else {
                format!("\"{}\"", s)
            }
        }
        serde_json::Value::Object(obj) => {
            if obj.is_empty() {
                "{}".to_string()
            } else {
                let keys: Vec<String> = obj.keys().take(3).cloned().collect();
                if keys.len() == obj.len() {
                    format!("{{{}}}", keys.join(", "))
                } else {
                    format!("{{{}, ...}}", keys.join(", "))
                }
            }
        }
        serde_json::Value::Array(arr) => {
            if arr.is_empty() {
                "[]".to_string()
            } else {
                format!("[{} items]", arr.len())
            }
        }
        _ => value.to_string(),
    };
    
    // Truncate if too long
    if formatted.len() > max_length {
        format!("{}...", &formatted[..max_length.saturating_sub(3)])
    } else {
        formatted
    }
}

/// Extract time portion from ISO timestamp
fn extract_time_from_timestamp(timestamp: &str) -> String {
    if let Some(time_part) = timestamp.split('T').nth(1) {
        if let Some(time_without_tz) = time_part.split('+').next().or_else(|| time_part.split('Z').next()) {
            // Return HH:MM:SS format
            if time_without_tz.len() >= 8 {
                return time_without_tz[..8].to_string();
            }
        }
    }
    timestamp.to_string() // Fallback to full timestamp
}

/// Format file location for compact display
fn format_location(file: &str, line: u32) -> String {
    if let Some(filename) = file.split('/').last() {
        format!("({}:{})", filename, line)
    } else {
        format!("({}:{})", file, line)
    }
}

/// Extract type name from unserializable placeholder
fn extract_type_from_placeholder(placeholder: &str) -> String {
    if placeholder.starts_with("<unserializable:") {
        if let Some(type_part) = placeholder.strip_prefix("<unserializable: ").and_then(|s| s.strip_suffix(">")) {
            format!("<{}>", simplify_type_name(type_part))
        } else {
            "<unserializable>".to_string()
        }
    } else if placeholder.starts_with("<debug:") {
        if let Some(debug_part) = placeholder.strip_prefix("<debug: ") {
            if let Some(type_part) = debug_part.split(" = ").next() {
                format!("<{}>", simplify_type_name(type_part))
            } else {
                "<debug>".to_string()
            }
        } else {
            "<debug>".to_string()
        }
    } else {
        placeholder.to_string()
    }
}

/// Simplify Rust type names for display
fn simplify_type_name(type_name: &str) -> String {
    // Common type simplifications
    let simplified = type_name
        .replace("alloc::string::String", "String")
        .replace("alloc::vec::Vec", "Vec")
        .replace("std::collections::hash::map::HashMap", "HashMap")
        .replace("core::result::Result", "Result")
        .replace("core::option::Option", "Option")
        .replace("alloc::rc::Rc", "Rc")
        .replace("std::sync::", "");
    
    // If still too long, take just the last part
    if simplified.len() > 30 {
        if let Some(last_part) = simplified.split("::").last() {
            last_part.to_string()
        } else {
            simplified
        }
    } else {
        simplified
    }
}

/// Check if a JSON value is an empty object
fn is_empty_object(value: &serde_json::Value) -> bool {
    match value {
        serde_json::Value::Object(obj) => obj.is_empty(),
        _ => false,
    }
} 