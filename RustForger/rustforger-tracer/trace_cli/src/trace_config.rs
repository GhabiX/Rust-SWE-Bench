// Auto-generated trace configuration file
// Created by trace_cli tool

// Propagation instrumentation: disabled
// Only manually traced functions will be recorded

use trace_runtime::tracer::interface::{enable_auto_save_default, TraceError};

/// Initialize tracing system with intelligent defaults
/// 
/// This uses platform-appropriate directories and avoids hardcoded paths.
/// Path resolution priority:
/// 1. TRACE_OUTPUT_FILE environment variable
/// 2. Platform-specific application data directory  
/// 3. Current working directory (trace_output.json)
pub fn init_tracing() -> Result<(), TraceError> {
    // Use the improved default API that follows platform conventions
    enable_auto_save_default()?;
    eprintln!("🔄 Tracing initialized with intelligent defaults");
    Ok(())
}

/// Convenience initialization function that ignores errors
pub fn init_tracing_ignore_errors() {
    if let Err(e) = init_tracing() {
        eprintln!("⚠️  Failed to initialize tracing: {}", e);
    }
}
