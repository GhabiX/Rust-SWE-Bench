//! Common test utilities and fixtures for trace_cli integration tests
//! 
//! This module provides shared test infrastructure including:
//! - Temporary directory management
//! - Sample Rust code and Cargo.toml templates
//! - File creation and reading utilities

use std::fs;
use std::path::Path;
use tempfile::TempDir;
use anyhow::Result;

/// Test fixture providing temporary directory and file operations
pub struct TestFixture {
    pub temp_dir: TempDir,
}

impl TestFixture {
    /// Create a new test fixture with temporary directory
    pub fn new() -> Result<Self> {
        let temp_dir = TempDir::new()?;
        Ok(Self { temp_dir })
    }

    /// Get path to the temporary directory
    pub fn path(&self) -> &Path {
        self.temp_dir.path()
    }

    /// Create a Rust source file with given content
    #[allow(dead_code)]
    pub fn create_rust_file(&self, name: &str, content: &str) -> Result<std::path::PathBuf> {
        let file_path = self.path().join(name);
        if let Some(parent) = file_path.parent() {
            fs::create_dir_all(parent)?;
        }
        fs::write(&file_path, content)?;
        Ok(file_path)
    }

    /// Create a Cargo.toml file with given content
    #[allow(dead_code)]
    pub fn create_cargo_toml(&self, content: &str) -> Result<std::path::PathBuf> {
        let cargo_path = self.path().join("Cargo.toml");
        fs::write(&cargo_path, content)?;
        Ok(cargo_path)
    }

    /// Read file content from the temporary directory
    #[allow(dead_code)]
    pub fn read_file(&self, name: &str) -> Result<String> {
        let file_path = self.path().join(name);
        Ok(fs::read_to_string(file_path)?)
    }

    /// Create a directory structure for testing
    #[allow(dead_code)]
    pub fn create_dir(&self, path: &str) -> Result<std::path::PathBuf> {
        let dir_path = self.path().join(path);
        fs::create_dir_all(&dir_path)?;
        Ok(dir_path)
    }
}

/// Sample Rust code without any tracing instrumentation
#[allow(dead_code)]
pub const SAMPLE_RUST_CODE: &str = r#"
fn simple_function(x: i32) -> i32 {
    x + 1
}

impl SomeStruct {
    fn method(&self, data: &str) -> String {
        format!("processed: {}", data)
    }
}

async fn async_function(items: Vec<String>) -> usize {
    items.len()
}

pub fn public_function() {
    println!("Hello");
}
"#;

/// Sample Rust code with existing tracing instrumentation
#[allow(dead_code)]
pub const TRACED_RUST_CODE: &str = r#"
use trace_runtime::trace_macro::rustforger_trace;

#[rustforger_trace]
fn traced_function(x: i32) -> i32 {
    x + 1
}

impl SomeStruct {
    #[rustforger_trace]
    fn traced_method(&self, data: &str) -> String {
        format!("processed: {}", data)
    }

    fn normal_method(&self) -> bool {
        true
    }
}

fn normal_function() {
    println!("not traced");
}
"#;

/// Basic Cargo.toml template for testing
#[allow(dead_code)]
pub const SAMPLE_CARGO_TOML: &str = r#"
[package]
name = "test-project"
version = "0.1.0"
edition = "2021"

[dependencies]
serde = "1.0"
"#;

/// Cargo.toml template with trace dependencies already configured
#[allow(dead_code)]
pub const CARGO_TOML_WITH_TRACE: &str = r#"
[package]
name = "test-project"
version = "0.1.0"
edition = "2021"

[dependencies]
serde = "1.0"
serde_json = "1.0"
trace_runtime = { path = "../trace_runtime" }
trace_common = { path = "../trace_common" }
"#; 