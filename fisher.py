import cv2
import numpy as np
import pyautogui
import time
import sys
import os
from pathlib import Path
import pygetwindow as gw

from utils.keyboard import press_space, prepare_for_fishing

from task_scheduler.scheduler import exit_signal, setup_task_scheduler
from task_scheduler.message_queue_handler import add_message_to_queue

try:
    sys.stdout.reconfigure(line_buffering=True, write_through=True)
    sys.stderr.reconfigure(line_buffering=True, write_through=True)
except Exception:
    pass

print("\nFisher script started.\n", flush=True)
time.sleep(5)

# Global variables
def bundled_base_dir() -> Path:
    """Return the folder that contains bundled read-only assets."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent


def writable_output_dir() -> Path:
    """Return a writable folder for screenshots generated at runtime."""
    configured_dir = os.environ.get("FISHER_OUTPUT_DIR")
    if configured_dir:
        output_dir = Path(configured_dir).expanduser()
    elif getattr(sys, "frozen", False):
        output_dir = Path.cwd() / "fishbot-output"
    else:
        output_dir = bundled_base_dir() / 'media'

    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def env_float(name, default):
    """Read a float from the environment and fall back to a safe default."""
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default

    try:
        return float(raw_value)
    except ValueError:
        print(
            f"[GUI/FISHER] Warning: invalid {name}={raw_value!r}; "
            f"using default {default}"
        )
        return default


BASE_DIR = bundled_base_dir()
MEDIA_DIR = BASE_DIR / 'media'
OUTPUT_DIR = writable_output_dir()
TEMPLATE_FILE_NAMES = ('1_1.png', '1_2.png', '2_1.png', '2_2.png', '3_1.png', '3_2.png')
template_image_save_path = OUTPUT_DIR / 'caught.png'
DEBUG_SCREENSHOTS = True
DEBUG_SCREENSHOT_EVERY_N_ATTEMPTS = 20
template_match_threshold = env_float("FISHER_TEMPLATE_THRESHOLD", 0.40)
templating_delay_speed = 0.10

print(f"[GUI/FISHER] Base dir: {BASE_DIR}")
print(f"[GUI/FISHER] Media dir: {MEDIA_DIR}")
print(f"[GUI/FISHER] Output dir: {OUTPUT_DIR}")
print(f"[GUI/FISHER] Template match threshold: {template_match_threshold}")
print(
    f"[GUI/FISHER] Debug screenshots enabled: {DEBUG_SCREENSHOTS} "
    f"(every {DEBUG_SCREENSHOT_EVERY_N_ATTEMPTS} attempts)"
)


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

    print(
        f"[GUI/FISHER] Loaded {len(templates)} template image(s): "
        + ", ".join(sorted(templates.keys()))
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
window_title = "Projekt Hard"


def get_available_window_titles():
    try:
        return [title for title in gw.getAllTitles() if title]
    except Exception as exc:
        return [f"<unable to list windows: {exc}>"]


def describe_window(window):
    try:
        return (
            f"title={window.title!r}, "
            f"left={window.left}, top={window.top}, "
            f"width={window.width}, height={window.height}"
        )
    except Exception as exc:
        return f"<stale or unavailable window: {exc}>"


def find_target_window(title):
    print(f"[GUI/FISHER] Looking for window with title: {title}")

    try:
        matching_windows = gw.getWindowsWithTitle(title)
    except Exception as exc:
        print(f"[GUI/FISHER] Warning: unable to query windows: {exc}")
        matching_windows = []

    if not matching_windows:
        available_windows = get_available_window_titles()
        print(f"[GUI/FISHER] Window with title {title!r} was not found.")
        print("[GUI/FISHER] Available windows:")
        for available_title in available_windows:
            print(f"[GUI/FISHER] - {available_title}")
        raise RuntimeError(f"Window with title {title!r} was not found")

    for matching_window in matching_windows:
        window_description = describe_window(matching_window)

        if window_description.startswith("<stale or unavailable window:"):
            print(f"[GUI/FISHER] Warning: skipping invalid window: {window_description}")
            continue

        print(f"[GUI/FISHER] Found window: {window_description}")
        return matching_window

    available_windows = get_available_window_titles()
    print(f"[GUI/FISHER] Window with title {title!r} was found, but no valid window handle was available.")
    print("[GUI/FISHER] Available windows:")
    for available_title in available_windows:
        print(f"[GUI/FISHER] - {available_title}")
    raise RuntimeError(f"Window with title {title!r} was not available")


def restore_window_if_minimized(window):
    try:
        if window.isMinimized:
            print("[GUI/FISHER] Window is minimized; attempting to restore it.")
            window.restore()
            time.sleep(0.2)
    except Exception as exc:
        print(f"[GUI/FISHER] Warning: unable to restore window: {exc}")


def activate_window(window):
    try:
        print(f"[GUI/FISHER] Activating target window: {describe_window(window)}")
        window.activate()
        time.sleep(1)
        print("[GUI/FISHER] Activation request completed.")
        return True
    except Exception as exc:
        print(f"[GUI/FISHER] Warning: unable to activate window: {exc}")
        return False


def prepare_target_window(window):
    print("[GUI/FISHER] Preparing target window.")
    restore_window_if_minimized(window)
    activate_window(window)


def get_window_rectangles(window):
    try:
        left = window.left
        top = window.top
        width = window.width
        height = window.height
    except Exception as exc:
        raise RuntimeError(f"Unable to read target window geometry: {exc}") from exc

    window_rect = (left, top, width, height)
    window_rect_aoi = window_rect
    print(f"[GUI/FISHER] window_rect: {window_rect}")
    print(f"[GUI/FISHER] window_rect_aoi: {window_rect_aoi}")
    return window_rect, window_rect_aoi


window = find_target_window(window_title)
prepare_target_window(window)
try:
    window_rect, window_rect_aoi = get_window_rectangles(window)
except RuntimeError as exc:
    print(f"[GUI/FISHER] Warning: target window became unavailable after activation attempt: {exc}")
    window = find_target_window(window_title)
    window_rect, window_rect_aoi = get_window_rectangles(window)

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

    attempt_number = detection_attempts + 1

    # Take a screenshot for the area of interest
    screenshot = pyautogui.screenshot(region=window_rect_aoi)

    if (
        DEBUG_SCREENSHOTS
        and DEBUG_SCREENSHOT_EVERY_N_ATTEMPTS > 0
        and attempt_number % DEBUG_SCREENSHOT_EVERY_N_ATTEMPTS == 0
    ):
        debug_screenshot_path = OUTPUT_DIR / f"debug_aoi_{attempt_number}.png"
        screenshot.save(debug_screenshot_path)
        print(f"[GUI/FISHER] Saved debug AOI screenshot: {debug_screenshot_path}")

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
    best_template = best_match['name'] if best_match else '<none>'
    print(
        "Image not detected: ",
        detection_attempts,
        " - best template: ",
        best_template,
        " - best score: ",
        best_score,
        " - threshold: ",
        template_match_threshold,
        " - AOI: ",
        window_rect_aoi,
    )
    return False


def pull_hook(template_name):
    # Check if the window is active
    try:
        is_window_active = window.isActive
    except Exception as exc:
        print(f"[GUI/FISHER] Warning: unable to read active window state: {exc}")
        is_window_active = False

    print(f"[GUI/FISHER] Window active before pull: {is_window_active}")

    if not is_window_active:
        activate_window(window)

    space_press_count = int(template_name.split('_', 1)[0])
    print(
        "Pulling the hook for template: ",
        template_name,
        " - space presses: ",
        space_press_count,
        " - attempt: ",
        pull_attempts,
    )

    print("[GUI/FISHER] Waiting before sending pull input.")
    time.sleep(2)

    for press_index in range(space_press_count):
        print(f"[GUI/FISHER] Sending space press {press_index + 1}/{space_press_count}")
        press_space()

        if press_index < space_press_count - 1:
            time.sleep(0.2)

# Function to check for the unexpected attempt count
def check_for_unexpected_attempt_count():
    global detection_attempts
    global bypass_on_fail
    global bypass_fail_count 

    if detection_attempts >= max_detection_attempts_threshold:
        print(
            f"[GUI/FISHER] Detection threshold reached: "
            f"{detection_attempts}/{max_detection_attempts_threshold}"
        )
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
            print(f"[GUI/FISHER] Capturing bypass screenshot for full window: {window_rect}")
            screenshot = pyautogui.screenshot(region=window_rect)    
            bypass_screenshot_path = OUTPUT_DIR / ('bypass_on_fail_' + str(bypass_fail_count) + '.png')
            screenshot.save(bypass_screenshot_path)
            print(f"[GUI/FISHER] Saved bypass screenshot: {bypass_screenshot_path}")
            bypass_fail_count = bypass_fail_count + 1

            continuously_check_for_image()
            return False
        else:
            return True

# Function to continuously check for the image
def continuously_check_for_image():
    global templating_delay_speed
    print("[GUI/FISHER] Starting continuous image detection loop.")
    prepare_for_fishing()
    try:
        while True:
            print(f"[GUI/FISHER] Sleeping {templating_delay_speed} seconds before next detection attempt.")
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

        if sys.stdin and sys.stdin.isatty():
            print("Press any key to quit.", flush=True)
            input()  # Wait for user to press any key
        sys.exit(1) # Exit the script

print("[GUI/FISHER] Setting up task scheduler.")
setup_task_scheduler()
print("[GUI/FISHER] Task scheduler setup completed.")
continuously_check_for_image()
