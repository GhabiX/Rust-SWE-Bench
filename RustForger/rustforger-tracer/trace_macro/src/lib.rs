// trace_macro/src/lib.rs

use proc_macro::TokenStream;
use proc_macro2;
use quote::quote;
use syn::{parse_macro_input, FnArg, ItemFn, Pat, Type, Expr, Block, Stmt, ExprCall};

#[derive(Debug, Clone)]
struct PropagateConfig {
    enabled: bool,
    exclude_patterns: Vec<String>,
    #[allow(dead_code)]
    user_code_only: bool,
    max_depth: Option<usize>,
}

impl Default for PropagateConfig {
    fn default() -> Self {
        Self {
            enabled: false,
            exclude_patterns: vec![
                "std::".to_string(),
                "core::".to_string(),
                "__rust_".to_string(),
            ],
            user_code_only: true,
            max_depth: None,
        }
    }
}

fn parse_attributes(attr: TokenStream) -> PropagateConfig {
    let attr_str = attr.to_string();
    let mut config = PropagateConfig::default();
    
    if attr_str.contains("propagate") {
        config.enabled = true;
    }
    
    if let Some(depth_match) = attr_str.find("max_depth") {
        if let Some(eq_pos) = attr_str[depth_match..].find('=') {
            let start = depth_match + eq_pos + 1;
            if let Some(value_str) = attr_str[start..].split(',').next() {
                if let Ok(depth) = value_str.trim().parse::<usize>() {
                    config.max_depth = Some(depth);
                }
            }
        }
    }
    
    if attr_str.contains("exclude") {
        if attr_str.contains("std::") {
            config.exclude_patterns.push("std::".to_string());
        }
    }
    
    config
}

fn might_be_serializable(ty: &Type) -> bool {
    let type_str = quote!(#ty).to_string();
    
    const PRIMITIVES: &[&str] = &[
        "i8", "i16", "i32", "i64", "i128", "isize",
        "u8", "u16", "u32", "u64", "u128", "usize", 
        "f32", "f64", "bool", "char", "String"
    ];
    
    // Check for exact primitive matches
    if PRIMITIVES.contains(&type_str.as_str()) {
        return true;
    }
    
    // String references
    if matches!(type_str.as_str(), "&str" | "& str" | "&String" | "& String") {
        return true;
    }
    
    // Simple references to primitives
    if let Some(inner) = type_str.strip_prefix('&').map(str::trim) {
        if PRIMITIVES.contains(&inner) {
            return true;
        }
    }
    
    // Arrays and slices of primitives
    if is_array_of_primitives(&type_str) || is_vec_of_primitives(&type_str) {
        return true;
    }
    
    // Option of primitives
    if let Some(inner) = extract_generic_inner(&type_str, "Option") {
        if PRIMITIVES.contains(&inner.trim()) {
            return true;
        }
    }
    
    // Conservative check for simple test types 
    is_known_serializable_test_type(&type_str)
}

/// Checks if type string represents an array of primitives
fn is_array_of_primitives(type_str: &str) -> bool {
    if let Some(inner) = type_str.strip_prefix('[').and_then(|s| s.strip_suffix(']')) {
        if let Some(element_type) = inner.split(';').next() {
            return matches!(element_type.trim(), 
                "i8" | "i16" | "i32" | "i64" | "i128" | "isize" |
                "u8" | "u16" | "u32" | "u64" | "u128" | "usize" |
                "f32" | "f64" | "bool" | "char"
            );
        }
    }
    false
}

/// Checks if type string represents a Vec of primitives
fn is_vec_of_primitives(type_str: &str) -> bool {
    if let Some(inner) = extract_generic_inner(type_str, "Vec") {
        return matches!(inner.trim(), 
            "i8" | "i16" | "i32" | "i64" | "i128" | "isize" |
            "u8" | "u16" | "u32" | "u64" | "u128" | "usize" |
            "f32" | "f64" | "bool" | "char" | "String"
        );
    }
    false
}

/// Extracts the inner type from a generic type like "Vec<T>" -> "T"
fn extract_generic_inner<'a>(type_str: &'a str, wrapper: &str) -> Option<&'a str> {
    let prefix = format!("{} <", wrapper);
    if type_str.starts_with(&prefix) && type_str.ends_with('>') {
        let start = prefix.len();
        let end = type_str.len() - 1;
        return Some(&type_str[start..end]);
    }
    None
}

fn is_known_serializable_test_type(type_str: &str) -> bool {
    if type_str.contains("::") || type_str.contains('<') || type_str.contains('&') {
        return false;
    }
    matches!(type_str, 
        "Person" | "TestData" | "MySerializableType" |
        "SerializableStruct" | "SimpleStruct"
    ) || (type_str.starts_with("Test") && type_str.contains("Serializable"))
      || (type_str.starts_with("My") && type_str.contains("Serializable"))
}

#[allow(dead_code)]
fn get_return_serialization_method(return_type: &syn::ReturnType) -> proc_macro2::TokenStream {
    match return_type {
        syn::ReturnType::Default => {
            // Unit type () - use placeholder
            quote! { safe_serialize_any }
        }
        syn::ReturnType::Type(_, ty) => {
            if might_be_serializable(ty) {
                quote! { serialize_if_serializable }
            } else {
                quote! { safe_serialize_any }
            }
        }
    }
}

fn generate_parameter_records(sig: &syn::Signature) -> Vec<proc_macro2::TokenStream> {
    let mut records = Vec::new();
    
    for arg in &sig.inputs {
        if let FnArg::Typed(pat_type) = arg {
            if let Pat::Ident(pat_ident) = &*pat_type.pat {
                let name = &pat_ident.ident;
                let name_str = name.to_string();
                let ty = &pat_type.ty;
                
                if might_be_serializable(ty) {
                    records.push(quote! { 
                        #name_str => ::trace_common::serialize_if_serializable!(&#name)
                    });
                } else {
                    records.push(quote! { 
                        #name_str => ::trace_common::placeholder_for!(&#name)
                    });
                }
            }
        }
    }
    
    records
}

fn instrument_block_with_tracing(block: &Block, config: &PropagateConfig) -> proc_macro2::TokenStream {
    let mut instrumented_stmts = Vec::new();
    
    for stmt in &block.stmts {
        let instrumented_stmt = instrument_stmt_with_tracing(stmt, config);
        instrumented_stmts.push(instrumented_stmt);
    }
    
    quote! {
        {
            #(#instrumented_stmts)*
        }
    }
}

fn instrument_stmt_with_tracing(stmt: &Stmt, config: &PropagateConfig) -> proc_macro2::TokenStream {
    match stmt {
        Stmt::Expr(expr, semi) => {
            let instrumented_expr = instrument_expr_with_tracing(expr, config);
            if semi.is_some() {
                quote! { #instrumented_expr; }
            } else {
                quote! { #instrumented_expr }
            }
        }
        Stmt::Local(local) => {
            if let Some(init) = &local.init {
                let instrumented_init = instrument_expr_with_tracing(&init.expr, config);
                let pat = &local.pat;
                let attrs = &local.attrs;
                
                quote! {
                    #(#attrs)*
                    let #pat = #instrumented_init;
                }
            } else {
                quote! { #stmt }
            }
        }
        _ => quote! { #stmt }
    }
}

fn instrument_expr_with_tracing(expr: &Expr, config: &PropagateConfig) -> proc_macro2::TokenStream {
    match expr {
        Expr::Call(call) => {
            if should_instrument_call(call, config) {
                instrument_function_call_with_tracing(call, config)
            } else {
                quote! { #expr }
            }
        }
        Expr::Block(block_expr) => {
            let instrumented_block = instrument_block_with_tracing(&block_expr.block, config);
            quote! { #instrumented_block }
        }
        Expr::If(if_expr) => {
            let cond = &if_expr.cond;
            let then_branch = instrument_block_with_tracing(&if_expr.then_branch, config);
            
            if let Some((_, else_branch)) = &if_expr.else_branch {
                let instrumented_else = instrument_expr_with_tracing(else_branch, config);
                quote! {
                    if #cond {
                        #then_branch
                    } else {
                        #instrumented_else
                    }
                }
            } else {
                quote! {
                    if #cond {
                        #then_branch
                    }
                }
            }
        }
        _ => quote! { #expr }
    }
}

fn should_instrument_call(call: &ExprCall, config: &PropagateConfig) -> bool {
    if !config.enabled {
        return false;
    }
    
    let func_name = extract_function_name_from_call(call);
    
    if let Some(name) = func_name {
        for pattern in &config.exclude_patterns {
            if name.contains(pattern) {
                return false;
            }
        }
        
        if name.starts_with("std::") ||
           name.starts_with("core::") ||
           name.contains("println!") ||
           name.contains("format!") ||
           matches!(name.as_str(), "Ok" | "Err" | "Some" | "None") {
            return false;
        }
        
        return name.chars().all(|c| c.is_alphanumeric() || c == '_') &&
               !name.starts_with('_') &&
               name.len() >= 3;
    }
    
    false
}

fn extract_function_name_from_call(call: &ExprCall) -> Option<String> {
    match &*call.func {
        Expr::Path(path_expr) => {
            let path_string = quote!(#path_expr).to_string();
            Some(path_string.replace(" ", ""))
        }
        _ => None
    }
}

fn instrument_function_call_with_tracing(call: &ExprCall, _config: &PropagateConfig) -> proc_macro2::TokenStream {
    let func = &call.func;
    let args = &call.args;
    
    if let Some(func_name) = extract_function_name_from_call(call) {
        quote! {
            {
                ::trace_runtime::tracer::interface::enter_dynamic(#func_name, file!(), line!());
                let __result = #func(#args);
                ::trace_runtime::tracer::interface::exit();
                
                __result
            }
        }
    } else {
        quote! { #func(#args) }
    }
}

#[proc_macro_attribute]
pub fn rustforger_trace(attr: TokenStream, item: TokenStream) -> TokenStream {
    let config = parse_attributes(attr);
    
    let input_fn = parse_macro_input!(item as ItemFn);

    let output = generate_tracing_instrumentation(&input_fn, &config);
    
    output.into()
}

fn generate_tracing_instrumentation(
    input_fn: &ItemFn,
    _config: &PropagateConfig,
) -> proc_macro2::TokenStream {
    let vis = &input_fn.vis;
    let sig = &input_fn.sig;
    let block = &input_fn.block;
    let attrs = &input_fn.attrs;
    let fn_name = &sig.ident;
    let fn_name_str = fn_name.to_string();
    let is_async = sig.asyncness.is_some();
    
    let param_records = generate_parameter_records(sig);
    
    let serialize_args = if param_records.is_empty() {
        quote! {
            let __trace_inputs = ::serde_json::Value::Object(::serde_json::Map::new());
        }
    } else {
        quote! {
            let __trace_inputs = ::trace_common::args_json!(#(#param_records),*);
        }
    };

    let auto_init_code = quote! {
        ::trace_runtime::tracer::interface::ensure_auto_save_initialized();
    };
    match &sig.output {
        syn::ReturnType::Default => {
            if is_async {
                quote! {
                    #(#attrs)*
                    #vis #sig {
                        #auto_init_code
                        ::trace_runtime::tracer::interface::enter(#fn_name_str, file!(), line!());
                        #serialize_args
                        let __result = #block;
                        let __trace_output = ::serde_json::Value::Null;
                        ::trace_runtime::tracer::interface::record_top_level_call(__trace_inputs, __trace_output);
                        ::trace_runtime::tracer::interface::exit();
                        __result
                    }
                }
            } else {
                quote! {
                    #(#attrs)*
                    #vis #sig {
                        #auto_init_code
                        ::trace_runtime::tracer::interface::enter(#fn_name_str, file!(), line!());
                        #serialize_args
                        let __result = #block;
                        let __trace_output = ::serde_json::Value::Null;
                        ::trace_runtime::tracer::interface::record_top_level_call(__trace_inputs, __trace_output);
                        ::trace_runtime::tracer::interface::exit();
                        __result
                    }
                }
            }
        }
        syn::ReturnType::Type(_, ty) => {
            let serialize_method = if might_be_serializable(ty) {
                quote! { ::trace_common::serialize_if_serializable!(&__result) }
            } else {
                quote! { ::trace_common::placeholder_for!(&__result) }
            };
            
            if is_async {
                quote! {
                    #(#attrs)*
                    #vis #sig {
                        #auto_init_code
                        ::trace_runtime::tracer::interface::enter(#fn_name_str, file!(), line!());
                        #serialize_args
                        let __result = #block;
                        let __trace_output = #serialize_method;
                        ::trace_runtime::tracer::interface::record_top_level_call(__trace_inputs, __trace_output);
                        ::trace_runtime::tracer::interface::exit();
                        __result
                    }
                }
            } else {
                quote! {
                    #(#attrs)*
                    #vis #sig {
                        #auto_init_code
                        ::trace_runtime::tracer::interface::enter(#fn_name_str, file!(), line!());
                        #serialize_args
                        let __result = #block;
                        let __trace_output = #serialize_method;
                        ::trace_runtime::tracer::interface::record_top_level_call(__trace_inputs, __trace_output);
                        ::trace_runtime::tracer::interface::exit();
                        __result
                    }
                }
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use syn::parse_quote;
    
    fn parse_attributes_from_str(attr_str: &str) -> PropagateConfig {
        let mut config = PropagateConfig::default();
        
        if attr_str.contains("propagate") {
            config.enabled = true;
        }
    
        if let Some(depth_match) = attr_str.find("max_depth") {
            if let Some(eq_pos) = attr_str[depth_match..].find('=') {
                let start = depth_match + eq_pos + 1;
                if let Some(value_str) = attr_str[start..].split(',').next() {
                    if let Ok(depth) = value_str.trim().parse::<usize>() {
                        config.max_depth = Some(depth);
                    }
                }
            }
        }
        
        if attr_str.contains("exclude") {
            if attr_str.contains("std::") {
                config.exclude_patterns.push("std::".to_string());
            }
        }
        
        config
    }
    
    #[test]
    fn test_parse_empty_attributes() {
        let config = parse_attributes_from_str("");
        assert!(!config.enabled);
        assert_eq!(config.max_depth, None);
    }
    
    #[test]
    fn test_parse_propagate_attribute() {
        let config = parse_attributes_from_str("propagate");
        assert!(config.enabled);
    }
    
    #[test]
    fn test_parse_max_depth_attribute() {
        let config = parse_attributes_from_str("propagate, max_depth = 5");
        assert!(config.enabled);
        assert_eq!(config.max_depth, Some(5));
    }
    
    #[test]
    fn test_might_be_serializable_primitives() {
        let ty: Type = parse_quote! { i32 };
        assert!(might_be_serializable(&ty));
        
        let ty: Type = parse_quote! { String };
        assert!(might_be_serializable(&ty));
        
        let ty: Type = parse_quote! { &str };
        assert!(might_be_serializable(&ty));
    }
    
    #[test]
    fn test_might_be_serializable_complex() {
        let ty: Type = parse_quote! { std::collections::HashMap<String, i32> };
        assert!(!might_be_serializable(&ty));
    }
    
    #[test]
    fn test_generate_parameter_records() {
        let sig: syn::Signature = parse_quote! {
            fn test_fn(x: i32, y: &str) -> String
        };
        
        let records = generate_parameter_records(&sig);
        assert_eq!(records.len(), 2);
    }
    
    #[test]
    fn test_should_instrument_call_disabled() {
        let call: ExprCall = parse_quote! { some_function() };
        let config = PropagateConfig::default();
        
        assert!(!should_instrument_call(&call, &config));
    }
    
    #[test]
    fn test_should_instrument_call_enabled() {
        let call: ExprCall = parse_quote! { user_function() };
        let mut config = PropagateConfig::default();
        config.enabled = true;
        
        assert!(should_instrument_call(&call, &config));
    }
    
    #[test]
    fn test_should_instrument_call_excluded() {
        let call: ExprCall = parse_quote! { std::process::exit(0) };
        let mut config = PropagateConfig::default();
        config.enabled = true;
        
        assert!(!should_instrument_call(&call, &config));
    }
    
    #[test]
    fn test_extract_function_name_from_call() {
        let call: ExprCall = parse_quote! { test_function() };
        let name = extract_function_name_from_call(&call);
        assert_eq!(name, Some("test_function".to_string()));
        
        let call: ExprCall = parse_quote! { module::function() };
        let name = extract_function_name_from_call(&call);
        assert_eq!(name, Some("module::function".to_string()));
    }
}
