//! Tests for listing traced files functionality

use anyhow::Result;
use std::fs;

mod common;
use common::{TestFixture, TRACED_RUST_CODE, SAMPLE_RUST_CODE};

/// Test listing files with traces
#[tokio::test]
async fn list_traced_with_traces() -> Result<()> {
    let fixture = TestFixture::new()?;
    
    // Create files with and without traces
    fixture.create_rust_file("traced.rs", TRACED_RUST_CODE)?;
    fixture.create_rust_file("normal.rs", SAMPLE_RUST_CODE)?;
    
    // Create subdirectory with traced file
    fixture.create_dir("src")?;
    fixture.create_rust_file("src/traced_module.rs", TRACED_RUST_CODE)?;
    
    // Run list command (non-verbose)
    let result = trace_cli::commands::list_traced::run(fixture.path(), false);
    
    assert!(result.is_ok(), "List command should succeed");
    
    Ok(())
}

/// Test listing with verbose output
#[tokio::test]
async fn list_traced_verbose() -> Result<()> {
    let fixture = TestFixture::new()?;
    
    fixture.create_rust_file("traced.rs", TRACED_RUST_CODE)?;
    
    // Run list command with verbose output
    let result = trace_cli::commands::list_traced::run(fixture.path(), true);
    
    assert!(result.is_ok(), "Verbose list command should succeed");
    
    Ok(())
}

/// Test listing when no traces exist
#[tokio::test]
async fn list_traced_no_traces() -> Result<()> {
    let fixture = TestFixture::new()?;
    
    // Create only files without traces
    fixture.create_rust_file("normal1.rs", SAMPLE_RUST_CODE)?;
    fixture.create_rust_file("normal2.rs", SAMPLE_RUST_CODE)?;
    
    let result = trace_cli::commands::list_traced::run(fixture.path(), false);
    
    assert!(result.is_ok(), "Should succeed even with no traced files");
    
    Ok(())
}

/// Test listing in empty directory
#[tokio::test]
async fn list_traced_empty_directory() -> Result<()> {
    let fixture = TestFixture::new()?;
    
    let result = trace_cli::commands::list_traced::run(fixture.path(), false);
    
    assert!(result.is_ok(), "Should succeed with empty directory");
    
    Ok(())
}

/// Test error handling for missing directory
#[tokio::test]
async fn list_traced_missing_directory() -> Result<()> {
    let fixture = TestFixture::new()?;
    let missing_dir = fixture.path().join("missing");
    
    let result = trace_cli::commands::list_traced::run(&missing_dir, false);
    
    assert!(result.is_err(), "Should fail for missing directory");
    assert!(result.unwrap_err().to_string().contains("does not exist"), 
            "Error should mention directory doesn't exist");
    
    Ok(())
}

/// Test listing with mixed file types (should ignore non-Rust files)
#[tokio::test]
async fn list_traced_mixed_files() -> Result<()> {
    let fixture = TestFixture::new()?;
    
    // Create various file types
    fixture.create_rust_file("traced.rs", TRACED_RUST_CODE)?;
    fixture.create_rust_file("normal.rs", SAMPLE_RUST_CODE)?;
    
    // Create non-Rust files (should be ignored)
    let txt_content = "This is a text file";
    fs::write(fixture.path().join("readme.txt"), txt_content)?;
    
    let result = trace_cli::commands::list_traced::run(fixture.path(), false);
    
    assert!(result.is_ok(), "Should handle mixed file types");
    
    Ok(())
} 