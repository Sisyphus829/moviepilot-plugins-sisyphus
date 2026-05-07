import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from apscheduler.triggers.cron import CronTrigger

from app.plugins import _PluginBase


class ShareRateTracker(_PluginBase):
    """分享率追踪插件 (V2)"""

    plugin_name = "分享率追踪"
    plugin_desc = "追踪并可视化馒头、CARPT、聆音、自由农场四个站点的分享率变化趋势"
    plugin_icon = "trending_up.png"
    plugin_version = "1.0.0"
    plugin_author = "Sisyphus"
    author_url = "https://github.com/Sisyphus829"
    plugin_config_prefix = "share_rate_tracker_"
    plugin_order = 100
    auth_level = 1

    TARGET_SITES = ["馒头", "CARPT", "聆音", "自由农场"]

    _enabled = False

    def init_plugin(self, config: dict = None):
        self._enabled = True

    def get_state(self) -> bool:
        return self._enabled

    def stop_service(self):
        self._enabled = False

    @property
    def data_file(self) -> Path:
        return self.get_data_path() / "share_rate_history.json"

    def collect_data(self):
        try:
            from app.chain.site import SiteChain
            sites = SiteChain().get_sites()
            now = datetime.now().strftime("%Y-%m-%d %H:%M")
            record = {"timestamp": now}

            for site in sites:
                site_name = site.get("name")
                if site_name in self.TARGET_SITES:
                    record[site_name] = {
                        "ratio": site.get("ratio", 0),
                        "upload": site.get("upload", 0),
                        "download": site.get("download", 0),
                    }

            history = []
            if self.data_file.exists():
                with open(self.data_file, "r", encoding="utf-8") as f:
                    history = json.load(f)

            history.append(record)

            cutoff = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
            history = [h for h in history if h["timestamp"][:10] >= cutoff]

            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(history, f, ensure_ascii=False, indent=2)

            self.info(f"数据采集完成，共 {len(history)} 条记录")
        except Exception as e:
            self.error(f"数据采集失败：{e}")

    def get_service(self) -> List[Dict[str, Any]]:
        if not self._enabled:
            return []
        return [
            {
                "id": "ShareRateTracker.Collect",
                "name": "分享率追踪-定时采集",
                "trigger": CronTrigger.from_crontab("0 * * * *"),
                "func": self.collect_data,
                "kwargs": {},
            }
        ]

    def get_api(self) -> List[Dict[str, Any]]:
        return [
            {
                "path": "/history",
                "endpoint": self.api_get_history,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "获取分享率历史数据",
            },
            {
                "path": "/latest",
                "endpoint": self.api_get_latest,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "获取最新分享率数据",
            },
        ]

    def api_get_history(self, days: int = 30) -> Dict:
        if not self.data_file.exists():
            return {"code": 0, "data": []}
        with open(self.data_file, "r", encoding="utf-8") as f:
            history = json.load(f)
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        filtered = [h for h in history if h["timestamp"] >= cutoff]
        return {"code": 0, "data": filtered}

    def api_get_latest(self) -> Dict:
        if not self.data_file.exists():
            return {"code": 0, "data": {}}
        with open(self.data_file, "r", encoding="utf-8") as f:
            history = json.load(f)
        return {"code": 0, "data": history[-1] if history else {}}

    def get_dashboard(self, key: str = "main", **kwargs) -> Optional[Tuple[Dict, Dict, List[dict]]]:
        latest_data = self._load_latest()
        col_config = {"cols": 12, "md": 6}
        global_config = {"title": "📊 分享率追踪", "refresh": 30, "border": True}
        items = []
        colors = {"馒头": "#FF9800", "CARPT": "#4CAF50", "聆音": "#2196F3", "自由农场": "#9C27B0"}

        for site in self.TARGET_SITES:
            info = latest_data.get(site, {})
            ratio = info.get("ratio", "N/A")
            items.append({
                "component": "VListItem",
                "props": {
                    "title": site,
                    "subtitle": f"分享率: {ratio}",
                    "prependIcon": "mdi-circle",
                    "prependIconColor": colors.get(site, "#999"),
                },
            })

        page = [{"component": "VList", "content": items}]
        return col_config, global_config, page

    def _load_latest(self) -> dict:
        if not self.data_file.exists():
            return {}
        with open(self.data_file, "r", encoding="utf-8") as f:
            history = json.load(f)
        return history[-1] if history else {}

    def get_page(self) -> List[dict]:
        history = []
        if self.data_file.exists():
            with open(self.data_file, "r", encoding="utf-8") as f:
                history = json.load(f)

        table_rows = []
        for record in reversed(history[-50:]):
            row = [record["timestamp"]]
            for site in self.TARGET_SITES:
                if site in record:
                    row.append(str(record[site].get("ratio", "")))
                else:
                    row.append("")
            table_rows.append(row)

        headers = ["时间"]
        headers.extend(self.TARGET_SITES)

        return [
            {
                "component": "VContainer",
                "content": [
                    {
                        "component": "VCard",
                        "content": [
                            {"component": "VCardTitle", "props": {"text": "📊 分享率变化历史"}},
                            {
                                "component": "VCardText",
                                "content": [
                                    {
                                        "component": "VDataTable",
                                        "props": {
                                            "headers": headers,
                                            "items": table_rows,
                                            "density": "compact",
                                        },
                                    }
                                ],
                            },
                        ],
                    }
                ],
            }
        ]

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        return [
            {
                "component": "VForm",
                "content": [
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "enabled",
                                            "label": "启用插件",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VBtn",
                                        "props": {
                                            "text": "立即采集一次",
                                            "color": "primary",
                                            "onclick": "fetch('/api/v1/plugin/ShareRateTracker/service/collect')",
                                        },
                                    }
                                ],
                            },
                        ],
                    }
                ],
            }
        ], {"enabled": True}

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        return []
