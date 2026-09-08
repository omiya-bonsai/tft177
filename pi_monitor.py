#!/usr/bin/env python3

import os
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

PI_LOGO_PATH = (
    "/home/bonsai/tft177/"
    "raspberry-pi-logo-32x40.png"
)

WIDTH = 160
HEIGHT = 128

UPDATE_INTERVAL = 10.0

# 30 minutes
DISPLAY_TIMEOUT = 30 * 60

LOOP_INTERVAL = 0.10

CPU_WARN = 80.0
TEMP_WARN = 60.0
MEM_WARN = 85.0

SW1_PIN = 5
SW2_PIN = 6

LED1_PIN = 17
LED2_PIN = 27

SHUTDOWN_HOLD_TIME = 2.0

SLIDE_MINIMAL = 0
SLIDE_HTOP = 1


# ============================================================
# Storage activity LED
# ============================================================

# Raspberry Pi SD card block device
STORAGE_STAT_PATH = "/sys/block/mmcblk0/stat"

# Poll every 50 ms
STORAGE_POLL_INTERVAL = 0.01
STORAGE_LED_HOLD_TIME = 0.03

# ============================================================
# Colors
# ============================================================

BG = (0, 0, 0)

PRIMARY = (245, 245, 245)
SECONDARY = (145, 145, 155)
TERTIARY = (85, 85, 95)

WARN = (190, 25, 0)

# htop-style colors
CYAN = (0, 150, 170)
GREEN = (0, 135, 0)
YELLOW = (190, 135, 0)
BLUE = (0, 70, 180)
RED = (190, 25, 0)

BAR_OFF = (18, 18, 22)


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
    11
)

font_htop_value = ImageFont.truetype(
    FONT_MONO,
    10
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
# Raspberry Pi logo
# ============================================================

try:
    pi_logo = Image.open(
        PI_LOGO_PATH
    ).convert("RGB")

except Exception as exc:
    print(
        f"WARNING: could not load Raspberry Pi logo: {exc}"
    )

    pi_logo = None


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


# SD card READ activity LED
led1 = LED(
    LED1_PIN
)

# SD card WRITE activity LED
led2 = LED(
    LED2_PIN
)

# ============================================================
# Events / State
# ============================================================

shutdown_requested = threading.Event()
sw1_pressed = threading.Event()

storage_monitor_stop = threading.Event()

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
# Storage activity monitoring
# ============================================================

def read_storage_activity():
    """
    Read Linux block-device statistics.

    /sys/block/mmcblk0/stat fields include:
      0  reads completed
      2  sectors read
      4  writes completed
      6  sectors written

    We use those four counters to detect both reads and writes.
    """

    with open(
        STORAGE_STAT_PATH
    ) as f:
        values = list(
            map(
                int,
                f.read().split()
            )
        )

    if len(values) < 7:
        raise RuntimeError(
            "unexpected mmcblk0 stat format"
        )

    return (
        values[0],
        values[2],
        values[4],
        values[6]
    )


def storage_activity_worker():
    """
    Monitor SD-card activity.

    LED1 / GPIO17:
        READ activity

    LED2 / GPIO27:
        WRITE activity

    The LEDs are kept on for a short minimum period so very
    short I/O operations remain visible to the human eye.
    """

    if not os.path.exists(
        STORAGE_STAT_PATH
    ):
        print(
            "WARNING: storage activity monitor disabled: "
            f"{STORAGE_STAT_PATH} not found"
        )

        led1.off()
        led2.off()
        return

    try:
        previous = read_storage_activity()

    except Exception as exc:
        print(
            "WARNING: storage activity monitor disabled: "
            f"{exc}"
        )

        led1.off()
        led2.off()
        return

    read_led_until = 0.0
    write_led_until = 0.0

    while not storage_monitor_stop.is_set():

        now = time.monotonic()

        try:
            current = read_storage_activity()

        except Exception as exc:
            print(
                f"WARNING: storage stat read failed: {exc}"
            )

            led1.off()
            led2.off()
            return

        (
            previous_reads,
            previous_sectors_read,
            previous_writes,
            previous_sectors_written
        ) = previous

        (
            current_reads,
            current_sectors_read,
            current_writes,
            current_sectors_written
        ) = current

        # ====================================================
        # READ activity
        # ====================================================

        read_activity = (
            current_reads
            != previous_reads
            or
            current_sectors_read
            != previous_sectors_read
        )

        if read_activity:

            led1.on()

            read_led_until = max(
                read_led_until,
                now + STORAGE_LED_HOLD_TIME
            )

        elif now >= read_led_until:

            led1.off()

        # ====================================================
        # WRITE activity
        # ====================================================

        write_activity = (
            current_writes
            != previous_writes
            or
            current_sectors_written
            != previous_sectors_written
        )

        if write_activity:

            led2.on()

            write_led_until = max(
                write_led_until,
                now + STORAGE_LED_HOLD_TIME
            )

        elif now >= write_led_until:

            led2.off()

        # ====================================================
        # Save counters for next poll
        # ====================================================

        previous = current

        storage_monitor_stop.wait(
            STORAGE_POLL_INTERVAL
        )

    led1.off()
    led2.off()


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


def get_load_average():
    with open("/proc/loadavg") as f:
        fields = f.read().split()

    return (
        float(fields[0]),
        float(fields[1]),
        float(fields[2])
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


def get_sleep_remaining():
    remaining = (
        DISPLAY_TIMEOUT
        - (
            time.monotonic()
            - last_activity
        )
    )

    remaining = max(
        0,
        remaining
    )

    minutes = int(
        remaining / 60
    )

    if minutes < 1:
        return "<1m"

    return f"{minutes}m"


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
    segments = 20
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

                if ratio < 0.60:
                    color = GREEN

                elif ratio < 0.80:
                    color = YELLOW

                else:
                    color = RED

            else:

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
    # Raspberry Pi logo
    # --------------------------------------------------------

    if pi_logo is not None:

        image.paste(
            pi_logo,
            (
                99,
                69
            )
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

    sleep_remaining = get_sleep_remaining()

    sleep_text = (
        f"Sleep {sleep_remaining}"
    )

    bbox = draw.textbbox(
        (0, 0),
        sleep_text,
        font=font_footer
    )

    sleep_width = (
        bbox[2]
        - bbox[0]
    )

    draw.text(
        (
            WIDTH
            - sleep_width
            - 5,
            115
        ),
        sleep_text,
        font=font_footer,
        fill=TERTIARY
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
    load15
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

    # ========================================================
    # CPU
    # ========================================================

    draw.text(
        (4, 3),
        "CPU",
        font=font_htop_label,
        fill=CYAN
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
            - 3,
            4
        ),
        cpu_text,
        font=font_htop_value,
        fill=PRIMARY
    )

    draw.text(
        (4, 18),
        "[",
        font=font_htop_label,
        fill=PRIMARY
    )

    draw_segment_bar(
        draw,
        14,
        19,
        132,
        11,
        cpu,
        mode="cpu"
    )

    draw.text(
        (148, 18),
        "]",
        font=font_htop_label,
        fill=PRIMARY
    )

    # ========================================================
    # Memory
    # ========================================================

    draw.text(
        (4, 36),
        "MEM",
        font=font_htop_label,
        fill=CYAN
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
            - 3,
            37
        ),
        mem_text,
        font=font_htop_value,
        fill=PRIMARY
    )

    draw.text(
        (4, 51),
        "[",
        font=font_htop_label,
        fill=PRIMARY
    )

    draw_segment_bar(
        draw,
        14,
        52,
        132,
        11,
        mem,
        mode="mem"
    )

    draw.text(
        (148, 51),
        "]",
        font=font_htop_label,
        fill=PRIMARY
    )

    # ========================================================
    # Load
    # ========================================================

    draw.text(
        (4, 72),
        "Load",
        font=font_htop_label,
        fill=CYAN
    )

    draw.text(
        (42, 73),
        f"{load1:.2f} {load5:.2f} {load15:.2f}",
        font=font_htop_value,
        fill=PRIMARY
    )

    # ========================================================
    # Temperature
    # ========================================================

    draw.text(
        (4, 89),
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
        (42, 90),
        f"{temp:.1f}C",
        font=font_htop_value,
        fill=temp_color
    )

    # ========================================================
    # Uptime
    # ========================================================

    draw.text(
        (4, 106),
        "Uptime",
        font=font_htop_label,
        fill=CYAN
    )

    draw.text(
        (58, 107),
        uptime,
        font=font_htop_value,
        fill=PRIMARY
    )

    draw.text(
        (149, 117),
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
    load15
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
            load15
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

    clear_display()

    # Digital OFF only.
    # Never use PWM.
    lcd177_1.set_backlight(False)

    display_is_on = False


def turn_display_on():
    global display_is_on
    global last_activity

    # Digital ON only.
    # Never use PWM.
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

    # Stop storage monitor.
    storage_monitor_stop.set()

    # Storage LEDs are no longer used as shutdown indicators.
    led1.off()
    led2.off()

    lcd177_1.set_backlight(True)

    draw_shutdown_screen()

    time.sleep(1.5)

    subprocess.run(
        [
            "/usr/bin/systemctl",
            "poweroff"
        ],
        check=False
    )

# ============================================================
# Read all monitor values
# ============================================================

def read_monitor_values(
    previous_cpu
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
        load15
    ) = get_load_average()

    return (
        previous_cpu,
        cpu,
        temp,
        mem,
        uptime,
        load1,
        load5,
        load15
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

    led1.off()
    led2.off()

    # --------------------------------------------------------
    # Start storage activity monitor
    # --------------------------------------------------------

    storage_thread = threading.Thread(
        target=storage_activity_worker,
        name="storage-activity",
        daemon=True
    )

    storage_thread.start()

    # --------------------------------------------------------
    # Display state
    # --------------------------------------------------------

    display_is_on = True
    current_slide = SLIDE_MINIMAL

    last_activity = time.monotonic()

    previous_cpu = read_cpu_times()

    # --------------------------------------------------------
    # Initial CPU sampling
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

    (
        previous_cpu,
        cpu,
        temp,
        mem,
        uptime,
        load1,
        load5,
        load15
    ) = read_monitor_values(
        previous_cpu
    )

    draw_current_screen(
        cpu,
        temp,
        mem,
        uptime,
        load1,
        load5,
        load15
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

                    previous_cpu = read_cpu_times()

                    time.sleep(0.25)

                    (
                        previous_cpu,
                        cpu,
                        temp,
                        mem,
                        uptime,
                        load1,
                        load5,
                        load15
                    ) = read_monitor_values(
                        previous_cpu
                    )

                    draw_current_screen(
                        cpu,
                        temp,
                        mem,
                        uptime,
                        load1,
                        load5,
                        load15
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

                    (
                        previous_cpu,
                        cpu,
                        temp,
                        mem,
                        uptime,
                        load1,
                        load5,
                        load15
                    ) = read_monitor_values(
                        previous_cpu
                    )

                    draw_current_screen(
                        cpu,
                        temp,
                        mem,
                        uptime,
                        load1,
                        load5,
                        load15
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

                    (
                        previous_cpu,
                        cpu,
                        temp,
                        mem,
                        uptime,
                        load1,
                        load5,
                        load15
                    ) = read_monitor_values(
                        previous_cpu
                    )

                    draw_current_screen(
                        cpu,
                        temp,
                        mem,
                        uptime,
                        load1,
                        load5,
                        load15
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

        storage_monitor_stop.set()

        led1.off()
        led2.off()


if __name__ == "__main__":
    main()
