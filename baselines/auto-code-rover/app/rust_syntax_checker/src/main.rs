
use std::env;
use std::fs;
use std::process;
use syn::parse_file;

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() != 2 {
        eprintln!("Usage: {} <rust_file>", args[0]);
        process::exit(1);
    }

    let filepath = &args[1];
    let code = match fs::read_to_string(filepath) {
        Ok(content) => content,
        Err(e) => {
            eprintln!("Failed to read file {}: {}", filepath, e);
            process::exit(1);
        }
    };

    match parse_file(&code) {
        Ok(_) => process::exit(0), // 语法正确
        Err(e) => {
            eprintln!("Syntax error: {}", e);
            process::exit(1);
        }
    }
}
