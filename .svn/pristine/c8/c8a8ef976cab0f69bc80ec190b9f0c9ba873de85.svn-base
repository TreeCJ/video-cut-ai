"""CLI serve 命令选项契约测试（不真起服务器）。

`serve --help` 是纯文本观测点：断言 reload 开关存在且默认开启、
端口默认固定 8462。app 工厂本身的行为由 web 测试覆盖。
"""

from __future__ import annotations

import re

from typer.testing import CliRunner

from video_cut.cli import app

cli_runner = CliRunner()


def test_serve_help_offers_reload_default_on() -> None:
    result = cli_runner.invoke(app, ["serve", "--help"])

    assert result.exit_code == 0
    help_text = result.output
    # --reload/--no-reload 开关存在，且默认值为 reload=True（开关显示在
    # 「启用」一侧，typer 的 help 输出里默认开显示为 --no-reload 形式可用）。
    assert "--reload" in help_text
    assert "--no-reload" in help_text


def test_serve_help_default_port_is_pinned() -> None:
    result = cli_runner.invoke(app, ["serve", "--help"])

    assert result.exit_code == 0
    # 默认端口固定：help 文本中 [default: 8462]。
    assert re.search(r"--port[^\n]*", result.output) is not None
    assert "8462" in result.output


def test_serve_reload_default_is_true() -> None:
    """默认进入 reload 模式（dev 场景：改代码免重启）。"""
    import inspect

    from video_cut.cli import serve_command

    # typer 把函数参数默认包成 OptionInfo，真默认值在其 .default。
    signature = inspect.signature(serve_command)
    default = signature.parameters["reload"].default
    assert getattr(default, "default", None) is True
