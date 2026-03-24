import os
import sys
import subprocess


def print_header():
    print("=" * 50)
    print("       AutoCut — AI-Powered Video Generator")
    print("=" * 50)
    print()


def check_config():
    if not os.path.exists("config.json"):
        print("[ERROR] config.json not found.")
        print("Please create config.json with your API keys and settings.")
        print("See README.md for the required fields.")
        return False
    return True


def run_step(script, description, args=None):
    print(f"\n>>> {description}")
    print("-" * 40)
    cmd = [sys.executable, script]
    if args:
        cmd.extend(args)
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"\n[ERROR] Step failed: {script}")
        return False
    return True


def main():
    print_header()

    if not check_config():
        sys.exit(1)

    steps = [
        ("prompt_generator.py", "Step 1: Generating image prompts from script"),
        ("image_generator.py", "Step 2: Generating images from prompts"),
        ("ai_mapper.py",       "Step 3: Mapping images to timestamps"),
        ("video_builder.py",   "Step 4: Building final video"),
    ]

    for script, description in steps:
        if not run_step(script, description):
            print("\nPipeline stopped due to an error.")
            sys.exit(1)

    print("\n" + "=" * 50)
    print("Pipeline complete! Check assets/output/final_video.mp4")
    print("=" * 50)


if __name__ == "__main__":
    main()
