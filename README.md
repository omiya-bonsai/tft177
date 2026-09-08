# tft177 - Raspberry Pi System Monitor

Raspberry Pi用「TFT 1.77インチ + スイッチ2個 + LED 2個」の汎用UI基板を使用した、
小型システムモニターです。

[momorara/tft177](https://github.com/momorara/tft177) をforkし、
Raspberry Piの状態表示・ストレージアクセスLED・自動スリープ・Safe Shutdownを追加しています。

- Upstream: [momorara/tft177](https://github.com/momorara/tft177)
- Fork: [omiya-bonsai/tft177](https://github.com/omiya-bonsai/tft177)

## Features

- 1.77インチ / 160 x 128 TFT
- Minimal / htop風の2画面
- CPU使用率・CPU温度・メモリ・Load Average・Uptime
- 30分無操作でDisplay OFF
- SW1: 画面切替 / Display復帰
- SW2: 2秒長押しでSafe Shutdown
- LED1: SDカード READ activity
- LED2: SDカード WRITE activity
- systemdによる自動起動

## Display

### Minimal

```text
rpi1

  12%          43.2°
  CPU          TEMP

  31%                 [Pi]
  MEMORY

Up 2d 04h          Sleep 17m
```

### htop Style

```text
CPU                         12%
 [||||.................]

MEM                         31%
 [||||||...............]

Load      0.12 0.08 0.05
Temp      43.2C
Uptime    2d 04h
```

## GPIO

| Device | GPIO | Function |
|---|---:|---|
| SW1 | GPIO5 | Screen / Wake |
| SW2 | GPIO6 | Safe Shutdown |
| LED1 | GPIO17 | SD READ |
| LED2 | GPIO27 | SD WRITE |
| TFT RESET | GPIO18 | Reset |
| TFT Backlight | GPIO13 | Backlight |
| TFT DC | GPIO0 | Data / Command |

## Installation

```bash
git clone https://github.com/omiya-bonsai/tft177.git
cd tft177

sudo apt update
sudo apt install -y \
  python3-pigpio python3-pil python3-gpiozero \
  pigpio fonts-dejavu fonts-ipafont

sudo systemctl enable --now pigpiod
```

SPIは `raspi-config` で有効化してください。

TFTテスト：

```bash
sudo python3 test_tft_12345_1.py
```

モニターを手動起動：

```bash
sudo python3 pi_monitor.py
```

## Documentation

詳細は `docs/` に分離しています。

- [Hardware](docs/hardware.md) — 基板、GPIO、TFT構成
- [Display](docs/display.md) — 画面、スリープ、描画方式
- [Storage LEDs](docs/storage-leds.md) — READ / WRITEアクセスLED
- [systemd](docs/systemd.md) — 自動起動とサービス管理
- [Troubleshooting](docs/troubleshooting.md) — チラつき、SPI、LEDなどの問題

## Tested Environment

```text
Raspberry Pi 1
Raspberry Pi OS / Debian
Python 3
pigpio
SPI
160 x 128 TFT
```

本環境ではLCD側にプラグを設定する `_1` 系を使用しています。

```text
lcd177_1.py
test_tft_12345_1.py
```

## License

MIT License

詳細：

```text
LICENSE.txt
THIRD_PARTY_LICENSES.txt
```

## Credits

Original project: [TKJ-Works / momorara](https://github.com/momorara/tft177)
