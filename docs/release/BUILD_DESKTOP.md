# Desktop Build Guide

这份说明面向仓库维护者，用来生成桌面版可分发包。

## 前置要求

- 已创建并激活项目虚拟环境
- 已执行过：

```bash
pip install -e .
```

- 本地能正常运行：

```bash
tradingagents-desktop
```

## macOS 打包

执行：

```bash
./scripts/build_desktop_mac.sh
```

产物位置：

```text
dist/macos/TradingAgentsDesktop.app
dist/macos/TradingAgentsDesktop/
```

说明：

- 脚本会自动安装或升级 `PyInstaller`
- 使用 `--windowed` 打包，默认不弹出终端
- 会把 `assets/`、`tradingagents`、`cli` 和关键依赖一起收进包里

## Windows 打包

在 PowerShell 中执行：

```powershell
.\scripts\build_desktop_windows.ps1
```

产物位置：

```text
dist\windows\TradingAgentsDesktop.exe
dist\windows\TradingAgentsDesktop\
```

## 推荐发布方式

- macOS：优先发布 `.app` 所在目录压缩包
- Windows：优先发布整个 `TradingAgentsDesktop` 文件夹压缩包

不建议第一次就做：

- `onefile`
- 代码签名
- 自动更新

先确认基础可运行，再逐步加分发体验。

## 发布前检查清单

- 能正常打开主窗口
- API Key 能保存并自动回填
- 能直接分析 A 股代码，例如 `600519`
- 能直接分析中文股名，例如 `中际旭创`
- 能处理中国主题词，例如 `黄金板块`
- `results/` 目录能正常写出报告
- 日志区和报告区显示正常

## 常见问题

### 1. 打包后启动闪退

先在源码环境运行：

```bash
tradingagents-desktop
```

如果源码环境本身就报错，先修源码再打包。

### 2. Windows 下双击没反应

常见原因：

- 缺少 API Key
- 安全软件拦截
- 打包时依赖没收全

可以先在 PowerShell 里直接运行源码版本确认。

### 3. 打包产物体积大

这是正常现象。`PySide6`、`pandas`、`akshare` 这类依赖会让桌面包偏大。
