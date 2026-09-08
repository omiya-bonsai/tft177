# Hardware

## Board

ラズベリーパイ用 汎用UI基板（TFT 1.77インチ）

搭載デバイス：

- TFT 1.77インチ / 160 x 128 / RGB / SPI
- スイッチ x2
- LED x2

本環境ではLCD側にプラグを設定する `_1` 系を使用します。

```text
lcd177_1.py
test_tft_12345_1.py
```

## GPIO

| Device | GPIO | Function |
|---|---:|---|
| SW1 | GPIO5 | Screen switch / Wake |
| SW2 | GPIO6 | Safe Shutdown |
| LED1 | GPIO17 | SD READ activity |
| LED2 | GPIO27 | SD WRITE activity |
| TFT RESET | GPIO18 | Display reset |
| TFT Backlight | GPIO13 | Backlight |
| TFT DC | GPIO0 | Data / Command |

SW1 / SW2は `gpiozero.Button` の内部プルダウンを使用します。

## SPI

TFTはSPI0を使用します。

```python
SPI_DEVICE = 0
SPI_SPEED_HZ = 8000000
```

SPIは事前に有効化してください。

```bash
sudo raspi-config
```

確認用：

```bash
sudo python3 test_tft_12345_1.py
```
