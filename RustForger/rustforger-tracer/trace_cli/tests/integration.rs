//! Integration tests for complete workflows

use anyhow::Result;
use std::fs;

mod common;
use common::{TestFixture, SAMPLE_RUST_CODE, CARGO_TOML_WITH_TRACE};

/// Test complete workflow: instrument -> list -> revert
#[tokio::test]
async fn complete_workflow() -> Result<()> {
    let fixture = TestFixture::new()?;
    
    // Step 1: Create a project
    let rust_file = fixture.create_rust_file("lib.rs", SAMPLE_RUST_CODE)?;
    fixture.create_cargo_toml(CARGO_TOML_WITH_TRACE)?;
    
    // Step 2: Instrument a function
    let result = trace_cli::commands::instrument::run(&rust_file, "simple_function", None, None);
    assert!(result.is_ok(), "Instrumentation should succeed");
    
    // Verify instrumentation
    let content = fixture.read_file("lib.rs")?;
    assert!(content.contains("#[rustforger_trace]"), "Should contain trace attribute");
    
    // Step 3: List traced files
    let result = trace_cli::commands::list_traced::run(fixture.path(), false);
    assert!(result.is_ok(), "List command should succeed");
    
    // Step 4: Instrument another function
    let result = trace_cli::commands::instrument::run(&rust_file, "public_function", None, None);
    assert!(result.is_ok(), "Second instrumentation should succeed");
    
    // Verify multiple traces
    let content = fixture.read_file("lib.rs")?;
    let trace_count = content.matches("#[rustforger_trace]").count();
    assert_eq!(trace_count, 2, "Should have two trace attributes");
    
    // Step 5: Revert all instrumentation
    let result = trace_cli::commands::revert::run(&rust_file);
    assert!(result.is_ok(), "Revert should succeed");
    
    // Verify clean revert
    let content = fixture.read_file("lib.rs")?;
    assert!(!content.contains("#[rustforger_trace]"), "Should not contain trace attributes");
    assert!(!content.contains("use trace_runtime"), "Should not contain trace imports");
    
    Ok(())
}

/// Test directory-based workflow with multiple files
#[tokio::test]
async fn directory_workflow() -> Result<()> {
    let fixture = TestFixture::new()?;
    
    // Create multiple files
    let file1 = fixture.create_rust_file("mod1.rs", SAMPLE_RUST_CODE)?;
    let file2 = fixture.create_rust_file("mod2.rs", SAMPLE_RUST_CODE)?;
    
    // Create subdirectory
    fixture.create_dir("src")?;
    let file3 = fixture.create_rust_file("src/mod3.rs", SAMPLE_RUST_CODE)?;
    
    fixture.create_cargo_toml(CARGO_TOML_WITH_TRACE)?;
    
    // Instrument functions in different files
    trace_cli::commands::instrument::run(&file1, "simple_function", None, None)?;
    trace_cli::commands::instrument::run(&file2, "public_function", None, None)?;
    trace_cli::commands::instrument::run(&file3, "simple_function", None, None)?;
    
    // List all traced files
    let result = trace_cli::commands::list_traced::run(fixture.path(), true);
    assert!(result.is_ok(), "List should find all traced files");
    
    // Revert entire directory
    let result = trace_cli::commands::revert::run(fixture.path());
    assert!(result.is_ok(), "Directory revert should succeed");
    
    // Verify all files were reverted
    for file in ["mod1.rs", "mod2.rs", "src/mod3.rs"] {
        let content = fixture.read_file(file)?;
        assert!(!content.contains("#[rustforger_trace]"), 
                "File {} should not contain traces", file);
    }
    
    Ok(())
}

/// Test propagation instrumentation workflow
#[tokio::test]
async fn propagation_workflow() -> Result<()> {
    let fixture = TestFixture::new()?;
    
    let rust_file = fixture.create_rust_file("lib.rs", SAMPLE_RUST_CODE)?;
    fixture.create_cargo_toml(CARGO_TOML_WITH_TRACE)?;
    
    // Test propagation instrumentation
    let propagation_config = trace_cli::utils::config::PropagationConfig::enabled();
    let result = trace_cli::commands::instrument::run(&rust_file, "simple_function", None, Some(propagation_config));
    assert!(result.is_ok(), "Propagation instrumentation should succeed");
    
    // Verify propagation attribute
    let content = fixture.read_file("lib.rs")?;
    assert!(content.contains("#[rustforger_trace(propagate = true)]"), "Should contain propagation attribute");
    
    // Test revert still works
    let result = trace_cli::commands::revert::run(&rust_file);
    assert!(result.is_ok(), "Revert should work with propagation attributes");
    
    Ok(())
}

/// Test error recovery and resilience
#[tokio::test]
async fn error_recovery() -> Result<()> {
    let fixture = TestFixture::new()?;
    
    let rust_file = fixture.create_rust_file("lib.rs", SAMPLE_RUST_CODE)?;
    fixture.create_cargo_toml(CARGO_TOML_WITH_TRACE)?;
    
    // Try to instrument non-existent function
    let result = trace_cli::commands::instrument::run(&rust_file, "nonexistent", None, None);
    assert!(result.is_err(), "Should fail for non-existent function");
    
    // File should remain unchanged
    let content = fixture.read_file("lib.rs")?;
    assert!(!content.contains("#[rustforger_trace]"), "File should be unchanged");
    
    // Successful instrumentation should still work
    let result = trace_cli::commands::instrument::run(&rust_file, "simple_function", None, None);
    assert!(result.is_ok(), "Valid instrumentation should work after error");
    
    Ok(())
}

/// Test handling of mixed file types
#[tokio::test]
async fn mixed_file_types() -> Result<()> {
    let fixture = TestFixture::new()?;
    
    // Create mixed file types
    fixture.create_rust_file("code.rs", SAMPLE_RUST_CODE)?;
    fs::write(fixture.path().join("readme.md"), "# README")?;
    fs::write(fixture.path().join("config.toml"), "[config]")?;
    fs::write(fixture.path().join("data.json"), "{}")?;
    
    // Commands should handle mixed file types gracefully
    let result = trace_cli::commands::list_traced::run(fixture.path(), false);
    assert!(result.is_ok(), "Should handle mixed file types");
    
    let result = trace_cli::commands::revert::run(fixture.path());
    assert!(result.is_ok(), "Directory revert should handle mixed file types");
    
    Ok(())
} 