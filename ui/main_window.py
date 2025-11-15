"""Main window for AI Git Assistant."""

import os
from typing import Dict, Any, Optional
from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtWidgets import QFileDialog, QMessageBox, QProgressBar, QDialog, QVBoxLayout, QListWidget, QDialogButtonBox

from backend import git_utils
from backend import ollama_client
from backend import config
from backend import ai_features
from ui import ai_features_widget
import shutil


class Worker(QtCore.QThread):
    """Run a callable in a background thread and emit (error, result) when done."""
    done = QtCore.Signal(object)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.cancel_requested = False

    def request_cancel(self):
        """Request to cancel the task (soft signal)."""
        self.cancel_requested = True

    def run(self):
        try:
            res = self.fn(*self.args, **self.kwargs)
            self.done.emit((None, res))
        except Exception as e:
            self.done.emit((e, None))


class CommitMessageDialog(QDialog):
    """A dialog to show multiple commit message suggestions and let the user choose one."""
    def __init__(self, suggestions: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI 커밋 메시지 제안")
        self.suggestions = suggestions
        self.selected_message = None

        layout = QVBoxLayout(self)
        self.list_widget = QListWidget()
        for suggestion in self.suggestions:
            # Format the suggestion for display
            scope = suggestion.get('scope')
            subject = suggestion.get('subject', 'No subject')
            
            header = f"{scope}({subject})" if scope else subject
            
            item = QtWidgets.QListWidgetItem(header)
            item.setToolTip(suggestion.get('body', ''))
            self.list_widget.addItem(item)

        layout.addWidget(self.list_widget)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.list_widget.setCurrentRow(0) # Select the first item by default


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Git 어시스턴트")
        self.resize(1024, 768)

        # --- Config and Backend Initialization ---
        self.app_config = config.load_config()
        # Apply configured git executable to git_utils
        git_exec = self.app_config.get("git_executable")
        if git_exec:
            git_utils.set_git_executable(git_exec)
        # Configure ollama client
        ollama_client.configure_client(self.app_config)
        self.max_diff_bytes = self.app_config.get("max_diff_bytes", 2_000_000)

        # --- Main UI Structure ---
        main_splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal, self)
        self.setCentralWidget(main_splitter)

        # Right Content Pages
        self.pages_widget = QtWidgets.QStackedWidget()
        self._create_pages()

        # Left Navigation Panel (must be created after pages_widget)
        nav_widget = self._create_nav_panel()

        # Add widgets to splitter
        main_splitter.addWidget(nav_widget)
        main_splitter.addWidget(self.pages_widget)

        main_splitter.setSizes([150, 850]) # Initial size ratio

        # --- Status Bar ---
        self.status_label = QtWidgets.QLabel("")
        self.progress = QProgressBar()
        self.progress.setMinimum(0)
        self.progress.setMaximum(0)
        self.progress.setVisible(False)
        self.statusBar().addPermanentWidget(self.progress)

        # --- Internal State ---
        self.current_project = None
        self._busy = False
        self._threads = []
        self._current_worker = None

        # --- Initialize UI ---
        self._update_workspace_state()

    def _create_nav_panel(self) -> QtWidgets.QWidget:
        """Creates the left-side navigation panel with buttons."""
        nav_widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(nav_widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        self.nav_btn_group = QtWidgets.QButtonGroup(self)
        self.nav_btn_group.setExclusive(True)

        buttons = {
            "프로젝트": 0,
            "작업공간": 1,
            "AI 도구": 2,
            "설정": 3,
            "도움말": 4,
        }

        for name, index in buttons.items():
            btn = QtWidgets.QPushButton(name)
            btn.setCheckable(True)
            # Use a dedicated handler to allow for specific actions per page
            btn.clicked.connect(lambda _, i=index: self.on_nav_button_clicked(i))
            layout.addWidget(btn)
            self.nav_btn_group.addButton(btn, index)

        layout.addStretch()
        
        # Start with "프로젝트" selected
        self.pages_widget.setCurrentIndex(0)
        self.nav_btn_group.button(0).setChecked(True)
        return nav_widget

    def _create_pages(self):
        """Creates all the pages for the QStackedWidget."""
        # Page 0: Project Selection
        self.project_page = self._create_project_page()
        self.pages_widget.addWidget(self.project_page)

        # Page 1: Workspace (Git operations)
        self.workspace_page = self._create_workspace_page()
        self.pages_widget.addWidget(self.workspace_page)

        # Page 2: AI Tools
        self.ai_tools_page = ai_features_widget.AIFeaturesWidget(self)
        self.ai_tools_page.command_requested.connect(self.on_ai_command_requested)
        self.pages_widget.addWidget(self.ai_tools_page)

        # Page 3: Settings
        self.settings_page = SettingsPage(self.app_config, self)
        self.settings_page.settings_saved.connect(self.on_settings_saved)
        self.pages_widget.addWidget(self.settings_page)

        # Page 4: Help
        self.help_page = self._create_help_page()
        self.pages_widget.addWidget(self.help_page)

    def on_nav_button_clicked(self, index: int):
        """Handle clicks on the main navigation buttons."""
        self.pages_widget.setCurrentIndex(index)
        # If switching to AI Tools, ensure the assistant tab is selected
        if index == 2: # AI Tools page
            # Assuming the assistant tab is at index 0 in AIFeaturesWidget
            self.ai_tools_page.set_current_tab(0)

    def set_busy(self, busy: bool, message: str = ""):
        self._busy = busy
        # Disable all nav buttons while busy
        for btn in self.nav_btn_group.buttons():
            btn.setEnabled(not busy)
        
        # Also disable buttons on the current page if it's the workspace
        self.workspace_page.setEnabled(not busy)

        # self.cancel_btn.setVisible(busy)
        self.progress.setVisible(busy)

        if message:
            self.statusBar().showMessage(message)
        elif not busy:
            self.statusBar().clearMessage()


    def on_cancel(self): # This method seems to be unused in the provided code, but we'll keep it.
        """Cancel the current operation."""
        if self._current_worker:
            self._current_worker.request_cancel()
            self.statusBar().showMessage("작업 취소 요청됨", 5000)

    def _start_worker(self, fn, on_done, busy_message=""):
        if self._busy:
            QMessageBox.warning(self, "작업중", "다른 작업이 이미 실행 중입니다")
            return None

        self.set_busy(True, busy_message)
        worker = Worker(fn)
        self._threads.append(worker)
        self._current_worker = worker

        def done_wrapper(result):
            self.set_busy(False)
            on_done(result)

        worker.done.connect(done_wrapper)

        def _cleanup(result):
            try:
                self._threads.remove(worker)
            except ValueError:
                pass
            self._current_worker = None

        worker.done.connect(_cleanup)
        worker.start()
        return worker

    def _create_project_page(self) -> QtWidgets.QWidget:
        """Creates the project selection page."""
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)

        # Top: Repository scanner
        h = QtWidgets.QHBoxLayout()
        h.addWidget(QtWidgets.QLabel("저장소 검색:"))
        self.repo_root_edit = QtWidgets.QLineEdit()
        self.repo_root_edit.setPlaceholderText("Git 저장소를 검색할 상위 폴더 경로를 입력하세요")
        self.repo_root_edit.setText(os.path.expanduser("~"))
        h.addWidget(self.repo_root_edit)
        self.scan_btn = QtWidgets.QPushButton("저장소 찾기")
        self.scan_btn.clicked.connect(self.scan_repos)
        h.addWidget(self.scan_btn)
        layout.addLayout(h)

        # Repository results list
        layout.addWidget(QtWidgets.QLabel("검색된 Git 저장소 (더블클릭하여 열기):"))
        self.repo_list = QtWidgets.QListWidget()
        self.repo_list.itemDoubleClicked.connect(self._on_repo_double_clicked)
        layout.addWidget(self.repo_list)

        return page

    def _create_workspace_page(self) -> QtWidgets.QWidget:
        """Creates the main workspace page for Git operations."""
        page = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(page)

        # Top bar: Project Label, Branch Selector
        top_bar = self._create_workspace_top_bar()
        v.addLayout(top_bar)

        # Main content tabs (Files, History)
        tab_widget = QtWidgets.QTabWidget()
        files_tab = self._create_files_tab()
        history_tab = self._create_history_tab()
        tab_widget.addTab(files_tab, "파일")
        tab_widget.addTab(history_tab, "히스토리")
        
        tab_widget.currentChanged.connect(self.on_workspace_tab_changed)

        v.addWidget(tab_widget)
        return page

    def on_workspace_tab_changed(self, index: int):
        """Handle switching between workspace tabs."""
        # 0: Files, 1: History
        if index == 1:
            self.refresh_history()

    def _create_workspace_top_bar(self) -> QtWidgets.QHBoxLayout:
        """Creates the top bar for the workspace with project and branch info."""
        top_bar = QtWidgets.QHBoxLayout()
        self.current_project_label = QtWidgets.QLabel("선택된 프로젝트 없음")
        self.current_project_label.setStyleSheet("font-weight: bold;")
        top_bar.addWidget(self.current_project_label)
        top_bar.addStretch()
        top_bar.addWidget(QtWidgets.QLabel("브랜치:"))
        self.branch_combo = QtWidgets.QComboBox()
        self.branch_combo.currentTextChanged.connect(self.on_branch_changed)
        top_bar.addWidget(self.branch_combo)
        return top_bar

    def _create_files_tab(self) -> QtWidgets.QWidget:
        """Creates the tab for file staging and committing."""
        files_widget = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(files_widget)
        # Staged / Unstaged files
        files_h = QtWidgets.QHBoxLayout()
        left_v = QtWidgets.QVBoxLayout()
        right_v = QtWidgets.QVBoxLayout()

        left_v.addWidget(QtWidgets.QLabel("스테이지된 파일:"))
        self.staged_list = QtWidgets.QListWidget()
        self.staged_list.itemDoubleClicked.connect(self.on_unstage_file)
        left_v.addWidget(self.staged_list)

        self.refresh_btn = QtWidgets.QPushButton("새로고침")
        self.refresh_btn.clicked.connect(self.refresh_staged)
        left_v.addWidget(self.refresh_btn)

        right_v.addWidget(QtWidgets.QLabel("스테이지되지 않은 파일:"))
        self.unstaged_list = QtWidgets.QListWidget()
        self.unstaged_list.itemDoubleClicked.connect(self.on_stage_file)
        # Add context menu for discarding changes
        self.unstaged_list.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.unstaged_list.customContextMenuRequested.connect(self.on_unstaged_list_context_menu)
        right_v.addWidget(self.unstaged_list)

        self.stage_all_btn = QtWidgets.QPushButton("전체 스테이지")
        self.stage_all_btn.clicked.connect(self.on_stage_all)
        right_v.addWidget(self.stage_all_btn)

        files_h.addLayout(left_v)
        files_h.addLayout(right_v)
        v.addLayout(files_h)

        # Commit message
        v.addWidget(QtWidgets.QLabel("커밋 메시지 (AI 생성):"))
        self.commit_edit = QtWidgets.QLineEdit()
        v.addWidget(self.commit_edit)

        # Buttons - Commit row
        btn_row = QtWidgets.QHBoxLayout()
        self.ai_commit_btn = QtWidgets.QPushButton("AI로 커밋 메시지 생성")
        self.ai_commit_btn.clicked.connect(self.on_ai_commit)
        self.commit_btn = QtWidgets.QPushButton("커밋")
        self.commit_btn.clicked.connect(self.on_commit)
        self.cancel_btn = QtWidgets.QPushButton("취소")
        self.cancel_btn.clicked.connect(self.on_cancel)
        self.cancel_btn.setVisible(False)
        
        btn_row.addWidget(self.ai_commit_btn)
        btn_row.addWidget(self.commit_btn)
        btn_row.addWidget(self.cancel_btn)
        v.addLayout(btn_row)

        # Buttons - Git operations row
        git_ops_row = QtWidgets.QHBoxLayout()
        btn_push = QtWidgets.QPushButton("푸시")
        btn_push.clicked.connect(self.on_push)
        btn_pull = QtWidgets.QPushButton("풀")
        btn_pull.clicked.connect(self.on_pull)
        btn_merge = QtWidgets.QPushButton("머지")
        btn_merge.clicked.connect(self.on_merge_dialog)

        git_ops_row.addWidget(btn_push)
        git_ops_row.addWidget(btn_pull)
        git_ops_row.addWidget(btn_merge)
        v.addLayout(git_ops_row)

        # Buttons - Undo operations row
        undo_ops_row = QtWidgets.QHBoxLayout()
        btn_undo_commit = QtWidgets.QPushButton("마지막 커밋 취소 (soft)")
        btn_undo_commit.clicked.connect(self.on_undo_commit_soft)
        btn_undo_commit_hard = QtWidgets.QPushButton("마지막 커밋 취소 (hard)")
        btn_undo_commit_hard.clicked.connect(self.on_undo_commit_hard)
        btn_abort_merge = QtWidgets.QPushButton("머지 중단")
        btn_abort_merge.clicked.connect(self.on_abort_merge)
        btn_reset_staged = QtWidgets.QPushButton("스테이지 해제")
        btn_reset_staged.clicked.connect(self.on_reset_staged)
        undo_ops_row.addWidget(btn_undo_commit)
        undo_ops_row.addWidget(btn_undo_commit_hard)
        undo_ops_row.addWidget(btn_abort_merge)
        undo_ops_row.addWidget(btn_reset_staged)
        v.addLayout(undo_ops_row)
        return files_widget

    def _create_history_tab(self) -> QtWidgets.QWidget:
        """Creates the tab for viewing commit history."""
        history_widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(history_widget)

        self.history_table = QtWidgets.QTableWidget()
        self.history_table.setColumnCount(4)
        self.history_table.setHorizontalHeaderLabels(["해시", "작성자", "날짜", "제목"])
        self.history_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.history_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.history_table.horizontalHeader().setStretchLastSection(True)
        self.history_table.itemDoubleClicked.connect(self.on_history_item_double_clicked)
        layout.addWidget(self.history_table)
        # Add context menu for history table
        self.history_table.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.history_table.customContextMenuRequested.connect(self.on_history_table_context_menu)

        # Add a text edit for showing diffs
        self.diff_view = QtWidgets.QTextEdit()
        self.diff_view.setReadOnly(True)
        self.diff_view.setFont(QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.FixedFont))
        layout.addWidget(self.diff_view)

        btn_layout = QtWidgets.QHBoxLayout()
        
        self.ai_summarize_history_btn = QtWidgets.QPushButton("AI로 히스토리 요약")
        self.ai_summarize_history_btn.clicked.connect(self.on_ai_summarize_history)
        btn_layout.addWidget(self.ai_summarize_history_btn)

        refresh_history_btn = QtWidgets.QPushButton("히스토리 새로고침")
        refresh_history_btn.clicked.connect(self.refresh_history)
        btn_layout.addWidget(refresh_history_btn)

        layout.addLayout(btn_layout)
        return history_widget

    def _create_help_page(self) -> QtWidgets.QWidget:
        """Creates the help and usage guide page."""
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        
        help_text_edit = QtWidgets.QTextEdit()
        help_text_edit.setReadOnly(True)
        
        help_content = """
        <h1>AI Git 어시스턴트 사용법</h1>
        <p>AI Git 어시스턴트는 Git 작업을 더 쉽고 효율적으로 만들어주는 도구입니다.</p>

        <h2>1. 프로젝트 페이지</h2>
        <ul>
            <li><b>저장소 찾기:</b> 로컬 컴퓨터에 있는 Git 저장소를 검색합니다. 검색할 폴더 경로를 입력하고 '저장소 찾기'를 누르세요.</li>
            <li><b>저장소 열기:</b> 검색된 목록에서 작업할 저장소를 더블클릭하면 '작업공간' 탭으로 이동하며 해당 프로젝트가 열립니다.</li>
        </ul>

        <h2>2. 작업공간 페이지</h2>
        <p>프로젝트를 열면 활성화되는 메인 작업 공간입니다.</p>
        <ul>
            <li><b>파일 탭:</b>
                <ul>
                    <li><b>스테이지되지 않은 파일:</b> 변경되었지만 아직 커밋 대상이 아닌 파일 목록입니다. 파일을 더블클릭하면 스테이지로 이동합니다. 파일에 우클릭하여 변경사항을 폐기할 수도 있습니다.</li>
                    <li><b>스테이지된 파일:</b> 커밋할 대상 파일 목록입니다. 파일을 더블클릭하면 스테이지에서 내려옵니다.</li>
                    <li><b>AI로 커밋 메시지 생성:</b> 스테이지된 파일의 변경사항을 기반으로 AI가 자동으로 3개의 커밋 메시지를 제안합니다. 제안된 메시지 중 하나를 선택하여 커밋할 수 있습니다.</li>
                    <li><b>커밋:</b> 작성된 메시지로 스테이지된 파일들을 커밋합니다.</li>
                    <li><b>푸시/풀/머지:</b> 원격 저장소와 상호작용하거나 다른 브랜치를 병합합니다.</li>
                </ul>
            </li>
            <li><b>히스토리 탭:</b>
                <ul>
                    <li>프로젝트의 커밋 내역을 보여줍니다. 커밋을 더블클릭하면 해당 커밋의 변경사항을 'AI 도구'의 '변경사항 설명' 탭에서 바로 확인할 수 있습니다.</li>
                    <li><b>AI로 히스토리 요약:</b> 최근 커밋 내역을 AI가 분석하여 프로젝트 진행 상황을 요약해줍니다.</li>
                </ul>
            </li>
        </ul>

        <h2>3. AI 도구 페이지</h2>
        <p>다양한 AI 기능을 제공합니다.</p>
        <ul>
            <li><b>AI 어시스턴트:</b> "모든 파일 스테이지해줘", "커밋해줘" 와 같이 자연어 명령으로 Git 작업을 수행할 수 있습니다. Git 관련 질문에 답변도 받을 수 있습니다.</li>
            <li><b>머지 충돌 분석:</b> 머지 충돌이 발생했을 때 충돌 코드를 붙여넣으면 AI가 해결책을 제안합니다. (머지/풀 작업 시 충돌이 발생하면 자동으로 분석을 시작합니다)</li>
            <li><b>코드 리뷰:</b> 코드 스니펫을 붙여넣으면 AI가 코드 품질, 버그 가능성 등을 검토하고 개선안을 제시합니다.</li>
            <li><b>변경사항 설명:</b> 'git diff' 결과를 붙여넣으면 AI가 변경 내용을 사람이 이해하기 쉽게 설명해줍니다.</li>
        </ul>

        <h2>4. 설정 페이지</h2>
        <p>Ollama 모델, Git 실행 파일 경로 등 애플리케이션의 동작을 설정할 수 있습니다.</p>
        """
        help_text_edit.setHtml(help_content)
        layout.addWidget(help_text_edit)
        
        return page

    def _update_workspace_state(self):
        """Enable/disable workspace based on whether a project is open."""
        has_project = self.current_project is not None
        self.workspace_page.setEnabled(has_project)
        self.nav_btn_group.button(1).setEnabled(has_project) # Workspace nav button
        self.ai_summarize_history_btn.setEnabled(has_project)
        
        if not has_project:
            self.current_project_label.setText("선택된 프로젝트 없음")
            self.staged_list.clear()
            self.unstaged_list.clear()
            self.branch_combo.clear()
            self.commit_edit.clear()
            self.history_table.setRowCount(0)
            # If no project, switch to project selection page
            if self.pages_widget.currentIndex() == 1:
                self.pages_widget.setCurrentIndex(0)
                self.nav_btn_group.button(0).setChecked(True)

    def on_history_table_context_menu(self, pos: QtCore.QPoint):
        """Show context menu for the history table."""
        item = self.history_table.itemAt(pos)
        if not item:
            return

        menu = QtWidgets.QMenu()
        show_diff_action = menu.addAction("이 커밋의 변경사항 보기")
        action = menu.exec(self.history_table.mapToGlobal(pos))

        if action == show_diff_action:
            row = item.row()
            hash_item = self.history_table.item(row, 0)
            if hash_item:
                self.show_commit_diff(hash_item.text())

    def on_history_item_double_clicked(self, item: QtWidgets.QTableWidgetItem):
        """Handle double-click on a commit in the history table."""
        self.diff_view.clear() # Clear previous diff on new click

    def scan_repos(self):
        """Scan the filesystem under the provided root for git repositories."""
        path_input = self.repo_root_edit.text().strip()
        if not path_input:
            QMessageBox.warning(self, "입력 필요", "검색할 루트 경로를 입력하세요")
            return

        root = None
        if os.path.isdir(path_input):
            root = path_input
        elif os.path.isfile(path_input):
            root = os.path.dirname(path_input)
        else:
            QMessageBox.warning(self, "경로 오류", "유효한 파일 또는 디렉터리 경로를 입력하세요.")
            return

        def task():
            # increase depth for wider search, don't search hidden folders by default
            return git_utils.find_git_repos(root, max_depth=5, include_hidden=False)

        def done_cb(result):
            err, res = result
            if err:
                QMessageBox.critical(self, "검색 실패", str(err))
                return
            repos = res or []
            self.repo_list.clear()
            for p in repos:
                self.repo_list.addItem(p)
            if not repos:
                QMessageBox.information(self, "검색 결과", "지정한 경로에서 Git 저장소를 찾지 못했습니다")

        self._start_worker(task, done_cb, busy_message=f"'{root}'에서 Git 저장소 검색 중...")

    def _on_repo_double_clicked(self, item):
        path = item.text()
        if not path:
            return
        self.current_project = path
        self.current_project_label.setText(f"현재: {os.path.basename(path)}")
        self.current_project_label.setToolTip(path)

        self._update_workspace_state()
        self.refresh_branches()
        self.refresh_staged()
        self.refresh_history()
        self.pages_widget.setCurrentIndex(1) # Switch to workspace
        self.nav_btn_group.button(1).setChecked(True)
    def refresh_staged(self):
        if not self.current_project:
            return
        try:
            staged = git_utils.staged_files(cwd=self.current_project)
            unstaged = git_utils.unstaged_files(cwd=self.current_project)
        except Exception as e:
            QMessageBox.critical(self, "깃 오류", str(e))
            return
        self.staged_list.clear()
        for f in staged:
            self.staged_list.addItem(f)
        if not staged:
            self.staged_list.addItem("(스테이지된 파일이 없습니다)")

        self.unstaged_list.clear()
        for f in unstaged:
            self.unstaged_list.addItem(f)
        if not unstaged:
            self.unstaged_list.addItem("(스테이지되지 않은 파일이 없습니다)")

    def refresh_history(self):
        """Fetch and display the commit history."""
        if not self.current_project:
            return

        def task():
            return git_utils.get_commit_history(cwd=self.current_project, limit=200)

        def done_cb(result):
            err, history = result
            if err:
                QMessageBox.critical(self, "히스토리 조회 실패", str(err))
                return
            
            self.history_table.setRowCount(len(history))
            for row, commit in enumerate(history):
                self.history_table.setItem(row, 0, QtWidgets.QTableWidgetItem(commit["hash"]))
                self.history_table.setItem(row, 1, QtWidgets.QTableWidgetItem(commit["author"]))
                self.history_table.setItem(row, 2, QtWidgets.QTableWidgetItem(commit["date"]))
                self.history_table.setItem(row, 3, QtWidgets.QTableWidgetItem(commit["subject"]))
            self.history_table.itemSelectionChanged.connect(self.on_history_item_selected)
            self.history_table.resizeColumnsToContents()

        self._start_worker(task, done_cb, busy_message="커밋 히스토리 조회 중...")

    def on_ai_summarize_history(self):
        """Ask AI to summarize the current commit history."""
        if not self.current_project:
            QMessageBox.warning(self, "프로젝트 없음", "먼저 Git 프로젝트를 열어주세요")
            return

        def task():
            # Fetch history first, then pass to AI
            history = git_utils.get_commit_history(cwd=self.current_project, limit=50)
            if not history:
                return "요약할 커밋이 없습니다."
            
            return ai_features.summarize_history(history)

        def done_cb(result):
            err, summary = result
            if err:
                QMessageBox.critical(self, "AI 요약 실패", str(err))
                return
            
            # Display the summary in the AI chat widget
            self.pages_widget.setCurrentIndex(2) # Switch to AI Tools page
            self.ai_tools_page.add_chat_message("AI", f"**최근 커밋 히스토리 요약:**\n\n{summary}")

        self._start_worker(task, done_cb, busy_message="AI가 커밋 히스토리를 분석하는 중...")

    def on_ai_commit(self, done_cb=None, auto_commit=False):
        if not self.current_project:
            QMessageBox.warning(self, "프로젝트 없음", "먼저 Git 프로젝트를 열어주세요")
            return

        size = git_utils.staged_diff_size(cwd=self.current_project)
        if size == 0:
            QMessageBox.information(self, "스테이지 없음", "스테이지된 변경사항이 없습니다.")
            return
        if size > self.max_diff_bytes:
            mb = size / (1024 * 1024)
            resp = QMessageBox.question(
                self,
                "큰 변경사항 감지",
                f"스테이지된 변경사항이 크기 {mb:.1f}MB입니다. 계속하시겠습니까?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if resp != QMessageBox.Yes:
                return

        def task():
            diff = git_utils.diff_staged(cwd=self.current_project)
            from backend import ai_features
            return ai_features.suggest_commit_messages(diff, count=3)

        def internal_done_cb(result):
            err, suggestions = result
            if err:
                err_msg = str(err)
                if "timeout" in err_msg.lower():
                    msg = f"AI 호출이 시간 초과했습니다.\n({err_msg})"
                else:
                    msg = f"AI 생성 실패:\n{err_msg}"
                if done_cb: done_cb(err, msg)
                else: QMessageBox.critical(self, "AI 오류", msg)
                self.statusBar().showMessage("AI 생성 실패", 5000)
                return
            
            if not isinstance(suggestions, list) or not suggestions:
                msg = f"AI가 유효한 커밋 메시지를 생성하지 못했습니다. 응답: {suggestions}"
                if done_cb: done_cb(ValueError("Invalid AI response"), msg)
                else: QMessageBox.warning(self, "AI 응답 오류", msg)
                return

            dialog = CommitMessageDialog(suggestions, self)
            if dialog.exec():
                selected_index = dialog.list_widget.currentRow()
                selected_suggestion = suggestions[selected_index]
                
                scope = selected_suggestion.get('scope')
                subject = selected_suggestion.get('subject', 'No subject')
                header = f"{scope}({subject})" if scope else subject
                full_message = f"{header}\n\n{selected_suggestion.get('body', '')}".strip()
                
                if auto_commit:
                    if done_cb: done_cb(None, full_message)
                else:
                    self.commit_edit.setText(header) # Show short message in line edit
                    self.statusBar().showMessage("AI 커밋 메시지 선택 완료", 5000)
                    # If there's a non-auto-commit callback, call it.
                    if done_cb: done_cb(None, header)
            elif done_cb: # Dialog was cancelled
                done_cb(RuntimeError("User cancelled"), None)
                
        self._start_worker(task, internal_done_cb, busy_message="AI로 커밋 메시지 생성 중...")
    
    def on_commit(self, done_cb=None):
        if not self.current_project:
            QMessageBox.warning(self, "프로젝트 없음", "먼저 Git 프로젝트를 열어주세요")
            return
        msg = self.commit_edit.text().strip()
        if not msg:
            QMessageBox.warning(self, "메시지 없음", "커밋 메시지가 비어 있습니다")
            return

        def task():
            return git_utils.safe_commit(msg, cwd=self.current_project)

        def internal_done_cb(result):
            err, res = result
            if err:
                if not done_cb: # AI 호출이 아닐 때만 팝업 표시
                    QMessageBox.critical(self, "깃 오류", str(err))
                self.statusBar().showMessage("커밋 실패", 5000)
            else:
                if not done_cb: # AI 호출이 아닐 때만 팝업 표시
                    QMessageBox.information(self, "커밋됨", "커밋이 완료되었습니다")
                self.commit_edit.clear()
                self.refresh_staged()
                self.statusBar().showMessage("커밋 성공", 5000)
            if done_cb:
                done_cb(err, res)

        self._start_worker(task, internal_done_cb, busy_message="커밋 실행 중...")

    def on_settings_saved(self):
        """Apply settings after they have been saved from the settings page."""
        self.app_config = self.settings_page.get_config()
        config.save_config(self.app_config)
        git_exec = self.app_config.get("git_executable")
        if git_exec:
            git_utils.set_git_executable(git_exec)
        ollama_client.configure_client(self.app_config)
        self.max_diff_bytes = self.app_config.get("max_diff_bytes", 2_000_000)

    def on_branch_changed(self, branch_name: str, done_cb=None):
        """Handle branch selection change."""
        if not self.current_project or not branch_name:
            return
        
        def task():
            return git_utils.checkout_branch(branch_name, cwd=self.current_project)
        
        def internal_done_cb(result):
            err, res = result
            if err:
                if not done_cb:
                    QMessageBox.critical(self, "브랜치 전환 실패", str(err))
                self.refresh_branches()
            else:
                if not done_cb:
                    QMessageBox.information(self, "브랜치 전환", f"'{branch_name}'으로 전환되었습니다")
                self.refresh_staged()
            if done_cb:
                done_cb(err, res)
        
        self._start_worker(task, internal_done_cb, busy_message=f"브랜치 '{branch_name}'로 전환 중...")
    
    def refresh_branches(self):
        """Refresh branch list from git."""
        if not self.current_project:
            return
        try:
            branches = git_utils.list_branches(cwd=self.current_project)
            current = git_utils.current_branch(cwd=self.current_project)
            self.branch_combo.blockSignals(True)
            self.branch_combo.clear()
            self.branch_combo.addItems(branches)
            if current and current in branches:
                self.branch_combo.setCurrentText(current)
            self.branch_combo.blockSignals(False)
        except Exception as e:
            QMessageBox.critical(self, "브랜치 조회 실패", str(e))

    def on_push(self):
        """Push current branch to remote."""
        if not self.current_project:
            QMessageBox.warning(self, "프로젝트 없음", "먼저 Git 프로젝트를 열어주세요")
            return
        
        def task():
            return git_utils.push(cwd=self.current_project)
        
        def done_cb(result):
            err, res = result
            if err:
                QMessageBox.critical(self, "푸시 실패", str(err))
                return
            QMessageBox.information(self, "푸시 성공", "변경사항이 원격 저장소로 푸시되었습니다")
            self.statusBar().showMessage("푸시 완료", 5000)
        
        self._start_worker(task, done_cb, busy_message="푸시 중...")
    
    def on_pull(self, done_cb=None):
        """Pull from remote to current branch."""
        if not self.current_project:
            QMessageBox.warning(self, "프로젝트 없음", "먼저 Git 프로젝트를 열어주세요")
            return
        
        def task():
            return git_utils.pull(cwd=self.current_project)
        
        def internal_done_cb(result):
            err, res = result
            if isinstance(err, git_utils.GitConflictError):
                if not done_cb:
                    QMessageBox.warning(self, "풀 충돌", "원격 변경사항을 가져오는 중 충돌이 발생했습니다.\nAI가 충돌 분석을 시작합니다.")
                self.handle_merge_conflict("원격 저장소의 변경사항")
            elif err:
                if not done_cb:
                    QMessageBox.critical(self, "풀 실패", str(err))
            else:
                # res는 git pull의 stdout 결과입니다.
                pull_summary = res.strip() if res else "원격 변경사항이 병합되었습니다."
                if not done_cb:
                    QMessageBox.information(self, "풀 성공", pull_summary)
                self.refresh_staged()
                self.refresh_history()
                self.statusBar().showMessage("풀 완료", 5000)
            if done_cb:
                done_cb(err, pull_summary) # 요약 정보를 콜백으로 전달
        
        self._start_worker(task, internal_done_cb, busy_message="풀 중...")
    
    def on_merge_dialog(self, force_branch: Optional[str] = None, done_cb=None):
        """Show dialog to select branch to merge."""
        if not self.current_project:
            QMessageBox.warning(self, "프로젝트 없음", "먼저 Git 프로젝트를 열어주세요")
            return
        
        branches = git_utils.list_branches(cwd=self.current_project)
        current = git_utils.current_branch(cwd=self.current_project)
        other_branches = [b for b in branches if b != current]
        
        if not other_branches:
            QMessageBox.information(self, "머지 불가", "다른 브랜치가 없습니다")
            return
        
        branch_to_merge = force_branch
        if not branch_to_merge:
            branch_to_merge, ok = QtWidgets.QInputDialog.getItem(
                self, "머지할 브랜치 선택", "브랜치:", other_branches, 0, False
            )
            if not ok or not branch_to_merge:
                return
        
        def task():
            return git_utils.merge(branch_to_merge, cwd=self.current_project)
        
        def internal_done_cb(result):
            err, res = result
            if isinstance(err, git_utils.GitConflictError):
                if not done_cb:
                    QMessageBox.warning(self, "머지 충돌", f"'{branch_to_merge}' 브랜치 머지 중 충돌이 발생했습니다.\nAI가 충돌 분석을 시작합니다.")
                self.handle_merge_conflict(branch_to_merge)
            elif err:
                if not done_cb:
                    QMessageBox.critical(self, "머지 실패", f"{branch_to_merge} 브랜치 머지 실패:\n{err}")
            else:
                if not done_cb:
                    QMessageBox.information(self, "머지 성공", f"'{branch_to_merge}' 브랜치가 병합되었습니다")
                self.refresh_staged()
                self.statusBar().showMessage("머지 완료", 5000)
            if done_cb:
                done_cb(err, res)
        
        self._start_worker(task, internal_done_cb, busy_message=f"'{branch_to_merge}' 브랜치 머지 중...")

    def handle_merge_conflict(self, source_branch: str):
        """Handle merge conflict by triggering AI analysis."""
        conflicted = git_utils.conflicted_files(cwd=self.current_project)
        if not conflicted:
            QMessageBox.information(self, "정보", "충돌이 감지되었지만 충돌 파일을 찾을 수 없습니다.")
            return
        
        # For simplicity, analyze the first conflicted file
        first_conflict_file = conflicted[0]
        content = git_utils.get_file_content(first_conflict_file, cwd=self.current_project)
        context = f"'{source_branch}' 브랜치를 현재 브랜치로 머지하는 중 '{first_conflict_file}' 파일에서 충돌 발생"
        
        self.pages_widget.setCurrentIndex(2) # Switch to AI Tools page
        self.ai_tools_page.start_conflict_analysis(content, context)

    def on_ai_command_requested(self, command_data: dict):
        """Execute a command interpreted by the AI assistant."""
        command = command_data.get("command")
        chat_widget = self.ai_tools_page

        if not self.current_project:
            chat_widget.add_chat_message("시스템", "오류: 먼저 Git 프로젝트를 열어주세요. '프로젝트' 탭에서 저장소를 선택할 수 있습니다.")
            return

        if command == "stage":
            files = command_data.get("files", [])
            if "all" in files:
                def done_cb(err, _):
                    if err:
                        chat_widget.add_chat_message("시스템", f"전체 스테이징 실패: {err}")
                    else:
                        chat_widget.add_chat_message("시스템", "모든 파일을 스테이지했습니다.")
                self.on_stage_all(done_cb=done_cb)

        elif command == "commit":
            msg = command_data.get("message")
            # 사용자가 "AI로 메시지 생성 후 커밋"이라고 했을 때, LLM이 사용자 입력을 message로 잘못 해석하는 경우를 방지합니다.
            # "생성", "만들어줘", "ai" 등의 키워드가 있으면 AI 생성 로직을 타도록 합니다.
            user_input = getattr(chat_widget.chat_input, 'user_text', '') # 원본 사용자 입력을 가져옵니다.
            force_ai_generation = any(keyword in user_input for keyword in ["생성", "만들어줘", "ai", "AI"]) if user_input else False

            if msg and not force_ai_generation and msg not in ["commit", "커밋"]:
                self.commit_edit.setText(msg)
                def done_cb(err, _):
                    if err:
                        chat_widget.add_chat_message("시스템", f"커밋 실패: {err}")
                    else:
                        chat_widget.add_chat_message("시스템", f"'{msg}' 메시지로 커밋했습니다.")
                self.on_commit(done_cb=done_cb)
            else:
                chat_widget.add_chat_message("시스템", "AI로 커밋 메시지를 생성 후 커밋을 진행합니다.")
                def ai_done_cb(err, message):
                    if err:
                        chat_widget.add_chat_message("시스템", f"AI 커밋 메시지 생성 실패: {message}")
                    elif message:
                        chat_widget.add_chat_message("시스템", "AI가 생성한 메시지로 커밋을 시도합니다.")
                        self.commit_edit.setText(message.splitlines()[0])
                        def commit_done_cb(err, _):
                            if err: chat_widget.add_chat_message("시스템", f"커밋 실패: {err}")
                            else: chat_widget.add_chat_message("시스템", f"'{message.splitlines()[0]}' 메시지로 커밋했습니다.")
                        self.on_commit(done_cb=commit_done_cb)
                    else:
                        chat_widget.add_chat_message("시스템", "사용자가 커밋 메시지 생성을 취소했습니다.")
                self.on_ai_commit(done_cb=ai_done_cb, auto_commit=True)

        elif command == "push":
            def done_cb(err, _):
                # AI 호출이 아니므로, 여기서 직접 채팅 메시지를 추가합니다.
                if err:
                    chat_widget.add_chat_message("시스템", f"푸시 실패: {err}")
                else:
                    chat_widget.add_chat_message("시스템", "푸시 성공.")
            self.on_push(done_cb=done_cb)

        elif command == "pull":
            def done_cb(err, _):
                # AI 호출이 아니므로, 여기서 직접 채팅 메시지를 추가합니다.
                if err:
                    chat_widget.add_chat_message("시스템", f"풀 실패: {str(err)}")
                else:
                    chat_widget.add_chat_message("시스템", f"풀 성공.\n{_}")
            self.on_pull(done_cb=done_cb)

        elif command == "checkout":
            branch = command_data.get("branch")
            if branch:
                # AI 호출이 아니므로, 여기서 직접 채팅 메시지를 추가합니다.
                def done_cb(err, _):
                    if err:
                        chat_widget.add_chat_message("시스템", f"'{branch}' 브랜치로 전환 실패: {err}")
                    else:
                        chat_widget.add_chat_message("시스템", f"'{branch}' 브랜치로 전환했습니다.")
                self.on_branch_changed(branch, done_cb=done_cb)

        elif command == "merge":
            branch = command_data.get("branch")
            if branch:
                def done_cb(err, _):
                    # The main merge logic already handles chat messages for conflicts/success
                    if err and not isinstance(err, git_utils.GitConflictError):
                         chat_widget.add_chat_message("시스템", f"'{branch}' 머지 실패: {err}")
                self.on_merge_dialog(force_branch=branch, done_cb=done_cb)

        elif command == "reset":
            mode = command_data.get("mode", "soft") # Default to soft
            if mode == "hard":
                def done_cb(err, _):
                    # AI 호출이 아니므로, 여기서 직접 채팅 메시지를 추가합니다.
                    if err: chat_widget.add_chat_message("시스템", f"마지막 커밋 취소(hard) 실패: {err}")
                    else: chat_widget.add_chat_message("시스템", "마지막 커밋을 취소하고 변경사항을 폐기했습니다.")
                self.on_undo_commit_hard(done_cb=done_cb)
            else: # soft reset
                def done_cb(err, _):
                    # AI 호출이 아니므로, 여기서 직접 채팅 메시지를 추가합니다.
                    if err: chat_widget.add_chat_message("시스템", f"마지막 커밋 취소(soft) 실패: {err}")
                    else: chat_widget.add_chat_message("시스템", "마지막 커밋을 취소했습니다. 변경사항은 스테이지에 남아있습니다.")
                self.on_undo_commit_soft(done_cb=done_cb)

        elif command == "check_status":
            self.on_ai_check_status()

    def show_commit_diff(self, commit_hash: str):
        """Fetch a commit diff and show it in the AI diff explanation tab."""
        def task():
            return git_utils.get_commit_diff(commit_hash, cwd=self.current_project)

        def done_cb(result):
            err, diff_content = result
            if err:
                QMessageBox.critical(self, "Diff 조회 실패", str(err))
                return
            self.diff_view.setText(diff_content)
        self._start_worker(task, done_cb, busy_message=f"'{commit_hash}' 커밋의 변경사항 조회 중...")

    def on_history_item_selected(self):
        """When a history item is selected, show its diff."""
        selected_items = self.history_table.selectedItems()
        if not selected_items:
            return

        row = selected_items[0].row()
        hash_item = self.history_table.item(row, 0)
        if hash_item:
            self.show_commit_diff(hash_item.text())

    def on_ai_check_status(self):
        """Check for local and remote changes and report to the user via AI chat."""
        chat_widget = self.ai_tools_page
        if not self.current_project:
            chat_widget.add_chat_message("시스템", "오류: 먼저 Git 프로젝트를 열어주세요.")
            return

        def task():
            # 1. Check for local unstaged changes
            unstaged = git_utils.unstaged_files(cwd=self.current_project)
            staged = git_utils.staged_files(cwd=self.current_project)
            
            # 2. Fetch and check for incoming changes
            git_utils.fetch_remote(cwd=self.current_project)
            incoming = git_utils.get_incoming_commits(cwd=self.current_project)
            
            return {"unstaged": unstaged, "staged": staged, "incoming": incoming}

        def done_cb(result):
            err, status = result
            chat_widget = self.ai_tools_page
            if err:
                chat_widget.add_chat_message("시스템", f"프로젝트 상태 확인 실패: {err}")
                return

            messages = []
            if status["incoming"]:
                messages.append(f"원격 저장소에 {len(status['incoming'])}개의 새로운 커밋이 있습니다. 'pull'을 실행하여 업데이트하세요.")
            if status["staged"]:
                messages.append(f"{len(status['staged'])}개의 파일이 스테이지되어 커밋을 기다리고 있습니다.")
            if status["unstaged"]:
                messages.append(f"{len(status['unstaged'])}개의 파일에 반영되지 않은 변경사항이 있습니다.")

            if not messages:
                chat_widget.add_chat_message("AI", "✅ 확인 완료! 특별한 변경사항이 없습니다. 바로 작업을 시작하셔도 좋습니다!")
            else:
                summary = "현재 프로젝트 상태입니다:\n- " + "\n- ".join(messages)
                chat_widget.add_chat_message("AI", summary)

                # If there are incoming changes, ask the user if they want to pull
                if status["incoming"]:
                    commit_list = "\n".join([f"- {c['subject']} ({c['author']})" for c in status["incoming"][:5]])
                    reply = QMessageBox.question(
                        self, "업데이트 확인",
                        f"원격 저장소에 새로운 업데이트가 있습니다. 지금 `pull` 하시겠습니까?\n\n**최신 커밋:**\n{commit_list}",
                        QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
                    )
                    if reply == QMessageBox.Yes:
                        def pull_done_cb(err, _):
                            if err: chat_widget.add_chat_message("시스템", f"풀 실패: {err}")
                            else: chat_widget.add_chat_message("시스템", f"풀 성공.\n{_}")
                        self.on_pull(done_cb=pull_done_cb)

        self._start_worker(task, done_cb, busy_message="프로젝트 상태 확인 중...")

    def on_undo_commit_soft(self, done_cb=None):
        """Undo last commit but keep changes staged."""
        if not self.current_project:
            QMessageBox.warning(self, "프로젝트 없음", "먼저 Git 프로젝트를 열어주세요")
            return
        
        resp = QMessageBox.question(
            self,
            "마지막 커밋 취소 (soft)",
            "마지막 커밋을 취소하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        # If called from AI (done_cb is not None), skip the confirmation dialog
        if resp != QMessageBox.Yes and done_cb is None:
            return
        
        def task():
            return git_utils.undo_last_commit(cwd=self.current_project)
        
        def internal_done_cb(result):
            err, res = result
            if err:
                if not done_cb:
                    QMessageBox.critical(self, "실패", str(err))
            else:
                if not done_cb:
                    QMessageBox.information(self, "완료", "마지막 커밋이 취소되었습니다")
                self.refresh_staged()
                self.statusBar().showMessage("커밋 취소 완료", 5000)
            if done_cb:
                done_cb(err, res)
        
        self._start_worker(task, internal_done_cb, busy_message="마지막 커밋 취소 중...")
    
    def on_undo_commit_hard(self, done_cb=None):
        """Undo last commit and discard changes."""
        if not self.current_project:
            QMessageBox.warning(self, "프로젝트 없음", "먼저 Git 프로젝트를 열어주세요")
            return
        
        resp = QMessageBox.question(
            self,
            "마지막 커밋 취소 (hard)",
            "마지막 커밋을 취소하고 변경사항을 폐기하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        # If called from AI (done_cb is not None), skip the confirmation dialog
        if resp != QMessageBox.Yes and done_cb is None:
            return
        
        def task():
            return git_utils.undo_last_commit_hard(cwd=self.current_project)
        
        def internal_done_cb(result):
            err, res = result
            if err:
                if not done_cb:
                    QMessageBox.critical(self, "실패", str(err))
            else:
                if not done_cb:
                    QMessageBox.information(self, "완료", "마지막 커밋이 취소되었습니다")
                self.refresh_staged()
                self.statusBar().showMessage("커밋 취소 완료", 5000)
            if done_cb:
                done_cb(err, res)
        
        self._start_worker(task, internal_done_cb, busy_message="마지막 커밋 취소 중...")
    
    def on_abort_merge(self):
        """Abort an ongoing merge."""
        if not self.current_project:
            QMessageBox.warning(self, "프로젝트 없음", "먼저 Git 프로젝트를 열어주세요")
            return
        
        resp = QMessageBox.question(
            self,
            "머지 중단",
            "진행 중인 머지를 중단하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if resp != QMessageBox.Yes:
            return
        
        def task():
            return git_utils.abort_merge(cwd=self.current_project)
        
        def done_cb(result):
            err, res = result
            if err:
                QMessageBox.critical(self, "실패", str(err))
                return
            QMessageBox.information(self, "완료", "머지가 중단되었습니다")
            self.refresh_staged()
            self.statusBar().showMessage("머지 중단 완료", 5000)
        
        self._start_worker(task, done_cb, busy_message="머지 중단 중...")
    
    def on_reset_staged(self):
        """Unstage all staged changes."""
        if not self.current_project:
            QMessageBox.warning(self, "프로젝트 없음", "먼저 Git 프로젝트를 열어주세요")
            return
        
        def task():
            return git_utils.reset_staged(cwd=self.current_project)
        
        def done_cb(result):
            err, res = result
            if err:
                QMessageBox.critical(self, "실패", str(err))
                return
            QMessageBox.information(self, "완료", "모든 변경사항이 스테이지에서 해제되었습니다")
            self.refresh_staged()
            self.statusBar().showMessage("스테이지 해제 완료", 5000)
        
        self._start_worker(task, done_cb, busy_message="스테이지 해제 중...")

    def on_stage_file(self, item, done_cb=None):
        """Stage a selected unstaged file."""
        if not self.current_project:
            return
        file_path = item.text()
        if not file_path or "(" in file_path: # "(...)" 메시지 클릭 방지
            return

        def task():
            return git_utils.stage_file(file_path, cwd=self.current_project)

        def done_cb(result):
            err, _ = result
            if err:
                QMessageBox.critical(self, "스테이징 실패", str(err))
            self.refresh_staged()
            if done_cb:
                done_cb(err, _)

        self._start_worker(task, done_cb, busy_message=f"'{file_path}' 스테이징 중...")

    def on_unstage_file(self, item):
        """Unstage a selected staged file."""
        if not self.current_project:
            return
        file_path = item.text()
        if not file_path or "(" in file_path: # "(...)" 메시지 클릭 방지
            return

        def task():
            return git_utils.reset_file(file_path, cwd=self.current_project)

        def done_cb(result):
            err, _ = result
            if err:
                QMessageBox.critical(self, "스테이징 취소 실패", str(err))
            self.refresh_staged()

        self._start_worker(task, done_cb, busy_message=f"'{file_path}' 스테이징 취소 중...")

    def on_stage_all(self, done_cb=None):
        """Stage all unstaged files."""
        if not self.current_project:
            QMessageBox.warning(self, "프로젝트 없음", "먼저 Git 프로젝트를 열어주세요")
            return

        if not git_utils.unstaged_files(cwd=self.current_project):
            if not done_cb: # Only show popup if not called from AI
                QMessageBox.information(self, "변경사항 없음", "스테이지할 파일이 없습니다.")
            return

        def task():
            return git_utils.stage_file(".", cwd=self.current_project)

        def internal_done_cb(result):
            err, _ = result
            if err:
                if not done_cb:
                    QMessageBox.critical(self, "전체 스테이징 실패", str(err))
            self.refresh_staged()
            if done_cb:
                done_cb(err, _)

        self._start_worker(task, internal_done_cb, busy_message="모든 변경사항 스테이징 중...")

    def on_unstaged_list_context_menu(self, pos: QtCore.QPoint):
        """Show context menu for the unstaged files list."""
        item = self.unstaged_list.itemAt(pos)
        if not item or not item.text() or "(" in item.text():
            return

        menu = QtWidgets.QMenu()
        discard_action = menu.addAction("변경사항 폐기 (Discard)")
        action = menu.exec(self.unstaged_list.mapToGlobal(pos))

        if action == discard_action:
            self.on_discard_file_changes(item)

    def on_discard_file_changes(self, item: QtWidgets.QListWidgetItem):
        """Handle discarding changes for a single unstaged file."""
        if not self.current_project:
            return
        file_path = item.text()

        reply = QMessageBox.question(
            self, "변경사항 폐기",
            f"'{file_path}' 파일의 변경사항을 정말로 폐기하시겠습니까?\n이 작업은 되돌릴 수 없습니다.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        def task():
            return git_utils.discard_unstaged_file_changes(file_path, cwd=self.current_project)

        def done_cb(result):
            err, _ = result
            if err:
                QMessageBox.critical(self, "폐기 실패", str(err))
            self.refresh_staged()

        self._start_worker(task, done_cb, busy_message=f"'{file_path}' 변경사항 폐기 중...")

class SettingsPage(QtWidgets.QWidget):
    """Settings page widget."""
    settings_saved = QtCore.Signal()

    def __init__(self, app_config: Dict[str, Any], parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.app_config = app_config.copy()

        layout = QtWidgets.QVBoxLayout(self)
        form_layout = QtWidgets.QFormLayout()

        # Max Diff Bytes
        self.max_diff_spin = QtWidgets.QSpinBox()
        self.max_diff_spin.setMinimum(100_000)
        self.max_diff_spin.setMaximum(100_000_000)
        self.max_diff_spin.setValue(self.app_config.get("max_diff_bytes", 2_000_000))
        self.max_diff_spin.setSingleStep(100_000)
        h1 = QtWidgets.QHBoxLayout()
        h1.addWidget(self.max_diff_spin)
        h1.addWidget(QtWidgets.QLabel("(100KB ~ 100MB)"))
        form_layout.addRow("스테이지 diff 경고 임계값 (바이트):", h1)

        # AI Timeout
        self.ai_timeout_spin = QtWidgets.QDoubleSpinBox()
        self.ai_timeout_spin.setMinimum(5.0)
        self.ai_timeout_spin.setMaximum(300.0)
        self.ai_timeout_spin.setValue(self.app_config.get("ai_timeout_seconds", 60.0))
        self.ai_timeout_spin.setSingleStep(1.0)
        h2 = QtWidgets.QHBoxLayout()
        h2.addWidget(self.ai_timeout_spin)
        h2.addWidget(QtWidgets.QLabel("(5초 ~ 5분)"))
        form_layout.addRow("AI 호출 타임아웃 (초):", h2)

        # Git Executable
        self.git_exec_edit = QtWidgets.QLineEdit()
        self.git_exec_edit.setPlaceholderText("예: /opt/homebrew/bin/git")
        current_git = self.app_config.get("git_executable") or shutil.which("git") or "git"
        self.git_exec_edit.setText(current_git)
        form_layout.addRow("Git 실행 파일 경로:", self.git_exec_edit)

        # Ollama Host
        self.ollama_host_edit = QtWidgets.QLineEdit()
        self.ollama_host_edit.setText(self.app_config.get("ollama_host", "http://localhost:11434"))
        form_layout.addRow("Ollama 서버 주소:", self.ollama_host_edit)

        # Ollama Model
        self.ollama_model_edit = QtWidgets.QLineEdit()
        self.ollama_model_edit.setText(self.app_config.get("ollama_model", "exaone3.5:2.4b"))
        form_layout.addRow("Ollama 모델 이름:", self.ollama_model_edit)

        layout.addLayout(form_layout)
        layout.addStretch()

        h1 = QtWidgets.QHBoxLayout()
        h1.addStretch()
        save_btn = QtWidgets.QPushButton("설정 저장")
        save_btn.clicked.connect(self.save)
        h1.addWidget(save_btn)
        layout.addLayout(h1)

    def get_config(self) -> Dict[str, Any]:
        """Return current config values from the UI fields."""
        self.app_config["max_diff_bytes"] = self.max_diff_spin.value()
        self.app_config["ai_timeout_seconds"] = self.ai_timeout_spin.value()
        self.app_config["git_executable"] = self.git_exec_edit.text().strip()
        self.app_config["ollama_host"] = self.ollama_host_edit.text().strip()
        self.app_config["ollama_model"] = self.ollama_model_edit.text().strip()
        return self.app_config

    def save(self):
        """Save the current settings and emit a signal."""
        self.get_config() # Update internal dict from UI
        self.settings_saved.emit()
        QMessageBox.information(self, "설정 저장", "설정이 저장 및 적용되었습니다.")
