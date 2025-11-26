import json
import os
from pathlib import Path
from typing import Optional, Dict, Any

def extract_patch_info(json_file: str) -> Optional[Dict[str, Any]]:
    """
    Extract patch information from a JSON log file.
    
    Args:
        json_file: Path to the JSON log file
        
    Returns:
        Dictionary containing instance_id, model_name and patch info, or None if extraction fails
    """
    try:
        with open(json_file) as f:
            data = json.load(f)

        task_report = data.get('task_report')
        if task_report is None:
            print(f"No task_report found in {json_file}")
            return None
            
        # Extract diff info from task report
        diff_info = task_report.get('task_modify_files_diff', {})
        if not diff_info:
            print(f"No task_modify_files_diff found in {json_file}")
            return None
            
        valid_diffs = {k: v for k, v in diff_info.items() if v != "No changes detected by git"}
        if not valid_diffs:
            print(f"No valid diffs found in {json_file}")
            return None
            
        # Extract instance_id from filename
        instance_id = Path(json_file).stem
        # Remove rustforger_log_ prefix
        if instance_id.startswith('rustforger_log_'):
            instance_id = instance_id[len('rustforger_log_'):]
        
        # Combine all diffs instead of taking just the first one
        combined_patch = "\n".join(valid_diffs.values())
        
        print(f"Successfully extracted patch from {json_file} with {len(valid_diffs)} file changes")
            
        return {
            "instance_id": instance_id,
            "model_name_or_path": "rustforger",
            "model_patch": combined_patch,
            "task_analysis": task_report.get('task_analysis', ""),
            "task_resolve_success": task_report.get('task_resolve_success', False)
        }
    except Exception as e:
        print(f"Error processing {json_file}: {e}")
        return None

def generate_patches_jsonl(log_dir: str, output_file: str) -> None:
    """
    Process all JSON log files and generate a JSONL file with patch information.
    
    Args:
        log_dir: Directory containing JSON log files
        output_file: Path to output JSONL file
    """
    # Create output directory if needed
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    
    processed_count = 0
    # Process only rustforger_log_* files
    with open(output_file, 'w') as f:
        for json_file in Path(log_dir).glob("rustforger_log_*.json"):
            print(f"Processing {json_file.name}...")
            if patch_info := extract_patch_info(str(json_file)):
                f.write(f"{json.dumps(patch_info)}\n")
                processed_count += 1
    
    print(f"Total processed files: {processed_count}")

def main():
    """Main function to process log files and generate patch information."""
    result_dir = "./RustForger/log"
    output_file = f"{result_dir}/rustforger.jsonl"
    
    generate_patches_jsonl(result_dir, output_file)
    print(f"Processing complete. Output saved to: {output_file}")

if __name__ == "__main__":
    main()
