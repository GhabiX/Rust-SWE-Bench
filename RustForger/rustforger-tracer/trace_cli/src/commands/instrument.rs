use anyhow::{Context, Result, ensure};
use std::path::Path;
use std::fs;
use syn::{parse_file, visit_mut::VisitMut, ItemFn, ItemImpl, Attribute, Item};
use quote::ToTokens;
use prettyplease::unparse;

use crate::utils::fs::{find_cargo_toml, find_project_root};
use crate::utils::cargo::{DependencyType, update_cargo_toml_with_deps};
use crate::utils::config::{PropagationConfig, create_trace_config_file};

/// Function specification that can handle both simple names and qualified paths
#[derive(Debug, Clone)]
struct FunctionSpec {
    /// Type name (optional): CollectLifetimes, self, super::Type
    pub type_name: Option<String>,
    /// Method name: visit_path_mut
    pub method_name: String,
    /// Original input for debugging
    pub original_input: String,
}

impl FunctionSpec {
    /// Parse function specification from input string
    /// Supports formats like:
    /// - "visit_path_mut" (simple function name)
    /// - "CollectLifetimes::visit_path_mut" (qualified method name)
    /// - "std::collections::HashMap::new" (fully qualified path)
    fn parse(input: &str) -> Self {
        if let Some(last_colon) = input.rfind("::") {
            // Has type prefix: CollectLifetimes::visit_path_mut
            Self {
                type_name: Some(input[..last_colon].to_string()),
                method_name: input[last_colon + 2..].to_string(),
                original_input: input.to_string(),
            }
        } else {
            // No type prefix: visit_path_mut
            Self {
                type_name: None,
                method_name: input.to_string(),
                original_input: input.to_string(),
            }
        }
    }
    
    /// Check if this spec matches a simple function name
    fn matches_function_name(&self, name: &syn::Ident) -> bool {
        name.to_string() == self.method_name
    }
    
    /// Check if this spec matches a method in an impl block
    fn matches_impl_method(&self, impl_type: &syn::Type, method_name: &syn::Ident) -> bool {
        // Method name must match
        if method_name.to_string() != self.method_name {
            return false;
        }
        
        // If no type specified, match any impl block
        let Some(expected_type) = &self.type_name else {
            return true;
        };
        
        // Extract type name and compare
        let actual_type = extract_type_name(impl_type);
        actual_type == *expected_type
    }
}

/// Extract type name from syn::Type for matching purposes
/// Handles various type formats and extracts the main identifier
fn extract_type_name(ty: &syn::Type) -> String {
    match ty {
        syn::Type::Path(type_path) => {
            // Extract the last segment of the path (e.g., "HashMap" from "std::collections::HashMap")
            if let Some(last_segment) = type_path.path.segments.last() {
                last_segment.ident.to_string()
            } else {
                String::new()
            }
        }
        syn::Type::Reference(type_ref) => {
            // Handle &Type
            extract_type_name(&type_ref.elem)
        }
        syn::Type::Ptr(type_ptr) => {
            // Handle *Type
            extract_type_name(&type_ptr.elem)
        }
        _ => {
            // For other complex types, convert to string and try to extract identifier
            let type_str = quote::quote!(#ty).to_string();
            // Simple heuristic: take the last identifier-like token
            type_str.split(&[' ', '<', '>', ':'])
                .filter(|s| !s.is_empty() && s.chars().all(|c| c.is_alphanumeric() || c == '_'))
                .last()
                .unwrap_or("")
                .to_string()
        }
    }
}

/// Add tracing instrumentation to specified function
pub fn run(
    file_path: &Path, 
    function_name: &str, 
    trace_output: Option<&Path>,
    propagation_config: Option<PropagationConfig>
) -> Result<()> {
    ensure!(file_path.exists(), "File does not exist: {}", file_path.display());
    
    let source_code = fs::read_to_string(file_path)
        .with_context(|| format!("Failed to read file: {}", file_path.display()))?;
    
    let mut syntax_tree = parse_file(&source_code)
        .context("Failed to parse Rust source code")?;
    
    ensure_trace_imports(&mut syntax_tree);
    
    let mut instrumenter = FunctionInstrumenter::new(function_name, propagation_config.clone());
    instrumenter.visit_file_mut(&mut syntax_tree);
    
    ensure!(instrumenter.found_function, 
        "Function '{}' not found in file\n\n{}", 
        function_name,
        generate_function_suggestions_with_similarity(&syntax_tree, function_name)
    );
    
    let formatted_code = unparse(&syntax_tree);
    fs::write(file_path, formatted_code)
        .with_context(|| format!("Failed to write modified code to: {}", file_path.display()))?;
    
    add_dependencies_to_cargo_toml(file_path)?;
    
    let project_root = find_project_root(file_path)?;
    create_trace_config_file(&project_root, trace_output, propagation_config.as_ref())?;
    
    println!("instrumented function '{}' in {}", function_name, file_path.display());
    Ok(())
}

/// Add tracing instrumentation to multiple specified functions
pub fn run_multiple(
    file_path: &Path, 
    function_names: &[String], 
    trace_output: Option<&Path>,
    propagation_config: Option<PropagationConfig>
) -> Result<()> {
    ensure!(file_path.exists(), "File does not exist: {}", file_path.display());
    ensure!(!function_names.is_empty(), "No function names provided");
    
    let source_code = fs::read_to_string(file_path)
        .with_context(|| format!("Failed to read file: {}", file_path.display()))?;
    
    let mut syntax_tree = parse_file(&source_code)
        .context("Failed to parse Rust source code")?;
    
    ensure_trace_imports(&mut syntax_tree);
    
    let mut instrumenter = MultipleFunctionInstrumenter::new(function_names, propagation_config.clone());
    instrumenter.visit_file_mut(&mut syntax_tree);
    
    // Check which functions were found and report any missing ones
    let missing_functions: Vec<_> = instrumenter.missing_functions();
    if !missing_functions.is_empty() {
        // For multiple missing functions, use the first one for similarity matching
        let primary_missing = missing_functions.first().unwrap();
        anyhow::bail!(
            "Functions not found in file: {:?}\n\n{}", 
            missing_functions,
            generate_function_suggestions_with_similarity(&syntax_tree, primary_missing)
        );
    }
    
    let formatted_code = unparse(&syntax_tree);
    fs::write(file_path, formatted_code)
        .with_context(|| format!("Failed to write modified code to: {}", file_path.display()))?;
    
    add_dependencies_to_cargo_toml(file_path)?;
    
    let project_root = find_project_root(file_path)?;
    create_trace_config_file(&project_root, trace_output, propagation_config.as_ref())?;
    
    println!("instrumented {} function(s) in {}: {:?}", 
             instrumenter.instrumented_count, 
             file_path.display(), 
             instrumenter.instrumented_functions());
    Ok(())
}

/// Add tracing instrumentation to all functions in a file
pub fn run_all(
    file_path: &Path, 
    trace_output: Option<&Path>,
    propagation_config: Option<PropagationConfig>
) -> Result<()> {
    ensure!(file_path.exists(), "File does not exist: {}", file_path.display());
    
    let source_code = fs::read_to_string(file_path)
        .with_context(|| format!("Failed to read file: {}", file_path.display()))?;
    
    let mut syntax_tree = parse_file(&source_code)
        .context("Failed to parse Rust source code")?;
    
    ensure_trace_imports(&mut syntax_tree);
    
    let mut instrumenter = AllFunctionInstrumenter::new(propagation_config.clone());
    instrumenter.visit_file_mut(&mut syntax_tree);
    
    let formatted_code = unparse(&syntax_tree);
    fs::write(file_path, formatted_code)
        .with_context(|| format!("Failed to write modified code to: {}", file_path.display()))?;
    
    add_dependencies_to_cargo_toml(file_path)?;
    
    let project_root = find_project_root(file_path)?;
    create_trace_config_file(&project_root, trace_output, propagation_config.as_ref())?;
    
    println!("instrumented {} functions in {}", instrumenter.instrumented_count, file_path.display());
    Ok(())
}

/// Ensure necessary use statements are present
fn ensure_trace_imports(syntax_tree: &mut syn::File) {
    let has_trace_import = syntax_tree.items.iter().any(|item| {
        if let Item::Use(use_item) = item {
            use_item.tree.to_token_stream().to_string().contains("trace_runtime")
        } else {
            false
        }
    });
    
    if !has_trace_import {
        let use_statement: syn::ItemUse = syn::parse_quote! {
            use trace_runtime::trace_macro::rustforger_trace;
        };
        syntax_tree.items.insert(0, Item::Use(use_statement));
    }
}

/// Function instrumenter visitor for single function
struct FunctionInstrumenter {
    target_spec: FunctionSpec,
    found_function: bool,
    propagation_config: Option<PropagationConfig>,
}

impl FunctionInstrumenter {
    fn new(target_function: &str, propagation_config: Option<PropagationConfig>) -> Self {
        Self {
            target_spec: FunctionSpec::parse(target_function),
            found_function: false,
            propagation_config,
        }
    }
    
    /// Check if function name matches target (for standalone functions)
    fn is_target_function(&self, name: &syn::Ident) -> bool {
        // Only match standalone functions if no type is specified
        self.target_spec.type_name.is_none() && self.target_spec.matches_function_name(name)
    }
    
    /// Check if method in impl block matches target
    fn is_target_impl_method(&self, impl_type: &syn::Type, method_name: &syn::Ident) -> bool {
        self.target_spec.matches_impl_method(impl_type, method_name)
    }
}

impl VisitMut for FunctionInstrumenter {
    fn visit_item_fn_mut(&mut self, node: &mut ItemFn) {
        if self.is_target_function(&node.sig.ident) {
            self.found_function = true;
            add_trace_attribute(&mut node.attrs, &self.propagation_config);
        }
        syn::visit_mut::visit_item_fn_mut(self, node);
    }

    fn visit_item_impl_mut(&mut self, node: &mut ItemImpl) {
        for item in &mut node.items {
            if let syn::ImplItem::Fn(method) = item {
                if self.is_target_impl_method(&node.self_ty, &method.sig.ident) {
                    self.found_function = true;
                    add_trace_attribute(&mut method.attrs, &self.propagation_config);
                }
            }
        }
        syn::visit_mut::visit_item_impl_mut(self, node);
    }
}

/// All function instrumenter visitor
struct AllFunctionInstrumenter {
    propagation_config: Option<PropagationConfig>,
    instrumented_count: usize,
}

impl AllFunctionInstrumenter {
    fn new(propagation_config: Option<PropagationConfig>) -> Self {
        Self {
            propagation_config,
            instrumented_count: 0,
        }
    }
    
    /// Check if function should be instrumented (skip test functions and other special cases)
    fn should_instrument_function(&self, node: &ItemFn) -> bool {
        let function_name = node.sig.ident.to_string();
        
        // Skip test functions
        if node.attrs.iter().any(|attr| attr.path().is_ident("test")) {
            return false;
        }
        
        // Skip functions that already have trace attributes
        if node.attrs.iter().any(|attr| {
            attr.path().is_ident("rustforger_trace") || attr.path().is_ident("trace")
        }) {
            return false;
        }
        
        // Skip main function (it's usually handled separately)
        if function_name == "main" {
            return false;
        }
        
        // Skip functions starting with underscore (typically private/internal)
        if function_name.starts_with('_') {
            return false;
        }
        
        true
    }
    
    /// Check if method should be instrumented
    fn should_instrument_method(&self, method: &syn::ImplItemFn) -> bool {
        let method_name = method.sig.ident.to_string();
        
        // Skip test methods
        if method.attrs.iter().any(|attr| attr.path().is_ident("test")) {
            return false;
        }
        
        // Skip methods that already have trace attributes
        if method.attrs.iter().any(|attr| {
            attr.path().is_ident("rustforger_trace") || attr.path().is_ident("trace")
        }) {
            return false;
        }
        
        // Skip methods starting with underscore
        if method_name.starts_with('_') {
            return false;
        }
        
        true
    }
}

impl VisitMut for AllFunctionInstrumenter {
    fn visit_item_fn_mut(&mut self, node: &mut ItemFn) {
        if self.should_instrument_function(node) {
            add_trace_attribute(&mut node.attrs, &self.propagation_config);
            self.instrumented_count += 1;
        }
        syn::visit_mut::visit_item_fn_mut(self, node);
    }

    fn visit_item_impl_mut(&mut self, node: &mut ItemImpl) {
        for item in &mut node.items {
            if let syn::ImplItem::Fn(method) = item {
                if self.should_instrument_method(method) {
                    add_trace_attribute(&mut method.attrs, &self.propagation_config);
                    self.instrumented_count += 1;
                }
            }
        }
        syn::visit_mut::visit_item_impl_mut(self, node);
    }
}

/// Add trace attribute to function if not already present
fn add_trace_attribute(attrs: &mut Vec<Attribute>, propagation_config: &Option<PropagationConfig>) {
    let has_trace_attr = attrs.iter().any(|attr| {
        attr.path().is_ident("rustforger_trace") || attr.path().is_ident("trace")
    });
    
    if !has_trace_attr {
        let trace_attr: Attribute = if let Some(config) = propagation_config {
            if config.enabled {
                // Build propagation instrumentation attribute based on configuration
                if config.max_depth.is_some() || !config.exclude_patterns.is_empty() || !config.user_code_only {
                    // Complex configuration - use simplified form for now
                    syn::parse_quote! { #[rustforger_trace(propagate = true)] }
                } else {
                    // Simple propagation instrumentation
                    syn::parse_quote! { #[rustforger_trace(propagate = true)] }
                }
            } else {
                // No propagation, use basic trace
                syn::parse_quote! { #[rustforger_trace] }
            }
        } else {
            // No configuration, use basic trace
            syn::parse_quote! { #[rustforger_trace] }
        };
        
        attrs.push(trace_attr);
    }
}

/// Add required dependencies to Cargo.toml
fn add_dependencies_to_cargo_toml(file_path: &Path) -> Result<()> {
    let cargo_toml_path = find_cargo_toml(file_path)?;
    
    // eprintln!("note: recommend running 'setup' command first to configure dependency paths");
    
    // Add only basic dependencies, path configuration left to setup command
    let basic_deps = [
        ("serde_json", DependencyType::Version("1.0")),
    ];
    
    let _stats = update_cargo_toml_with_deps(&cargo_toml_path, &basic_deps, false)?;
    
    // Check for trace dependencies
    let cargo_content = fs::read_to_string(&cargo_toml_path)?;
    let doc = cargo_content.parse::<toml_edit::Document>()?;
    
    let trace_deps = ["trace_runtime", "trace_common"];
    let missing_trace_deps: Vec<_> = trace_deps.iter()
        .filter(|&dep| !crate::utils::cargo::dependency_exists(&doc, dep))
        .collect();
    
    if !missing_trace_deps.is_empty() {
        eprintln!("warning: missing trace dependencies: {:?}", missing_trace_deps);
        eprintln!("note: run setup command first to configure trace dependencies");
    }
    
    Ok(())
}

/// Multiple function instrumenter visitor for specific functions
struct MultipleFunctionInstrumenter {
    target_specs: Vec<FunctionSpec>,
    found_functions: std::collections::HashSet<String>,
    propagation_config: Option<PropagationConfig>,
    pub instrumented_count: usize,
}

impl MultipleFunctionInstrumenter {
    fn new(target_functions: &[String], propagation_config: Option<PropagationConfig>) -> Self {
        Self {
            target_specs: target_functions.iter().map(|f| FunctionSpec::parse(f)).collect(),
            found_functions: std::collections::HashSet::new(),
            propagation_config,
            instrumented_count: 0,
        }
    }
    
    /// Check if function name matches any target (for standalone functions)
    fn is_target_function(&self, name: &syn::Ident) -> bool {
        self.target_specs.iter().any(|spec| {
            spec.type_name.is_none() && spec.matches_function_name(name)
        })
    }
    
    /// Check if method in impl block matches any target
    fn is_target_impl_method(&self, impl_type: &syn::Type, method_name: &syn::Ident) -> bool {
        self.target_specs.iter().any(|spec| {
            spec.matches_impl_method(impl_type, method_name)
        })
    }
    
    /// Mark function as found and increment counter
    fn mark_function_found(&mut self, name: &syn::Ident) {
        for spec in &self.target_specs {
            if spec.type_name.is_none() && spec.matches_function_name(name) {
                self.found_functions.insert(spec.original_input.clone());
                self.instrumented_count += 1;
                break;
            }
        }
    }
    
    /// Mark impl method as found and increment counter
    fn mark_impl_method_found(&mut self, impl_type: &syn::Type, method_name: &syn::Ident) {
        for spec in &self.target_specs {
            if spec.matches_impl_method(impl_type, method_name) {
                self.found_functions.insert(spec.original_input.clone());
                self.instrumented_count += 1;
                break;
            }
        }
    }
    
    /// Get list of functions that were not found
    pub fn missing_functions(&self) -> Vec<String> {
        self.target_specs
            .iter()
            .filter_map(|spec| {
                if self.found_functions.contains(&spec.original_input) {
                    None
                } else {
                    Some(spec.original_input.clone())
                }
            })
            .collect()
    }
    
    /// Get list of functions that were successfully instrumented
    pub fn instrumented_functions(&self) -> Vec<String> {
        self.found_functions.iter().cloned().collect()
    }
}

impl VisitMut for MultipleFunctionInstrumenter {
    fn visit_item_fn_mut(&mut self, node: &mut ItemFn) {
        if self.is_target_function(&node.sig.ident) {
            self.mark_function_found(&node.sig.ident);
            add_trace_attribute(&mut node.attrs, &self.propagation_config);
        }
        syn::visit_mut::visit_item_fn_mut(self, node);
    }

    fn visit_item_impl_mut(&mut self, node: &mut ItemImpl) {
        for item in &mut node.items {
            if let syn::ImplItem::Fn(method) = item {
                if self.is_target_impl_method(&node.self_ty, &method.sig.ident) {
                    self.mark_impl_method_found(&node.self_ty, &method.sig.ident);
                    add_trace_attribute(&mut method.attrs, &self.propagation_config);
                }
            }
        }
        syn::visit_mut::visit_item_impl_mut(self, node);
    }
} 

/// Function information for suggestion generation
#[derive(Debug, Clone)]
struct AvailableFunction {
    /// Complete function specification (e.g., "CollectLifetimes::new")
    full_name: String,
    /// Function category for grouping in output
    function_type: FunctionCategory,
}

/// Categories of functions for organized display
#[derive(Debug, Clone)]
enum FunctionCategory {
    /// Standalone functions (e.g., "main", "parse_file")
    Standalone,
    /// Methods in impl blocks (e.g., "CollectLifetimes::new")
    ImplMethod { type_name: String },
}

/// AST visitor that collects all available functions in a file
struct FunctionCollector {
    functions: Vec<AvailableFunction>,
}

impl FunctionCollector {
    /// Create a new function collector
    fn new() -> Self {
        Self {
            functions: Vec::new(),
        }
    }
    
    /// Get collected functions, sorted by category and name for consistent output
    fn into_sorted_functions(mut self) -> Vec<AvailableFunction> {
        self.functions.sort_by(|a, b| {
            match (&a.function_type, &b.function_type) {
                (FunctionCategory::Standalone, FunctionCategory::ImplMethod { .. }) => std::cmp::Ordering::Less,
                (FunctionCategory::ImplMethod { .. }, FunctionCategory::Standalone) => std::cmp::Ordering::Greater,
                (FunctionCategory::Standalone, FunctionCategory::Standalone) => a.full_name.cmp(&b.full_name),
                (FunctionCategory::ImplMethod { type_name: a_type }, FunctionCategory::ImplMethod { type_name: b_type }) => {
                    match a_type.cmp(b_type) {
                        std::cmp::Ordering::Equal => a.full_name.cmp(&b.full_name),
                        other => other,
                    }
                }
            }
        });
        self.functions
    }
}

impl syn::visit::Visit<'_> for FunctionCollector {
    fn visit_item_fn(&mut self, node: &syn::ItemFn) {
        // Collect standalone functions (those defined at module level)
        let function_name = node.sig.ident.to_string();
        
        // Skip test functions and other special functions to reduce noise
        let should_skip = node.attrs.iter().any(|attr| {
            attr.path().is_ident("test") || 
            attr.path().is_ident("bench") ||
            attr.path().is_ident("cfg")
        });
        
        if !should_skip {
            self.functions.push(AvailableFunction {
                full_name: function_name,
                function_type: FunctionCategory::Standalone,
            });
        }
        
        // Continue visiting nested items
        syn::visit::visit_item_fn(self, node);
    }

    fn visit_item_impl(&mut self, node: &syn::ItemImpl) {
        // Extract the type name from the impl block
        let type_name = extract_type_name(&node.self_ty);
        
        // Skip empty type names (shouldn't happen with valid Rust code)
        if type_name.is_empty() {
            syn::visit::visit_item_impl(self, node);
            return;
        }
        
        // Collect all methods in this impl block
        for item in &node.items {
            if let syn::ImplItem::Fn(method) = item {
                let method_name = method.sig.ident.to_string();
                
                // Skip test methods and private methods (starting with _) to reduce noise
                let should_skip = method.attrs.iter().any(|attr| {
                    attr.path().is_ident("test") || 
                    attr.path().is_ident("bench") ||
                    attr.path().is_ident("cfg")
                }) || method_name.starts_with('_');
                
                if !should_skip {
                    self.functions.push(AvailableFunction {
                        full_name: format!("{}::{}", type_name, method_name),
                        function_type: FunctionCategory::ImplMethod { 
                            type_name: type_name.clone() 
                        },
                    });
                }
            }
        }
        
        // Continue visiting nested items
        syn::visit::visit_item_impl(self, node);
    }
}

/// Generate helpful function suggestions when user input doesn't match any functions
/// Returns a formatted string listing all available functions organized by category
fn generate_function_suggestions(syntax_tree: &syn::File) -> String {
    let mut collector = FunctionCollector::new();
    syn::visit::visit_file(&mut collector, syntax_tree);
    
    let functions = collector.into_sorted_functions();
    
    if functions.is_empty() {
        return "No public functions found in this file.".to_string();
    }
    
    format_function_list(&functions)
}

/// Calculate similarity score between user input and function name
/// Returns a score from 0.0 (no similarity) to 1.0 (perfect match)
fn calculate_similarity(user_input: &str, function_name: &str) -> f64 {
    // If exact match (case insensitive), return perfect score
    if user_input.to_lowercase() == function_name.to_lowercase() {
        return 1.0;
    }
    
    // Extract method name from qualified names for comparison
    let user_method = user_input.split("::").last().unwrap_or(user_input);
    let func_method = function_name.split("::").last().unwrap_or(function_name);
    
    let mut score = 0.0;
    
    // 1. Exact method name match (case insensitive) - highest priority
    if user_method.to_lowercase() == func_method.to_lowercase() {
        score += 0.8;
    }
    
    // 2. Substring matching - check if user input is contained in function name
    let user_lower = user_input.to_lowercase();
    let func_lower = function_name.to_lowercase();
    if func_lower.contains(&user_lower) {
        score += 0.3;
    }
    
    // 3. Common prefix length scoring
    let common_prefix_len = user_lower.chars()
        .zip(func_lower.chars())
        .take_while(|(a, b)| a == b)
        .count();
    if common_prefix_len > 0 {
        score += (common_prefix_len as f64 / user_input.len().max(function_name.len()) as f64) * 0.4;
    }
    
    // 4. Levenshtein distance for similar spelling
    let edit_distance = levenshtein_distance(user_method, func_method);
    let max_len = user_method.len().max(func_method.len());
    if max_len > 0 {
        let distance_score = 1.0 - (edit_distance as f64 / max_len as f64);
        score += distance_score * 0.3;
    }
    
    // 5. Word boundary matching (useful for snake_case and camelCase)
    let user_words: Vec<&str> = user_method.split('_').collect();
    let func_words: Vec<&str> = func_method.split('_').collect();
    let matching_words = user_words.iter()
        .filter(|&word| func_words.iter().any(|&fw| fw.to_lowercase().contains(&word.to_lowercase())))
        .count();
    if !user_words.is_empty() {
        score += (matching_words as f64 / user_words.len() as f64) * 0.2;
    }
    
    // Cap the score at 1.0
    score.min(1.0)
}

/// Calculate Levenshtein distance between two strings
fn levenshtein_distance(s1: &str, s2: &str) -> usize {
    let len1 = s1.len();
    let len2 = s2.len();
    
    if len1 == 0 {
        return len2;
    }
    if len2 == 0 {
        return len1;
    }
    
    let mut matrix = vec![vec![0; len2 + 1]; len1 + 1];
    
    // Initialize first row and column
    for i in 0..=len1 {
        matrix[i][0] = i;
    }
    for j in 0..=len2 {
        matrix[0][j] = j;
    }
    
    let s1_chars: Vec<char> = s1.chars().collect();
    let s2_chars: Vec<char> = s2.chars().collect();
    
    for i in 1..=len1 {
        for j in 1..=len2 {
            let cost = if s1_chars[i - 1] == s2_chars[j - 1] { 0 } else { 1 };
            matrix[i][j] = (matrix[i - 1][j] + 1)
                .min(matrix[i][j - 1] + 1)
                .min(matrix[i - 1][j - 1] + cost);
        }
    }
    
    matrix[len1][len2]
}

/// Generate function suggestions with similarity-based filtering
/// Limits output to top 20 most similar functions when there are many options
fn generate_function_suggestions_with_similarity(syntax_tree: &syn::File, user_input: &str) -> String {
    let mut collector = FunctionCollector::new();
    syn::visit::visit_file(&mut collector, syntax_tree);
    
    let mut functions = collector.into_sorted_functions();
    
    if functions.is_empty() {
        return "No public functions found in this file.".to_string();
    }
    
    // If we have more than 20 functions, filter by similarity
    if functions.len() > 20 {
        // Calculate similarity scores for each function
        let mut scored_functions: Vec<(AvailableFunction, f64)> = functions.into_iter()
            .map(|func| {
                let score = calculate_similarity(user_input, &func.full_name);
                (func, score)
            })
            .collect();
        
        // Sort by similarity score (descending) and take top 20
        scored_functions.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
        
        functions = scored_functions.into_iter()
            .take(20)
            .map(|(func, _score)| func)
            .collect();
        
        // Add a note about filtering
        let mut result = format!("Found {} functions, showing top 20 most similar to '{}':\n\n", 
                                functions.len(), user_input);
        result.push_str(&format_function_list(&functions));
        return result;
    }
    
    format_function_list(&functions)
}

/// Format the list of functions into a user-friendly display
/// Groups functions by category (standalone vs impl methods) and by type name
fn format_function_list(functions: &[AvailableFunction]) -> String {
    let mut output = String::from("Available functions in this file:\n\n");
    
    // Separate functions by category
    let mut standalone = Vec::new();
    let mut by_type: std::collections::BTreeMap<String, Vec<String>> = std::collections::BTreeMap::new();
    
    for func in functions {
        match &func.function_type {
            FunctionCategory::Standalone => {
                standalone.push(func.full_name.clone());
            }
            FunctionCategory::ImplMethod { type_name } => {
                by_type.entry(type_name.clone())
                      .or_insert_with(Vec::new)
                      .push(func.full_name.clone());
            }
        }
    }
    
    // Display standalone functions first
    if !standalone.is_empty() {
        output.push_str("Standalone functions:\n");
        for func in standalone {
            output.push_str(&format!("  - {}\n", func));
        }
        output.push('\n');
    }
    
    // Display methods grouped by type
    for (type_name, methods) in by_type {
        output.push_str(&format!("Methods in {}:\n", type_name));
        for method in methods {
            output.push_str(&format!("  - {}\n", method));
        }
        output.push('\n');
    }
    
    // Add helpful hint at the end
    output.push_str("Use the exact function name from above with --function parameter.\n");
    output.push_str("For methods, use the full qualified name like 'TypeName::method_name'.");
    
    output
} 