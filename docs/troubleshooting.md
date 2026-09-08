# Troubleshooting

## Displayが表示されない

本環境では `_1` 系を使用します。

```bash
sudo python3 test_tft_12345_1.py
```

SPIも確認してください。

```bash
ls /dev/spidev*
```

## `draw_image()` TypeError

正しい呼び出し：

```python
lcd177_1.image = image
lcd177_1.draw_image()
```

誤り：

```python
lcd177_1.draw_image(image)
```

## Displayが激しくチラつく

GPIO13のバックライトにソフトウェアPWMを使用しないでください。

この実機ではPWMによって強い明滅が発生しました。

部分更新も使用せず、全面更新方式を使用します。

## WRITE LEDが反応しない

まず書き込み先を確認します。

```bash
findmnt -T /tmp
findmnt -T "$HOME"
```

`/tmp` が `tmpfs` の場合、`/tmp` への書き込みではSDカードへI/Oが発生しません。

テスト：

```bash
dd if=/dev/zero \
  of="$HOME/storage-led-test.bin" \
  bs=1M count=100 \
  conv=fsync
```

## Serviceが起動しない

```bash
systemctl status tft-monitor.service --no-pager
journalctl -u tft-monitor.service -n 50 --no-pager
```

Pythonの構文も確認します。

```bash
python3 -m py_compile pi_monitor.py
```
