#!/usr/bin/env python3

import subprocess
import threading
import time

from gpiozero import Button, LED
from PIL import Image, ImageDraw, ImageFont

import lcd177_1


# ============================================================
# Configuration
# ============================================================

FONT_LIGHT = (
    "/usr/share/fonts/truetype/dejavu/"
    "DejaVuSans-ExtraLight.ttf"
)

FONT_REGULAR = (
    "/usr/share/fonts/truetype/dejavu/"
    "DejaVuSans.ttf"
)

FONT_MONO = (
    "/usr/share/fonts/truetype/dejavu/"
    "DejaVuSansMono.ttf"
)

WIDTH = 160
HEIGHT = 128

UPDATE_INTERVAL = 10.0

# 30 minutes
DISPLAY_TIMEOUT = 30 * 60

# Main loop responsiveness
LOOP_INTERVAL = 0.10

CPU_WARN = 80.0
TEMP_WARN = 60.0
MEM_WARN = 85.0

SW1_PIN = 5
SW2_PIN = 6
LED2_PIN = 27

SHUTDOWN_HOLD_TIME = 2.0

SLIDE_MINIMAL = 0
SLIDE_HTOP = 1


# ============================================================
# Colors
# ============================================================

BG = (0, 0, 0)

PRIMARY = (255, 255, 255)
SECONDARY = (165, 165, 175)
TERTIARY = (100, 100, 110)

WARN = (255, 32, 0)

# htop-style vivid colors
CYAN = (0, 255, 255)
GREEN = (0, 255, 0)
YELLOW = (255, 255, 0)
BLUE = (0, 160, 255)
RED = (255, 32, 0)

# Inactive gauge segments
BAR_OFF = (45, 45, 48)


# ============================================================
# Fonts
# ============================================================

# Minimal slide

font_header = ImageFont.truetype(
    FONT_REGULAR,
    14
)

font_value = ImageFont.truetype(
    FONT_LIGHT,
    22
)

font_label = ImageFont.truetype(
    FONT_REGULAR,
    9
)

font_footer = ImageFont.truetype(
    FONT_REGULAR,
    9
)

# htop slide

font_htop_label = ImageFont.truetype(
    FONT_MONO,
    10
)

font_htop_value = ImageFont.truetype(
    FONT_MONO,
    9
)

font_htop_small = ImageFont.truetype(
    FONT_MONO,
    8
)

# Shutdown

font_shutdown = ImageFont.truetype(
    FONT_REGULAR,
    17
)

font_shutdown_small = ImageFont.truetype(
    FONT_REGULAR,
    9
)


# ============================================================
# GPIO
# ============================================================

sw1 = Button(
    SW1_PIN,
    pull_up=False
)

sw2 = Button(
    SW2_PIN,
    pull_up=False,
    hold_time=SHUTDOWN_HOLD_TIME,
    hold_repeat=False
)

led2 = LED(
    LED2_PIN
)


# ============================================================
# Events / State
# ============================================================

shutdown_requested = threading.Event()
sw1_pressed = threading.Event()

display_is_on = True

current_slide = SLIDE_MINIMAL

last_activity = time.monotonic()
last_update = 0.0


# ============================================================
# Button callbacks
# ============================================================

def request_slide_action():
    sw1_pressed.set()


def request_shutdown():
    shutdown_requested.set()


sw1.when_pressed = request_slide_action
sw2.when_held = request_shutdown


# ============================================================
# CPU information
# ============================================================

def read_cpu_times():
    with open("/proc/stat") as f:
        line = f.readline()

    values = list(
        map(
            int,
            line.split()[1:]
        )
    )

    user = values[0]
    nice = values[1]
    system = values[2]
    idle = values[3]

    iowait = (
        values[4]
        if len(values) > 4
        else 0
    )

    irq = (
        values[5]
        if len(values) > 5
        else 0
    )

    softirq = (
        values[6]
        if len(values) > 6
        else 0
    )

    steal = (
        values[7]
        if len(values) > 7
        else 0
    )

    idle_all = (
        idle
        + iowait
    )

    non_idle = (
        user
        + nice
        + system
        + irq
        + softirq
        + steal
    )

    total = (
        idle_all
        + non_idle
    )

    return (
        total,
        idle_all
    )


def get_cpu_percent(previous):
    total_now, idle_now = read_cpu_times()
    total_prev, idle_prev = previous

    total_delta = (
        total_now
        - total_prev
    )

    idle_delta = (
        idle_now
        - idle_prev
    )

    if total_delta <= 0:
        percent = 0.0

    else:
        percent = (
            (
                total_delta
                - idle_delta
            )
            / total_delta
            * 100.0
        )

    percent = max(
        0.0,
        min(
            100.0,
            percent
        )
    )

    return (
        percent,
        (
            total_now,
            idle_now
        )
    )


# ============================================================
# System information
# ============================================================

def get_cpu_temp():
    with open(
        "/sys/class/thermal/thermal_zone0/temp"
    ) as f:

        return (
            int(
                f.read().strip()
            )
            / 1000.0
        )


def get_memory_percent():
    mem = {}

    with open("/proc/meminfo") as f:

        for line in f:
            key, value = line.split(
                ":",
                1
            )

            mem[key] = int(
                value
                .strip()
                .split()[0]
            )

    total = mem["MemTotal"]
    available = mem["MemAvailable"]

    return (
        (
            total
            - available
        )
        / total
        * 100.0
    )


def get_load_info():
    with open("/proc/loadavg") as f:
        fields = f.read().split()

    load1 = float(fields[0])
    load5 = float(fields[1])
    load15 = float(fields[2])

    running_text = fields[3]

    running, tasks = running_text.split(
        "/",
        1
    )

    return (
        load1,
        load5,
        load15,
        int(running),
        int(tasks)
    )


def get_uptime():
    with open("/proc/uptime") as f:

        seconds = int(
            float(
                f.read().split()[0]
            )
        )

    days, seconds = divmod(
        seconds,
        86400
    )

    hours, seconds = divmod(
        seconds,
        3600
    )

    minutes, _ = divmod(
        seconds,
        60
    )

    if days:
        return (
            f"{days}d {hours:02d}h"
        )

    return (
        f"{hours:02d}h {minutes:02d}m"
    )


# ============================================================
# Drawing helpers
# ============================================================

def centered_text(
    draw,
    x_center,
    y,
    text,
    font,
    fill
):
    bbox = draw.textbbox(
        (0, 0),
        text,
        font=font
    )

    text_width = (
        bbox[2]
        - bbox[0]
    )

    draw.text(
        (
            int(
                x_center
                - text_width / 2
            ),
            y
        ),
        text,
        font=font,
        fill=fill
    )


def draw_segment_bar(
    draw,
    x,
    y,
    width,
    height,
    percent,
    mode="cpu"
):
    """
    Draw a vivid htop-style segmented gauge.

    CPU:
        green -> yellow -> red

    Memory:
        green -> blue -> yellow

    The active segments use highly saturated RGB colors
    for better visibility on the small 1.77-inch TFT.
    """

    segments = 18
    gap = 1

    available_width = (
        width
        - gap
        * (
            segments
            - 1
        )
    )

    segment_width = (
        available_width
        / segments
    )

    active_segments = int(
        round(
            percent
            / 100.0
            * segments
        )
    )

    active_segments = max(
        0,
        min(
            segments,
            active_segments
        )
    )

    for i in range(segments):

        x1 = int(
            round(
                x
                + i
                * (
                    segment_width
                    + gap
                )
            )
        )

        x2 = int(
            round(
                x1
                + segment_width
                - 1
            )
        )

        if i >= active_segments:

            color = BAR_OFF

        else:

            ratio = (
                i
                / max(
                    1,
                    segments - 1
                )
            )

            if mode == "cpu":

                # CPU gauge:
                # 0-59%   vivid green
                # 60-79%  vivid yellow
                # 80-100% vivid red

                if ratio < 0.60:
                    color = GREEN

                elif ratio < 0.80:
                    color = YELLOW

                else:
                    color = RED

            else:

                # MEM gauge:
                # green -> blue -> yellow

                if ratio < 0.40:
                    color = GREEN

                elif ratio < 0.70:
                    color = BLUE

                else:
                    color = YELLOW

        draw.rectangle(
            (
                x1,
                y,
                x2,
                y + height - 1
            ),
            fill=color
        )


# ============================================================
# Slide 1 - Minimal
# ============================================================

def draw_minimal_screen(
    cpu,
    temp,
    mem,
    uptime
):
    image = Image.new(
        "RGB",
        (
            WIDTH,
            HEIGHT
        ),
        BG
    )

    draw = ImageDraw.Draw(
        image
    )

    # --------------------------------------------------------
    # Header
    # --------------------------------------------------------

    draw.text(
        (8, 5),
        "rpi1",
        font=font_header,
        fill=PRIMARY
    )

    # --------------------------------------------------------
    # CPU
    # --------------------------------------------------------

    cpu_color = (
        WARN
        if cpu >= CPU_WARN
        else PRIMARY
    )

    centered_text(
        draw,
        42,
        29,
        f"{cpu:.0f}%",
        font_value,
        cpu_color
    )

    centered_text(
        draw,
        42,
        55,
        "CPU",
        font_label,
        SECONDARY
    )

    # --------------------------------------------------------
    # Temperature
    # --------------------------------------------------------

    temp_color = (
        WARN
        if temp >= TEMP_WARN
        else PRIMARY
    )

    centered_text(
        draw,
        118,
        29,
        f"{temp:.1f}°",
        font_value,
        temp_color
    )

    centered_text(
        draw,
        118,
        55,
        "TEMP",
        font_label,
        SECONDARY
    )

    # --------------------------------------------------------
    # Memory
    # --------------------------------------------------------

    mem_color = (
        WARN
        if mem >= MEM_WARN
        else PRIMARY
    )

    centered_text(
        draw,
        42,
        70,
        f"{mem:.0f}%",
        font_value,
        mem_color
    )

    centered_text(
        draw,
        42,
        96,
        "MEMORY",
        font_label,
        SECONDARY
    )

    # --------------------------------------------------------
    # Uptime
    # --------------------------------------------------------

    draw.text(
        (8, 115),
        "Up",
        font=font_footer,
        fill=TERTIARY
    )

    draw.text(
        (25, 115),
        uptime,
        font=font_footer,
        fill=SECONDARY
    )

    lcd177_1.image = image
    lcd177_1.draw_image()


# ============================================================
# Slide 2 - htop style
# ============================================================

def draw_htop_screen(
    cpu,
    temp,
    mem,
    uptime,
    load1,
    load5,
    load15,
    running,
    tasks
):
    image = Image.new(
        "RGB",
        (
            WIDTH,
            HEIGHT
        ),
        BG
    )

    draw = ImageDraw.Draw(
        image
    )

    # --------------------------------------------------------
    # CPU gauge
    # --------------------------------------------------------

    draw.text(
        (4, 3),
        "CPU",
        font=font_htop_label,
        fill=CYAN
    )

    draw.text(
        (28, 3),
        "[",
        font=font_htop_label,
        fill=PRIMARY
    )

    draw_segment_bar(
        draw,
        36,
        5,
        88,
        8,
        cpu,
        mode="cpu"
    )

    draw.text(
        (126, 3),
        "]",
        font=font_htop_label,
        fill=PRIMARY
    )

    cpu_text = (
        f"{cpu:.0f}%"
    )

    bbox = draw.textbbox(
        (0, 0),
        cpu_text,
        font=font_htop_value
    )

    draw.text(
        (
            WIDTH
            - (
                bbox[2]
                - bbox[0]
            )
            - 2,
            4
        ),
        cpu_text,
        font=font_htop_value,
        fill=PRIMARY
    )

    # --------------------------------------------------------
    # Memory gauge
    # --------------------------------------------------------

    draw.text(
        (4, 19),
        "MEM",
        font=font_htop_label,
        fill=CYAN
    )

    draw.text(
        (28, 19),
        "[",
        font=font_htop_label,
        fill=PRIMARY
    )

    draw_segment_bar(
        draw,
        36,
        21,
        88,
        8,
        mem,
        mode="mem"
    )

    draw.text(
        (126, 19),
        "]",
        font=font_htop_label,
        fill=PRIMARY
    )

    mem_text = (
        f"{mem:.0f}%"
    )

    bbox = draw.textbbox(
        (0, 0),
        mem_text,
        font=font_htop_value
    )

    draw.text(
        (
            WIDTH
            - (
                bbox[2]
                - bbox[0]
            )
            - 2,
            20
        ),
        mem_text,
        font=font_htop_value,
        fill=PRIMARY
    )

    # --------------------------------------------------------
    # Load average
    # --------------------------------------------------------

    y = 39

    draw.text(
        (4, y),
        "Load",
        font=font_htop_label,
        fill=CYAN
    )

    draw.text(
        (44, y + 1),
        f"{load1:.2f} {load5:.2f} {load15:.2f}",
        font=font_htop_value,
        fill=PRIMARY
    )

    # --------------------------------------------------------
    # Tasks
    # --------------------------------------------------------

    y = 55

    draw.text(
        (4, y),
        "Tasks",
        font=font_htop_label,
        fill=CYAN
    )

    draw.text(
        (50, y + 1),
        str(tasks),
        font=font_htop_value,
        fill=PRIMARY
    )

    # --------------------------------------------------------
    # Running
    # --------------------------------------------------------

    y = 71

    draw.text(
        (4, y),
        "Running",
        font=font_htop_label,
        fill=CYAN
    )

    draw.text(
        (66, y + 1),
        str(running),
        font=font_htop_value,
        fill=GREEN
    )

    # --------------------------------------------------------
    # Temperature
    # --------------------------------------------------------

    y = 87

    draw.text(
        (4, y),
        "Temp",
        font=font_htop_label,
        fill=CYAN
    )

    temp_color = (
        RED
        if temp >= TEMP_WARN
        else PRIMARY
    )

    draw.text(
        (44, y + 1),
        f"{temp:.1f}C",
        font=font_htop_value,
        fill=temp_color
    )

    # --------------------------------------------------------
    # Uptime
    # --------------------------------------------------------

    y = 103

    draw.text(
        (4, y),
        "Uptime",
        font=font_htop_label,
        fill=CYAN
    )

    draw.text(
        (58, y + 1),
        uptime,
        font=font_htop_value,
        fill=PRIMARY
    )

    # --------------------------------------------------------
    # Slide indicator
    # --------------------------------------------------------

    draw.text(
        (145, 116),
        "2",
        font=font_htop_small,
        fill=TERTIARY
    )

    lcd177_1.image = image
    lcd177_1.draw_image()


# ============================================================
# Screen update
# ============================================================

def draw_current_screen(
    cpu,
    temp,
    mem,
    uptime,
    load1,
    load5,
    load15,
    running,
    tasks
):
    if current_slide == SLIDE_MINIMAL:

        draw_minimal_screen(
            cpu,
            temp,
            mem,
            uptime
        )

    else:

        draw_htop_screen(
            cpu,
            temp,
            mem,
            uptime,
            load1,
            load5,
            load15,
            running,
            tasks
        )


# ============================================================
# Display power control
# ============================================================

def clear_display():
    image = Image.new(
        "RGB",
        (
            WIDTH,
            HEIGHT
        ),
        BG
    )

    lcd177_1.image = image
    lcd177_1.draw_image()


def turn_display_off():
    global display_is_on

    if not display_is_on:
        return

    # Clear LCD first.
    clear_display()

    # Digital OFF only.
    # Do not use PWM.
    lcd177_1.set_backlight(False)

    display_is_on = False


def turn_display_on():
    global display_is_on
    global last_activity

    # Digital ON only.
    # Do not use PWM.
    lcd177_1.set_backlight(True)

    display_is_on = True
    last_activity = time.monotonic()


# ============================================================
# Shutdown screen
# ============================================================

def draw_shutdown_screen():
    image = Image.new(
        "RGB",
        (
            WIDTH,
            HEIGHT
        ),
        BG
    )

    draw = ImageDraw.Draw(
        image
    )

    centered_text(
        draw,
        WIDTH / 2,
        44,
        "Shutting Down",
        font_shutdown,
        PRIMARY
    )

    centered_text(
        draw,
        WIDTH / 2,
        72,
        "please wait",
        font_shutdown_small,
        SECONDARY
    )

    lcd177_1.image = image
    lcd177_1.draw_image()


# ============================================================
# Shutdown handling
# ============================================================

def perform_shutdown():
    lcd177_1.set_backlight(True)

    draw_shutdown_screen()

    led2.blink(
        on_time=0.15,
        off_time=0.15,
        background=True
    )

    time.sleep(1.5)

    subprocess.run(
        [
            "/usr/bin/systemctl",
            "poweroff"
        ],
        check=False
    )


# ============================================================
# Main
# ============================================================

def main():
    global display_is_on
    global current_slide
    global last_activity
    global last_update

    lcd177_1.init("on")

    led2.off()

    display_is_on = True
    current_slide = SLIDE_MINIMAL

    last_activity = time.monotonic()

    previous_cpu = read_cpu_times()

    # --------------------------------------------------------
    # Initial CPU sample
    # --------------------------------------------------------

    start = time.monotonic()

    while (
        time.monotonic()
        - start
        < 1.0
    ):
        if shutdown_requested.is_set():
            perform_shutdown()
            return

        time.sleep(0.05)

    cpu, previous_cpu = get_cpu_percent(
        previous_cpu
    )

    temp = get_cpu_temp()
    mem = get_memory_percent()
    uptime = get_uptime()

    (
        load1,
        load5,
        load15,
        running,
        tasks
    ) = get_load_info()

    draw_current_screen(
        cpu,
        temp,
        mem,
        uptime,
        load1,
        load5,
        load15,
        running,
        tasks
    )

    last_update = time.monotonic()

    # --------------------------------------------------------
    # Main loop
    # --------------------------------------------------------

    try:

        while True:

            # =================================================
            # Shutdown
            # =================================================

            if shutdown_requested.is_set():
                perform_shutdown()
                return

            # =================================================
            # SW1
            # =================================================

            if sw1_pressed.is_set():
                sw1_pressed.clear()

                # ---------------------------------------------
                # Display is sleeping
                # ---------------------------------------------

                if not display_is_on:

                    turn_display_on()

                    # Reset CPU sampling baseline.
                    previous_cpu = read_cpu_times()

                    time.sleep(0.25)

                    cpu, previous_cpu = (
                        get_cpu_percent(
                            previous_cpu
                        )
                    )

                    temp = get_cpu_temp()
                    mem = get_memory_percent()
                    uptime = get_uptime()

                    (
                        load1,
                        load5,
                        load15,
                        running,
                        tasks
                    ) = get_load_info()

                    draw_current_screen(
                        cpu,
                        temp,
                        mem,
                        uptime,
                        load1,
                        load5,
                        load15,
                        running,
                        tasks
                    )

                    last_update = (
                        time.monotonic()
                    )

                # ---------------------------------------------
                # Display is already on
                # ---------------------------------------------

                else:

                    last_activity = (
                        time.monotonic()
                    )

                    if current_slide == SLIDE_MINIMAL:
                        current_slide = SLIDE_HTOP

                    else:
                        current_slide = SLIDE_MINIMAL

                    # Immediately redraw selected slide.
                    cpu, previous_cpu = (
                        get_cpu_percent(
                            previous_cpu
                        )
                    )

                    temp = get_cpu_temp()
                    mem = get_memory_percent()
                    uptime = get_uptime()

                    (
                        load1,
                        load5,
                        load15,
                        running,
                        tasks
                    ) = get_load_info()

                    draw_current_screen(
                        cpu,
                        temp,
                        mem,
                        uptime,
                        load1,
                        load5,
                        load15,
                        running,
                        tasks
                    )

                    last_update = (
                        time.monotonic()
                    )

            # =================================================
            # Display sleep
            # =================================================

            if display_is_on:

                idle_time = (
                    time.monotonic()
                    - last_activity
                )

                if idle_time >= DISPLAY_TIMEOUT:
                    turn_display_off()

                    time.sleep(
                        LOOP_INTERVAL
                    )

                    continue

            # =================================================
            # Periodic monitor update
            # =================================================

            if display_is_on:

                if (
                    time.monotonic()
                    - last_update
                    >= UPDATE_INTERVAL
                ):

                    cpu, previous_cpu = (
                        get_cpu_percent(
                            previous_cpu
                        )
                    )

                    temp = get_cpu_temp()
                    mem = get_memory_percent()
                    uptime = get_uptime()

                    (
                        load1,
                        load5,
                        load15,
                        running,
                        tasks
                    ) = get_load_info()

                    draw_current_screen(
                        cpu,
                        temp,
                        mem,
                        uptime,
                        load1,
                        load5,
                        load15,
                        running,
                        tasks
                    )

                    last_update = (
                        time.monotonic()
                    )

            time.sleep(
                LOOP_INTERVAL
            )

    except KeyboardInterrupt:
        pass

    finally:
        led2.off()


if __name__ == "__main__":
    main()
