from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QStackedWidget,
                              QVBoxLayout, QHBoxLayout, QPushButton,
                              QLabel, QTextBrowser, QLineEdit, QFrame,
                              QFileDialog, QMessageBox, QSizePolicy)
from PyQt6.QtGui import QPixmap, QImage, QIcon, QMovie
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QSize
import cv2, sys, os, tempfile, random, webbrowser
from ExtractFromImage import ExtractFromImage, ItemParse


class AnalyzeWorker(QThread):
    # adds two extra strings for maps links (empty string = no link)
    finished = pyqtSignal(str, str, str, str, str)
    error    = pyqtSignal(str)

    def __init__(self, image_path, zip_code=None):
        super().__init__()
        self.image_path = image_path
        self.zip_code   = zip_code

    def run(self):
        try:
            items = ExtractFromImage.extract([self.image_path])

            projectIdeas_result   = ""
            recyclingIdeas_result = ""
            resaleIdeas_result    = ""
            disposing_maps_link   = ""
            selling_maps_link     = ""

            for item in items.items:
                result = ItemParse.parse_item(item, self.zip_code)
                projectIdeas_result   += f"### {result['item'].item_name}\n{result['item_using_options']}\n\n"
                recyclingIdeas_result += f"### {result['item'].item_name}\n{result['item_disposing_options']}\n\n"
                resaleIdeas_result    += f"### {result['item'].item_name}\n{result['item_selling_options']}\n\n"
                # use last non-None link found
                if result['disposing_maps_link']:
                    disposing_maps_link = result['disposing_maps_link']
                if result['selling_maps_link']:
                    selling_maps_link = result['selling_maps_link']

            self.finished.emit(
                projectIdeas_result.strip(),
                recyclingIdeas_result.strip(),
                resaleIdeas_result.strip(),
                disposing_maps_link,
                selling_maps_link,
            )
        except Exception as e:
            self.error.emit(str(e))


def _make_card(bg_color: str, border_color: str) -> tuple[QFrame, QVBoxLayout]:
    """Helper — returns a styled card frame and its inner layout."""
    card = QFrame()
    card.setStyleSheet(f"""
        QFrame {{
            background-color: {bg_color};
            border: 1px solid {border_color};
            border-left: 4px solid {border_color};
            border-radius: 8px;
            padding: 4px;
        }}
    """)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(8, 8, 8, 8)
    layout.setSpacing(6)
    return card, layout


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("WasteWiseAI")
        self.setFixedSize(500, 750)
        self.current_image = None
        self.cap = None
        self.worker = None
        self.zip_code = None
        self.setWindowIcon(QIcon("leaf1.png"))

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)

        self._loading_step = 0
        self._loading_phases = [
            "Analyzing object .    ",
            "Analyzing object . .  ",
            "Analyzing object . . .",
        ]
        self.loading_timer = QTimer()
        self.loading_timer.timeout.connect(self._tick_loading)

        self._eco_facts = [
            "Recycling one glass bottle saves enough energy to power a lightbulb for 4 hours.",
            "Americans throw away 2.5 million plastic bottles every hour.",
            "One recycled aluminum can saves enough energy to run a TV for 3 hours.",
            "It takes 450 years for a plastic bottle to decompose.",
            "Composting can reduce household waste by up to 30%.",
            "Recycling one ton of paper saves 17 trees and 7,000 gallons of water.",
            "The average person generates over 4 pounds of trash every day.",
            "Glass is 100% recyclable and can be reused endlessly without quality loss.",
            "Producing recycled plastic uses 88% less energy than making new plastic.",
            "Food scraps and yard waste make up about 30% of what we throw away.",
        ]
        self._fact_index = 0
        self.fact_timer = QTimer()
        self.fact_timer.timeout.connect(self._rotate_fact)
        self.fact_timer.start(5000)

        self._quiz_questions = [
            {
                "q": "How long does it take for a plastic bottle to decompose in a landfill?",
                "choices": ["10 years", "50 years", "200 years", "450 years"],
                "correct": 3,
                "explanation": "Plastic bottles take about 450 years to break down. Even then, they don't truly biodegrade — they just fragment into microplastics that persist in the environment."
            },
            {
                "q": "Which material can be recycled infinitely without quality loss?",
                "choices": ["Plastic", "Paper", "Glass", "Cardboard"],
                "correct": 2,
                "explanation": "Glass is made of silica, sodium carbonate, and limestone, which retain their properties through melting. Plastic and paper degrade a little each recycling cycle, but glass can be recycled endlessly."
            },
            {
                "q": "How much energy does recycling aluminum save vs. producing new aluminum?",
                "choices": ["25%", "50%", "75%", "95%"],
                "correct": 3,
                "explanation": "Recycling aluminum uses 95% less energy. Making new aluminum requires extracting bauxite ore and a huge amount of electricity to separate the aluminum, which is why aluminum recycling is one of the most impactful habits."
            },
            {
                "q": "What should you do before recycling food containers?",
                "choices": ["Nothing, just toss them in", "Rinse them", "Crush them flat", "Remove all labels"],
                "correct": 1,
                "explanation": "Rinsing prevents food residue from contaminating other recyclables. Contaminated batches often get sent to landfill entirely. Labels are usually fine to leave on — facilities can handle them."
            },
            {
                "q": "What does the number inside a recycling triangle on plastic tell you?",
                "choices": ["Times it can be recycled", "Type of plastic resin", "Age of the product", "Weight in ounces"],
                "correct": 1,
                "explanation": "The number (1–7) identifies the plastic resin type. Types 1 (PET) and 2 (HDPE) are the most widely recyclable; types 3–7 are often not accepted curbside."
            },
            {
                "q": "Which of these is NOT typically recyclable in standard curbside bins?",
                "choices": ["Aluminum cans", "Pizza boxes with grease stains", "Cardboard boxes", "Clean glass bottles"],
                "correct": 1,
                "explanation": "Grease and food oils contaminate the paper fibers, making pizza boxes non-recyclable in most programs."
            },
            {
                "q": "What is 'wish-cycling'?",
                "choices": ["Biking to work", "Throwing unsure items in the recycling bin hoping they'll be recycled", "A type of composting", "Recycling gift wrap"],
                "correct": 1,
                "explanation": "Wish-cycling is well-intentioned but harmful — non-recyclable items contaminate the batch and can send the whole load to landfill."
            },
            {
                "q": "Which item should NEVER go in curbside recycling?",
                "choices": ["Newspaper", "Plastic grocery bags", "Steel cans", "Cardboard"],
                "correct": 1,
                "explanation": "Plastic bags tangle in sorting machinery and shut down entire facilities for hours."
            },
            {
                "q": "Which bin does a used paper coffee cup typically belong in?",
                "choices": ["Recycling", "Compost", "Trash", "Hazardous waste"],
                "correct": 2,
                "explanation": "Most disposable coffee cups have a thin plastic lining which makes them non-recyclable in standard streams."
            },
            {
                "q": "What should you do with old batteries?",
                "choices": ["Throw in regular trash", "Put in recycling bin", "Take to a battery drop-off location", "Flush down the drain"],
                "correct": 2,
                "explanation": "Batteries contain toxic heavy metals that can leach into groundwater if landfilled."
            },
        ]

        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #F5F7F5;
                font-family: 'Segoe UI';
            }
            QPushButton {
                background-color: #16A34A;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 16px;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #15803D; }
            QPushButton:pressed { background-color: #166534; }
            QTextBrowser {
                border: none;
                background-color: transparent;
                font-size: 13px;
                color: #1E293B;
            }
            QLabel { color: #1E293B; font-size: 13px; }
        """)

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.stack.addWidget(self._build_input_page())   # 0
        self.stack.addWidget(self._build_loading_page()) # 1
        self.stack.addWidget(self._build_results_page()) # 2
        self.stack.addWidget(self._build_quiz_page())    # 3

        self.open_camera()

    # ── Page builders ──────────────────────────────────────────────────────────

    def _build_input_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 10, 20, 20)
        layout.setSpacing(20)

        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_pixmap = QPixmap("WasteWiseAI Title.png")
        logo_label.setPixmap(logo_pixmap.scaled(640, 135, Qt.AspectRatioMode.KeepAspectRatio,
                                                Qt.TransformationMode.SmoothTransformation))
        logo_label.setFixedHeight(140)

        self.image_label = QLabel("No image uploaded")
        self.image_label.setFixedWidth(460)
        self.image_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        btn_row = QHBoxLayout()
        upload_btn = QPushButton("Upload Image")
        upload_btn.clicked.connect(self.upload_image)
        self.camera_btn = QPushButton("Capture")
        self.camera_btn.clicked.connect(self.capture_frame)
        btn_row.addWidget(upload_btn)
        btn_row.addWidget(self.camera_btn)

        analyze_btn = QPushButton("Analyze")
        analyze_btn.clicked.connect(self.analyze)

        zip_row = QHBoxLayout()
        zip_label = QLabel("Zip Code (optional):")
        zip_label.setStyleSheet("font-size: 12px; color: #4B5563;")
        self.zip_input = QLineEdit()
        self.zip_input.setPlaceholderText("e.g. 92083")
        self.zip_input.setMaxLength(5)
        self.zip_input.setFixedWidth(100)
        self.zip_input.setStyleSheet("border:1px solid #D1D5DB; border-radius:6px; padding:6px 8px; background:white; color: #1E293B; font-size:13px; selection-background-color: #BBF7D0; selection-color: #1E293B;")
        self.zip_input.textChanged.connect(self._on_zip_changed)
        zip_row.addStretch()
        zip_row.addWidget(zip_label)
        zip_row.addWidget(self.zip_input)
        zip_row.addStretch()

        quiz_btn = QPushButton("Take this quick quiz to learn more about recycling!")
        quiz_btn.setStyleSheet("""
            QPushButton { background-color:white; color:#16A34A; border:1px solid #16A34A; border-radius:6px; padding:10px 16px; font-size:13px; }
            QPushButton:hover { background-color:#ECFDF5; }
        """)
        quiz_btn.clicked.connect(self.start_quiz)

        layout.addWidget(logo_label)
        layout.addWidget(self.image_label)
        layout.addLayout(btn_row)
        layout.addLayout(zip_row)
        layout.addWidget(analyze_btn)
        layout.addWidget(quiz_btn)
        layout.addStretch()

        help_btn = QPushButton(page)
        help_btn.setFixedSize(32, 32)
        help_btn.setStyleSheet("QPushButton{background:white;border:1px solid #16A34A;border-radius:16px;} QPushButton:hover{background:#ECFDF5;}")
        help_btn.clicked.connect(self.show_about_popup)
        help_btn.move(448, 12)
        help_btn.raise_()
        q_label = QLabel("?", help_btn)
        q_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        q_label.setFixedSize(32, 32)
        q_label.setStyleSheet("color:#16A34A;font-size:16px;font-weight:bold;background:transparent;")
        q_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        return page

    def _build_loading_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        spinner_label = QLabel()
        spinner_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.spinner_movie = QMovie("magnifyingglass1.gif")
        self.spinner_movie.setScaledSize(QSize(180, 180))
        spinner_label.setMovie(self.spinner_movie)

        self.loading_label = QLabel("Analyzing object .    ")
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_label.setFixedWidth(380)
        self.loading_label.setStyleSheet("font-size:20px;font-weight:bold;color:#1E293B;")

        sub_label = QLabel("Please be patient. This may take a while.")
        sub_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.fact_label = QLabel(self._eco_facts[0])
        self.fact_label.setWordWrap(True)
        self.fact_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.fact_label.setStyleSheet("font-size:12px;color:#4B5563;font-style:italic;padding:10px;background:#ECFDF5;border:1px solid #BBF7D0;border-radius:6px;")

        layout.addWidget(spinner_label)
        layout.addSpacing(16)
        layout.addWidget(self.loading_label)
        layout.addSpacing(8)
        layout.addWidget(sub_label)
        layout.addSpacing(8)
        layout.addWidget(self.fact_label)
        return page

    def _build_results_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        header = QLabel("Analysis")
        header.setStyleSheet("font-size:18px;font-weight:bold;color:#1E293B;")

        # ── Project Ideas ──
        proj_header = QLabel("Project Ideas")
        proj_header.setStyleSheet("font-size:13px;font-weight:bold;color:#15803D;")
        self.output_projectIdeas = QTextBrowser()
        self.output_projectIdeas.setReadOnly(True)
        self.output_projectIdeas.setOpenExternalLinks(True)
        self.output_projectIdeas.setStyleSheet("""
            QTextBrowser {
                border: 2px solid #16A34A;
                border-radius: 8px;
                padding: 10px;
                background-color: #ECFDF5;
                font-size: 13px;
                color: #1E293B;
            }
        """)

        # ── Recyclability ──
        rec_header = QLabel("Recyclability")
        rec_header.setStyleSheet("font-size:13px;font-weight:bold;color:#1D4ED8;")
        self.output_recyclingIdeas = QTextBrowser()
        self.output_recyclingIdeas.setReadOnly(True)
        self.output_recyclingIdeas.setOpenExternalLinks(True)
        self.output_recyclingIdeas.setStyleSheet("""
            QTextBrowser {
                border: 2px solid #3B82F6;
                border-radius: 8px;
                padding: 10px;
                background-color: #EFF6FF;
                font-size: 13px;
                color: #1E293B;
            }
        """)
        self.disposing_directions_btn = QPushButton("Get Directions")
        self.disposing_directions_btn.setStyleSheet("background-color:#3B82F6;font-size:12px;padding:6px 12px;")
        self.disposing_directions_btn.hide()

        # ── Resalability ──
        res_header = QLabel("Resalability")
        res_header.setStyleSheet("font-size:13px;font-weight:bold;color:#C2410C;")
        self.output_resaleIdeas = QTextBrowser()
        self.output_resaleIdeas.setReadOnly(True)
        self.output_resaleIdeas.setOpenExternalLinks(True)
        self.output_resaleIdeas.setStyleSheet("""
            QTextBrowser {
                border: 2px solid #F97316;
                border-radius: 8px;
                padding: 10px;
                background-color: #FFF7ED;
                font-size: 13px;
                color: #1E293B;
            }
        """)
        self.selling_directions_btn = QPushButton("Get Directions")
        self.selling_directions_btn.setStyleSheet("background-color:#F97316;font-size:12px;padding:6px 12px;")
        self.selling_directions_btn.hide()

        btn_row = QHBoxLayout()
        retake_btn = QPushButton("Take New Picture")
        retake_btn.clicked.connect(self.restart_with_camera)
        upload_new_btn = QPushButton("Upload Image")
        upload_new_btn.clicked.connect(self.restart_with_upload)
        btn_row.addWidget(upload_new_btn)
        btn_row.addWidget(retake_btn)

        layout.addWidget(header)
        layout.addWidget(proj_header)
        layout.addWidget(self.output_projectIdeas)
        layout.addWidget(rec_header)
        layout.addWidget(self.output_recyclingIdeas)
        layout.addWidget(self.disposing_directions_btn)
        layout.addWidget(res_header)
        layout.addWidget(self.output_resaleIdeas)
        layout.addWidget(self.selling_directions_btn)
        layout.addLayout(btn_row)
        return page

    def _build_quiz_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        header = QLabel("Recycling Quiz")
        header.setStyleSheet("font-size:18px;font-weight:bold;color:#1E293B;")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.quiz_progress = QLabel("Question 1 of 5")
        self.quiz_progress.setStyleSheet("font-size:12px;color:#4B5563;")
        self.quiz_progress.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.quiz_question = QLabel()
        self.quiz_question.setWordWrap(True)
        self.quiz_question.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.quiz_question.setStyleSheet("font-size:15px;font-weight:bold;color:#1E293B;padding:20px;background:white;border:1px solid #D1D5DB;border-left:3px solid #16A34A;border-radius:6px;")

        self.quiz_choice_btns = []
        choices_layout = QVBoxLayout()
        choices_layout.setSpacing(8)
        for i in range(4):
            btn = QPushButton()
            btn.setCheckable(True)
            btn.setStyleSheet("""
                QPushButton { background:white; color:#1E293B; border:1px solid #D1D5DB; border-radius:6px; padding:12px; font-size:13px; text-align:left; }
                QPushButton:hover { background:#F9FAFB; }
                QPushButton:checked { background:#ECFDF5; border:2px solid #16A34A; color:#15803D; font-weight:bold; }
            """)
            btn.clicked.connect(lambda _, idx=i: self._select_choice(idx))
            self.quiz_choice_btns.append(btn)
            choices_layout.addWidget(btn)

        self.quiz_feedback = QLabel("")
        self.quiz_feedback.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.quiz_feedback.setWordWrap(True)
        self.quiz_feedback.setStyleSheet("font-size:13px;font-weight:bold;padding:8px;")

        btn_row = QHBoxLayout()
        self.quiz_back_btn = QPushButton("Back to Home")
        self.quiz_back_btn.clicked.connect(self.exit_quiz)
        self.quiz_submit_btn = QPushButton("Submit")
        self.quiz_submit_btn.clicked.connect(self._submit_quiz_answer)
        btn_row.addWidget(self.quiz_back_btn)
        btn_row.addWidget(self.quiz_submit_btn)

        layout.addWidget(header)
        layout.addWidget(self.quiz_progress)
        layout.addWidget(self.quiz_question)
        layout.addLayout(choices_layout)
        layout.addWidget(self.quiz_feedback)
        layout.addStretch()
        layout.addLayout(btn_row)
        return page

    # ── Quiz logic ─────────────────────────────────────────────────────────────

    def start_quiz(self):
        self._active_quiz = random.sample(self._quiz_questions, min(5, len(self._quiz_questions)))
        self._quiz_index = 0
        self._quiz_score = 0
        self._load_question()
        self.stack.setCurrentIndex(3)

    def _load_question(self):
        q = self._active_quiz[self._quiz_index]
        self.quiz_progress.setText(f"Question {self._quiz_index + 1} of {len(self._active_quiz)}")
        self.quiz_question.setText(q["q"])
        for i, btn in enumerate(self.quiz_choice_btns):
            btn.setText(q["choices"][i])
            btn.setChecked(False)
            btn.setEnabled(True)
        self.quiz_feedback.setText("")
        self.quiz_feedback.setStyleSheet("")
        self.quiz_submit_btn.setText("Submit")
        self._quiz_selected = None

    def _select_choice(self, idx):
        self._quiz_selected = idx
        for i, btn in enumerate(self.quiz_choice_btns):
            if i != idx:
                btn.setChecked(False)

    def _submit_quiz_answer(self):
        if self.quiz_feedback.text():
            self._quiz_index += 1
            if self._quiz_index >= len(self._active_quiz):
                self._show_quiz_result()
            else:
                self._load_question()
            return
        if self._quiz_selected is None:
            QMessageBox.warning(self, "No Answer", "Please select an answer first.")
            return
        q = self._active_quiz[self._quiz_index]
        correct_idx = q["correct"]
        if self._quiz_selected == correct_idx:
            self._quiz_score += 1
            self.quiz_feedback.setText("✓ Correct!")
            self.quiz_feedback.setStyleSheet("font-size:14px;font-weight:bold;color:#16A34A;padding:8px;")
        else:
            self.quiz_feedback.setText(f"✗ Incorrect. The correct answer is: {q['choices'][correct_idx]}\n\n{q['explanation']}")
            self.quiz_feedback.setStyleSheet("font-size:13px;color:#1E293B;padding:12px;background:#FEF2F2;border:1px solid #FECACA;border-radius:6px;")
        for btn in self.quiz_choice_btns:
            btn.setEnabled(False)
        is_last = self._quiz_index == len(self._active_quiz) - 1
        self.quiz_submit_btn.setText("See Results" if is_last else "Next Question")

    def _show_quiz_result(self):
        total = len(self._active_quiz)
        QMessageBox.information(self, "Quiz Complete",
            f"You scored {self._quiz_score} / {total}!\n\n"
            f"{'Great job! You know your recycling.' if self._quiz_score >= total * 0.7 else 'Keep learning — every bit helps!'}")
        self.exit_quiz()

    def exit_quiz(self):
        self.stack.setCurrentIndex(0)

    def show_about_popup(self):
        popup = QMessageBox(self)
        popup.setWindowTitle("About WasteWiseAI")
        popup.setTextFormat(Qt.TextFormat.RichText)
        popup.setText("<h3 style='color:#16A34A;'>About WasteWiseAI</h3>"
                      "<p>WasteWiseAI helps you find sustainable ways to handle everyday objects.</p>"
                      "<ul><li>Take a photo or upload an image</li>"
                      "<li>AI identifies what it is</li>"
                      "<li>Get project ideas, recycling info, and resale options</li></ul>"
                      "<p><b>Tips:</b> Add your zip code for local drop-off locations.</p>")
        popup.setIconPixmap(QPixmap("leaf1.png").scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatio,
                                                        Qt.TransformationMode.SmoothTransformation))
        popup.setStandardButtons(QMessageBox.StandardButton.Ok)
        popup.exec()

    # ── Analyze flow ───────────────────────────────────────────────────────────

    def analyze(self):
        if self.current_image is None:
            QMessageBox.warning(self, "No Image", "Please upload or capture an image first.")
            return
        self._loading_step = 0
        self.loading_timer.start(400)
        self.spinner_movie.start()
        self.stack.setCurrentIndex(1)
        self.worker = AnalyzeWorker(self.current_image, self.zip_code)
        self.worker.finished.connect(self.on_analysis_done)
        self.worker.error.connect(self.on_analysis_error)
        self.worker.start()

    def _tick_loading(self):
        self.loading_label.setText(self._loading_phases[self._loading_step])
        self._loading_step = (self._loading_step + 1) % len(self._loading_phases)

    def on_analysis_done(self, proj, recycling, resale, disposing_link, selling_link):
        self.loading_timer.stop()
        self.spinner_movie.stop()
        self.output_projectIdeas.setMarkdown(proj)
        self.output_recyclingIdeas.setMarkdown(recycling)
        self.output_resaleIdeas.setMarkdown(resale)

        # show/hide directions buttons
        if disposing_link:
            self.disposing_directions_btn.show()
            self.disposing_directions_btn.clicked.connect(lambda: webbrowser.open(disposing_link))
        else:
            self.disposing_directions_btn.hide()

        if selling_link:
            self.selling_directions_btn.show()
            self.selling_directions_btn.clicked.connect(lambda: webbrowser.open(selling_link))
        else:
            self.selling_directions_btn.hide()

        self.stack.setCurrentIndex(2)

    def on_analysis_error(self, message):
        self.loading_timer.stop()
        self.spinner_movie.stop()
        self.output_projectIdeas.setMarkdown("")
        self.output_recyclingIdeas.setMarkdown(f"**Error:** {message}")
        self.output_resaleIdeas.setMarkdown("")
        self.disposing_directions_btn.hide()
        self.selling_directions_btn.hide()
        self.stack.setCurrentIndex(2)

    # ── Restart helpers ────────────────────────────────────────────────────────

    def restart_with_camera(self):
        self.current_image = None
        self.camera_btn.setText("Capture")
        self.image_label.setText("No image uploaded")
        self.stack.setCurrentIndex(0)
        self.open_camera()

    def restart_with_upload(self):
        self.current_image = None
        self.camera_btn.setText("Capture")
        self.image_label.setText("No image uploaded")
        self.stack.setCurrentIndex(0)
        self.upload_image()

    # ── Camera ─────────────────────────────────────────────────────────────────

    def open_camera(self):
        if self.cap is None:
            self.cap = cv2.VideoCapture(0)
            self.timer.start(30)
            self.camera_btn.setText("Capture")

    def close_camera(self):
        if self.cap is not None:
            self.timer.stop()
            self.cap.release()
            self.cap = None

    def update_frame(self):
        ret, frame = self.cap.read()
        if not ret:
            return
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = frame.shape
        qt_image = QImage(frame.data, w, h, ch * w, QImage.Format.Format_RGB888)
        self.image_label.setPixmap(QPixmap.fromImage(qt_image).scaled(460, 460, Qt.AspectRatioMode.KeepAspectRatio))

    def capture_frame(self):
        if self.cap is not None:
            ret, frame = self.cap.read()
            if not ret:
                return
            path = os.path.join(tempfile.gettempdir(), "captured_image.jpg")
            cv2.imwrite(path, frame)
            self.current_image = path
            self.close_camera()
            self.image_label.setPixmap(QPixmap(path).scaled(460, 460, Qt.AspectRatioMode.KeepAspectRatio))
            self.camera_btn.setText("Retake Picture")
        else:
            self.open_camera()
            self.current_image = None

    def upload_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Image", "", "Images (*.png *.jpg *.webp)")
        if path:
            self.current_image = path
            self.close_camera()
            self.camera_btn.setText("Retake Picture")
            self.image_label.setPixmap(QPixmap(path).scaled(460, 460, Qt.AspectRatioMode.KeepAspectRatio))

    def _on_zip_changed(self, text):
        self.zip_code = text if text.isdigit() and len(text) == 5 else None

    def _rotate_fact(self):
        self._fact_index = (self._fact_index + 1) % len(self._eco_facts)
        self.fact_label.setText(self._eco_facts[self._fact_index])


app = QApplication(sys.argv)
window = MainWindow()
window.show()
sys.exit(app.exec())