//! Tests for trace reversion functionality

use anyhow::Result;

mod common;
use common::{TestFixture, TRACED_RUST_CODE};

/// Test reverting traces from a single file
#[tokio::test]
async fn revert_single_file() -> Result<()> {
    let fixture = TestFixture::new()?;
    
    let rust_file = fixture.create_rust_file("lib.rs", TRACED_RUST_CODE)?;
    
    // Run revert command
    let result = trace_cli::commands::revert::run(&rust_file);
    
    assert!(result.is_ok(), "Revert should succeed");
    
    // Verify traces were removed
    let content = fixture.read_file("lib.rs")?;
    assert!(!content.contains("#[rustforger_trace]"), "Should not contain trace attributes");
    assert!(!content.contains("use trace_runtime::trace_macro::rustforger_trace"), 
            "Should not contain trace use statement");
    
    Ok(())
}

/// Test reverting traces from an entire directory
#[tokio::test]
async fn revert_directory() -> Result<()> {
    let fixture = TestFixture::new()?;
    
    // Create multiple Rust files with traces
    fixture.create_rust_file("lib.rs", TRACED_RUST_CODE)?;
    fixture.create_rust_file("main.rs", TRACED_RUST_CODE)?;
    
    // Create subdirectory
    fixture.create_dir("src")?;
    fixture.create_rust_file("src/module.rs", TRACED_RUST_CODE)?;
    
    // Run revert on directory
    let result = trace_cli::commands::revert::run(fixture.path());
    
    assert!(result.is_ok(), "Directory revert should succeed");
    
    // Verify all files were reverted
    for file in ["lib.rs", "main.rs", "src/module.rs"] {
        let content = fixture.read_file(file)?;
        assert!(!content.contains("#[rustforger_trace]"), 
                "File {} should not contain trace attributes", file);
    }
    
    Ok(())
}

/// Test reverting files with no traces (should succeed gracefully)
#[tokio::test]
async fn revert_no_traces() -> Result<()> {
    let fixture = TestFixture::new()?;
    
    let clean_code = r#"
fn normal_function() -> i32 {
    42
}
"#;
    
    let rust_file = fixture.create_rust_file("lib.rs", clean_code)?;
    
    // Should succeed even with no traces
    let result = trace_cli::commands::revert::run(&rust_file);
    
    assert!(result.is_ok(), "Should succeed even with no traces to revert");
    
    Ok(())
}

/// Test reverting files with mixed attributes (preserve non-trace attributes)
#[tokio::test]
async fn revert_mixed_attributes() -> Result<()> {
    let fixture = TestFixture::new()?;
    
    let mixed_code = r#"
use trace_runtime::trace_macro::rustforger_trace;

#[rustforger_trace]
fn traced_function() -> i32 {
    42
}

#[derive(Debug)]
fn normal_function_with_other_attr() -> String {
    "test".to_string()
}
"#;
    
    let rust_file = fixture.create_rust_file("lib.rs", mixed_code)?;
    
    let result = trace_cli::commands::revert::run(&rust_file);
    
    assert!(result.is_ok(), "Should handle mixed attributes");
    
    let content = fixture.read_file("lib.rs")?;
    assert!(!content.contains("#[rustforger_trace]"), "Should remove trace attributes");
    assert!(content.contains("#[derive(Debug)]"), "Should preserve other attributes");
    
    Ok(())
}

/// Test error handling for missing files
#[tokio::test]
async fn revert_missing_file() -> Result<()> {
    let fixture = TestFixture::new()?;
    let missing_file = fixture.path().join("missing.rs");
    
    let result = trace_cli::commands::revert::run(&missing_file);
    
    assert!(result.is_err(), "Should fail for missing file");
    assert!(result.unwrap_err().to_string().contains("does not exist"), 
            "Error should mention file doesn't exist");
    
    Ok(())
} 