import os,tempfile,subprocess
def check_rust_syntax(code):
    """
    使用 syn 检查 Rust 代码的语法是否正确

    Args:
        code: 单个代码字符串或代码字符串列表

    Returns:
        bool: 如果所有代码语法正确则返回True，否则返回False
    """
    if not isinstance(code, list):
        code = [code]

    
    checker_path = ensure_syntax_checker_exists()
    if not checker_path:
        print("无法创建或找到 Rust 语法检查器")
        return False

    for c in code:
        if not c.strip():  
            return False

        
        with tempfile.NamedTemporaryFile(suffix=".rs", delete=False) as temp_file:
            temp_path = temp_file.name
            try:
                temp_file.write(c.encode('utf-8'))
                temp_file.close()

                
                result = subprocess.run(
                    [checker_path, temp_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )

                if result.returncode != 0:
                    return False

            except Exception as e:
                print(f"语法检查出错: {e}")
                return False
            finally:
                
                try:
                    os.unlink(temp_path)
                except:
                    pass

    return True


def ensure_syntax_checker_exists():
    """确保 Rust 语法检查器存在，不存在则构建"""
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    checker_dir = os.path.join(script_dir, "rust_syntax_checker")
    checker_path = os.path.join(checker_dir, "target", "release", "rust_syntax_checker")
    if os.name == "nt":  # Windows
        checker_path += ".exe"

    
    if os.path.exists(checker_path):
        return checker_path

    
    if not os.path.exists(checker_dir):
        os.makedirs(checker_dir)

    
    cargo_toml = """
[package]
name = "rust_syntax_checker"
version = "0.1.0"
edition = "2021"

[dependencies]
syn = { version = "2.0", features = ["full", "parsing", "extra-traits"] }
"""

    with open(os.path.join(checker_dir, "Cargo.toml"), "w") as f:
        f.write(cargo_toml)

    
    src_dir = os.path.join(checker_dir, "src")
    if not os.path.exists(src_dir):
        os.makedirs(src_dir)

    
    main_rs = """
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
"""

    with open(os.path.join(src_dir, "main.rs"), "w") as f:
        f.write(main_rs)

    
    try:
        subprocess.run(
            ["cargo", "build", "--release"],
            cwd=checker_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True
        )
        return checker_path
    except Exception as e:
        print(f"构建语法检查器失败: {e}")
        return None