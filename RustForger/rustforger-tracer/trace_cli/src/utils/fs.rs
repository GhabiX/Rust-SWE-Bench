use anyhow::Result;
use std::path::{Path, PathBuf};
use std::fs;

/// Find the project's Cargo.toml file by traversing up the directory tree
pub fn find_cargo_toml(start_path: &Path) -> Result<PathBuf> {
    let mut current = if start_path.is_file() {
        start_path.parent().unwrap_or(start_path)
    } else {
        start_path
    };

    loop {
        let cargo_toml = current.join("Cargo.toml");
        if cargo_toml.exists() {
            return Ok(cargo_toml);
        }

        current = current.parent()
            .ok_or_else(|| anyhow::anyhow!("Could not find Cargo.toml file in {} or its parent directories", 
                                          start_path.display()))?;
    }
}

/// Find the project root directory (where Cargo.toml is located)
pub fn find_project_root(start_path: &Path) -> Result<PathBuf> {
    let mut current = if start_path.is_file() {
        start_path.parent().unwrap_or(start_path)
    } else {
        start_path
    };

    loop {
        let cargo_toml = current.join("Cargo.toml");
        if cargo_toml.exists() {
            return Ok(current.to_path_buf());
        }

        current = current.parent()
            .ok_or_else(|| anyhow::anyhow!("Could not find project root (Cargo.toml)"))?;
    }
}

/// Check if file is a Rust source file
pub fn is_rust_file(path: &Path) -> bool {
    path.extension().map_or(false, |ext| ext == "rs")
}

/// Check if directory should be skipped during traversal
pub fn should_skip_directory(path: &Path) -> bool {
    path.file_name()
        .and_then(|name| name.to_str())
        .map_or(false, |name| {
            matches!(name, "target" | ".git" | "node_modules" | ".vscode")
        })
}

/// Visit all Rust files in directory recursively
pub fn visit_rust_files<F>(dir: &Path, processor: &mut F) -> Result<()>
where
    F: FnMut(&Path) -> Result<()>,
{
    for entry in fs::read_dir(dir)? {
        let entry = entry?;
        let path = entry.path();
        
        if path.is_dir() {
            if should_skip_directory(&path) {
                continue;
            }
            visit_rust_files(&path, processor)?;
        } else if is_rust_file(&path) {
            processor(&path)?;
        }
    }
    Ok(())
} 