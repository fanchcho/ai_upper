"""给逐页对比补一份可复现的 config.json（语言 / 主题 / 一个可用模型）。

为什么需要：原版的语言跟随系统；本机 `LANG` 为空，Electron 会落到 `en`，而 QML 壳
默认中文，两边页面文案不同就没法逐像素比。这里把 `locale` 显式写成 `en`，桌面端与
QML 壳两侧读同一份 config，看到的文案才一致。

模型同样要显式给：没有可用模型时对话页会渲染「Connect an AI model」引导卡，正文被
遮住，代码块/表格那几页就比不了。指向本机代理（`ANTHROPIC_BASE_URL`）时原版才可能
真发请求；这里只求「有模型可选」，不写密钥。

用法: .venv/bin/python scripts/parity/make_pages_config.py <DEVA_HOME> [--theme light|dark] [--locale en|zh-CN] [--model]
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def main(argv: list) -> None:
    home = Path(argv[1])
    theme = "light"
    locale = "en"
    with_model = "--model" in argv
    if "--theme" in argv:
        theme = argv[argv.index("--theme") + 1]
    if "--locale" in argv:
        locale = argv[argv.index("--locale") + 1]

    config_path = home / "config.json"
    config = {}
    if config_path.is_file():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            config = {}
    config["locale"] = locale
    config["theme"] = theme

    if with_model:
        base = os.environ.get("ANTHROPIC_BASE_URL", "").strip()
        model = os.environ.get("ANTHROPIC_MODEL", "").strip() or "deepseek-v4.1-flash"
        providers = (config.get("models") or {}).get("providers") or []
        for provider in providers:
            if provider.get("id") != "anthropic":
                continue
            provider["enabled"] = True
            provider["apiHost"] = base or "https://api.anthropic.com"
            provider["models"] = [
                {
                    "id": model,
                    "name": model,
                    "enabled": True,
                    "purpose": "llm",
                    "contextWindow": 200000,
                }
            ]
            break
        config.setdefault("models", {})["providers"] = providers
        config.setdefault("models", {})["activeModelId"] = "anthropic:" + model

    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    print("config ok theme=%s locale=%s model=%s at %s" % (theme, locale, with_model, config_path))


if __name__ == "__main__":
    main(sys.argv)
