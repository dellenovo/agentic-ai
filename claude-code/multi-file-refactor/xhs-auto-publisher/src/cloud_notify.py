from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class CloudNotifier:
    def __init__(self, app_config: dict[str, Any]) -> None:
        self.app_config = app_config

    def qr_handoff_enabled(self) -> bool:
        mode = str(self.app_config.get("notify_qr_via", "none")).lower()
        return mode in ("lobster_channel", "feishu_direct")

    def notify_qr(self, screenshot_path: Path, *, run_dir: Path) -> None:
        mode = str(self.app_config.get("notify_qr_via", "none")).lower()
        if mode == "lobster_channel":
            self._emit_lobster_channel_payload(screenshot_path, run_dir=run_dir)
        elif mode == "feishu_direct":
            self._notify_qr_direct_feishu(screenshot_path, run_dir=run_dir)
        else:
            raise RuntimeError(f"Unsupported cloud notify mode: {mode}")

    def _emit_lobster_channel_payload(self, screenshot_path: Path, *, run_dir: Path) -> None:
        notify_dir = self._notify_dir(run_dir)
        notify_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "ts": datetime.now(timezone.utc).astimezone().isoformat(),
            "channel": "lobster_channel",
            "kind": "login_qr",
            "platform": str(self.app_config.get("platform", "xiaohongshu")),
            "title": f"{self._title_prefix()} 小红书登录二维码",
            "run_id": run_dir.name,
            "screenshot_path": str(screenshot_path),
            "message_lines": self._build_message_lines(screenshot_path, run_dir=run_dir),
            "action": "send_image_to_feishu_group",
            "delivery": {
                "type": "image_file",
                "path": str(screenshot_path),
                "caption_lines": self._build_message_lines(screenshot_path, run_dir=run_dir),
            },
        }
        path = notify_dir / "login_qr.payload.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _notify_qr_direct_feishu(self, screenshot_path: Path, *, run_dir: Path) -> None:
        """Send QR screenshot directly to a Feishu group via Feishu IM API."""
        # Lazy import: only load FeishuClient when feishu_direct mode is active
        _common_dir = Path(__file__).resolve().parent.parent.parent / "common"
        if str(_common_dir) not in sys.path:
            sys.path.insert(0, str(_common_dir))
        from feishu.client import FeishuClient  # noqa: E402
        from feishu.errors import FeishuApiError  # noqa: E402

        # Resolve credentials: env vars first, then config
        feishu_app_id = os.environ.get("FEISHU_APP_ID") or self.app_config.get("feishu_app_id")
        feishu_app_secret = os.environ.get("FEISHU_APP_SECRET") or self.app_config.get(
            "feishu_app_secret"
        )
        chat_id = os.environ.get("FEISHU_CHAT_ID") or self.app_config.get("feishu_chat_id")

        if not all([feishu_app_id, feishu_app_secret, chat_id]):
            raise RuntimeError(
                "feishu_direct mode requires FEISHU_APP_ID, FEISHU_APP_SECRET, "
                "and FEISHU_CHAT_ID (set via env vars or config/app.json)."
            )

        client = FeishuClient(app_id=str(feishu_app_id), app_secret=str(feishu_app_secret))

        try:
            # Send image first
            client.send_im_image(chat_id=str(chat_id), image_path=screenshot_path)
            # Send caption text as follow-up
            caption = "\n".join(self._build_message_lines(screenshot_path, run_dir=run_dir))
            client.send_im_text(chat_id=str(chat_id), text=caption)
        except FeishuApiError as exc:
            # Soft error: log but don't crash the publish flow
            print(f"[cloud_notify] feishu_direct failed: {exc}", file=sys.stderr)

    def _notify_dir(self, run_dir: Path) -> Path:
        configured = str(self.app_config.get("lobster_notify_dir", "runtime/lobster-notify")).strip()
        base = Path(configured)
        if not base.is_absolute():
            base = run_dir.parent.parent / base.name
        return base / run_dir.name

    def _title_prefix(self) -> str:
        return str(self.app_config.get("feishu_title_prefix", "[XHS Cloud Login]")).strip() or "[XHS Cloud Login]"

    def _build_message_lines(self, screenshot_path: Path, *, run_dir: Path) -> list[str]:
        return [
            f"{self._title_prefix()} 小红书登录二维码",
            f"Run ID: {run_dir.name}",
            f"图片路径: {screenshot_path}",
            "请把这张二维码图片直接发到飞书群，用户扫码后等待任务继续。",
        ]
