pub mod commands;
pub mod utils;

// Re-export main command modules for library usage
pub use commands::{instrument, revert, list_traced, setup};

// Re-export common types and utilities
pub use utils::config::PropagationConfig;
pub use utils::cargo::{DependencyStats, DependencyType};

// Common result type for the library
pub type Result<T> = anyhow::Result<T>; 