//! Tests for project setup functionality

use anyhow::Result;
use std::fs;
use std::path::PathBuf;

mod common;
use common::{TestFixture, SAMPLE_CARGO_TOML};

/// Create a mock trace tool directory structure for testing
fn create_mock_trace_tool(fixture: &TestFixture) -> Result<PathBuf> {
    let trace_tool_path = fixture.path().join("trace_tool");
    
    // Create the required directories
    fs::create_dir_all(trace_tool_path.join("trace_runtime"))?;
    fs::create_dir_all(trace_tool_path.join("trace_macro"))?;
    fs::create_dir_all(trace_tool_path.join("trace_common"))?;
    
    // Create placeholder Cargo.toml files
    for component in ["trace_runtime", "trace_macro", "trace_common"] {
        let cargo_toml = format!(r#"
[package]
name = "{}"
version = "0.1.0"
edition = "2021"
"#, component);
        fs::write(trace_tool_path.join(component).join("Cargo.toml"), cargo_toml)?;
    }
    
    // Create workspace Cargo.toml (required by validate_trace_tool_path)
    let workspace_cargo = r#"
[workspace]
resolver = "2"
members = [
    "trace_common",
    "trace_macro", 
    "trace_runtime"
]

[workspace.package]
version = "0.1.0"
edition = "2021"
"#;
    fs::write(trace_tool_path.join("Cargo.toml"), workspace_cargo)?;
    
    Ok(trace_tool_path)
}

/// Test basic setup with explicit trace tool path
#[tokio::test]
async fn setup_with_explicit_path() -> Result<()> {
    let fixture = TestFixture::new()?;
    
    // Create project
    fixture.create_cargo_toml(SAMPLE_CARGO_TOML)?;
    
    // Create mock trace tool
    let trace_tool_path = create_mock_trace_tool(&fixture)?;
    
    // Run setup command
    let result = trace_cli::commands::setup::run(
        fixture.path(), 
        Some(&trace_tool_path), 
        false,
        None,
        false
    );
    
    assert!(result.is_ok(), "Setup should succeed with explicit path");
    
    // Verify dependencies were added
    let cargo_content = fixture.read_file("Cargo.toml")?;
    assert!(cargo_content.contains("trace_runtime"), "Should add trace_runtime dependency");
    assert!(cargo_content.contains("trace_common"), "Should add trace_common dependency");
    
    Ok(())
}

/// Test setup with force overwrite of existing dependencies
#[tokio::test]
async fn setup_force_overwrite() -> Result<()> {
    let fixture = TestFixture::new()?;
    
    // Create project with existing trace dependencies
    let existing_cargo = r#"
[package]
name = "test-project"
version = "0.1.0"
edition = "2021"

[dependencies]
trace_runtime = { path = "old/path" }
serde = "1.0"
"#;
    fixture.create_cargo_toml(existing_cargo)?;
    
    let trace_tool_path = create_mock_trace_tool(&fixture)?;
    
    // Run setup with force flag
    let result = trace_cli::commands::setup::run(
        fixture.path(), 
        Some(&trace_tool_path), 
        true,
        None,
        false
    );
    
    assert!(result.is_ok(), "Setup should succeed with force flag");
    
    let cargo_content = fixture.read_file("Cargo.toml")?;
    assert!(cargo_content.contains("trace_tool/trace_runtime"), 
            "Should update dependency path");
    
    Ok(())
}

/// Test setup skipping existing dependencies
#[tokio::test]
async fn setup_skip_existing() -> Result<()> {
    let fixture = TestFixture::new()?;
    
    let existing_cargo = r#"
[package]
name = "test-project"
version = "0.1.0"
edition = "2021"

[dependencies]
trace_runtime = { path = "existing/path" }
"#;
    fixture.create_cargo_toml(existing_cargo)?;
    
    let trace_tool_path = create_mock_trace_tool(&fixture)?;
    
    // Run setup without force flag
    let result = trace_cli::commands::setup::run(
        fixture.path(), 
        Some(&trace_tool_path), 
        false,
        None,
        false
    );
    
    assert!(result.is_ok(), "Setup should succeed and skip existing dependencies");
    
    let cargo_content = fixture.read_file("Cargo.toml")?;
    assert!(cargo_content.contains("existing/path"), 
            "Should preserve existing dependency path");
    
    Ok(())
}

/// Test setup with propagation configuration enabled
#[tokio::test]
async fn setup_with_propagation() -> Result<()> {
    let fixture = TestFixture::new()?;
    
    fixture.create_cargo_toml(SAMPLE_CARGO_TOML)?;
    let trace_tool_path = create_mock_trace_tool(&fixture)?;
    
    // Run setup with propagation enabled
    let result = trace_cli::commands::setup::run(
        fixture.path(), 
        Some(&trace_tool_path), 
        false,
        None,
        true
    );
    
    assert!(result.is_ok(), "Setup with propagation should succeed");
    
    // Verify trace config file was created with propagation
    let config_content = fixture.read_file("src/trace_config.rs")?;
    assert!(config_content.contains("Enabled: true"), "Should enable propagation");
    
    Ok(())
}

/// Test error handling for missing Cargo.toml
#[tokio::test]
async fn setup_missing_cargo_toml() -> Result<()> {
    let fixture = TestFixture::new()?;
    
    let trace_tool_path = create_mock_trace_tool(&fixture)?;
    
    let result = trace_cli::commands::setup::run(
        fixture.path(), 
        Some(&trace_tool_path), 
        false,
        None,
        false
    );
    
    assert!(result.is_err(), "Should fail when Cargo.toml is missing");
    assert!(result.unwrap_err().to_string().contains("Could not find Cargo.toml"), 
            "Error should mention missing Cargo.toml");
    
    Ok(())
}

/// Test error handling for invalid trace tool path
#[tokio::test]
async fn setup_invalid_trace_tool_path() -> Result<()> {
    let fixture = TestFixture::new()?;
    
    fixture.create_cargo_toml(SAMPLE_CARGO_TOML)?;
    
    // Use non-existent path
    let invalid_path = fixture.path().join("invalid");
    
    let result = trace_cli::commands::setup::run(
        fixture.path(), 
        Some(&invalid_path), 
        false,
        None,
        false
    );
    
    assert!(result.is_err(), "Should fail with invalid trace tool path");
    
    Ok(())
}

/// Test error handling for incomplete trace tool structure
#[tokio::test]
async fn setup_incomplete_trace_tool() -> Result<()> {
    let fixture = TestFixture::new()?;
    
    fixture.create_cargo_toml(SAMPLE_CARGO_TOML)?;
    
    // Create incomplete trace tool (missing trace_common)
    let trace_tool_path = fixture.path().join("incomplete_trace_tool");
    fs::create_dir_all(trace_tool_path.join("trace_runtime"))?;
    fs::create_dir_all(trace_tool_path.join("trace_macro"))?;
    // Missing trace_common
    
    let result = trace_cli::commands::setup::run(
        fixture.path(), 
        Some(&trace_tool_path), 
        false,
        None,
        false
    );
    
    assert!(result.is_err(), "Should fail with incomplete trace tool");
    assert!(result.unwrap_err().to_string().contains("Missing required component"), 
            "Error should mention missing component");
    
    Ok(())
} 