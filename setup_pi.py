import os
import sys

def setup_config():
    config_path = '/boot/firmware/config.txt'
    if not os.path.exists(config_path):
        config_path = '/boot/config.txt'
        
    if not os.path.exists(config_path):
        print(f"Error: Could not find config.txt at /boot/firmware/ or /boot/")
        return

    print(f"Reading {config_path}...")
    with open(config_path, 'r') as f:
        lines = f.readlines()

    print("\nArducam OwlSight 64MP Configuration")
    print("1. Low-Speed Mode (Default, maximum stability)")
    print("2. High-Speed Mode (Higher frame rates)")
    speed_choice = input("Select speed mode (1/2) [1]: ") or "1"
    
    is_cm = input("Are you using a Compute Module (CM3/4) on CAM0? (y/n) [n]: ").lower() == 'y'
    
    link_freq = "360000000" if speed_choice == "1" else "456000000"
    cam_str = ",cam0" if is_cm else ""
    
    dtoverlay_target = f"dtoverlay=ov64a40{cam_str},link-frequency={link_freq}\n"
    auto_detect_target = "camera_auto_detect=0\n"

    new_lines = []
    auto_detect_fixed = False
    dtoverlay_added = False
    
    # Check if we are in an [all] section
    current_section = None

    for line in lines:
        strip_line = line.strip()
        if strip_line.startswith("[") and strip_line.endswith("]"):
            current_section = strip_line
        
        if strip_line.startswith("camera_auto_detect="):
            new_lines.append(auto_detect_target)
            auto_detect_fixed = True
        elif "dtoverlay=ov64a40" in line:
            new_lines.append(dtoverlay_target)
            dtoverlay_added = True
        else:
            new_lines.append(line)

    if not auto_detect_fixed:
        new_lines.append(auto_detect_target)
    
    if not dtoverlay_added:
        # Try to find [all] section to append to
        try:
            idx = -1
            for i, line in enumerate(new_lines):
                if line.strip() == "[all]":
                    idx = i
                    break
            
            if idx != -1:
                new_lines.insert(idx + 1, dtoverlay_target)
            else:
                new_lines.append("\n[all]\n" + dtoverlay_target)
        except Exception:
            new_lines.append(dtoverlay_target)

    print("\nProposed changes to config.txt:")
    print("----------------------------")
    print(f"Setting: {auto_detect_target.strip()}")
    print(f"Setting: {dtoverlay_target.strip()}")
    print("----------------------------")

    confirm = input("Apply these changes? (y/n): ")
    if confirm.lower() == 'y':
        try:
            with open(config_path, 'w') as f:
                f.writelines(new_lines)
            print("\nSuccessfully updated configuration. PLEASE REBOOT YOUR PI.")
        except PermissionError:
            print("\nError: Please run this script with sudo (e.g., sudo python setup_pi.py)")
    else:
        print("\nAborted.")

if __name__ == "__main__":
    setup_config()
