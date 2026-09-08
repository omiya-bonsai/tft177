# Display

## Screens

`pi_monitor.py` は2種類の画面を持ちます。

### Minimal

- CPU使用率
- CPU温度
- メモリ使用率
- Uptime
- Sleepまでの残り時間
- Raspberry Piロゴ

### htop Style

- CPU使用率 / ゲージ
- メモリ使用率 / ゲージ
- Load Average
- CPU温度
- Uptime

SW1で切り替えます。

## Auto Sleep

無操作状態が30分続くとDisplayをOFFにします。

OFFになるのはTFTとバックライトのみです。

LED1 / LED2によるストレージ監視は継続します。

SW1を押すとDisplayが復帰し、スリープタイマーもリセットされます。

## Update

通常の画面更新周期は10秒です。

Pillow上で画面全体を作成してから、

```python
lcd177_1.image = image
lcd177_1.draw_image()
```

で全面転送します。

`draw_image()` に画像を引数として渡さないことに注意してください。

## Backlight

GPIO13をデジタルON/OFFで制御します。

```python
backlight = DigitalOutputDevice(
    BACKLIGHT_PIN,
    initial_value=False
)
```

この実機ではソフトウェアPWMによる輝度制御で強いチラつきが発生したため、
PWMは使用していません。

部分更新でも表示乱れが発生したため、全面更新方式を使用しています。
