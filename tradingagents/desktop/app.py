from __future__ import annotations

import os
import sys
import traceback

from dotenv import load_dotenv

try:
    from PySide6.QtCore import QDate, QObject, QSettings, Qt, QThread, QTimer, QUrl, Signal
    from PySide6.QtGui import QColor, QDesktopServices, QFontDatabase
    from PySide6.QtWidgets import (
        QApplication,
        QComboBox,
        QDateEdit,
        QFormLayout,
        QFrame,
        QGridLayout,
        QGroupBox,
        QHeaderView,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMessageBox,
        QPlainTextEdit,
        QProgressBar,
        QPushButton,
        QScrollArea,
        QSizePolicy,
        QSplitter,
        QTableWidget,
        QTableWidgetItem,
        QTextBrowser,
        QVBoxLayout,
        QWidget,
    )
except ImportError as exc:
    raise SystemExit(
        "PySide6 is required for the desktop app. Reinstall the project so the "
        "desktop dependency is available."
    ) from exc

from tradingagents.llm_clients.model_catalog import get_model_options
from tradingagents.desktop.runtime import (
    AGENT_DISPLAY_NAMES,
    ANALYST_OPTIONS,
    ANTHROPIC_EFFORT_OPTIONS,
    DesktopAnalysisRunner,
    DesktopSelection,
    GOOGLE_THINKING_OPTIONS,
    LANGUAGE_DISPLAY_OPTIONS,
    OPENAI_REASONING_OPTIONS,
    PROVIDER_SPECS,
    RESEARCH_DEPTH_OPTIONS,
    STATUS_AGENT_ORDER,
)
from tradingagents.ticker_utils import normalize_ticker_symbol


APP_STYLESHEET = """
QMainWindow {
    background: #f5efe6;
}
QWidget {
    color: #251a12;
}
QFrame#HeaderCard, QFrame#StatsCard {
    background: #fffdf8;
    border: 1px solid #d4c0a7;
    border-radius: 18px;
}
QGroupBox {
    font-size: 14px;
    font-weight: 600;
    color: #322319;
    border: 1px solid #d4c0a7;
    border-radius: 16px;
    margin-top: 14px;
    background: #fffdf9;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 6px;
}
QLineEdit, QComboBox, QDateEdit, QPlainTextEdit, QTextBrowser, QTableWidget {
    background: #ffffff;
    color: #1f140d;
    border: 1px solid #ccb798;
    border-radius: 10px;
    padding: 7px 10px;
    selection-background-color: #b56f3b;
    selection-color: white;
}
QComboBox QAbstractItemView {
    background: #ffffff;
    color: #1f140d;
    selection-background-color: #c56c39;
    selection-color: white;
}
QLabel {
    color: #2f2219;
}
QLabel[muted="true"] {
    color: #6a5747;
}
QPushButton {
    background: #1f5e52;
    color: white;
    border: none;
    border-radius: 12px;
    padding: 10px 16px;
    font-weight: 600;
}
QPushButton:hover {
    background: #18493f;
}
QPushButton:disabled {
    background: #b6ada1;
    color: #f7f2eb;
}
QProgressBar {
    background: #ede2d4;
    border: none;
    border-radius: 10px;
    min-height: 12px;
}
QProgressBar::chunk {
    background: #c56c39;
    border-radius: 10px;
}
QHeaderView::section {
    background: #efe0ce;
    color: #2d2018;
    border: none;
    padding: 8px;
    font-weight: 600;
}
QScrollArea {
    border: none;
    background: transparent;
}
QFrame#NoticeCard {
    background: #fff4ea;
    border: 1px solid #dbb894;
    border-radius: 16px;
}
"""


COMPLIANCE_NOTICE_VERSION = "2026-04-03.zh-cn.v1"
COMPLIANCE_NOTICE_SUMMARY = (
    "本项目是开源的技术研究/演示工具，仅提供技术支持与辅助分析能力，"
    "不提供任何形式的投资建议、证券推荐、收益承诺或委托理财服务。"
)
COMPLIANCE_NOTICE_HTML = """
<p><b>请在使用前了解以下说明：</b></p>
<ul>
  <li>本项目是开源技术项目，面向研究、学习、工程验证和辅助分析场景，不是持牌证券、投资顾问或资产管理服务。</li>
  <li>分析内容可能综合第三方财经接口、公开网页、联网搜索结果、AI 搜索和大模型生成输出，存在延迟、缺失、误差、幻觉或过时风险。</li>
  <li>程序输出仅供技术参考，不构成任何投资建议、证券买卖建议、收益承诺、招揽或保证。</li>
  <li>使用者应自行核验关键数据，并独立承担交易、投资、税务、法律和运营相关风险与责任。</li>
  <li>第三方数据源、搜索服务、模型服务和网络链路的可用性、准确性与合规性，由对应提供方负责，本项目不作保证。</li>
  <li>桌面端会在本机保存你填写的 API Key 配置，请自行做好设备、账号与密钥安全管理。</li>
  <li>项目按当前仓库许可协议和“按现状”方式提供；如需商业化、面向客户分发或用于投顾场景，请先咨询专业律师或合规顾问。</li>
</ul>
"""


class AnalysisWorker(QObject):
    log = Signal(str)
    status_updated = Signal(dict)
    reports_updated = Signal(str, str)
    stats_updated = Signal(dict)
    finished = Signal(dict)
    failed = Signal(str)

    def __init__(self, selection: DesktopSelection):
        super().__init__()
        self.selection = selection

    def run(self) -> None:
        try:
            runner = DesktopAnalysisRunner(
                self.selection,
                on_log=self.log.emit,
                on_status=self.status_updated.emit,
                on_reports=self.reports_updated.emit,
                on_stats=self.stats_updated.emit,
            )
            self.finished.emit(runner.run())
        except Exception:
            self.failed.emit(traceback.format_exc())


class MainWindow(QMainWindow):
    def __init__(self, show_compliance_notice: bool = True) -> None:
        super().__init__()
        load_dotenv()
        self.settings = QSettings("TradingAgents", "Desktop")
        self.show_compliance_notice = show_compliance_notice
        self._provider_keys: dict[str, str] = {}
        self._active_provider: str | None = None
        self.worker_thread: QThread | None = None
        self.worker: AnalysisWorker | None = None
        self.latest_results_dir: str | None = None
        self.latest_report_path: str | None = None
        self._build_ui()
        self._load_saved_state()
        self._refresh_agent_table({})
        if self.show_compliance_notice:
            QTimer.singleShot(0, self._show_compliance_notice_if_needed)

    def _build_ui(self) -> None:
        self.setWindowTitle("TradingAgents 桌面版")
        self.resize(1520, 980)
        self.setMinimumSize(1280, 840)
        base_font = self.font()
        if base_font.pointSize() < 13:
            base_font.setPointSize(13)
            self.setFont(base_font)
        self.setStyleSheet(APP_STYLESHEET)

        central = QWidget()
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(18, 18, 18, 18)
        root_layout.setSpacing(14)

        header = QFrame()
        header.setObjectName("HeaderCard")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(20, 18, 20, 18)
        title = QLabel("TradingAgents 桌面版")
        title.setStyleSheet("font-size: 28px; font-weight: 700; color: #24180f;")
        subtitle = QLabel(
            "在原生桌面窗口中配置并运行多智能体交易分析，实时查看各个 Agent 的进度、日志和最终报告。"
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("font-size: 13px; color: #4e3d2f;")
        notice_card = QFrame()
        notice_card.setObjectName("NoticeCard")
        notice_layout = QHBoxLayout(notice_card)
        notice_layout.setContentsMargins(14, 12, 14, 12)
        notice_layout.setSpacing(12)
        notice_label = QLabel(
            "合规提示：本项目为开源技术演示，内容可能综合 AI 搜索、第三方财经数据与模型生成结果，仅供研究和技术支持，不构成投资建议。"
        )
        notice_label.setWordWrap(True)
        notice_label.setStyleSheet("color: #6c3f1e; font-size: 12px; font-weight: 600;")
        self.notice_button = QPushButton("查看完整声明")
        self.notice_button.setCursor(Qt.PointingHandCursor)
        self.notice_button.setMaximumWidth(132)
        self.notice_button.setStyleSheet(
            "QPushButton { background: #f3dfca; color: #6c3f1e; border: 1px solid #d7b28c; "
            "border-radius: 10px; padding: 8px 12px; font-weight: 700; }"
            "QPushButton:hover { background: #ecd4bb; }"
        )
        self.notice_button.clicked.connect(self._show_compliance_notice)
        notice_layout.addWidget(notice_label, 1)
        notice_layout.addWidget(self.notice_button, 0, Qt.AlignTop)
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        header_layout.addWidget(notice_card)
        root_layout.addWidget(header)

        stats_row = QFrame()
        stats_row.setObjectName("StatsCard")
        stats_layout = QGridLayout(stats_row)
        stats_layout.setContentsMargins(16, 14, 16, 14)
        stats_layout.setHorizontalSpacing(18)
        stats_layout.setVerticalSpacing(8)

        self.run_state_value = QLabel("空闲")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.llm_calls_value = QLabel("0")
        self.tool_calls_value = QLabel("0")
        self.tokens_in_value = QLabel("0")
        self.tokens_out_value = QLabel("0")
        self.report_path_value = QLabel("尚未运行")
        self.report_path_value.setWordWrap(True)
        self.report_path_value.setTextInteractionFlags(Qt.TextSelectableByMouse)

        for value_label in (
            self.run_state_value,
            self.llm_calls_value,
            self.tool_calls_value,
            self.tokens_in_value,
            self.tokens_out_value,
        ):
            value_label.setStyleSheet("font-weight: 700; color: #24180f;")
        self.report_path_value.setStyleSheet("font-weight: 600; color: #4f3c2e;")

        stats_layout.addWidget(QLabel("运行状态"), 0, 0)
        stats_layout.addWidget(self.run_state_value, 0, 1)
        stats_layout.addWidget(QLabel("进度"), 0, 2)
        stats_layout.addWidget(self.progress_bar, 0, 3)
        stats_layout.addWidget(QLabel("LLM 调用"), 1, 0)
        stats_layout.addWidget(self.llm_calls_value, 1, 1)
        stats_layout.addWidget(QLabel("工具调用"), 1, 2)
        stats_layout.addWidget(self.tool_calls_value, 1, 3)
        stats_layout.addWidget(QLabel("输入 Tokens"), 2, 0)
        stats_layout.addWidget(self.tokens_in_value, 2, 1)
        stats_layout.addWidget(QLabel("输出 Tokens"), 2, 2)
        stats_layout.addWidget(self.tokens_out_value, 2, 3)
        stats_layout.addWidget(QLabel("最新报告"), 3, 0)
        stats_layout.addWidget(self.report_path_value, 3, 1, 1, 3)
        root_layout.addWidget(stats_row)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        controls_scroll = QScrollArea()
        controls_scroll.setWidgetResizable(True)
        controls_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        controls_scroll.setFrameShape(QFrame.NoFrame)
        controls_scroll.setWidget(self._build_controls_panel())
        splitter.addWidget(controls_scroll)
        splitter.addWidget(self._build_output_panel())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([560, 980])
        root_layout.addWidget(splitter, 1)

        self.setCentralWidget(central)

    def _build_controls_panel(self) -> QWidget:
        panel = QWidget()
        panel.setMinimumWidth(500)
        panel.setMaximumWidth(620)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        run_group = QGroupBox("运行配置")
        run_layout = QFormLayout(run_group)
        run_layout.setLabelAlignment(Qt.AlignLeft)
        run_layout.setFormAlignment(Qt.AlignTop)
        run_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        run_layout.setHorizontalSpacing(18)
        run_layout.setVerticalSpacing(12)

        self.ticker_input = QLineEdit()
        self.ticker_input.setPlaceholderText("例如：600519、000001、159915、中际旭创、0700.HK、NVDA")
        self.ticker_input.setClearButtonEnabled(True)

        self.date_input = QDateEdit()
        self.date_input.setCalendarPopup(True)
        self.date_input.setDisplayFormat("yyyy-MM-dd")
        self.date_input.setDate(QDate.currentDate())

        self.language_combo = QComboBox()
        self.language_combo.setEditable(True)
        for display, value in LANGUAGE_DISPLAY_OPTIONS:
            self.language_combo.addItem(display, value)

        self.depth_combo = QComboBox()
        for label, value in RESEARCH_DEPTH_OPTIONS:
            self.depth_combo.addItem(label, value)
        self.depth_combo.setCurrentIndex(1)

        self.provider_combo = QComboBox()
        for provider, spec in PROVIDER_SPECS.items():
            self.provider_combo.addItem(spec["label"], provider)
        self.provider_combo.currentIndexChanged.connect(self._handle_provider_changed)

        self.quick_model_combo = QComboBox()
        self.deep_model_combo = QComboBox()

        self.provider_key_label = QLabel("提供商 API Key")
        self.provider_key_input = QLineEdit()
        self.provider_key_input.setEchoMode(QLineEdit.Password)
        self.provider_key_input.setPlaceholderText("如果环境里已经配置过，这里可以留空")
        self.provider_key_input.setClearButtonEnabled(True)
        self.provider_key_input.textChanged.connect(self._cache_current_provider_key)

        self.alpha_vantage_input = QLineEdit()
        self.alpha_vantage_input.setEchoMode(QLineEdit.Password)
        self.alpha_vantage_input.setPlaceholderText("可选，Yahoo Finance 被限流时用于兜底")
        self.alpha_vantage_input.setClearButtonEnabled(True)
        self.alpha_vantage_input.textChanged.connect(self._cache_alpha_vantage_key)

        self.openai_reasoning_combo = QComboBox()
        for label, value in OPENAI_REASONING_OPTIONS:
            self.openai_reasoning_combo.addItem(label, value)

        self.anthropic_effort_combo = QComboBox()
        for label, value in ANTHROPIC_EFFORT_OPTIONS:
            self.anthropic_effort_combo.addItem(label, value)
        self.anthropic_effort_combo.setCurrentIndex(0)

        self.google_thinking_combo = QComboBox()
        for label, value in GOOGLE_THINKING_OPTIONS:
            self.google_thinking_combo.addItem(label, value)

        expanding_fields = [
            self.ticker_input,
            self.date_input,
            self.language_combo,
            self.depth_combo,
            self.provider_combo,
            self.quick_model_combo,
            self.deep_model_combo,
            self.provider_key_input,
            self.alpha_vantage_input,
            self.openai_reasoning_combo,
            self.anthropic_effort_combo,
            self.google_thinking_combo,
        ]
        for widget in expanding_fields:
            widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        for combo in (
            self.language_combo,
            self.depth_combo,
            self.provider_combo,
            self.quick_model_combo,
            self.deep_model_combo,
            self.openai_reasoning_combo,
            self.anthropic_effort_combo,
            self.google_thinking_combo,
        ):
            combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
            combo.setMinimumContentsLength(18)

        self.openai_reasoning_row = QWidget()
        openai_layout = QHBoxLayout(self.openai_reasoning_row)
        openai_layout.setContentsMargins(0, 0, 0, 0)
        openai_layout.addWidget(self.openai_reasoning_combo)

        self.anthropic_effort_row = QWidget()
        anthropic_layout = QHBoxLayout(self.anthropic_effort_row)
        anthropic_layout.setContentsMargins(0, 0, 0, 0)
        anthropic_layout.addWidget(self.anthropic_effort_combo)

        self.google_thinking_row = QWidget()
        google_layout = QHBoxLayout(self.google_thinking_row)
        google_layout.setContentsMargins(0, 0, 0, 0)
        google_layout.addWidget(self.google_thinking_combo)

        self.ticker_row_label = QLabel("股票代码")
        self.date_row_label = QLabel("分析日期")
        self.language_row_label = QLabel("输出语言")
        self.depth_row_label = QLabel("研究深度")
        self.provider_row_label = QLabel("模型提供商")
        self.quick_model_row_label = QLabel("快速模型")
        self.deep_model_row_label = QLabel("深度模型")
        self.alpha_vantage_label = QLabel("Alpha Vantage Key（可选）")
        self.openai_reasoning_label = QLabel("OpenAI 推理力度")
        self.anthropic_effort_label = QLabel("Claude 思考强度")
        self.google_thinking_label = QLabel("Gemini 思考模式")

        run_layout.addRow(self.ticker_row_label, self.ticker_input)
        run_layout.addRow(self.date_row_label, self.date_input)
        run_layout.addRow(self.language_row_label, self.language_combo)
        run_layout.addRow(self.depth_row_label, self.depth_combo)
        run_layout.addRow(self.provider_row_label, self.provider_combo)
        run_layout.addRow(self.quick_model_row_label, self.quick_model_combo)
        run_layout.addRow(self.deep_model_row_label, self.deep_model_combo)
        run_layout.addRow(self.provider_key_label, self.provider_key_input)
        run_layout.addRow(self.alpha_vantage_label, self.alpha_vantage_input)
        run_layout.addRow(self.openai_reasoning_label, self.openai_reasoning_row)
        run_layout.addRow(self.anthropic_effort_label, self.anthropic_effort_row)
        run_layout.addRow(self.google_thinking_label, self.google_thinking_row)

        run_hint = QLabel(
            "A 股可直接输入 6 位代码或中文股名，程序会自动识别并补成 600519.SS / 000001.SZ 这类格式；分析时会优先走 AkShare、东方财富、百度财经等更适合中国网络的链路。默认推荐使用 DeepSeek；若仍需海外备用源，可补充 Alpha Vantage Key。"
        )
        run_hint.setProperty("muted", "true")
        run_hint.setWordWrap(True)
        run_layout.addRow(QLabel("使用建议"), run_hint)

        analysts_group = QGroupBox("分析师选择")
        analysts_layout = QVBoxLayout(analysts_group)
        analysts_layout.setSpacing(8)
        self.analyst_toggles = {}
        for label, value in ANALYST_OPTIONS:
            checkbox = QPushButton(label)
            checkbox.setCheckable(True)
            checkbox.setChecked(True)
            checkbox.setMinimumHeight(40)
            checkbox.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            checkbox.setStyleSheet(
                "QPushButton { text-align: left; background: #f7f1e8; color: #3d2d22; border: 1px solid #d7c8b3; }"
                "QPushButton:hover { background: #efe5d7; }"
                "QPushButton:checked { background: #b85d2d; color: white; border: none; }"
            )
            analysts_layout.addWidget(checkbox)
            self.analyst_toggles[value] = checkbox

        actions_group = QGroupBox("操作")
        actions_layout = QVBoxLayout(actions_group)
        actions_layout.setSpacing(10)
        self.start_button = QPushButton("开始分析")
        self.start_button.setMinimumHeight(44)
        self.start_button.clicked.connect(self._start_analysis)
        self.open_results_button = QPushButton("打开结果文件夹")
        self.open_results_button.setMinimumHeight(44)
        self.open_results_button.setEnabled(False)
        self.open_results_button.clicked.connect(self._open_results_folder)
        actions_layout.addWidget(self.start_button)
        actions_layout.addWidget(self.open_results_button)

        action_hint = QLabel("分析过程中会实时刷新进度、日志和报告，不需要切回终端。")
        action_hint.setProperty("muted", "true")
        action_hint.setWordWrap(True)
        actions_layout.addWidget(action_hint)

        layout.addWidget(run_group)
        layout.addWidget(actions_group)
        layout.addWidget(analysts_group)
        layout.addStretch(1)
        return panel

    def _build_output_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        reports_group = QGroupBox("报告")
        reports_layout = QHBoxLayout(reports_group)
        self.current_report_view = QTextBrowser()
        self.current_report_view.setOpenExternalLinks(True)
        self.current_report_view.setPlaceholderText("当前正在生成的报告片段会显示在这里。")
        self.final_report_view = QTextBrowser()
        self.final_report_view.setOpenExternalLinks(True)
        self.final_report_view.setPlaceholderText("完整分析报告会显示在这里。")
        report_css = (
            "body { color: #1f140d; font-size: 14px; }"
            "h1, h2, h3 { color: #24180f; }"
            "p, li { color: #33241a; }"
            "code { background: #f3eadf; color: #5a341c; padding: 2px 4px; border-radius: 4px; }"
        )
        self.current_report_view.document().setDefaultStyleSheet(report_css)
        self.final_report_view.document().setDefaultStyleSheet(report_css)
        current_report_panel = QWidget()
        current_report_layout = QVBoxLayout(current_report_panel)
        current_report_layout.setContentsMargins(0, 0, 0, 0)
        current_report_layout.setSpacing(8)
        current_report_title = QLabel("实时片段")
        current_report_title.setStyleSheet("font-weight: 700; color: #3c2a1f;")
        current_report_layout.addWidget(current_report_title)
        current_report_layout.addWidget(self.current_report_view, 1)

        final_report_panel = QWidget()
        final_report_layout = QVBoxLayout(final_report_panel)
        final_report_layout.setContentsMargins(0, 0, 0, 0)
        final_report_layout.setSpacing(8)
        final_report_title = QLabel("完整报告")
        final_report_title.setStyleSheet("font-weight: 700; color: #3c2a1f;")
        final_report_layout.addWidget(final_report_title)
        final_report_layout.addWidget(self.final_report_view, 1)

        reports_layout.addWidget(current_report_panel, 1)
        reports_layout.addWidget(final_report_panel, 1)

        lower_split = QSplitter(Qt.Horizontal)
        lower_split.setChildrenCollapsible(False)

        agents_group = QGroupBox("执行状态")
        agents_layout = QVBoxLayout(agents_group)
        self.agent_table = QTableWidget(0, 2)
        self.agent_table.setHorizontalHeaderLabels(["角色", "状态"])
        self.agent_table.verticalHeader().setVisible(False)
        self.agent_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.agent_table.setSelectionMode(QTableWidget.NoSelection)
        self.agent_table.setAlternatingRowColors(True)
        self.agent_table.setShowGrid(False)
        self.agent_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.agent_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        agents_layout.addWidget(self.agent_table)

        activity_group = QGroupBox("活动日志")
        activity_layout = QVBoxLayout(activity_group)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.log_view.setPlaceholderText("运行日志、工具调用和异常信息会显示在这里。")
        fixed_font = QFontDatabase.systemFont(QFontDatabase.FixedFont)
        if fixed_font.pointSize() < 12:
            fixed_font.setPointSize(12)
        self.log_view.setFont(fixed_font)
        activity_layout.addWidget(self.log_view)

        lower_split.addWidget(agents_group)
        lower_split.addWidget(activity_group)
        lower_split.setStretchFactor(0, 0)
        lower_split.setStretchFactor(1, 1)
        lower_split.setSizes([320, 780])

        layout.addWidget(reports_group, 1)
        layout.addWidget(lower_split, 1)
        return panel

    def _load_saved_state(self) -> None:
        ticker = self.settings.value("ticker", "600519")
        language = self.settings.value("language", "Chinese")
        provider = self.settings.value("provider", "deepseek")
        depth = int(self.settings.value("research_depth", 3))
        saved_date = self.settings.value("analysis_date")
        self._provider_keys = {
            provider_name: str(
                self.settings.value(self._provider_settings_key(provider_name), "") or ""
            )
            for provider_name, spec in PROVIDER_SPECS.items()
            if spec["env_var"]
        }

        self.ticker_input.setText(str(ticker))
        language_index = self.language_combo.findData(language)
        if language_index >= 0:
            self.language_combo.setCurrentIndex(language_index)
        else:
            self.language_combo.setEditText(str(language))

        provider_index = self.provider_combo.findData(provider)
        if provider_index >= 0:
            self.provider_combo.setCurrentIndex(provider_index)

        depth_index = self.depth_combo.findData(depth)
        if depth_index >= 0:
            self.depth_combo.setCurrentIndex(depth_index)

        self.alpha_vantage_input.setText(
            str(self.settings.value("alpha_vantage_api_key", "") or "")
        )

        if saved_date:
            qdate = QDate.fromString(str(saved_date), "yyyy-MM-dd")
            if qdate.isValid():
                self.date_input.setDate(qdate)

        self._handle_provider_changed()

    def _save_state(self) -> None:
        self._cache_current_provider_key()
        self._cache_alpha_vantage_key()
        self.settings.setValue("ticker", self.ticker_input.text().strip())
        self.settings.setValue(
            "language",
            self.language_combo.currentData() or self.language_combo.currentText().strip(),
        )
        self.settings.setValue("provider", self.provider_combo.currentData())
        self.settings.setValue("research_depth", self.depth_combo.currentData())
        self.settings.setValue("analysis_date", self.date_input.date().toString("yyyy-MM-dd"))
        self.settings.sync()

    def _provider_settings_key(self, provider: str) -> str:
        return f"provider_api_keys/{provider}"

    def _provider_supports_api_key(self, provider: str | None) -> bool:
        if not provider:
            return False
        spec = PROVIDER_SPECS.get(provider)
        return bool(spec and spec["env_var"])

    def _cache_current_provider_key(self, *_args) -> None:
        provider = self.provider_combo.currentData()
        if not self._provider_supports_api_key(provider):
            return
        key_value = self.provider_key_input.text().strip()
        self._provider_keys[str(provider)] = key_value
        self.settings.setValue(self._provider_settings_key(str(provider)), key_value)

    def _cache_alpha_vantage_key(self, *_args) -> None:
        self.settings.setValue(
            "alpha_vantage_api_key",
            self.alpha_vantage_input.text().strip(),
        )

    def _restore_provider_key(self, provider: str | None) -> None:
        if not self._provider_supports_api_key(provider):
            self.provider_key_input.clear()
            return
        self.provider_key_input.setText(self._provider_keys.get(str(provider), ""))

    def _set_form_row_visible(
        self, label: QLabel, field: QWidget, visible: bool
    ) -> None:
        label.setVisible(visible)
        field.setVisible(visible)

    def _handle_provider_changed(self, *_args) -> None:
        previous_provider = self._active_provider
        if self._provider_supports_api_key(previous_provider):
            self._provider_keys[str(previous_provider)] = (
                self.provider_key_input.text().strip()
            )

        self._active_provider = self.provider_combo.currentData()
        self._update_provider_controls()
        self._restore_provider_key(self._active_provider)

    def _update_provider_controls(self) -> None:
        provider = self.provider_combo.currentData()
        spec = PROVIDER_SPECS[provider]
        env_var = spec["env_var"]

        self._populate_model_combo(self.quick_model_combo, provider, "quick")
        self._populate_model_combo(self.deep_model_combo, provider, "deep")

        if env_var:
            self.provider_key_label.setText(f"{spec['label']} API Key")
            self.provider_key_input.setEnabled(True)
            if os.getenv(env_var):
                self.provider_key_input.setPlaceholderText(
                    f"已检测到环境变量 {env_var}，这里可以留空或临时覆盖"
                )
            else:
                self.provider_key_input.setPlaceholderText(
                    f"在这里粘贴 {spec['label']} 的 API Key，或先写入环境变量 {env_var}"
                )
        else:
            self.provider_key_label.setText("API Key")
            self.provider_key_input.clear()
            self.provider_key_input.setEnabled(False)
            self.provider_key_input.setPlaceholderText("本地 Ollama 不需要 API Key")

        self._set_form_row_visible(
            self.openai_reasoning_label,
            self.openai_reasoning_row,
            provider == "openai",
        )
        self._set_form_row_visible(
            self.anthropic_effort_label,
            self.anthropic_effort_row,
            provider == "anthropic",
        )
        self._set_form_row_visible(
            self.google_thinking_label,
            self.google_thinking_row,
            provider == "google",
        )

    def _populate_model_combo(self, combo: QComboBox, provider: str, mode: str) -> None:
        previous = combo.currentData()
        combo.blockSignals(True)
        combo.clear()
        for label, value in get_model_options(provider, mode):
            combo.addItem(label, value)
        if previous:
            index = combo.findData(previous)
            if index >= 0:
                combo.setCurrentIndex(index)
        combo.blockSignals(False)

    def _collect_selection(self) -> DesktopSelection:
        provider = self.provider_combo.currentData()
        selected_analysts = [
            analyst
            for analyst, button in self.analyst_toggles.items()
            if button.isChecked()
        ]

        return DesktopSelection(
            ticker=normalize_ticker_symbol(self.ticker_input.text()),
            analysis_date=self.date_input.date().toString("yyyy-MM-dd"),
            output_language=(
                self.language_combo.currentData()
                or self.language_combo.currentText().strip()
                or "Chinese"
            ),
            analysts=selected_analysts,
            research_depth=int(self.depth_combo.currentData()),
            llm_provider=provider,
            backend_url=PROVIDER_SPECS[provider]["base_url"],
            shallow_thinker=str(self.quick_model_combo.currentData()),
            deep_thinker=str(self.deep_model_combo.currentData()),
            provider_api_key=self.provider_key_input.text().strip(),
            alpha_vantage_api_key=self.alpha_vantage_input.text().strip(),
            google_thinking_level=(
                str(self.google_thinking_combo.currentData())
                if provider == "google"
                else None
            ),
            openai_reasoning_effort=(
                str(self.openai_reasoning_combo.currentData())
                if provider == "openai"
                else None
            ),
            anthropic_effort=(
                str(self.anthropic_effort_combo.currentData())
                if provider == "anthropic"
                else None
            ),
        )

    def _set_running(self, running: bool) -> None:
        self.start_button.setEnabled(not running)
        self.provider_combo.setEnabled(not running)
        self.ticker_input.setEnabled(not running)
        self.date_input.setEnabled(not running)
        self.language_combo.setEnabled(not running)
        self.depth_combo.setEnabled(not running)
        self.quick_model_combo.setEnabled(not running)
        self.deep_model_combo.setEnabled(not running)
        self.provider_key_input.setEnabled(False if running else self.provider_key_input.isEnabled())
        self.alpha_vantage_input.setEnabled(not running)
        for button in self.analyst_toggles.values():
            button.setEnabled(not running)
        self.run_state_value.setText("运行中" if running else "空闲")
        if not running:
            self._update_provider_controls()

    def _start_analysis(self) -> None:
        selection = self._collect_selection()
        self.ticker_input.setText(selection.ticker)
        self._save_state()
        self.latest_results_dir = None
        self.latest_report_path = None
        self.open_results_button.setEnabled(False)
        self.report_path_value.setText("正在运行...")
        self.current_report_view.clear()
        self.final_report_view.clear()
        self.log_view.clear()
        self._refresh_agent_table({})
        self.progress_bar.setValue(0)
        self._set_running(True)

        self.worker_thread = QThread(self)
        self.worker = AnalysisWorker(selection)
        self.worker.moveToThread(self.worker_thread)

        self.worker_thread.started.connect(self.worker.run)
        self.worker.log.connect(self._append_log)
        self.worker.status_updated.connect(self._refresh_agent_table)
        self.worker.reports_updated.connect(self._update_reports)
        self.worker.stats_updated.connect(self._update_stats)
        self.worker.finished.connect(self._handle_finished)
        self.worker.failed.connect(self._handle_failed)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.failed.connect(self.worker_thread.quit)
        self.worker_thread.finished.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)
        self.worker_thread.start()

    def _append_log(self, message: str) -> None:
        self.log_view.appendPlainText(message)
        scrollbar = self.log_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _refresh_agent_table(self, statuses: dict[str, str]) -> None:
        ordered_agents = [
            agent for agent in STATUS_AGENT_ORDER if agent in statuses
        ]
        extras = [agent for agent in statuses if agent not in ordered_agents]
        rows = ordered_agents + sorted(extras)

        self.agent_table.setRowCount(len(rows))
        completed = 0
        for row, agent in enumerate(rows):
            status = statuses.get(agent, "pending")
            display_agent = AGENT_DISPLAY_NAMES.get(agent, agent)
            display_status = {
                "completed": "已完成",
                "in_progress": "进行中",
                "pending": "等待中",
            }.get(status, status)
            agent_item = QTableWidgetItem(display_agent)
            status_item = QTableWidgetItem(display_status)
            if status == "completed":
                completed += 1
                status_item.setForeground(QColor("#216e4a"))
            elif status == "in_progress":
                status_item.setForeground(QColor("#a15a20"))
            else:
                status_item.setForeground(QColor("#6f6558"))
            self.agent_table.setItem(row, 0, agent_item)
            self.agent_table.setItem(row, 1, status_item)

        total = len(rows)
        progress = int((completed / total) * 100) if total else 0
        self.progress_bar.setValue(progress)

    def _update_reports(self, current_report: str, final_report: str) -> None:
        if current_report:
            self.current_report_view.setMarkdown(current_report)
        if final_report:
            self.final_report_view.setMarkdown(final_report)

    def _update_stats(self, stats: dict) -> None:
        self.llm_calls_value.setText(str(stats.get("llm_calls", 0)))
        self.tool_calls_value.setText(str(stats.get("tool_calls", 0)))
        self.tokens_in_value.setText(str(stats.get("tokens_in", 0)))
        self.tokens_out_value.setText(str(stats.get("tokens_out", 0)))

    def _handle_finished(self, summary: dict) -> None:
        self._set_running(False)
        self.run_state_value.setText("已完成")
        self.latest_results_dir = summary.get("results_dir")
        self.latest_report_path = summary.get("report_path")
        self.report_path_value.setText(summary.get("report_path", "报告已保存"))
        self.open_results_button.setEnabled(bool(self.latest_results_dir))
        if summary.get("current_report"):
            self.current_report_view.setMarkdown(summary["current_report"])
        if summary.get("final_report"):
            self.final_report_view.setMarkdown(summary["final_report"])
        self._append_log("系统 · 桌面端分析已成功完成。")

    def _friendly_error_message(self, error_text: str) -> str:
        attempts_line = ""
        for line in reversed(error_text.splitlines()):
            line = line.strip()
            if "Attempts:" in line:
                attempts_line = line
                break

        if "Unable to connect to proxy" in error_text or "ProxyError" in error_text:
            message = (
                "分析失败：当前网络代理拦截了数据请求。\n\n"
                "这通常不是模型问题，而是财经数据源请求被代理或网关中断了。\n"
                "建议先检查系统代理、终端代理环境变量，或切换网络后重试。"
            )
            if attempts_line:
                message += f"\n\n{attempts_line}"
            return message

        if "No available vendor for 'get_stock_data'" in error_text:
            message = (
                "分析失败：股票行情数据暂时不可用。\n\n"
                "程序已经按 A 股模式优先尝试了中国链路；如果仍失败，通常是当前网络、代理，"
                "或备用数据源配置导致的。\n"
                "你可以稍后重试，或检查代理设置；如果要保留海外兜底源，再补充 Alpha Vantage Key。"
            )
            if attempts_line:
                message += f"\n\n{attempts_line}"
            return message

        return error_text

    def _handle_failed(self, error_text: str) -> None:
        self._set_running(False)
        self.run_state_value.setText("失败")
        self.report_path_value.setText("分析失败")
        self._append_log(error_text)
        QMessageBox.critical(self, "分析失败", self._friendly_error_message(error_text))

    def _open_results_folder(self) -> None:
        if self.latest_results_dir:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.latest_results_dir))

    def _show_compliance_notice(self) -> None:
        self._show_compliance_dialog(require_ack=False)

    def _show_compliance_notice_if_needed(self) -> None:
        acknowledged_version = str(
            self.settings.value("compliance_notice_version", "") or ""
        )
        if acknowledged_version == COMPLIANCE_NOTICE_VERSION:
            return
        accepted = self._show_compliance_dialog(require_ack=True)
        if accepted:
            self.settings.setValue(
                "compliance_notice_version",
                COMPLIANCE_NOTICE_VERSION,
            )
            self.settings.sync()
        else:
            self.close()

    def _show_compliance_dialog(self, require_ack: bool) -> bool:
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Warning)
        dialog.setWindowTitle("使用声明与风险提示")
        dialog.setTextFormat(Qt.RichText)
        dialog.setText(COMPLIANCE_NOTICE_SUMMARY)
        dialog.setInformativeText(COMPLIANCE_NOTICE_HTML)

        if require_ack:
            accept_button = dialog.addButton("我已了解并继续", QMessageBox.AcceptRole)
            exit_button = dialog.addButton("退出应用", QMessageBox.RejectRole)
            dialog.setDefaultButton(accept_button)
            dialog.exec()
            return dialog.clickedButton() == accept_button and dialog.clickedButton() != exit_button

        dialog.addButton("关闭", QMessageBox.AcceptRole)
        dialog.exec()
        return True

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self.worker_thread and self.worker_thread.isRunning():
            QMessageBox.warning(
                self,
                "分析仍在运行",
                "请等待当前分析结束后再关闭桌面应用。",
            )
            event.ignore()
            return
        self._save_state()
        super().closeEvent(event)


def main() -> int:
    load_dotenv()
    app = QApplication(sys.argv)
    app.setApplicationName("TradingAgents 桌面版")
    app.setOrganizationName("TradingAgents")
    window = MainWindow(show_compliance_notice=True)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
