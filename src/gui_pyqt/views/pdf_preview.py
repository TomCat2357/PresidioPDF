"""
PresidioPDF PyQt - PDFプレビューウィジェット

Phase 4: 編集UI
- PDFページのレンダリング表示
- 検出結果のハイライト表示
- マウス操作によるページナビゲーション
"""

from typing import Optional, List, Dict
import fitz  # PyMuPDF
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
)
from PyQt6.QtCore import Qt, pyqtSignal, QRect
from PyQt6.QtGui import QPixmap, QImage, QPainter, QPen, QColor


class PDFPreviewWidget(QWidget):
    """PDFプレビュー表示ウィジェット"""

    # シグナル定義
    page_changed = pyqtSignal(int)  # ページ番号が変更された
    entity_clicked = pyqtSignal(int)  # クリックされたエンティティのインデックス

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pdf_document: Optional[fitz.Document] = None
        self.current_page_num: int = 0
        self.highlighted_entities: List[Dict] = []  # ハイライト表示するエンティティ
        self.zoom_level: float = 0.75

        self.init_ui()

    def init_ui(self):
        """UIの初期化"""
        layout = QVBoxLayout()

        # ページナビゲーション
        nav_layout = QHBoxLayout()
        self.prev_button = QPushButton("◀ 前へ")
        self.prev_button.clicked.connect(self.previous_page)
        self.prev_button.setEnabled(False)
        nav_layout.addWidget(self.prev_button)

        self.page_label = QLabel("ページ: -/-")
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nav_layout.addWidget(self.page_label)

        self.next_button = QPushButton("次へ ▶")
        self.next_button.clicked.connect(self.next_page)
        self.next_button.setEnabled(False)
        nav_layout.addWidget(self.next_button)

        layout.addLayout(nav_layout)

        # ズームコントロール
        zoom_layout = QHBoxLayout()
        zoom_out_btn = QPushButton("−")
        zoom_out_btn.setFixedWidth(30)
        zoom_out_btn.clicked.connect(self.zoom_out)
        zoom_layout.addWidget(zoom_out_btn)

        self.zoom_label = QLabel("75%")
        self.zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.zoom_label.setFixedWidth(50)
        zoom_layout.addWidget(self.zoom_label)

        zoom_in_btn = QPushButton("+")
        zoom_in_btn.setFixedWidth(30)
        zoom_in_btn.clicked.connect(self.zoom_in)
        zoom_layout.addWidget(zoom_in_btn)

        fit_btn = QPushButton("Fit")
        fit_btn.setFixedWidth(40)
        fit_btn.clicked.connect(self.zoom_fit)
        zoom_layout.addWidget(fit_btn)

        zoom_layout.addStretch()
        layout.addLayout(zoom_layout)

        # PDFプレビュー表示エリア（スクロール可能）
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setText("PDFファイルを読み込んでください")
        self.preview_label.setStyleSheet("background-color: #e0e0e0; padding: 20px;")
        self.preview_label.mousePressEvent = self._on_preview_click

        self.scroll_area.setWidget(self.preview_label)
        layout.addWidget(self.scroll_area)

        self.setLayout(layout)

    def load_pdf(self, pdf_path: str):
        """PDFファイルを読み込む"""
        try:
            if self.pdf_document:
                self.pdf_document.close()

            self.pdf_document = fitz.open(pdf_path)
            self.current_page_num = 0
            self.highlighted_entities = []

            self.update_preview()
            self.update_navigation_buttons()

        except Exception as e:
            self.preview_label.setText(f"PDFの読み込みに失敗: {str(e)}")
            self.pdf_document = None

    def update_preview(self):
        """現在のページをプレビュー表示"""
        if not self.pdf_document or self.current_page_num >= len(self.pdf_document):
            return

        try:
            # ページを取得
            page = self.pdf_document[self.current_page_num]

            # ページをPixmapとしてレンダリング（拡大率適用）
            mat = fitz.Matrix(self.zoom_level * 2, self.zoom_level * 2)  # 2倍で高解像度
            pix = page.get_pixmap(matrix=mat)

            # PyMuPDF PixmapをQImageに変換
            img_format = QImage.Format.Format_RGB888
            qimage = QImage(
                pix.samples,
                pix.width,
                pix.height,
                pix.stride,
                img_format
            )

            # QPixmapに変換してラベルに設定
            pixmap = QPixmap.fromImage(qimage)

            # ハイライト描画（該当ページのエンティティのみ）
            if self.highlighted_entities:
                pixmap = self.draw_highlights(pixmap, page)

            self.preview_label.setPixmap(pixmap)
            self.update_page_label()

        except Exception as e:
            self.preview_label.setText(f"プレビュー表示エラー: {str(e)}")

    def draw_highlights(self, pixmap: QPixmap, page: fitz.Page) -> QPixmap:
        """エンティティのハイライトを描画"""
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # スケール係数（レンダリング時の拡大率に合わせる）
        scale = self.zoom_level * 2

        # エンティティタイプごとの色設定
        color_map = {
            "PERSON": QColor(255, 200, 200, 100),
            "LOCATION": QColor(200, 255, 200, 100),
            "PHONE_NUMBER": QColor(200, 200, 255, 100),
            "DATE_TIME": QColor(255, 255, 200, 100),
            "INDIVIDUAL_NUMBER": QColor(255, 200, 255, 100),
            "YEAR": QColor(200, 255, 255, 100),
            "PROPER_NOUN": QColor(255, 220, 180, 100),
        }

        # 非選択エンティティを先に描画、選択エンティティを後に描画（前面に出す）
        for is_selected_pass in [False, True]:
            for entity in self.highlighted_entities:
                is_selected = entity.get("is_selected", False)
                if is_selected != is_selected_pass:
                    continue

                # 該当ページのエンティティのみ処理
                entity_page = entity.get("page_num", entity.get("page", 0))
                if entity_page != self.current_page_num:
                    continue

                entity_type = entity.get("entity_type", "OTHER")
                base_color = color_map.get(entity_type, QColor(200, 200, 200, 100))

                # 描画する矩形リストを取得
                rects = self._get_draw_rects(entity, scale)
                if not rects:
                    continue

                if is_selected:
                    # 選択中: 濃い色 + 太枠
                    fill_color = QColor(base_color.red(), base_color.green(), base_color.blue(), 160)
                    pen = QPen(base_color.darker(200), 3, Qt.PenStyle.SolidLine)
                else:
                    # 非選択: 通常の薄い色
                    fill_color = base_color
                    pen = QPen(base_color.darker(150), 1)

                painter.setPen(pen)
                painter.setBrush(fill_color)

                for rect in rects:
                    painter.drawRect(
                        int(rect[0]), int(rect[1]),
                        int(rect[2] - rect[0]), int(rect[3] - rect[1])
                    )

        painter.end()
        return pixmap

    def _get_draw_rects(self, entity: dict, scale: float) -> List[list]:
        """エンティティの描画矩形リストを取得（スケール適用済み）"""
        rects = []

        # rects_pdf（行ごとの矩形リスト）を優先
        rects_pdf = entity.get("rects_pdf")
        if rects_pdf and isinstance(rects_pdf, list):
            for r in rects_pdf:
                if isinstance(r, (list, tuple)) and len(r) >= 4:
                    rects.append([r[0] * scale, r[1] * scale, r[2] * scale, r[3] * scale])
            if rects:
                return rects

        # フォールバック: coordinates
        coords = entity.get("coordinates")
        if coords and isinstance(coords, dict):
            x0 = coords.get("x0", 0) * scale
            y0 = coords.get("y0", 0) * scale
            x1 = coords.get("x1", 0) * scale
            y1 = coords.get("y1", 0) * scale
            return [[x0, y0, x1, y1]]

        return []

    def set_highlighted_entities(self, entities: List[Dict]):
        """ハイライト表示するエンティティを設定"""
        self.highlighted_entities = entities
        self.update_preview()

    def go_to_page(self, page_num: int):
        """指定ページに移動"""
        if not self.pdf_document:
            return

        if 0 <= page_num < len(self.pdf_document):
            self.current_page_num = page_num
            self.update_preview()
            self.update_navigation_buttons()
            self.page_changed.emit(page_num)

    def previous_page(self):
        """前のページに移動"""
        if self.current_page_num > 0:
            self.go_to_page(self.current_page_num - 1)

    def next_page(self):
        """次のページに移動"""
        if self.pdf_document and self.current_page_num < len(self.pdf_document) - 1:
            self.go_to_page(self.current_page_num + 1)

    def update_navigation_buttons(self):
        """ナビゲーションボタンの有効/無効を更新"""
        if not self.pdf_document:
            self.prev_button.setEnabled(False)
            self.next_button.setEnabled(False)
            return

        self.prev_button.setEnabled(self.current_page_num > 0)
        self.next_button.setEnabled(self.current_page_num < len(self.pdf_document) - 1)

    def update_page_label(self):
        """ページ番号ラベルを更新"""
        if not self.pdf_document:
            self.page_label.setText("ページ: -/-")
        else:
            total = len(self.pdf_document)
            current = self.current_page_num + 1
            self.page_label.setText(f"ページ: {current}/{total}")

    def _on_preview_click(self, event):
        """プレビュー画像上のクリックでエンティティを特定"""
        if not self.highlighted_entities:
            return

        # ラベル内のPixmapオフセットを計算（中央揃えによるずれを補正）
        pixmap = self.preview_label.pixmap()
        if pixmap is None or pixmap.isNull():
            return

        label_w = self.preview_label.width()
        label_h = self.preview_label.height()
        pixmap_w = pixmap.width()
        pixmap_h = pixmap.height()

        offset_x = max((label_w - pixmap_w) / 2, 0)
        offset_y = max((label_h - pixmap_h) / 2, 0)

        click_x = event.position().x() - offset_x
        click_y = event.position().y() - offset_y

        # Pixmap範囲外のクリックは無視
        if click_x < 0 or click_y < 0 or click_x > pixmap_w or click_y > pixmap_h:
            return

        scale = self.zoom_level * 2

        for i, entity in enumerate(self.highlighted_entities):
            entity_page = entity.get("page_num", entity.get("page", 0))
            if entity_page != self.current_page_num:
                continue

            # 描画矩形リストを取得してヒットテスト
            rects = self._get_draw_rects(entity, scale)
            for rect in rects:
                if rect[0] <= click_x <= rect[2] and rect[1] <= click_y <= rect[3]:
                    self.entity_clicked.emit(i)
                    return

    def zoom_in(self):
        """ズームイン"""
        self.zoom_level = min(self.zoom_level + 0.25, 4.0)
        self.zoom_label.setText(f"{int(self.zoom_level * 100)}%")
        self.update_preview()

    def zoom_out(self):
        """ズームアウト"""
        self.zoom_level = max(self.zoom_level - 0.25, 0.25)
        self.zoom_label.setText(f"{int(self.zoom_level * 100)}%")
        self.update_preview()

    def zoom_fit(self):
        """ウィンドウ幅にフィット"""
        if not self.pdf_document or self.current_page_num >= len(self.pdf_document):
            return
        page = self.pdf_document[self.current_page_num]
        page_width = page.rect.width
        # scroll_areaの幅に合わせる（マージン分引く）
        available_width = self.scroll_area.viewport().width() - 20
        if page_width > 0 and available_width > 0:
            # 2倍レンダリングを考慮
            self.zoom_level = available_width / (page_width * 2)
            self.zoom_level = max(0.25, min(self.zoom_level, 4.0))
        else:
            self.zoom_level = 0.5
        self.zoom_label.setText(f"{int(self.zoom_level * 100)}%")
        self.update_preview()

    def close_pdf(self):
        """PDFドキュメントを閉じる"""
        if self.pdf_document:
            self.pdf_document.close()
            self.pdf_document = None
            self.preview_label.clear()
            self.preview_label.setText("PDFファイルを読み込んでください")
            self.update_navigation_buttons()
            self.update_page_label()
