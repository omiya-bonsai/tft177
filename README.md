# tft177 - Raspberry Pi System Monitor

Raspberry Pi用「TFT 1.77インチ + スイッチ2個 + LED 2個」の汎用UI基板を使用した、
小型システムモニターです。

このリポジトリは [momorara/tft177](https://github.com/momorara/tft177) をforkし、
Raspberry Piの常時表示システムモニターとして機能を追加したものです。

- Upstream: [momorara/tft177](https://github.com/momorara/tft177)
- Fork: [omiya-bonsai/tft177](https://github.com/omiya-bonsai/tft177)

---

## System Monitor

`pi_monitor.py` でRaspberry Piの状態を1.77インチTFTへ常時表示します。

表示項目：

- CPU使用率
- CPU温度
- メモリ使用率
- Uptime

160 x 128 pxの小型ディスプレイで視認しやすいよう、
情報量を抑えた2カラムUIにしています。

```text
rpi1

  12%          43.2°
  CPU          TEMP

  31%
  MEMORY

Up 2d 04h
```

数値には `DejaVu Sans ExtraLight`、ラベルには通常の `DejaVu Sans` を使用しています。

通常時はモノトーン表示とし、CPU負荷・CPU温度・メモリ使用率が閾値を超えた場合のみ赤色で表示します。

---

## Controls

### SW2 - Safe Shutdown

SW2を約2秒間長押しすると、Raspberry Piを安全にシャットダウンします。

シャットダウン開始時にはTFTへ

```text
Shutting Down

please wait
```

と表示し、LED2が点滅します。

GPIO：

| Device | GPIO | Function |
|---|---:|---|
| SW1 | GPIO5 | Reserved |
| SW2 | GPIO6 | Shutdown button |
| LED1 | GPIO17 | Reserved |
| LED2 | GPIO27 | Shutdown indicator |
| TFT RESET | GPIO18 | Display reset |
| TFT Backlight | GPIO13 | Backlight |
| TFT DC | GPIO0 | Data / Command |

SW1 / SW2は `gpiozero.Button` の内部プルダウンを使用します。

---

## Hardware

使用基板：

**ラズベリーパイ用 汎用UI基板（TFT 1.77インチ）**

TFT：

- 1.77 inch
- 160 x 128 px
- RGB
- SPI

基板には以下が搭載されています。

- TFTディスプレイ x1
- スイッチ x2
- LED x2

本環境では、LCD側にプラグを設定する `_1` 系プログラムを使用しています。

```text
lcd177_1.py
test_tft_12345_1.py
```

---

## Tested Environment

このforkのシステムモニターは以下の環境で動作確認しています。

```text
Raspberry Pi 1
Raspberry Pi OS / Debian
Python 3
pigpio
SPI
160 x 128 TFT
```

TFT表示、システムモニター、自動起動、SW2長押しによるシャットダウンを実機で確認しています。

---

## Installation

### 1. Clone

このforkを使用する場合：

```bash
git clone https://github.com/omiya-bonsai/tft177.git
cd tft177
```

### 2. SPIを有効化

```bash
sudo raspi-config
```

SPIを有効にします。

### 3. 必要パッケージ

```bash
sudo apt update

sudo apt install -y \
  python3-pigpio \
  python3-pil \
  python3-gpiozero \
  pigpio \
  fonts-dejavu \
  fonts-ipafont
```

### 4. pigpiod

```bash
sudo systemctl enable --now pigpiod
```

確認：

```bash
systemctl status pigpiod --no-pager
```

### 5. TFTテスト

```bash
cd ~/tft177
sudo python3 test_tft_12345_1.py
```

TFTへ数字列が表示されれば基本的なSPI通信は正常です。

---

## Run System Monitor

手動で実行する場合：

```bash
cd ~/tft177
sudo python3 pi_monitor.py
```

停止：

```text
Ctrl-C
```

通常運用ではsystemdから起動します。

---

## systemd

`pi_monitor.py` はsystemdサービスとして常時起動できます。

サービス：

```text
/etc/systemd/system/tft-monitor.service
```

設定例：

```ini
[Unit]
Description=TFT System Monitor
After=network.target pigpiod.service
Requires=pigpiod.service

[Service]
Type=simple
User=root
WorkingDirectory=/home/bonsai/tft177
ExecStart=/usr/bin/python3 /home/bonsai/tft177/pi_monitor.py

Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
```

反映：

```bash
sudo systemctl daemon-reload
sudo systemctl enable tft-monitor.service
sudo systemctl start tft-monitor.service
```

状態確認：

```bash
systemctl status tft-monitor.service --no-pager
```

ログ：

```bash
journalctl -u tft-monitor.service
```

再起動：

```bash
sudo systemctl restart tft-monitor.service
```

停止：

```bash
sudo systemctl stop tft-monitor.service
```

---

## Display Flicker

### バックライトPWMを使用しない

この環境では、GPIO13のバックライトを `PWMOutputDevice` で駆動すると、
TFT表示に強いチラつきが発生しました。

問題が発生した構成：

```python
from gpiozero import PWMOutputDevice

backlight = PWMOutputDevice(
    BACKLIGHT_PIN,
    frequency=1000,
    initial_value=0.45
)
```

実機では、雷のような強い明滅が発生しました。

バックライトを通常のデジタル出力へ戻すことで解消しています。

```python
from gpiozero import DigitalOutputDevice

backlight = DigitalOutputDevice(
    BACKLIGHT_PIN,
    initial_value=False
)
```

ON/OFF：

```python
def set_backlight(state):
    if state:
        backlight.on()
    else:
        backlight.off()
```

現在はGPIO13を常時HIGHとして使用しています。

**この環境ではバックライトのソフトウェアPWMは使用しないでください。**

---

## Display Update

TFTへの描画は `lcd177_1.py` の `draw_image()` を使用します。

SPI設定：

```python
SPI_DEVICE = 0
SPI_SPEED_HZ = 8000000
```

画面はPillow上で完成させてから、1フレームとしてTFTへ転送します。

過去に部分更新も試しましたが、このTFTでは強い表示乱れが発生したため採用していません。

現在は安定性を優先して全面更新方式を使用しています。

---

## Fonts

システムモニターでは以下を使用します。

### Values

```text
/usr/share/fonts/truetype/dejavu/DejaVuSans-ExtraLight.ttf
```

CPU使用率、CPU温度、メモリ使用率などの大きな数値に使用します。

### Labels

```text
/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf
```

`CPU`、`TEMP`、`MEMORY`、Uptimeなどに使用します。

---

## Files

主なファイル：

```text
lcd177_1.py
    TFT制御

pi_monitor.py
    Raspberry Pi System Monitor

test_tft_12345_1.py
    TFT基本表示テスト

test_LED.py
    LEDテスト

test_sw.py
    スイッチテスト
```

---

## Git

このforkではremoteを次のように構成しています。

```text
origin
  https://github.com/omiya-bonsai/tft177.git

upstream
  https://github.com/momorara/tft177.git
```

通常の変更：

```bash
git add .
git commit -m "..."
git push
```

上流リポジトリの更新確認：

```bash
git fetch upstream
```

---

## Upstream Project

このプロジェクトのハードウェア制御およびTFTドライバは、
TKJ-Works / momorara氏のオリジナルプロジェクトをベースにしています。

Upstream：

[https://github.com/momorara/tft177](https://github.com/momorara/tft177)

オリジナルプロジェクトは、TFT 1.77インチ、スイッチ2個、LED 2個を搭載した
Raspberry Pi用汎用UI基板のサンプルプログラムとして公開されています。

2026年4月以降のバージョンでは、TFTのSPI通信に `pigpio` が使用されています。

---

## Upstream Compatibility Notes

上流READMEでは以下のRaspberry Pi / OSについて動作確認情報が公開されています。

主な近年の更新：

- 2025-01-10: ライブラリを全面的に更新
- 2025-03-25: Bookworm 12.10 64bit
- 2025-06-18: Bookworm 12.11 64bit
- 2025-10-03: Bookworm 12.12 / Trixie 13.1
- 2025-11-17: Trixie 13.2
- 2026-01-28: Trixie 13.3
- 2026-03-19: Trixie 13.4 64bit
- 2026-04-08: `spidev` から `pigpio` へ変更
- 2026-04-13: Trixie 13.4 32bit
- 2026-05-17: Trixie 13.5 64bit
- 2026-07-13: Bookworm 12.14 64bit

詳細についてはupstreamリポジトリおよび付属資料を参照してください。

---

## License

This project is licensed under the MIT License.

オリジナル部分および使用ライブラリについては、
それぞれのライセンス条件に従います。

詳細：

```text
LICENSE.txt
THIRD_PARTY_LICENSES.txt
```

---

## Credits

Original project:

- TKJ-Works / momorara
- https://github.com/momorara/tft177

System Monitor fork:

- omiya-bonsai
- https://github.com/omiya-bonsai/tft177
