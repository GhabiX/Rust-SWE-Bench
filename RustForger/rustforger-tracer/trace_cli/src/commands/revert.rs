use anyhow::{Context, Result, ensure};
use std::path::Path;
use std::fs;
use syn::{parse_file, visit_mut::VisitMut, ItemFn, ItemImpl, Attribute, Item};
use quote::ToTokens;
use prettyplease::unparse;

use crate::utils::fs::visit_rust_files;

/// Remove tracing instrumentation from files
pub fn run(target_path: &Path) -> Result<()> {
    ensure!(target_path.exists(), "Path does not exist: {}", target_path.display());
    
    let mut stats = ProcessingStats::default();
    
    if target_path.is_file() {
        process_single_file(target_path, &mut stats)?;
    } else {
        process_directory(target_path, &mut stats)?;
    }
    
    // Print summary
    println!("processed {} files, reverted {} files", stats.total_files, stats.reverted_files);
    
    Ok(())
}

#[derive(Default)]
struct ProcessingStats {
    total_files: usize,
    reverted_files: usize,
}

/// Process a directory recursively
fn process_directory(dir_path: &Path, stats: &mut ProcessingStats) -> Result<()> {
    let mut file_processor = |file_path: &Path| -> Result<()> {
        stats.total_files += 1;
        if let Err(e) = process_single_file(file_path, stats) {
            eprintln!("warning: failed to process {}: {}", file_path.display(), e);
        }
        Ok(())
    };
    
    visit_rust_files(dir_path, &mut file_processor)
}

/// Process a single file
fn process_single_file(file_path: &Path, stats: &mut ProcessingStats) -> Result<()> {
    let source_code = fs::read_to_string(file_path)
        .with_context(|| format!("Failed to read file: {}", file_path.display()))?;
    
    let mut syntax_tree = parse_file(&source_code)
        .context("Failed to parse Rust source code")?;
    
    let mut reverter = TraceReverter::new();
    reverter.visit_file_mut(&mut syntax_tree);
    
    if reverter.modified {
        let formatted_code = unparse(&syntax_tree);
        fs::write(file_path, formatted_code)
            .with_context(|| format!("Failed to write modified code to: {}", file_path.display()))?;
        
        stats.reverted_files += 1;
    }
    
    Ok(())
}

/// Visitor to remove trace attributes
struct TraceReverter {
    modified: bool,
}

impl TraceReverter {
    fn new() -> Self {
        Self { modified: false }
    }
    
    /// Remove trace attributes from attribute list
    fn remove_trace_attributes(&mut self, attrs: &mut Vec<Attribute>) {
        let original_len = attrs.len();
        attrs.retain(|attr| {
            !attr.path().is_ident("rustforger_trace") && !attr.path().is_ident("trace")
        });
        
        if attrs.len() != original_len {
            self.modified = true;
        }
    }
}

impl VisitMut for TraceReverter {
    fn visit_item_fn_mut(&mut self, node: &mut ItemFn) {
        self.remove_trace_attributes(&mut node.attrs);
        syn::visit_mut::visit_item_fn_mut(self, node);
    }

    fn visit_item_impl_mut(&mut self, node: &mut ItemImpl) {
        for item in &mut node.items {
            if let syn::ImplItem::Fn(method) = item {
                self.remove_trace_attributes(&mut method.attrs);
            }
        }
        syn::visit_mut::visit_item_impl_mut(self, node);
    }
    
    fn visit_file_mut(&mut self, node: &mut syn::File) {
        // Remove trace-related use statements
        node.items.retain(|item| {
            if let Item::Use(use_item) = item {
                let use_str = use_item.tree.to_token_stream().to_string();
                let should_remove = use_str.contains("trace_runtime") || use_str.contains("rustforger_trace");
                if should_remove {
                    self.modified = true;
                }
                !should_remove
            } else {
                true
            }
        });
        
        // Continue with regular visit
        syn::visit_mut::visit_file_mut(self, node);
    }
} 