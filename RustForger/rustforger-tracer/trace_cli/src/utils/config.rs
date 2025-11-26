use anyhow::{Context, Result};
use std::path::Path;
use std::fs;

/// Propagation instrumentation configuration
#[derive(Debug, Clone)]
pub struct PropagationConfig {
    pub enabled: bool,
    pub max_depth: Option<u32>,
    pub exclude_patterns: Vec<String>,
    pub user_code_only: bool,
}

impl Default for PropagationConfig {
    fn default() -> Self {
        Self {
            enabled: false,
            max_depth: Some(10),
            exclude_patterns: vec!["std::".to_string(), "core::".to_string()],
            user_code_only: true,
        }
    }
}

impl PropagationConfig {
    /// Create a new propagation config with default settings
    #[allow(dead_code)]
    pub fn new() -> Self {
        Self::default()
    }

    /// Enable propagation with default settings
    pub fn enabled() -> Self {
        Self {
            enabled: true,
            ..Self::default()
        }
    }

    /// Set maximum depth for propagation
    #[allow(dead_code)]
    pub fn with_max_depth(mut self, depth: u32) -> Self {
        self.max_depth = Some(depth);
        self
    }

    /// Add exclude patterns
    #[allow(dead_code)]
    pub fn with_exclude_patterns(mut self, patterns: Vec<String>) -> Self {
        self.exclude_patterns = patterns;
        self
    }

    /// Set user code only flag
    #[allow(dead_code)]
    pub fn with_user_code_only(mut self, user_only: bool) -> Self {
        self.user_code_only = user_only;
        self
    }
}

/// Create trace configuration file
pub fn create_trace_config_file(
    project_root: &Path,
    trace_output: Option<&Path>,
    propagation_config: Option<&PropagationConfig>,
) -> Result<()> {
    let src_dir = project_root.join("src");
    fs::create_dir_all(&src_dir)
        .with_context(|| format!("Failed to create src directory: {}", src_dir.display()))?;

    let config_file_path = src_dir.join("trace_config.rs");
    let propagation_info = generate_propagation_comment(propagation_config);

    let config_content = if let Some(output_path) = trace_output {
        generate_config_with_output(output_path, &propagation_info)
    } else {
        generate_config_default(&propagation_info)
    };

    fs::write(&config_file_path, config_content)
        .with_context(|| format!("Failed to write trace config to: {}", config_file_path.display()))?;

    // println!("created trace configuration file: {}", config_file_path.display());
    // println!("note: add `mod trace_config; trace_config::init_tracing_ignore_errors();` to your main.rs");

    Ok(())
}

/// Generate propagation configuration comment
fn generate_propagation_comment(propagation_config: Option<&PropagationConfig>) -> String {
    if let Some(config) = propagation_config {
        if config.enabled {
            format!(
                "// Propagation instrumentation config:\n\
                 // - Enabled: true\n\
                 // - Max depth: {}\n\
                 // - Exclude patterns: {:?}\n\
                 // - User code only: {}\n\
                 //\n\
                 // Functions with propagation instrumentation automatically trace all internal calls\n\
                 // No need to manually add trace macros to each function\n\n",
                config.max_depth.map(|d| d.to_string()).unwrap_or_else(|| "unlimited".to_string()),
                config.exclude_patterns,
                config.user_code_only
            )
        } else {
            "// Propagation instrumentation: disabled\n\
             // Only manually traced functions will be recorded\n\n".to_string()
        }
    } else {
        "// Propagation instrumentation: disabled\n\
         // Only manually traced functions will be recorded\n\n".to_string()
    }
}

/// Generate configuration with custom output file path
fn generate_config_with_output(output_path: &Path, propagation_info: &str) -> String {
    format!(
        r#"// Auto-generated trace configuration file
// Created by trace_cli tool

{}use std::path::Path;
use trace_runtime::tracer::interface::{{enable_auto_save_with_path, TraceError}};

/// Initialize tracing system with custom output file path
pub fn init_tracing() -> Result<(), TraceError> {{
    let output_path = Path::new("{}");
    
    // Use the improved API that handles directory creation automatically
    enable_auto_save_with_path(output_path)?;
    eprintln!("🔄 Tracing initialized, output: {{}}", output_path.display());
    Ok(())
}}

/// Convenience initialization function that ignores errors
pub fn init_tracing_ignore_errors() {{
    if let Err(e) = init_tracing() {{
        eprintln!("⚠️  Failed to initialize tracing: {{}}", e);
    }}
}}
"#,
        propagation_info,
        output_path.display()
    )
}

/// Generate configuration with default settings
fn generate_config_default(propagation_info: &str) -> String {
    format!(
        r#"// Auto-generated trace configuration file
// Created by trace_cli tool

{}use trace_runtime::tracer::interface::{{enable_auto_save_default, TraceError}};

/// Initialize tracing system with intelligent defaults
/// 
/// This uses platform-appropriate directories and avoids hardcoded paths.
/// Path resolution priority:
/// 1. TRACE_OUTPUT_FILE environment variable
/// 2. Platform-specific application data directory  
/// 3. Current working directory (trace_output.json)
pub fn init_tracing() -> Result<(), TraceError> {{
    // Use the improved default API that follows platform conventions
    enable_auto_save_default()?;
    eprintln!("🔄 Tracing initialized with intelligent defaults");
    Ok(())
}}

/// Convenience initialization function that ignores errors
pub fn init_tracing_ignore_errors() {{
    if let Err(e) = init_tracing() {{
        eprintln!("⚠️  Failed to initialize tracing: {{}}", e);
    }}
}}
"#,
        propagation_info
    )
} 