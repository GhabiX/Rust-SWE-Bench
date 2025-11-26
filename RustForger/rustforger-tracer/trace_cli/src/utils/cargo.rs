use anyhow::{Context, Result};
use std::path::Path;
use std::fs;

/// Dependency type for Cargo.toml entries
#[derive(Debug, Clone)]
pub enum DependencyType<'a> {
    Path(&'a Path),
    Version(&'a str),
}

/// Statistics for dependency operations
#[derive(Debug, Default)]
pub struct DependencyStats {
    pub added: Vec<String>,
    pub skipped: Vec<String>,
}

impl DependencyStats {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn add_added(&mut self, name: String) {
        self.added.push(name);
    }

    pub fn add_skipped(&mut self, name: String) {
        self.skipped.push(name);
    }
}

/// Check if a dependency already exists in Cargo.toml
pub fn dependency_exists(doc: &toml_edit::Document, dep_name: &str) -> bool {
    doc.get("dependencies")
        .and_then(|deps| deps.as_table())
        .map(|table| table.contains_key(dep_name))
        .unwrap_or(false)
}

/// Ensure that the [dependencies] section exists in Cargo.toml
pub fn ensure_dependencies_section(doc: &mut toml_edit::Document) {
    if doc.get("dependencies").is_none() {
        doc["dependencies"] = toml_edit::table();
    }
}

/// Add a dependency to Cargo.toml
pub fn add_dependency(doc: &mut toml_edit::Document, name: &str, dep_type: DependencyType) {
    let dep_value = match dep_type {
        DependencyType::Path(path) => {
            let mut dep_table = toml_edit::InlineTable::new();
            let path_str = if path.is_absolute() {
                path.to_string_lossy().into_owned()
            } else {
                path.to_string_lossy().replace("\\", "/")
            };
            dep_table.insert("path", path_str.as_str().into());
            toml_edit::value(dep_table)
        }
        DependencyType::Version(version) => {
            toml_edit::value(version)
        }
    };
    
    doc["dependencies"][name] = dep_value;
}

/// Update Cargo.toml with given dependencies
pub fn update_cargo_toml_with_deps(
    cargo_toml_path: &Path,
    dependencies: &[(&str, DependencyType)],
    force: bool,
) -> Result<DependencyStats> {
    let cargo_content = fs::read_to_string(cargo_toml_path)
        .with_context(|| format!("Failed to read Cargo.toml: {}", cargo_toml_path.display()))?;

    let mut doc = cargo_content.parse::<toml_edit::Document>()
        .context("Failed to parse Cargo.toml")?;

    ensure_dependencies_section(&mut doc);
    let mut stats = DependencyStats::new();

    for (dep_name, dep_type) in dependencies {
        if dependency_exists(&doc, dep_name) && !force {
            stats.add_skipped(dep_name.to_string());
        } else {
            add_dependency(&mut doc, dep_name, dep_type.clone());
            stats.add_added(dep_name.to_string());
        }
    }

    fs::write(cargo_toml_path, doc.to_string())
        .with_context(|| format!("Failed to write Cargo.toml: {}", cargo_toml_path.display()))?;

    Ok(stats)
}

/// Display dependency operation summary
pub fn display_dependency_summary(stats: &DependencyStats) {
    // Only show summary if there were actual changes
    if !stats.added.is_empty() || !stats.skipped.is_empty() {
        eprintln!("dependency summary:");
        eprintln!("  added: {}", stats.added.len());
        eprintln!("  skipped: {}", stats.skipped.len());
        
        // if !stats.skipped.is_empty() {
        //     eprintln!("note: use --force to overwrite existing dependencies");
        // }
    }
}

/// Remove a dependency from Cargo.toml
pub fn remove_dependency(doc: &mut toml_edit::Document, name: &str) -> bool {
    if let Some(deps) = doc.get_mut("dependencies").and_then(|d| d.as_table_mut()) {
        if deps.contains_key(name) {
            deps.remove(name);
            return true;
        }
    }
    false
}

/// Remove trace-related dependencies from Cargo.toml
pub fn remove_dependencies_from_cargo_toml(cargo_toml_path: &Path) -> Result<DependencyStats> {
    let cargo_content = fs::read_to_string(cargo_toml_path)
        .with_context(|| format!("Failed to read Cargo.toml: {}", cargo_toml_path.display()))?;

    let mut doc = cargo_content.parse::<toml_edit::Document>()
        .context("Failed to parse Cargo.toml")?;

    let mut stats = DependencyStats::new();
    let trace_dependencies = ["trace_runtime", "trace_common", "serde_json"];

    for dep_name in &trace_dependencies {
        if remove_dependency(&mut doc, dep_name) {
            stats.add_added(dep_name.to_string()); // Reusing 'added' field for 'removed'
        } else {
            stats.add_skipped(dep_name.to_string());
        }
    }

    fs::write(cargo_toml_path, doc.to_string())
        .with_context(|| format!("Failed to write Cargo.toml: {}", cargo_toml_path.display()))?;

    Ok(stats)
}

/// Display dependency removal summary
pub fn display_removal_summary(stats: &DependencyStats) {
    eprintln!("dependency removal summary:");
    eprintln!("  removed: {}", stats.added.len()); // Reusing 'added' field for 'removed'
    eprintln!("  not found: {}", stats.skipped.len());
} 