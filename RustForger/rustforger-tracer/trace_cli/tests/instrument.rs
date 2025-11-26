//! Tests for function instrumentation functionality

use anyhow::Result;
use trace_cli;

mod common;
use common::{TestFixture, SAMPLE_RUST_CODE, CARGO_TOML_WITH_TRACE};

/// Test basic function instrumentation
#[tokio::test]
async fn instrument_simple_function() -> Result<()> {
    let fixture = TestFixture::new()?;
    
    // Create test files
    let rust_file = fixture.create_rust_file("lib.rs", SAMPLE_RUST_CODE)?;
    fixture.create_cargo_toml(CARGO_TOML_WITH_TRACE)?;

    // Run instrument command
    let result = trace_cli::commands::instrument::run(&rust_file, "simple_function", None, None);
    
    assert!(result.is_ok(), "Instrumentation should succeed");
    
    // Verify the function was instrumented
    let content = fixture.read_file("lib.rs")?;
    assert!(content.contains("#[rustforger_trace]"), "Should contain trace attribute");
    assert!(content.contains("use trace_runtime::trace_macro::rustforger_trace"), 
            "Should contain use statement");
    
    Ok(())
}

/// Test method instrumentation in impl blocks
#[tokio::test]
async fn instrument_method() -> Result<()> {
    let fixture = TestFixture::new()?;
    
    let rust_file = fixture.create_rust_file("lib.rs", SAMPLE_RUST_CODE)?;
    fixture.create_cargo_toml(CARGO_TOML_WITH_TRACE)?;

    // Instrument a method
    let result = trace_cli::commands::instrument::run(&rust_file, "method", None, None);
    
    assert!(result.is_ok(), "Method instrumentation should succeed");
    
    let content = fixture.read_file("lib.rs")?;
    assert!(content.contains("#[rustforger_trace]"), "Should contain trace attribute");
    
    Ok(())
}

/// Test instrumentation with propagation configuration
#[tokio::test]
async fn instrument_with_propagation() -> Result<()> {
    let fixture = TestFixture::new()?;
    
    let rust_file = fixture.create_rust_file("lib.rs", SAMPLE_RUST_CODE)?;
    fixture.create_cargo_toml(CARGO_TOML_WITH_TRACE)?;

    // Test with propagation config
    let propagation_config = trace_cli::utils::config::PropagationConfig::enabled();
    let result = trace_cli::commands::instrument::run(&rust_file, "simple_function", None, Some(propagation_config));
    
    assert!(result.is_ok(), "Propagation instrumentation should succeed");
    
    let content = fixture.read_file("lib.rs")?;
    assert!(content.contains("#[rustforger_trace(propagate = true)]"), "Should contain propagation attribute");
    
    Ok(())
}

/// Test handling of already traced functions
#[tokio::test]
async fn instrument_already_traced() -> Result<()> {
    let fixture = TestFixture::new()?;
    
    let already_traced = r#"
use trace_runtime::trace_macro::rustforger_trace;

#[rustforger_trace]
fn already_traced_function() -> i32 {
    42
}
"#;
    
    let rust_file = fixture.create_rust_file("lib.rs", already_traced)?;
    fixture.create_cargo_toml(CARGO_TOML_WITH_TRACE)?;

    // Should not add duplicate attributes
    let result = trace_cli::commands::instrument::run(&rust_file, "already_traced_function", None, None);
    
    assert!(result.is_ok(), "Should handle already traced functions");
    
    let content = fixture.read_file("lib.rs")?;
    let trace_count = content.matches("#[rustforger_trace]").count();
    assert_eq!(trace_count, 1, "Should not duplicate trace attributes");
    
    Ok(())
}

/// Test error handling for non-existent functions
#[tokio::test]
async fn instrument_nonexistent_function() -> Result<()> {
    let fixture = TestFixture::new()?;
    
    let rust_file = fixture.create_rust_file("lib.rs", SAMPLE_RUST_CODE)?;
    fixture.create_cargo_toml(CARGO_TOML_WITH_TRACE)?;

    // Try to instrument non-existent function
    let result = trace_cli::commands::instrument::run(&rust_file, "nonexistent_function", None, None);
    
    assert!(result.is_err(), "Should fail for non-existent function");
    assert!(result.unwrap_err().to_string().contains("not found"), 
            "Error should mention function not found");
    
    Ok(())
}

/// Test error handling for invalid Rust syntax
#[tokio::test]
async fn instrument_invalid_rust_file() -> Result<()> {
    let fixture = TestFixture::new()?;
    
    let invalid_rust = "fn invalid syntax { missing parentheses";
    let rust_file = fixture.create_rust_file("invalid.rs", invalid_rust)?;

    let result = trace_cli::commands::instrument::run(&rust_file, "any_function", None, None);
    
    assert!(result.is_err(), "Should fail for invalid Rust syntax");
    
    Ok(())
}

/// Test error handling for missing files
#[tokio::test]
async fn instrument_missing_file() -> Result<()> {
    let fixture = TestFixture::new()?;
    let missing_file = fixture.path().join("missing.rs");

    let result = trace_cli::commands::instrument::run(&missing_file, "any_function", None, None);
    
    assert!(result.is_err(), "Should fail for missing file");
    assert!(result.unwrap_err().to_string().contains("does not exist"), 
            "Error should mention file doesn't exist");
    
    Ok(())
} 