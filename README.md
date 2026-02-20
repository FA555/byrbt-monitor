# BYRBT Monitor

BYRBT Monitor 是一个监控 BYRBT 置顶种子并推送到 qBittorrent 的工具。

## 功能

- 监控 BYRBT 置顶种子列表
- 将新增的置顶种子推送到 qBittorrent 开始下载
- 通过 Bark（一个 iOS Only App）向自己的设备发送通知

## 配置

复制 `/config_example.py` 为 `/config.py`，并根据需要修改所有配置项。

## 运行

```bash
uv sync --no-dev
uv run monitor.py
```
