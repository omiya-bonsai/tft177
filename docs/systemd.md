# systemd

## Service

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

## Enable

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now tft-monitor.service
```

## Operations

状態確認：

```bash
systemctl status tft-monitor.service --no-pager
```

再起動：

```bash
sudo systemctl restart tft-monitor.service
```

停止：

```bash
sudo systemctl stop tft-monitor.service
```

リアルタイムログ：

```bash
journalctl -u tft-monitor.service -f
```

## Syntax Check

`pi_monitor.py` を変更した場合は、再起動前に確認できます。

```bash
python3 -m py_compile pi_monitor.py
```

出力がなければ構文エラーはありません。
