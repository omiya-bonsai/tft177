# Storage Activity LEDs

基板上のLEDをSDカードアクセス表示に使用します。

```text
LED1 / GPIO17 = READ
LED2 / GPIO27 = WRITE
```

## Monitoring

監視対象：

```text
/sys/block/mmcblk0/stat
```

以下のブロックデバイス統計を監視します。

- reads completed
- sectors read
- writes completed
- sectors written

READカウンタが変化するとLED1、
WRITEカウンタが変化するとLED2を点灯します。

Displayがスリープ中でも監視は継続します。

## READ Test

```bash
sudo find /usr -type f -size +1M -exec cat {} \; > /dev/null
```

主にLED1が反応します。

## WRITE Test

```bash
dd if=/dev/zero \
  of="$HOME/storage-led-test.bin" \
  bs=1M count=100 \
  conv=fsync

rm "$HOME/storage-led-test.bin"
sync
```

主にLED2が反応します。

## `/tmp`

`/tmp` が `tmpfs` の場合、書き込み先はSDカードではなくRAMです。

```bash
findmnt -T /tmp
findmnt -T "$HOME"
```

ストレージLEDのWRITEテストでは、SDカード上の `$HOME` を使用してください。
