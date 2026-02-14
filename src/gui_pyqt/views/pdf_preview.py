"""
PresidioPDF PyQt - PDFプレビューウィジェット

Phase 4: 編集UI
- PDFページのレンダリング表示
- 検出結果のハイライト表示
- マウス操作によるページナビゲーション
"""

from typing import Optional, List, Dict, Tuple
import fitz  # PyMuPDF
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap, QImage, QPainter, QPen, QColor


class PDFPreviewWidget(QWidget):
    """PDFプレビュー表示ウィジェット"""

    # シグナル定義
    page_changed = pyqtSignal(int)  # ページ番号が変更された
    entity_clicked = pyqtSignal(int)  # クリックされたエンティティのインデックス
    text_selected = pyqtSignal(dict)  # テキストが選択された（手動PII追記用）

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pdf_document: Optional[fitz.Document] = None
        self.current_page_num: int = 0
        self.highlighted_entities: List[Dict] = []  # ハイライト表示するエンティティ
        self.zoom_level: float = 0.75

        # ドラッグ選択用の状態
        self.is_dragging: bool = False
        self.drag_start_pos: Optional[tuple] = None
        self.drag_current_pos: Optional[tuple] = None
        self.drag_start_char_index: Optional[int] = None
        self._page_chars_cache: Dict[int, List[Dict]] = {}

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
        self.preview_label.mousePressEvent = self._on_preview_mouse_press
        self.preview_label.mouseMoveEvent = self._on_preview_mouse_move
        self.preview_label.mouseReleaseEvent = self._on_preview_mouse_release
        self.preview_label.setMouseTracking(False)  # ドラッグ中のみ追跡

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
            self._page_chars_cache = {}
            self.drag_start_char_index = None
            self.drag_start_pos = None
            self.drag_current_pos = None

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

    def _view_to_pdf(self, view_x: float, view_y: float) -> Tuple[float, float]:
        """ビュー座標をPDF座標へ変換"""
        scale = max(self.zoom_level * 2, 1e-6)
        return view_x / scale, view_y / scale

    def _get_hit_tolerance_pdf(self, tolerance_px: float = 14.0) -> float:
        """ヒット判定用の許容距離（PDF座標系）"""
        scale = max(self.zoom_level * 2, 1e-6)
        return tolerance_px / scale

    def _get_page_chars(self, page_num: int) -> List[Dict]:
        """ページの文字情報（rawdict）をキャッシュ付きで取得"""
        if page_num in self._page_chars_cache:
            return self._page_chars_cache[page_num]

        if not self.pdf_document or page_num < 0 or page_num >= len(self.pdf_document):
            return []

        page = self.pdf_document[page_num]
        rawdict = page.get_text("rawdict")

        chars: List[Dict] = []
        text_block_id = 0
        for block in rawdict.get("blocks", []):
            if "lines" not in block:
                continue

            block_offset = 0
            for line_idx, line in enumerate(block.get("lines", [])):
                for span in line.get("spans", []):
                    for char_info in span.get("chars", []):
                        ch = char_info.get("c", "")
                        bbox = char_info.get("bbox")
                        if not ch or not bbox or len(bbox) < 4:
                            block_offset += 1
                            continue

                        chars.append(
                            {
                                "char": ch,
                                "rect": fitz.Rect(bbox[:4]),
                                "block_num": text_block_id,
                                "line_num": line_idx,
                                "offset": block_offset,
                            }
                        )
                        block_offset += 1

            text_block_id += 1

        self._page_chars_cache[page_num] = chars
        return chars

    def _distance_sq_to_rect(self, x: float, y: float, rect: fitz.Rect) -> float:
        """点と矩形の最短距離（二乗）"""
        dx = 0.0
        if x < rect.x0:
            dx = rect.x0 - x
        elif x > rect.x1:
            dx = x - rect.x1

        dy = 0.0
        if y < rect.y0:
            dy = rect.y0 - y
        elif y > rect.y1:
            dy = y - rect.y1

        return dx * dx + dy * dy

    def _find_char_index(
        self,
        page_chars: List[Dict],
        pdf_x: float,
        pdf_y: float,
        max_distance: Optional[float] = None,
    ) -> Optional[int]:
        """座標に最も近い文字インデックスを返す"""
        for i, item in enumerate(page_chars):
            rect = item.get("rect")
            if isinstance(rect, fitz.Rect) and rect.x0 <= pdf_x <= rect.x1 and rect.y0 <= pdf_y <= rect.y1:
                return i

        nearest_idx: Optional[int] = None
        nearest_dist_sq: Optional[float] = None
        for i, item in enumerate(page_chars):
            rect = item.get("rect")
            if not isinstance(rect, fitz.Rect):
                continue
            dist_sq = self._distance_sq_to_rect(pdf_x, pdf_y, rect)
            if nearest_dist_sq is None or dist_sq < nearest_dist_sq:
                nearest_dist_sq = dist_sq
                nearest_idx = i

        if nearest_idx is None:
            return None
        if max_distance is None:
            return nearest_idx
        if nearest_dist_sq is not None and nearest_dist_sq <= (max_distance * max_distance):
            return nearest_idx
        return None

    def _find_drag_target_char_index(
        self,
        view_pos: Optional[tuple],
        snap_nearest: bool = False,
    ) -> Optional[int]:
        """ドラッグ座標に対応する文字インデックスを返す"""
        if not view_pos or not self.pdf_document:
            return None

        page_chars = self._get_page_chars(self.current_page_num)
        if not page_chars:
            return None

        pdf_x, pdf_y = self._view_to_pdf(float(view_pos[0]), float(view_pos[1]))
        max_distance = None if snap_nearest else self._get_hit_tolerance_pdf()
        return self._find_char_index(page_chars, pdf_x, pdf_y, max_distance=max_distance)

    def _build_selection_line_rects(self, chars: List[Dict]) -> List[list]:
        """選択文字から行単位の矩形リストを生成"""
        rects_by_line: Dict[tuple, List[fitz.Rect]] = {}
        for item in chars:
            rect = item.get("rect")
            if not isinstance(rect, fitz.Rect):
                continue
            key = (int(item.get("block_num", 0)), int(item.get("line_num", 0)))
            rects_by_line.setdefault(key, []).append(rect)

        rects_pdf: List[list] = []
        for line_rects in rects_by_line.values():
            if not line_rects:
                continue
            rects_pdf.append(
                [
                    min(r.x0 for r in line_rects),
                    min(r.y0 for r in line_rects),
                    max(r.x1 for r in line_rects),
                    max(r.y1 for r in line_rects),
                ]
            )
        return rects_pdf

    def _get_indices_from_drag_rect(self) -> Optional[Tuple[int, int]]:
        """ドラッグ矩形に交差した文字の先頭/末尾インデックスを返す（フォールバック）"""
        if not self.drag_start_pos or not self.drag_current_pos:
            return None

        page_chars = self._get_page_chars(self.current_page_num)
        if not page_chars:
            return None

        x1, y1 = self.drag_start_pos
        x2, y2 = self.drag_current_pos
        pdf_x1, pdf_y1 = self._view_to_pdf(x1, y1)
        pdf_x2, pdf_y2 = self._view_to_pdf(x2, y2)
        clip_rect = fitz.Rect(
            min(pdf_x1, pdf_x2),
            min(pdf_y1, pdf_y2),
            max(pdf_x1, pdf_x2),
            max(pdf_y1, pdf_y2),
        )

        hit_indices: List[int] = []
        for i, item in enumerate(page_chars):
            rect = item.get("rect")
            if isinstance(rect, fitz.Rect) and rect.intersects(clip_rect):
                hit_indices.append(i)

        if not hit_indices:
            return None
        return min(hit_indices), max(hit_indices)

    def _on_preview_mouse_press(self, event):
        """プレビュー画像上のマウス押下（ドラッグ開始またはエンティティクリック）"""
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

        # テキスト上以外ではドラッグを開始しない（クリック判定のみ）
        if not self._is_text_hit(click_x, click_y):
            self._handle_entity_click(click_x, click_y)
            return

        # ドラッグ開始
        self.is_dragging = True
        self.drag_start_pos = (click_x, click_y)
        self.drag_current_pos = (click_x, click_y)
        self.drag_start_char_index = self._find_drag_target_char_index(
            self.drag_start_pos, snap_nearest=False
        )

    def _on_preview_mouse_move(self, event):
        """プレビュー画像上のマウス移動（ドラッグ中）"""
        if not self.is_dragging:
            return

        pixmap = self.preview_label.pixmap()
        if pixmap is None or pixmap.isNull():
            return

        label_w = self.preview_label.width()
        label_h = self.preview_label.height()
        pixmap_w = pixmap.width()
        pixmap_h = pixmap.height()

        offset_x = max((label_w - pixmap_w) / 2, 0)
        offset_y = max((label_h - pixmap_h) / 2, 0)

        current_x = event.position().x() - offset_x
        current_y = event.position().y() - offset_y

        # Pixmap範囲内に制限
        current_x = max(0, min(current_x, pixmap_w))
        current_y = max(0, min(current_y, pixmap_h))

        self.drag_current_pos = (current_x, current_y)

        # 選択矩形をオーバーレイ描画
        self._draw_selection_overlay()

    def _on_preview_mouse_release(self, event):
        """プレビュー画像上のマウスリリース（ドラッグ終了）"""
        if not self.is_dragging:
            return

        self.is_dragging = False

        # ドラッグ範囲が小さい場合はエンティティクリックとして処理
        if self.drag_start_pos and self.drag_current_pos:
            dx = abs(self.drag_current_pos[0] - self.drag_start_pos[0])
            dy = abs(self.drag_current_pos[1] - self.drag_start_pos[1])

            if dx < 5 and dy < 5:
                # クリックとして処理
                self._handle_entity_click(self.drag_start_pos[0], self.drag_start_pos[1])
                self.drag_start_pos = None
                self.drag_current_pos = None
                self.drag_start_char_index = None
                self.update_preview()
                return

        # ドラッグ範囲からテキストを抽出
        self._extract_selected_text()

        # ドラッグ状態をリセット
        self.drag_start_pos = None
        self.drag_current_pos = None
        self.drag_start_char_index = None
        self.update_preview()

    def _handle_entity_click(self, click_x: float, click_y: float):
        """エンティティクリック処理"""
        if not self.highlighted_entities:
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

    def _draw_selection_overlay(self):
        """選択矩形をオーバーレイ描画"""
        if not self.drag_start_pos or not self.drag_current_pos:
            return

        # 現在のプレビューを再描画
        self.update_preview()

        # 選択矩形を追加描画
        pixmap = self.preview_label.pixmap()
        if pixmap is None or pixmap.isNull():
            return

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        drew_text_overlay = False
        scale = self.zoom_level * 2

        if self.drag_start_char_index is not None:
            page_chars = self._get_page_chars(self.current_page_num)
            end_char_index = self._find_drag_target_char_index(
                self.drag_current_pos, snap_nearest=True
            )

            if (
                end_char_index is None
                and page_chars
                and 0 <= self.drag_start_char_index < len(page_chars)
            ):
                end_char_index = self.drag_start_char_index

            if end_char_index is not None and page_chars:
                start_idx = max(0, min(self.drag_start_char_index, len(page_chars) - 1))
                end_idx = max(0, min(end_char_index, len(page_chars) - 1))
                lo, hi = (start_idx, end_idx) if start_idx <= end_idx else (end_idx, start_idx)

                selected_chars = page_chars[lo:hi + 1]
                line_rects_pdf = self._build_selection_line_rects(selected_chars)
                if line_rects_pdf:
                    painter.setPen(QPen(QColor(0, 120, 215), 2, Qt.PenStyle.SolidLine))
                    painter.setBrush(QColor(0, 120, 215, 50))
                    for r in line_rects_pdf:
                        painter.drawRect(
                            int(r[0] * scale),
                            int(r[1] * scale),
                            int((r[2] - r[0]) * scale),
                            int((r[3] - r[1]) * scale),
                        )
                    drew_text_overlay = True

        if not drew_text_overlay:
            # フォールバック: 選択矩形
            x1, y1 = self.drag_start_pos
            x2, y2 = self.drag_current_pos
            x_min, x_max = (x1, x2) if x1 < x2 else (x2, x1)
            y_min, y_max = (y1, y2) if y1 < y2 else (y2, y1)

            painter.setPen(QPen(QColor(0, 120, 215), 2, Qt.PenStyle.SolidLine))
            painter.setBrush(QColor(0, 120, 215, 50))
            painter.drawRect(int(x_min), int(y_min), int(x_max - x_min), int(y_max - y_min))

        painter.end()
        self.preview_label.setPixmap(pixmap)

    def _extract_selected_text(self):
        """選択範囲からテキストを抽出してシグナル発行"""
        if not self.pdf_document or not self.drag_start_pos or not self.drag_current_pos:
            return

        try:
            page_chars = self._get_page_chars(self.current_page_num)
            if not page_chars:
                return

            start_char_index = self.drag_start_char_index
            end_char_index = self._find_drag_target_char_index(
                self.drag_current_pos, snap_nearest=True
            )

            if start_char_index is None:
                drag_indices = self._get_indices_from_drag_rect()
                if not drag_indices:
                    return
                start_char_index, end_char_index = drag_indices
            elif end_char_index is None:
                drag_indices = self._get_indices_from_drag_rect()
                if drag_indices:
                    _, end_char_index = drag_indices
                else:
                    end_char_index = start_char_index

            start_char_index = max(0, min(int(start_char_index), len(page_chars) - 1))
            end_char_index = max(0, min(int(end_char_index), len(page_chars) - 1))
            lo, hi = (
                (start_char_index, end_char_index)
                if start_char_index <= end_char_index
                else (end_char_index, start_char_index)
            )
            selected_chars = page_chars[lo:hi + 1]
            if not selected_chars:
                return

            # 先頭・末尾の空白を除去し、位置情報を同期
            start_idx = 0
            end_idx = len(selected_chars) - 1
            while start_idx <= end_idx and str(selected_chars[start_idx]["char"]).isspace():
                start_idx += 1
            while end_idx >= start_idx and str(selected_chars[end_idx]["char"]).isspace():
                end_idx -= 1
            if start_idx > end_idx:
                return

            trimmed_chars = selected_chars[start_idx:end_idx + 1]
            selected_text = "".join(str(c["char"]) for c in trimmed_chars)
            if not selected_text.strip():
                return

            first_char = trimmed_chars[0]
            last_char = trimmed_chars[-1]

            # 行単位の矩形（ハイライト描画用）
            rects_pdf = self._build_selection_line_rects(trimmed_chars)

            selection_data = {
                "text": selected_text,
                "start": {
                    "page_num": self.current_page_num,
                    "block_num": int(first_char["block_num"]),
                    "offset": int(first_char["offset"]),
                },
                "end": {
                    "page_num": self.current_page_num,
                    "block_num": int(last_char["block_num"]),
                    "offset": int(last_char["offset"]),
                },
                # 互換用フィールド
                "page_num": self.current_page_num,
                "block_num": int(first_char["block_num"]),
                "offset": int(first_char["offset"]),
                "end_offset": int(last_char["offset"]),
                "rects_pdf": rects_pdf,
            }
            self.text_selected.emit(selection_data)

        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"テキスト抽出エラー: {e}")

    def _is_text_hit(self, view_x: float, view_y: float) -> bool:
        """ビュー座標がテキスト領域上かを判定"""
        if not self.pdf_document:
            return False

        try:
            return (
                self._find_drag_target_char_index(
                    (float(view_x), float(view_y)),
                    snap_nearest=False,
                )
                is not None
            )
        except Exception:
            return False

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
            self._page_chars_cache = {}
            self.drag_start_char_index = None
            self.drag_start_pos = None
            self.drag_current_pos = None
            self.preview_label.clear()
            self.preview_label.setText("PDFファイルを読み込んでください")
            self.update_navigation_buttons()
            self.update_page_label()
