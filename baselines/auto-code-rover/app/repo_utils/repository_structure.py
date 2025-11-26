import os
import subprocess
import tempfile
import shutil
from pathlib import Path
from urllib.parse import urlparse
import re

def get_git_repo_structure_from_url(repo_url: str, auth_token: str = None, ignore_git: bool = True) -> str:
    """
    从 Git 仓库的在线 URL 获取项目结构并返回字符串表示。
    
    Args:
        repo_url (str): Git 仓库的 URL（例如 https://github.com/user/repo.git）。
        auth_token (str, optional): 用于私密仓库的认证 token（例如 GitHub token）。
        ignore_git (bool): 是否忽略 .git 目录，默认为 True。
    
    Returns:
        str: 表示项目结构的字符串，类似 tree 命令输出。
    
    Raises:
        ValueError: 如果 URL 无效或克隆失败。
        RuntimeError: 如果无法访问仓库或处理文件系统时出错。
    """
    
    if not re.match(r'^(https?://|git@).*(\.git)?$', repo_url):
        raise ValueError(f"无效的 Git 仓库 URL: {repo_url}")

    
    temp_dir = Path(tempfile.mkdtemp())
    repo_dir = temp_dir / "repo"

    try:
        
        clone_url = repo_url
        if auth_token and repo_url.startswith("https://"):
            
            parsed_url = urlparse(repo_url)
            clone_url = f"https://{auth_token}@{parsed_url.netloc}{parsed_url.path}"

        clone_cmd = ["git", "clone", "--depth", "1", clone_url, str(repo_dir)]
        try:
            
            result = subprocess.run(
                clone_cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=300  # 5 分钟超时
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"克隆仓库失败: {e.stderr}")
        except subprocess.TimeoutExpired:
            raise RuntimeError("克隆仓库超时")

        
        if not (repo_dir / ".git").is_dir():
            raise RuntimeError(f"克隆的路径 {repo_dir} 不是有效的 Git 仓库")

        
        def build_tree(path: Path, prefix: str = "", level: int = 0) -> list[str]:
            lines = []
            try:
                
                entries = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
                total_entries = len(entries)
                
                for index, entry in enumerate(entries):
                    if ignore_git and entry.name == ".git":
                        continue
                    
                    is_last = index == total_entries - 1
                    connector = "└── " if is_last else "├── "
                    lines.append(f"{prefix}{connector}{entry.name}")
                    
                    if entry.is_dir():
                        new_prefix = prefix + ("    " if is_last else "│   ")
                        lines.extend(build_tree(entry, new_prefix, level + 1))
            
            except PermissionError:
                lines.append(f"{prefix}├── [权限错误] {entry.name}")
            except Exception as e:
                lines.append(f"{prefix}├── [错误] {entry.name}: {e}")
            
            return lines

        
        repo_name = repo_dir.name
        tree_lines = [repo_name]
        tree_lines.extend(build_tree(repo_dir))
        return "\n".join(tree_lines)

    finally:
        
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception as e:
            print(f"警告: 无法清理临时目录 {temp_dir}: {e}")

def main():
    
    try:
        repo_url = "https://github.com/tokio-rs/tokio.git"  
        # auth_token = "your_token_here"  
        structure = get_git_repo_structure_from_url(repo_url)  # , auth_token=auth_token
        print(structure)
    except ValueError as e:
        print(f"错误: {e}")
    except RuntimeError as e:
        print(f"运行时错误: {e}")
    except Exception as e:
        print(f"发生未知错误: {e}")

if __name__ == "__main__":
    main()