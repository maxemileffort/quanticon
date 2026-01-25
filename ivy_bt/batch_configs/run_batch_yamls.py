import os
import sys
import subprocess
import argparse

def main():
    parser = argparse.ArgumentParser(description="Run batch configurations sequentially.")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without executing.")
    parser.add_argument("--limit", type=int, help="Limit the number of batches to run (for testing).")
    args = parser.parse_args()

    # Determine directories
    # This script is in quanticon/ivy_bt/batch_configs/
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # Project root is quanticon/ivy_bt/
    project_root = os.path.dirname(current_dir)
    main_py_path = os.path.join(project_root, 'main.py')

    print(f"Searching for batch configurations in: {current_dir}")
    print(f"Project root identified as: {project_root}")

    # Find YAML files
    yaml_files = [f for f in os.listdir(current_dir) if f.endswith('.yaml')]
    
    # Sort for consistent execution order
    yaml_files.sort()

    if not yaml_files:
        print("No .yaml files found to run.")
        return

    print(f"Found {len(yaml_files)} batch configuration files.")

    failed_batches = []

    for i, yaml_file in enumerate(yaml_files, 1):
        if args.limit and i > args.limit:
            print(f"Limit of {args.limit} reached. Stopping.")
            break

        yaml_path = os.path.join(current_dir, yaml_file)
        
        print(f"\n[{i}/{len(yaml_files)}] Running batch: {yaml_file}")
        print("=" * 60)

        # Construct command
        # python main.py --batch "path/to/config.yaml"
        cmd = [sys.executable, main_py_path, '--batch', yaml_path]

        if args.dry_run:
            print(f"[DRY RUN] would execute: {' '.join(cmd)}")
            continue

        try:
            # Run the command with cwd set to project root
            # allowing main.py to find its imports/config correctly
            subprocess.run(cmd, cwd=project_root, check=True)
            print(f"Successfully completed: {yaml_file}")
        except subprocess.CalledProcessError as e:
            print(f"ERROR executing {yaml_file}. Exit code: {e.returncode}")
            failed_batches.append(yaml_file)
        except Exception as e:
            print(f"Unexpected ERROR executing {yaml_file}: {e}")
            failed_batches.append(yaml_file)

    print("\n" + "=" * 60)
    print("All batch jobs finished.")
    if failed_batches:
        print(f"The following {len(failed_batches)} batches failed:")
        for fb in failed_batches:
            print(f" - {fb}")
        sys.exit(1)
    else:
        print("All batches completed successfully.")

if __name__ == '__main__':
    main()
