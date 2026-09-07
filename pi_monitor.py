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

WIDTH = 160
HEIGHT = 128

UPDATE_INTERVAL = 10.0

CPU_WARN = 80.0
TEMP_WARN = 60.0
MEM_WARN = 85.0

SW2_PIN = 6
LED2_PIN = 27

SHUTDOWN_HOLD_TIME = 2.0


# ============================================================
# Colors
# ============================================================

BG = (0, 0, 0)

PRIMARY = (242, 242, 247)
SECONDARY = (142, 142, 147)
TERTIARY = (99, 99, 102)

WARN = (255, 69, 58)


# ============================================================
# Fonts
# ============================================================

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

sw2 = Button(
    SW2_PIN,
    pull_up=False,
    hold_time=SHUTDOWN_HOLD_TIME,
    hold_repeat=False
)

led2 = LED(
    LED2_PIN
)

shutdown_requested = threading.Event()


# ============================================================
# System information
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

    return (
        percent,
        (
            total_now,
            idle_now
        )
    )


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


# ============================================================
# Main screen
# ============================================================

def draw_screen(
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

    # --------------------------------------------------------
    # Full-screen transfer
    # --------------------------------------------------------

    lcd177_1.image = image
    lcd177_1.draw_image()


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

def request_shutdown():
    shutdown_requested.set()


sw2.when_held = request_shutdown


def perform_shutdown():
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
    lcd177_1.init("on")

    led2.off()

    previous_cpu = read_cpu_times()

    try:

        while True:

            if shutdown_requested.wait(
                timeout=UPDATE_INTERVAL
            ):
                perform_shutdown()
                return

            cpu, previous_cpu = (
                get_cpu_percent(
                    previous_cpu
                )
            )

            temp = get_cpu_temp()
            mem = get_memory_percent()
            uptime = get_uptime()

            draw_screen(
                cpu,
                temp,
                mem,
                uptime
            )

    except KeyboardInterrupt:
        pass

    finally:
        led2.off()


if __name__ == "__main__":
    main()
