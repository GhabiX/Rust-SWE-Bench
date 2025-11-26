import glob
import re
from os.path import join as pjoin
from pathlib import Path
import rust_parser, json

def is_test_file(file_path: str) -> bool:
    """Check if a file is a test file.

    This is a simple heuristic to check if a file is a test file.
    """
    return (
        "test" in Path(file_path).parts
        or "tests" in Path(file_path).parts
        or file_path.endswith("_test.rs")
    )

def find_python_files(dir_path: str) -> list[str]:
    """递归获取目录下的所有 .rs 文件。

    排除测试文件。

    Args:
        dir_path (str): 目录路径。

    Returns:
        List[str]: .rs 文件的绝对路径列表。
    """

    rs_files = glob.glob(pjoin(dir_path, "**/*.rs"), recursive=True)
    res = []
    for file in rs_files:
        rel_path = file[len(dir_path) + 1 :]
        if is_test_file(rel_path):
            continue
        res.append(file)
    return res

def parse_python_file(file_path: str) -> tuple[
    list[tuple[str, int, int]],  # structs: [(struct_name, start_line, end_line)]
    dict[str, list[tuple[str, int, int]]],  # impls: {struct_name: [(method_name, start_line, end_line)]}
    list[tuple[str, int, int]],  # functions: [(func_name, start_line, end_line)]
    list[tuple[str, int, int]],  # traits: [(struct_name, start_line, end_line)]
    dict[str, list[tuple[str, int, int]]],  # traits_impl: {struct_name: [(method_name, start_line, end_line)]}
    list[tuple[str, int, int]],  # macros: [(struct_name, start_line, end_line)]
    dict[tuple[str, int, int], list[str]],  # struct_trait_map: {(struct_name, start_line, end_line): [trait_names]}    
    # dict[tuple[str, int, int], list[str]],  # struct_relation_map: {(struct_name, start_line, end_line): [trait_names]}
    # list[tuple[str, int, int]]  # traits: [(trait_name, start_line, end_line)]
]:
    """解析 Rust 源文件。

    Args:
        file_path (str): Rust 源文件路径。

    Returns:
        tuple: 包含结构体、实现、函数、trait关系和trait定义的元组。
    """
    if file_path.endswith(".rs"):
        with open(file_path) as fp:
            
            data = json.loads(rust_parser.parse_rust_code(fp.read()))
            structs_meta = data.get("structs", [])
            structs = [(s["name"], s["start_line"], s["end_line"]) for s in structs_meta]
            impls = {}
            struct_trait_map: dict[tuple[str, int, int], list[str]] = {}
            for struct in structs_meta:
                impls[struct["name"]] = []
                struct_trait_map[(struct["name"], struct["start_line"], struct["end_line"])] = []
                for method in struct["methods"]:
                    impls[struct["name"]].append((method["name"], method["start_line"], method["end_line"]))
                for trait in struct["traits"]:
                    struct_trait_map[(struct["name"], struct["start_line"], struct["end_line"])].append(trait)
            traits_data = data.get("traits", [])
            traits = [(t["name"], t["start_line"], t["end_line"]) for t in traits_data]
            trait_impls = {}
            for trait in traits_data:
                trait_impls[trait["name"]] = []
                for method in trait["methods"]:
                    trait_impls[trait["name"]].append((method["name"], method["start_line"], method["end_line"]))
            macros_data = data.get("macros", [])
            macros = [(m["name"], m["start_line"], m["end_line"]) for m in macros_data]
            functions_meta = data.get("functions", [])
            functions = [(f["name"], f["start_line"], f["end_line"]) for f in functions_meta]
            return structs, impls, functions, traits, trait_impls, macros, struct_trait_map
    else:
        
        return None

def get_code_snippets(
    file_full_path: str, start: int, end: int, with_lineno=True
) -> str:
    with open(file_full_path) as f:
        file_content = f.readlines()
    snippet = ""
    for i in range(start - 1, end):
        if i < 0 or i >= len(file_content):
            continue
        if with_lineno:
            snippet += f"{i+1} {file_content[i]}"
        else:
            snippet += file_content[i]
    return snippet

def get_code_region_containing_code(
    file_full_path: str, code_str: str, with_lineno=True
) -> list[tuple[int, str]]:
    with open(file_full_path) as f:
        file_content = f.read()

    context_size = 5
    pattern = re.compile(re.escape(code_str))
    occurrences = []
    for match in pattern.finditer(file_content):
        matched_start_pos = match.start()
        matched_line_no = file_content.count("\n", 0, matched_start_pos)

        file_content_lines = file_content.splitlines()

        window_start_index = max(0, matched_line_no - context_size)
        window_end_index = min(
            len(file_content_lines), matched_line_no + context_size + 1
        )

        if with_lineno:
            context = ""
            for i in range(window_start_index, window_end_index):
                context += f"{i+1} {file_content_lines[i]}\n"
        else:
            context = "\n".join(file_content_lines[window_start_index:window_end_index])
        occurrences.append((matched_line_no + 1, context))  

    return occurrences


def get_class_signature(file_full_path: str, struct_name: str) -> str:
    """获取结构体签名。

    Args:
        file_full_path (str): 文件路径。
        struct_name (str): 结构体名称。
    """
    structs, impls, _,_,_,_,_ = parse_python_file(file_full_path)
    print(structs)
    print(impls)
    result = ""
    with open(file_full_path) as f:
        file_content = f.readlines()
    for (name,start_line,end_line) in structs: #structs: [(struct_name, start_line, end_line)]
        if name == struct_name:
            
            for i in range(start_line-1, end_line):
                result += file_content[i]
            break
    impls = impls.get(struct_name, [])
    if not impls:
        return result
    for (method,start_line,end_line) in impls: #impls: {struct_name: [(method_name, start_line, end_line)]}
        result += file_content[start_line-1]
    return result

def get_code_region_around_line(
    file_full_path: str, line_no: int, window_size: int = 10, with_lineno=True
) -> str | None:
    with open(file_full_path) as f:
        file_content = f.readlines()

    if line_no < 1 or line_no > len(file_content):
        return None

    start = max(1, line_no - window_size)
    end = min(len(file_content), line_no + window_size)
    snippet = ""
    for i in range(start - 1, end):
        if with_lineno:
            snippet += f"{i+1} {file_content[i]}"
        else:
            snippet += file_content[i]
    return snippet

if __name__ == "__main__":

    pass