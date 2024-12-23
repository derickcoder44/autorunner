from InquirerPy import prompt
import os
import libtmux

# Define checklist questions
questions = [
    {
        'type': 'checkbox',
        'name': 'Platform Setup',
        'message': 'Select all completed steps for Platform Setup:',
        'choices': [
            {'name': 'Drone Unpacked - Extend and lock out the drone’s arms and propeller blades', 'value': 'Drone Unpacked'},
            {'name': 'Lense Cap Off - Remove the lens cap from all cameras', 'value': 'Lense Cap Off'},
            {'name': 'Drone On - Power on the drone and verify connectivity with controller', 'value': 'Drone On'},
            {'name': 'Comm Link - Is the communication link active?', 'value': 'Comm Link'}
        ],
        'transformer': lambda result: ""  # Hide selected choices after prompt
    },
    {
        'type': 'checkbox',
        'name': 'RTK Setup and Verification',
        'message': 'Select all completed steps for RTK Setup and Verification:',
        'choices': [
            {'name': 'Controller on WiFi - Ensure the controller is on the WiFi network "HARELAB_RTK"', 'value': 'Controller on WiFi'},
            {'name': 'Drone RTK Configured - Ensure that the drone controller’s RTK setting is "Custom NTRIP Server"', 'value': 'Drone RTK Configured'},
            {'name': 'Drone RTK Connected - Ensure that the drone controller reports that RTK is connected and RTK data is in use', 'value': 'Drone RTK Connected'}
        ],
        'transformer': lambda result: ""  # Hide selected choices after prompt
    }
]

# Process each section
for question in questions:
    title = question['name']  # Get the section title
    total_items = len(question['choices'])  # Total number of steps in this section

    while True:  # Repeat until all boxes are checked
        # Prompt the user
        answers = prompt([question])
        completed = answers[title]  # Get the selected items

        # Check if all steps are completed
        if len(completed) == total_items:
            print(f"✅  {title} completed successfully!\n")
            break  # Exit loop and move to the next section
        else:
            print("⚠️  Checklist incomplete! Please check all boxes before continuing.")


# --- Configuration ---
SESSION_NAME = "preflight"
server = libtmux.Server()

def create_new_terminal(command):
    """Open a new terminal window and execute the tmux command."""
    if os.name == "posix":  # macOS or Linux
        if "darwin" in os.uname().sysname.lower():  # macOS
            os.system(f"osascript -e 'tell application \"Terminal\" to do script \"{command}\"'")
        else:  # Linux
            os.system(f"gnome-terminal -- bash -c '{command}; exec bash'")
    else:
        raise OSError("Unsupported OS for opening a new terminal window.")

def run_command_in_tmux(session, window_name, command, new_terminal=False):
    """Run a command in a tmux window or new terminal."""
    if new_terminal:
        create_new_terminal(f"tmux new-session -A -s {SESSION_NAME} \\; new-window -n {window_name} \\; send-keys '{command}' C-m")
    else:
        window = session.new_window(window_name=window_name)
        pane = window.attached_pane
        pane.send_keys(command)

def wait_for_prompt(question):
    """Prompt the user for verification before proceeding."""
    answer = prompt(question)
    return answer

# --- Create Tmux Session ---
session = server.new_session(session_name=SESSION_NAME, kill_session=True)

# --- Step 1: Camera Setup ---
print("\n--- Camera Setup ---")

# Open in a new terminal window
run_command_in_tmux(session, "camera_setup", "cd ros2_iron && ros2 launch camera_aravis2 camera_driver_gv_example.launch.py", new_terminal=True)

# Prompt for frame rate verification
question = [
    {
        'type': 'confirm',
        'name': 'frame_rate',
        'message': 'Verify that the camera frame rate is set to 5Hz. Is this correct?',
        'default': False
    }
]
while not wait_for_prompt(question)['frame_rate']:
    print("\n⚠️  Adjust the frame rate and try again using 'arv-tool-0.8 control [feature]'.")
print("✅  Camera frame rate verified!")

# --- Step 2: Inertial Sense Setup ---
print("\n--- Inertial Sense Setup ---")

# Check topic rate in a new terminal window
run_command_in_tmux(session, "topic_rate", "ros2 topic hz /camera_driver_gv_example/vis/image_raw", new_terminal=True)

# Run inertial sense in a new terminal window
run_command_in_tmux(session, "inertial_sense", "ros2 run inertial_sense_ros2 new_target /home/pi5-alpha/ros2_iron/src/inertial-sense-sdk/ros2/launch/example_params.yaml", new_terminal=True)

# Prompt for GPS antenna offset
question = [
    {
        'type': 'confirm',
        'name': 'gps_offset',
        'message': 'Check GPS1 antenna offset. Is it set correctly?',
        'default': False
    }
]
while not wait_for_prompt(question)['gps_offset']:
    print("\n⚠️  Adjust antenna offset using 'ros2 param set /nh_ antenna_offset_gps1'.")
print("✅  GPS antenna offset verified!")

# Prompt for magnetic declination
question = [
    {
        'type': 'confirm',
        'name': 'mag_declination',
        'message': 'Verify magnetic declination is adjusted for the local area. Is this correct?',
        'default': False
    }
]
while not wait_for_prompt(question)['mag_declination']:
    print("\n⚠️  Adjust magnetic declination and verify again.")
print("✅  Magnetic declination verified!")

# --- Step 3: Additional Systems Setup ---
print("\n--- Additional Systems Setup ---")

# Radar altimeter in new terminal window
run_command_in_tmux(session, "radar_altimeter", "ros2 run radalt radalt", new_terminal=True)

# Birdseye sub_node in new terminal window
run_command_in_tmux(session, "birdseye", "ros2 run birdseye sub_node --ros-params -r /image:=/camera_driver_gv_example/vis/image_raw -r /ins:=/ins_quat_uvw_lla", new_terminal=True)

# Prompt for bag recording
question = [
    {
        'type': 'confirm',
        'name': 'bag_recording',
        'message': 'Start ROS2 bag recording? Are all topics configured?',
        'default': True
    }
]
if wait_for_prompt(question)['bag_recording']:
    run_command_in_tmux(session, "bag_record", "ros2 bag record /imu_raw /ins_quat_uvw_lla /camera_driver_gv_example/vis/image_raw /rad_altitude -o [bag_output_path]", new_terminal=True)
    print("✅  Bag recording started!")
else:
    print("\n⚠️  Configure topics and restart bag recording.")

# --- Final Step: Attach to Session ---
session.attach_session()
