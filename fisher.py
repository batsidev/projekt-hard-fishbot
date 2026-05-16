import cv2
import numpy as np
import pyautogui
import time
import sys
from pathlib import Path
import pygetwindow as gw

from utils.keyboard import press_space, prepare_for_fishing

from task_scheduler.scheduler import exit_signal, setup_task_scheduler
from task_scheduler.message_queue_handler import add_message_to_queue

print("\nFisher script started.\n")
time.sleep(5)

# Global variables
BASE_DIR = Path(__file__).resolve().parent
MEDIA_DIR = BASE_DIR / 'media'
TEMPLATE_FILE_NAMES = ('1_1.png', '1_2.png', '2_1.png', '2_2.png', '3_1.png', '3_2.png')
template_image_save_path = MEDIA_DIR / 'caught.png'
template_match_threshold = 0.55
templating_delay_speed = 0.45


def load_template_images():
    templates = {}
    missing_templates = []

    for file_name in TEMPLATE_FILE_NAMES:
        template_path = MEDIA_DIR / file_name
        template_image = cv2.imread(str(template_path))

        if template_image is None:
            missing_templates.append(str(template_path))
            continue

        templates[template_path.stem] = template_image

    if missing_templates:
        raise FileNotFoundError(
            "Unable to load template image(s): " + ", ".join(missing_templates)
        )

    return templates


template_images = load_template_images()

# Bypass variables
max_detection_attempts_threshold = 75
bypass_on_fail = True
bypass_total_fail_threshold = 3
bypass_fail_count = 0

# Statistical variables
start_time = time.time()
pull_attempts = 0
detection_attempts = 0
max_detection_attempts_count = 0

# Get the window associated information
window_title = "Projekt-h4rd"
matching_windows = gw.getWindowsWithTitle(window_title)

if not matching_windows:
    raise RuntimeError(f'Window with title {window_title!r} was not found')

window = matching_windows[0]
window_rect = window.left, window.top, window.width, window.height
window_rect_aoi = window.left + 500, window.top, window.width - 1000, window.height - 700
window.activate()
time.sleep(1)

def find_best_template_match(screen_image):
    best_match = None

    for template_name, template_image in template_images.items():
        if (
            template_image.shape[0] > screen_image.shape[0]
            or template_image.shape[1] > screen_image.shape[1]
        ):
            print(f"Skipping {template_name}: template is larger than the screenshot area")
            continue

        result = cv2.matchTemplate(screen_image, template_image, cv2.TM_CCOEFF_NORMED)
        _, score, _, location = cv2.minMaxLoc(result)

        if best_match is None or score > best_match['score']:
            best_match = {
                'name': template_name,
                'score': score,
                'location': location,
            }

    return best_match


# Function to check for the presence of the image
def check_for_image():
    global detection_attempts
    global pull_attempts
    global max_detection_attempts_count

    # Take a screenshot for the area of interest
    screenshot = pyautogui.screenshot(region=window_rect_aoi)

    # Convert the screenshot to a NumPy array
    screen_image = np.array(screenshot)
    screen_image = cv2.cvtColor(screen_image, cv2.COLOR_RGB2BGR)

    best_match = find_best_template_match(screen_image)

    if best_match and best_match['score'] >= template_match_threshold:
        print(
            "\nImage detected: ",
            best_match['name'],
            " - score: ",
            best_match['score'],
            " - location: ",
            best_match['location'],
        )

        pull_attempts += 1
        detection_attempts = 0

        pull_hook(best_match['name'])
        prepare_for_fishing()
        return False

    detection_attempts += 1
    max_detection_attempts_count = max(detection_attempts, max_detection_attempts_count)
    best_score = best_match['score'] if best_match else 0
    print("Image not detected: ", detection_attempts, " - best score: ", best_score)
    return False


def pull_hook(template_name):
    # Check if the window is active
    if not window.isActive:
        window.activate()
        time.sleep(0.1)

    space_press_count = int(template_name.split('_', 1)[0])
    print(
        "Pulling the hook for template: ",
        template_name,
        " - space presses: ",
        space_press_count,
        " - attempt: ",
        pull_attempts,
    )

    time.sleep(2)

    for press_index in range(space_press_count):
        press_space()

        if press_index < space_press_count - 1:
            time.sleep(0.2)

# Function to check for the unexpected attempt count
def check_for_unexpected_attempt_count():
    global detection_attempts
    global bypass_on_fail
    global bypass_fail_count 

    if detection_attempts >= max_detection_attempts_threshold:
        add_message_to_queue("Unexpected detection attempt count threshold hit: " + str(detection_attempts))
                
        if bypass_on_fail:
            # Bypass the threshold on fail for a few times
            if bypass_fail_count >= bypass_total_fail_threshold:
                add_message_to_queue("Bypassing threshold limit reached")
                return True                 
            
            print("Bypassing the threshold")
            add_message_to_queue("Bypassing the threshold")
            detection_attempts = 0
            time.sleep(5)

            # Take a screenshot and continue processing
            screenshot = pyautogui.screenshot(region=window_rect)    
            screenshot.save(MEDIA_DIR / ('bypass_on_fail_' + str(bypass_fail_count) + '.png'))                                          
            bypass_fail_count = bypass_fail_count + 1

            continuously_check_for_image()
            return False
        else:
            return True

# Function to continuously check for the image
def continuously_check_for_image():
    global templating_delay_speed
    prepare_for_fishing()
    try:
        while True:
            time.sleep(templating_delay_speed)
            if check_for_image():
                break
            if check_for_unexpected_attempt_count():
                raise TimeoutError("Unexpected attempt count")  
            if exit_signal.is_set():
                raise InterruptedError("Exit signal received")          
    except (KeyboardInterrupt, TimeoutError, InterruptedError):
        global start_time
        global max_detection_attempts_count
        global bypass_fail_count
    
        end_time = time.time()
        elapsed_time_seconds = end_time - start_time
        elapsed_time_minutes = elapsed_time_seconds / 60

        print(f"\nMax failed attempts bypass count:", bypass_fail_count)
        print(f"Max failed attempts count:", max_detection_attempts_count)                

        print(f"\nScript started at: {time.ctime(start_time)}")
        print(f"Script ended at: {time.ctime(end_time)}")
        print(f"Script execution time: {elapsed_time_minutes:.2f} minutes ({elapsed_time_seconds:.2f} seconds)")
        
        exit_signal.set()

        print("\nPress any key to quit.\n")
        input()  # Wait for user to press any key
        sys.exit(1) # Exit the script

setup_task_scheduler()
continuously_check_for_image()