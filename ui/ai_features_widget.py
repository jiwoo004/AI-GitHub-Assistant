"""AI Features UI Widget for AI Git Assistant.

Provides tabs for:
- Merge Conflict Analysis
- Code Review
- Diff Explanation
- General Q&A
"""
import json

from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtWidgets import QMessageBox, QTextEdit, QPushButton, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QTabWidget, QListWidget, QLineEdit

from backend import ai_features


class AIFeaturesWidget(QTabWidget):
    """Tabbed widget for AI features."""
    # Signal to emit when a command is interpreted from chat
    command_requested = QtCore.Signal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI 도구")
        self.resize(600, 500)
        
        # Conflict Analysis Tab
        self.addTab(self.create_conflict_tab(), "머지 충돌 분석")
        
        # Code Review Tab
        self.addTab(self.create_review_tab(), "코드 리뷰")
        
        # Diff Explanation Tab
        self.addTab(self.create_diff_tab(), "변경사항 설명")
        
        # Q&A Tab
        self.addTab(self.create_assistant_tab(), "AI 어시스턴트")
    
    def create_conflict_tab(self):
        """Create merge conflict analysis tab."""
        widget = QtWidgets.QWidget()
        layout = QVBoxLayout(widget)
        
        layout.addWidget(QLabel("머지 충돌 코드를 붙여넣기:"))
        self.conflict_input = QTextEdit()
        self.conflict_input.setPlaceholderText("<<<<<<< HEAD\n...\n=======\n...\n>>>>>>> branch")
        layout.addWidget(self.conflict_input)
        
        layout.addWidget(QLabel("컨텍스트 (선택):"))
        self.conflict_context = QTextEdit()
        self.conflict_context.setPlaceholderText("파일명, 브랜치명 등 추가 정보...")
        self.conflict_context.setMaximumHeight(80)
        layout.addWidget(self.conflict_context)
        
        btn_analyze = QPushButton("분석")
        btn_analyze.clicked.connect(self.analyze_conflict)
        layout.addWidget(btn_analyze)
        
        layout.addWidget(QLabel("분석 결과:"))
        self.conflict_output = QTextEdit()
        self.conflict_output.setReadOnly(True)
        layout.addWidget(self.conflict_output)
        
        return widget
    
    def create_review_tab(self):
        """Create code review tab."""
        widget = QtWidgets.QWidget()
        layout = QVBoxLayout(widget)
        
        layout.addWidget(QLabel("리뷰할 코드:"))
        self.review_input = QTextEdit()
        self.review_input.setPlaceholderText("리뷰할 코드를 붙여넣기...")
        layout.addWidget(self.review_input)
        
        h = QHBoxLayout()
        h.addWidget(QLabel("초점:"))
        self.review_focus = QComboBox()
        self.review_focus.addItems(["일반", "성능", "보안", "스타일", "유지보수성"])
        h.addWidget(self.review_focus)
        layout.addLayout(h)
        
        layout.addWidget(QLabel("파일명 (선택):"))
        self.review_file = QtWidgets.QLineEdit()
        self.review_file.setPlaceholderText("예: src/main.py")
        layout.addWidget(self.review_file)
        
        btn_review = QPushButton("리뷰 시작")
        btn_review.clicked.connect(self.review_code)
        layout.addWidget(btn_review)
        
        layout.addWidget(QLabel("리뷰 결과:"))
        self.review_output = QTextEdit()
        self.review_output.setReadOnly(True)
        layout.addWidget(self.review_output)
        
        return widget
    
    def create_diff_tab(self):
        """Create diff explanation tab."""
        widget = QtWidgets.QWidget()
        layout = QVBoxLayout(widget)
        
        layout.addWidget(QLabel("변경사항 (diff):"))
        self.diff_input = QTextEdit()
        self.diff_input.setPlaceholderText("diff 내용을 붙여넣기... (git diff 형식)")
        layout.addWidget(self.diff_input)
        
        layout.addWidget(QLabel("컨텍스트 (선택):"))
        self.diff_context = QTextEdit()
        self.diff_context.setPlaceholderText("PR 설명, 이슈 정보 등...")
        self.diff_context.setMaximumHeight(80)
        layout.addWidget(self.diff_context)
        
        btn_explain = QPushButton("설명 생성")
        btn_explain.clicked.connect(self.explain_diff)
        layout.addWidget(btn_explain)
        
        layout.addWidget(QLabel("설명:"))
        self.diff_output = QTextEdit()
        self.diff_output.setReadOnly(True)
        layout.addWidget(self.diff_output)
        
        return widget
    
    def analyze_conflict(self):
        """Analyze merge conflict."""
        conflict = self.conflict_input.toPlainText().strip()
        context = self.conflict_context.toPlainText().strip()
        
        if not conflict:
            QMessageBox.warning(self, "입력 필요", "충돌 코드를 입력해주세요")
            return

        main_window = self.window()

        def task():
            return ai_features.analyze_merge_conflict(conflict, context)

        def done_cb(result):
            err, response = result
            if err:
                self.conflict_output.setText(f"오류: {err}")
                return
            self.conflict_output.setText(response)

        main_window._start_worker(task, done_cb, "충돌 분석 중...")
    
    def start_conflict_analysis(self, conflict_content: str, context: str):
        """Programmatically start conflict analysis from outside."""
        # Switch to the conflict tab
        self.setCurrentIndex(0)
        self.conflict_input.setText(conflict_content)
        self.conflict_context.setText(context)
        self.analyze_conflict()

    def review_code(self):
        """Review code."""
        code = self.review_input.toPlainText().strip()
        file_path = self.review_file.text().strip()
        focus_map = {"일반": "", "성능": "performance", "보안": "security", 
                     "스타일": "style", "유지보수성": "maintainability"}
        focus = focus_map.get(self.review_focus.currentText(), "")
        
        if not code:
            QMessageBox.warning(self, "입력 필요", "리뷰할 코드를 입력해주세요")
            return

        main_window = self.window()

        def task():
            return ai_features.review_code(code, file_path, focus)

        def done_cb(result):
            err, response = result
            if err:
                self.review_output.setText(f"오류: {err}")
                return
            self.review_output.setText(response)

        main_window._start_worker(task, done_cb, "코드 리뷰 중...")
    
    def explain_diff(self):
        """Explain diff."""
        diff = self.diff_input.toPlainText().strip()
        context = self.diff_context.toPlainText().strip()
        
        if not diff:
            QMessageBox.warning(self, "입력 필요", "diff를 입력해주세요")
            return

        main_window = self.window()

        def task():
            return ai_features.explain_diff(diff, context)

        def done_cb(result):
            err, response = result
            if err:
                self.diff_output.setText(f"오류: {err}")
                return
            self.diff_output.setText(response)

        main_window._start_worker(task, done_cb, "변경사항 설명 생성 중...")
    
    # --- Assistant Tab ---
    def create_assistant_tab(self):
        """Create the chat-style AI Assistant tab."""
        widget = QtWidgets.QWidget()
        layout = QVBoxLayout(widget)

        self.chat_history = QListWidget()
        layout.addWidget(self.chat_history)

        input_layout = QHBoxLayout()
        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("명령을 입력하거나 질문하세요... (예: 모든 파일 스테이지해줘)")
        self.chat_input.returnPressed.connect(self.send_chat_message)
        input_layout.addWidget(self.chat_input)

        send_btn = QPushButton("전송")
        send_btn.clicked.connect(self.send_chat_message)
        input_layout.addWidget(send_btn)
        layout.addLayout(input_layout)

        return widget

    def send_chat_message(self):
        """Handle sending a message to the AI assistant."""
        user_text = self.chat_input.text().strip()
        if not user_text:
            return

        self.add_chat_message("나", user_text)
        self.chat_input.clear()

        # Get the top-level window (MainWindow) to access project context
        main_window = self.window()
        context = f"Current project: {main_window.current_project}, Current branch: {main_window.branch_combo.currentText()}"

        def task():
            return ai_features.interpret_command(user_text, context)

        def done_cb(result):
            err, response = result
            if err:
                self.add_chat_message("AI", f"오류가 발생했습니다: {err}")
                return

            # Clean up markdown fences if present
            cleaned_response = response.strip()
            if cleaned_response.startswith("```json"):
                cleaned_response = cleaned_response[7:]
            if cleaned_response.endswith("```"):
                cleaned_response = cleaned_response[:-3]
            cleaned_response = cleaned_response.strip()

            try:
                command_data = json.loads(cleaned_response)
                if "command" in command_data:
                    self.add_chat_message("AI", f"알겠습니다. '{command_data['command']}' 명령을 실행합니다.")
                    self.command_requested.emit(command_data)
                    return
            except json.JSONDecodeError:
                pass

            self.add_chat_message("AI", response)

        main_window._start_worker(task, done_cb, "AI 어시스턴트 생각 중...")

    def add_chat_message(self, sender: str, message: str):
        """Add a message to the chat history widget."""
        item = QtWidgets.QListWidgetItem()
        item.setText(f"[{sender}]: {message}")
        self.chat_history.addItem(item)
        self.chat_history.scrollToBottom()
