/**
 * PDF個人情報マスキングツール - Webアプリケーション
 * JavaScript フロントエンド（PDF.js統合版）
 */

document.addEventListener('DOMContentLoaded', () => {
    console.log('=== PDF Viewer Debug Mode ===');
    
    // Wait for PDF.js library to be fully loaded
    const initializePDFViewer = () => {
        console.log('Checking PDF.js library availability...');
        console.log('pdfjsLib type:', typeof pdfjsLib);
        console.log('window.pdfjsLib:', window.pdfjsLib);
        console.log('Available globals:', Object.keys(window).filter(k => k.includes('pdf')));
        
        if (typeof pdfjsLib === 'undefined') {
            console.error('PDF.js library not found!');
            console.log('Checking alternative global names...');
            
            // Check alternative global variable names
            if (typeof window.pdfjsLib !== 'undefined') {
                window.pdfjsLib = window.pdfjsLib;
                console.log('Using window.pdfjsLib');
            } else if (typeof window.PDFJS !== 'undefined') {
                window.pdfjsLib = window.PDFJS;
                console.log('Using window.PDFJS');
            } else {
                console.error('No PDF.js library found in any global scope');
                alert('PDF.js library not loaded. Please check your internet connection.');
                return;
            }
        }
        
        console.log('PDF.js library found, setting worker...');
        pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
        console.log('PDF.js worker set to:', pdfjsLib.GlobalWorkerOptions.workerSrc);
        
        // Initialize the application
        initializeApp();
    };
    
    const initializeApp = () => {
        console.log('Initializing PDF web application...');

    class PresidioPDFWebApp {
        constructor() {
            this.currentPdfDocument = null;
            this.currentPdfPath = null;
            this.currentPage = 1;
            this.totalPages = 0;
            this.zoomLevel = 100;
            this.detectionResults = [];
            this.selectedEntityIndex = -1;
            this.currentSelection = null;
            this.viewport = null;
            
            // 選択範囲のバッファ（最新10件まで保存）
            this.selectionHistory = [];
            this.maxSelectionHistory = 10;

            // 追加：座標変換ユーティリティ（PDF.jsのviewportを使って相互変換）
            this.viewportRectToPdfRect = (vp, vx0, vy0, vx1, vy1) => {
                // CSS左上原点のviewport座標 → PDFポイント（左下原点）
                const p0 = vp.convertToPdfPoint(vx0, vy0);
                const p1 = vp.convertToPdfPoint(vx1, vy1);
                return [Math.min(p0[0], p1[0]), Math.min(p0[1], p1[1]),
                        Math.max(p0[0], p1[0]), Math.max(p0[1], p1[1])];
            };
            this.normRectFromPdfRect = (W, H, r) => [r[0]/W, r[1]/H, r[2]/W, r[3]/H];

            this.settings = {
                entities: ["PERSON", "LOCATION", "PHONE_NUMBER", "DATE_TIME", "INDIVIDUAL_NUMBER", "YEAR", "PROPER_NOUN"],
                masking_method: "both",           // 既定をbothへ（ハイライト＋FreeText）
                masking_text_mode: "verbose",
                spacy_model: "ja_core_news_sm",
                // 重複除去設定（CLI版と同様）
                deduplication_enabled: false,
                deduplication_method: "overlap",
                deduplication_priority: "wider_range",
                deduplication_overlap_mode: "partial_overlap"
            };

            this.initializeElements();
            this.bindEvents();
            this.loadSettings();
        }

        initializeElements() {
            this.elements = {
                uploadArea: document.getElementById('uploadArea'),
                pdfFileInput: document.getElementById('pdfFileInput'),
                selectedFileName: document.getElementById('selectedFileName'),
                detectBtn: document.getElementById('detectBtn'),
                settingsBtn: document.getElementById('settingsBtn'),
                prevPageBtn: document.getElementById('prevPageBtn'),
                nextPageBtn: document.getElementById('nextPageBtn'),
                pageInfo: document.getElementById('pageInfo'),
                pageJumpInput: document.getElementById('pageJumpInput'),
                pageJumpBtn: document.getElementById('pageJumpBtn'),
                zoomSlider: document.getElementById('zoomSlider'),
                zoomValue: document.getElementById('zoomValue'),
                showHighlights: document.getElementById('showHighlights'),
                zoomDisplay: document.getElementById('zoomDisplay'),
                entityList: document.getElementById('entityList'),
                resultCount: document.getElementById('resultCount'),
                saveBtn: document.getElementById('saveBtn'),
                resetBtn: document.getElementById('resetBtn'),
                statusMessage: document.getElementById('statusMessage'),
                loadingOverlay: document.getElementById('loadingOverlay'),
                pdfViewer: document.getElementById('pdfViewer'),
                pdfPlaceholder: document.getElementById('pdfPlaceholder'),
                pdfCanvasContainer: document.getElementById('pdfCanvasContainer'),
                pdfCanvas: document.getElementById('pdfCanvas'),
                textLayer: document.getElementById('textLayer'),
                highlightOverlay: document.getElementById('highlightOverlay'),
                saveSettingsBtn: document.getElementById('saveSettingsBtn'),
                contextMenu: document.getElementById('contextMenu'),
                cancelSelection: document.getElementById('cancelSelection'),
                exportSettingsBtn: document.getElementById('exportSettingsBtn'),
                importSettingsBtn: document.getElementById('importSettingsBtn'),
                importSettingsFile: document.getElementById('importSettingsFile'),
                excludeWords: document.getElementById('excludeWords'),
                additionalPersonWords: document.getElementById('additionalPersonWords'),
                additionalLocationWords: document.getElementById('additionalLocationWords'),
                additionalPhoneWords: document.getElementById('additionalPhoneWords'),
                additionalDateWords: document.getElementById('additionalDateWords'),
                additionalIndividualWords: document.getElementById('additionalIndividualWords'),
                additionalYearWords: document.getElementById('additionalYearWords'),
                additionalProperNounWords: document.getElementById('additionalProperNounWords')
            };
            this.pdfContext = this.elements.pdfCanvas.getContext('2d');
        }

        // =================================================================
        // ==  イベント処理の根本的な修正  ==
        // =================================================================
        bindEvents() {
            // --- ファイル操作と基本的なUIボタンのイベント ---
            this.elements.uploadArea.addEventListener('click', () => this.elements.pdfFileInput.click());
            this.elements.pdfFileInput.addEventListener('change', (e) => this.handleFileSelect(e.target.files[0]));
            ['dragover', 'dragleave', 'drop'].forEach(eventName => {
                this.elements.uploadArea.addEventListener(eventName, this.preventDefaults, false);
            });
            ['dragenter', 'dragover'].forEach(eventName => {
                this.elements.uploadArea.addEventListener(eventName, () => this.elements.uploadArea.classList.add('dragover'), false);
            });
            ['dragleave', 'drop'].forEach(eventName => {
                this.elements.uploadArea.addEventListener(eventName, () => this.elements.uploadArea.classList.remove('dragover'), false);
            });
            this.elements.uploadArea.addEventListener('drop', (e) => this.handleFileDrop(e), false);

            this.elements.detectBtn.addEventListener('click', () => this.detectEntities());
            this.elements.prevPageBtn.addEventListener('click', () => this.changePage(this.currentPage - 1));
            this.elements.nextPageBtn.addEventListener('click', () => this.changePage(this.currentPage + 1));
            this.elements.zoomSlider.addEventListener('input', (e) => this.updateZoom(parseInt(e.target.value, 10)));
            this.elements.showHighlights.addEventListener('change', () => this.renderHighlights());
            this.elements.saveBtn.addEventListener('click', () => this.generateAndDownloadPdf());

            // リセットボタンのイベント
            this.elements.resetBtn.addEventListener('click', async () => {
                if (!this.detectionResults.length) { 
                    this.updateStatus('リセット対象なし'); 
                    return; 
                }
                if (!window.confirm('検出済みの個人情報をすべて削除します。元に戻せません。実行しますか？')) return;
                try {
                    this.showLoading(true, 'リセット中...');
                    await fetch('/api/reset_entities', { method: 'POST' });
                    this.detectionResults = [];
                    this.selectedEntityIndex = -1;
                    this.renderEntityList();
                    this.renderHighlights();
                    this.updateResultCount?.();
                    this.updateSaveButtonState?.();
                    this.updateStatus('検出結果をリセットしました');
                } finally { 
                    this.showLoading(false); 
                }
            });

            // 個別のコピーボタンは廃止
            this.elements.saveSettingsBtn.addEventListener('click', () => this.saveSettings());

            // 設定エクスポート・インポートのイベント
            this.elements.exportSettingsBtn.addEventListener('click', () => this.exportSettings());
            this.elements.importSettingsBtn.addEventListener('click', () => this.elements.importSettingsFile.click());
            this.elements.importSettingsFile.addEventListener('change', (e) => this.importSettings(e));

            // --- PDFビューアのインタラクティブなイベント（整理・統合済み） ---

            // 1. マウスのボタンが押された時のログ出力
            this.elements.pdfViewer.addEventListener('mousedown', (e) => {
                if (e.button === 0) { // 左クリックのみ
                    console.log('Mouse Down (Left Button)', { x: e.clientX, y: e.clientY });
                }
            });

            // 2. マウスがドラッグされている間のログ出力
            this.elements.pdfViewer.addEventListener('mousemove', (e) => {
                if (e.buttons & 1) { // 左クリックが押されている場合
                    console.log('Mouse Move (Left Button Held)', { x: e.clientX, y: e.clientY });
                }
            });

            // 3. 左クリックを離した時に、選択範囲をエンティティとして追加
            let mouseDownPosition = null;
            let selectionAtMouseDown = null;
            
            this.elements.pdfViewer.addEventListener('mousedown', (e) => {
                if (e.button === 0) {
                    mouseDownPosition = { x: e.clientX, y: e.clientY };
                    selectionAtMouseDown = window.getSelection().toString();
                }
            });
            
            this.elements.pdfViewer.addEventListener('mouseup', async (e) => {
                if (e.button === 0) { // 左クリックのみ
                    console.log('Mouse Up (Left Button)', { x: e.clientX, y: e.clientY });
                    
                    // マウスが移動していない場合（単純なクリック）は処理しない
                    if (mouseDownPosition && 
                        Math.abs(e.clientX - mouseDownPosition.x) < 5 && 
                        Math.abs(e.clientY - mouseDownPosition.y) < 5) {
                        console.log('Single click detected, skipping selection processing');
                        return;
                    }
                    
                    // 短い遅延の代わりに、すぐに処理を実行
                    const selection = window.getSelection();
                    let currentSelection = null;
                    
                    console.log('Selection object:', selection);
                    console.log('Range count:', selection?.rangeCount);
                    
                    if (selection && selection.rangeCount > 0) {
                        const range = selection.getRangeAt(0);
                        const selectedText = range.toString().trim();
                        
                        console.log('Selected text:', selectedText);
                        console.log('Range commonAncestorContainer:', range.commonAncestorContainer);
                        console.log('TextLayer element:', this.elements.textLayer);
                        
                        // より厳密な含有チェック
                        let isInTextLayer = false;
                        if (range.commonAncestorContainer) {
                            if (range.commonAncestorContainer === this.elements.textLayer) {
                                isInTextLayer = true;
                            } else if (range.commonAncestorContainer.nodeType === Node.TEXT_NODE) {
                                isInTextLayer = this.elements.textLayer.contains(range.commonAncestorContainer.parentNode);
                            } else {
                                isInTextLayer = this.elements.textLayer.contains(range.commonAncestorContainer);
                            }
                        }
                        
                        console.log('Contains check:', isInTextLayer);
                        
                        // 選択範囲がtextLayerの中にあり、テキストが存在するかチェック
                        if (selectedText && selectedText.length > 0 && isInTextLayer) {
                            const rect = range.getBoundingClientRect();
                            const referenceRect = this.elements.textLayer.getBoundingClientRect();
                            
                            currentSelection = {
                                text: selectedText,
                                range: range.cloneRange(),
                                rect: rect,
                                pdfX: rect.left - referenceRect.left,
                                pdfY: rect.top - referenceRect.top,
                                pageNumber: this.currentPage
                            };
                            console.log('Created currentSelection:', currentSelection);
                        } else {
                            console.log('Failed text or contains check:', {
                                hasText: !!selectedText,
                                textLength: selectedText ? selectedText.length : 0,
                                isInTextLayer: isInTextLayer
                            });
                        }
                    } else {
                        console.log('No selection or no ranges');
                    }
                    
                    console.log('Mouse Up - Direct Selection:', currentSelection);
                    
                    // 直接の選択が取得できない場合は、選択履歴から最新の有効な選択を取得
                    if (!currentSelection) {
                        currentSelection = this.getLatestValidSelection();
                        console.log('Using selection from history:', currentSelection);
                    }
                    
                    if (currentSelection && currentSelection.text.length > 0) {
                        const selectedMode = document.querySelector('input[name="entityMode"]:checked');
                        console.log('Selected Mode:', selectedMode, 'Value:', selectedMode?.value);
                        
                        // 一時的にcurrentSelectionを設定
                        this.currentSelection = currentSelection;
                        
                        if (selectedMode && selectedMode.value && selectedMode.value !== 'none') {
                            // エンティティタイプが選択されている場合は直接追加
                            console.log('Adding manual entity:', selectedMode.value);
                            this.addManualEntity(selectedMode.value);
                        } else {
                            // コピーモードは自動コピー
                            try {
                                await navigator.clipboard.writeText(currentSelection.text);
                                this.updateStatus(`「${currentSelection.text}」をコピーしました`);
                            } catch {
                                this.updateStatus('コピーに失敗しました');
                            }
                        }
                    } else {
                        console.log('No valid selection found, even in history');
                    }
                }
            });

            // 4. 右クリックでコンテキストメニューを表示
            this.elements.pdfViewer.addEventListener('contextmenu', (e) => {
                e.preventDefault();
                this.handleSelection(e, true);
            });

            // 5. テキストの選択範囲が変化するたびに、選択情報を更新し、ログを出力
            document.addEventListener('selectionchange', () => {
                const selection = window.getSelection();
                if (selection && selection.rangeCount > 0) {
                    const range = selection.getRangeAt(0);
                    
                    // より厳密な含有チェック
                    let isInTextLayer = false;
                    if (range.commonAncestorContainer) {
                        if (range.commonAncestorContainer === this.elements.textLayer) {
                            isInTextLayer = true;
                        } else if (range.commonAncestorContainer.nodeType === Node.TEXT_NODE) {
                            isInTextLayer = this.elements.textLayer.contains(range.commonAncestorContainer.parentNode);
                        } else {
                            isInTextLayer = this.elements.textLayer.contains(range.commonAncestorContainer);
                        }
                    }
                    
                    if (isInTextLayer) {
                        const selectedText = selection.toString().trim();
                        if (selectedText.length > 0) {
                            console.log(`選択中の文字列: "${selectedText}", 文字数: ${selectedText.length}`);
                            const rect = range.getBoundingClientRect();
                            const referenceRect = this.elements.textLayer.getBoundingClientRect(); 
                            
                            // 行ごとのクライアント矩形を保持（複数行対応）
                            const clientRects = Array.from(range.getClientRects()).map(r => ({
                                left: r.left, top: r.top, right: r.right, bottom: r.bottom,
                                width: r.width, height: r.height
                            }));
                            
                            const selectionData = {
                                text: selectedText,
                                range: range.cloneRange(),
                                rect: rect,
                                rects: clientRects,
                                pdfX: rect.left - referenceRect.left,
                                pdfY: rect.top - referenceRect.top,
                                pageNumber: this.currentPage,
                                timestamp: Date.now()
                            };
                            
                            this.currentSelection = selectionData;
                            
                            // 選択履歴に追加
                            this.addToSelectionHistory(selectionData);
                        } else {
                            this.currentSelection = null;
                        }
                    }
                } else {
                    this.currentSelection = null;
                }
            });
            
            // 6. PDFビューア外のクリックでコンテキストメニューを閉じる
            document.addEventListener('click', (e) => {
                if (this.elements.contextMenu && !this.elements.contextMenu.contains(e.target)) {
                    this.hideContextMenu();
                }
            });
        }
        // =================================================================
        // ==  ここまでが修正点です ==
        // =================================================================
        
        preventDefaults(e) {
            e.preventDefault();
            e.stopPropagation();
        }

        handleFileDrop(e) {
            const dt = e.dataTransfer;
            const files = dt.files;
            if (files.length > 0) {
                this.elements.uploadArea.style.borderColor = '#28a745';
                this.elements.uploadArea.style.backgroundColor = '#d4edda';
                this.updateStatus('ファイルを処理中...');
                setTimeout(() => {
                    this.handleFileSelect(files[0]);
                }, 100);
            }
        }

        async handleFileSelect(file) {
            console.log('=== handleFileSelect called ===');
            console.log('File:', file);
            console.log('File type:', file?.type);
            console.log('File size:', file?.size);
            
            if (!file || file.type !== 'application/pdf') {
                console.error('Invalid file type:', file?.type);
                this.showError('PDFファイルを選択してください');
                return;
            }
            this.showLoading(true, 'PDFをアップロード中...');
            
            try {
                console.log('Creating FormData for upload...');
                const formData = new FormData();
                formData.append('pdf_file', file);
                
                console.log('Sending file to server...');
                const response = await fetch('/api/upload', { method: 'POST', body: formData });
                const data = await response.json();
                console.log('Server response:', data);

                if (!data.success) throw new Error(data.message);

                this.currentPdfPath = data.filename;
                this.elements.selectedFileName.textContent = file.name;
                this.updateStatus('PDFを読み込み中...');
                
                console.log('Reading file as ArrayBuffer...');
                const arrayBuffer = await file.arrayBuffer();
                console.log('ArrayBuffer size:', arrayBuffer.byteLength);
                
                console.log('Loading PDF with PDF.js...');
                console.log('pdfjsLib.getDocument typeof:', typeof pdfjsLib.getDocument);
                
                const loadingTask = pdfjsLib.getDocument(arrayBuffer);
                console.log('Loading task created:', loadingTask);
                
                this.currentPdfDocument = await loadingTask.promise;
                console.log('PDF document loaded:', this.currentPdfDocument);
                console.log('Number of pages:', this.currentPdfDocument.numPages);
                
                this.totalPages = this.currentPdfDocument.numPages;
                this.currentPage = 1;
                this.elements.detectBtn.disabled = false;
                console.log('Rendering first page.');
                await this.renderPage(this.currentPage);
                this.updateStatus(`PDF読み込み完了: ${file.name}`);
                console.log('PDF loading completed successfully');

            } catch (error) {
                console.error('=== File handling error ===');
                console.error('Error details:', error);
                console.error('Error stack:', error.stack);
                this.showError(error.message || 'ファイルの処理中にエラーが発生しました');
            } finally {
                this.showLoading(false);
            }
        }

        async renderPage(pageNum) {
            console.log('=== renderPage called ===');
            console.log('Page number:', pageNum);
            console.log('Total pages:', this.totalPages);
            console.log('PDF document:', this.currentPdfDocument);
            
            if (!this.currentPdfDocument || pageNum < 1 || pageNum > this.totalPages) {
                console.error('Invalid page rendering conditions');
                return;
            }
            this.showLoading(true, 'ページを描画中...');
            try {
                console.log('Getting page from PDF document...');
                // PDF.jsのPageオブジェクトを保持してページ高さ(PDFポイント)を参照できるようにする
                this.pdfPage = await this.currentPdfDocument.getPage(pageNum);
                const page = this.pdfPage;
                console.log('Page object:', page);
                
                const scale = this.zoomLevel / 100;
                console.log('Scale:', scale);
                
                this.viewport = page.getViewport({ scale });
                console.log('Viewport:', this.viewport);
                console.log('Viewport dimensions:', this.viewport.width, 'x', this.viewport.height);

                const canvas = this.elements.pdfCanvas;
                const container = this.elements.pdfCanvasContainer;
                console.log('Canvas element:', canvas);
                console.log('Container element:', container);

                container.style.setProperty('--scale-factor', this.viewport.scale);
                canvas.width = this.viewport.width;
                canvas.height = this.viewport.height;
                console.log('Canvas dimensions set to:', canvas.width, 'x', canvas.height);

                const renderContext = {
                    canvasContext: this.pdfContext,
                    viewport: this.viewport
                };
                console.log('Render context:', renderContext);
                console.log('Canvas context:', this.pdfContext);
                
                console.log('Starting page rendering...');
                await page.render(renderContext).promise;
                console.log('Page rendering completed');

                console.log('Rendering text layer...');
                await this.renderTextLayer(page);
                console.log('Text layer rendering completed');
                
                this.renderHighlights();

                this.updatePageInfo();
                this.elements.pdfPlaceholder.style.display = 'none';
                this.elements.pdfCanvasContainer.style.display = 'block';
                
                console.log('Page rendering process completed successfully');

            } catch (error) {
                console.error('=== renderPage error ===');
                console.error(`Error rendering page ${pageNum}:`, error);
                console.error('Error stack:', error.stack);
                this.showError('ページの描画に失敗しました');
            } finally {
                this.showLoading(false);
            }
        }

        async renderTextLayer(page) {
            const container = this.elements.textLayer;
            container.innerHTML = '';
            container.style.width = `${this.viewport.width}px`;
            container.style.height = `${this.viewport.height}px`;
            
            try {
                const textContent = await page.getTextContent();
                pdfjsLib.renderTextLayer({
                    textContentSource: textContent,
                    container: container,
                    viewport: this.viewport,
                    textDivs: []
                });
            } catch (error) {
                console.error('Failed to render text layer:', error);
            }
        }

        /**
         * entity に優先順で格納する座標:
         *   - rect_pdf: [x0,y0,x1,y1]  (PDFポイント, 左下原点)
         *   - rect_norm: [x0/W, y0/H, x1/W, y1/H]  (ページ基準の正規化)
         *   - page_num: 0ベース
         */
        viewportRectToPdfRect(viewport, vx0, vy0, vx1, vy1) {
            // viewport座標 -> PDFポイント（左下原点）
            const [px0, py0] = viewport.convertToPdfPoint(vx0, vy0);
            const [px1, py1] = viewport.convertToPdfPoint(vx1, vy1);
            const x0 = Math.min(px0, px1), y0 = Math.min(py0, py1);
            const x1 = Math.max(px0, px1), y1 = Math.max(py0, py1);
            return [x0, y0, x1, y1];
        }

        pdfRectToViewportRect(viewport, rx) {
            // PDFポイント -> viewport座標
            const [vx0, vy0] = viewport.convertToViewportPoint(rx[0], rx[1]);
            const [vx1, vy1] = viewport.convertToViewportPoint(rx[2], rx[3]);
            const left = Math.min(vx0, vx1);
            const top = Math.min(vy0, vy1);
            const width = Math.abs(vx1 - vx0);
            const height = Math.abs(vy1 - vy0);
            return { left, top, width, height };
        }

        // === 座標系ユーティリティ（Fitz<->PDF.js のY反転） ===
        // Fitz(左上原点) -> PDF.js(左下原点)
        fitzRectToPdfjsRect(rect, pageHeightPt) {
            const [x0, y0, x1, y1] = rect;
            return [x0, pageHeightPt - y1, x1, pageHeightPt - y0];
        }
        // PDF.js(左下原点) -> Fitz(左上原点)
        pdfjsRectToFitzRect(rect, pageHeightPt) {
            const [x0, y0, x1, y1] = rect;
            return [x0, pageHeightPt - y1, x1, pageHeightPt - y0];
        }

        normRectFromPdfRect(pageWidthPt, pageHeightPt, r) {
            return [r[0]/pageWidthPt, r[1]/pageHeightPt, r[2]/pageWidthPt, r[3]/pageHeightPt];
        }

        renderHighlights() {
            if (!this.viewport) return;
            const container = this.elements.highlightOverlay;
            container.innerHTML = '';
            const page = this.currentPage;

            // ページ判定を統一（page_num:0-based / page:1-based の混在に対応）
            const pageEntities = this.detectionResults.filter(e => (e.page_num + 1) === page);
            
            pageEntities.forEach((entity) => {
                const globalIndex = this.detectionResults.indexOf(entity);
                // line_rects があれば複数行ハイライト、なければ単一
                const needMulti =
                  (Array.isArray(entity.line_rects) && entity.line_rects.length > 0) ||
                  (typeof entity.text === 'string' && entity.text.includes('\n'));
                const el = needMulti
                  ? this.createMultiLineHighlight(entity, globalIndex)
                  : this.createHighlightElement(entity, globalIndex);
                if (el) {
                    container.appendChild(el);
                }
            });
        }
        
        createHighlightElement(entity, index) {
            let pdfRect;
            // ページ高さは pdfPage.getViewport(scale=1) を第一候補、なければ現在viewportから算出
            const pageHeightPt =
              (this.pdfPage && typeof this.pdfPage.getViewport === 'function'
                ? this.pdfPage.getViewport({ scale: 1 }).height
                : undefined) ??
              (this.viewport ? (this.viewport.height / this.viewport.scale) : undefined);
            if (entity.rect_pdf && pageHeightPt) {
                // Fitz -> PDF.js にY反転してからビューポート矩形へ
                pdfRect = this.fitzRectToPdfjsRect(entity.rect_pdf, pageHeightPt);
            } else if (entity.coordinates && pageHeightPt) { // 後方互換性（Fitz系）
                const c = entity.coordinates;
                pdfRect = this.fitzRectToPdfjsRect([c.x0, c.y0, c.x1, c.y1], pageHeightPt);
            } else {
                return null;
            }

            try {
                const viewportRect = this.viewport.convertToViewportRectangle(pdfRect);

                if (viewportRect) {
                    const left = Math.min(viewportRect[0], viewportRect[2]);
                    const top = Math.min(viewportRect[1], viewportRect[3]);
                    const width = Math.abs(viewportRect[2] - viewportRect[0]);
                    const height = Math.abs(viewportRect[3] - viewportRect[1]);

                    const el = document.createElement('div');
                    el.className = 'highlight-rect';
                    el.classList.add(entity.entity_type.toLowerCase().replace(/_/g, '-'));
                    if (index === this.selectedEntityIndex) {
                        el.classList.add('selected');
                    }

                    el.style.left = `${left}px`;
                    el.style.top = `${top}px`;
                    el.style.width = `${width}px`;
                    el.style.height = `${height}px`;
                    el.dataset.index = index;
                    el.addEventListener('click', (ev) => {
                        ev.stopPropagation();
                        this.selectEntity(index);
                    });
                    return el;
                }
                return null;
            } catch (error) {
                console.error('Error creating highlight element:', error, 'for entity:', entity);
                return null;
            }
        }

        createMultiLineHighlight(entity, index) {
            // 複数行ハイライト用のコンテナを作成
            const container = document.createElement('div');
            container.className = 'multi-line-highlight';
            container.dataset.index = index;

            // line_rectsが存在しない場合は、テキストを行分割して推定矩形を作成
            let lineRects = entity.line_rects;
            if (!lineRects || lineRects.length === 0) {
                lineRects = this.estimateLineRects(entity);
            }

            // PDFページの実寸を取得（Y反転に使用）
            const pageHeightPt =
              (this.pdfPage && typeof this.pdfPage.getViewport === 'function'
                ? this.pdfPage.getViewport({ scale: 1 }).height
                : undefined) ??
              (this.viewport ? (this.viewport.height / this.viewport.scale) : undefined);

            console.log('Multi-line highlight creation:', {
                entityText: entity.text,
                lineRectsCount: lineRects.length,
                lineRects: lineRects
            });

            // 各行の矩形を作成
            lineRects.forEach((lineRect, lineIndex) => {
                const highlightEl = document.createElement('div');
                highlightEl.className = 'highlight-rect';
                highlightEl.classList.add(entity.entity_type.toLowerCase().replace(/_/g, '-'));

                if (index === this.selectedEntityIndex) {
                    highlightEl.classList.add('selected');
                }

                // line_rects の座標系を判別してPDFユーザ空間に正規化
                const space = (lineRect.coord_space || lineRect.space || 'fitz'); // 後方互換：未指定はfitz扱い
                let pdfRect;
                if (space === 'fitz') {
                    if (!pageHeightPt) return; // 安全策
                    pdfRect = this.fitzRectToPdfjsRect(
                      [lineRect.rect.x0, lineRect.rect.y0, lineRect.rect.x1, lineRect.rect.y1],
                      pageHeightPt
                    );
                } else {
                    // 'pdf' はそのまま
                    pdfRect = [
                      lineRect.rect.x0, lineRect.rect.y0, lineRect.rect.x1, lineRect.rect.y1
                    ];
                }

                console.log(`Line ${lineIndex} conversion:`, {
                    originalRect: lineRect.rect,
                    coordSpace: space,
                    pdfRect: pdfRect
                });

                const viewportRect = this.viewport.convertToViewportRectangle(pdfRect);
                console.log(`Line ${lineIndex} viewport rect:`, viewportRect);
                
                const left = Math.min(viewportRect[0], viewportRect[2]);
                const top = Math.min(viewportRect[1], viewportRect[3]);
                const right = Math.max(viewportRect[0], viewportRect[2]);
                const bottom = Math.max(viewportRect[1], viewportRect[3]);
                
                const width = right - left;
                const height = bottom - top;
                
                const minHeight = 12;
                const adjustedHeight = Math.max(height, minHeight);

                console.log(`Line ${lineIndex} final position:`, {
                    left, top, width, height: adjustedHeight
                });

                highlightEl.style.left = `${left}px`;
                highlightEl.style.top = `${top}px`;
                highlightEl.style.width = `${width}px`;
                highlightEl.style.height = `${adjustedHeight}px`;
                highlightEl.style.position = 'absolute';

                highlightEl.addEventListener('click', (e) => {
                    e.stopPropagation();
                    this.selectEntity(index);
                    this.scrollToEntityInList(index);
                });

                container.appendChild(highlightEl);
            });

            return container;
        }

        estimateLineRects(entity) {
            // テキストが改行を含む場合、各行の矩形を推定
            const lines = entity.text.split('\n');
            const lineRects = [];

            if (lines.length > 1) {
                // 旧来の推定ロジック：coordinates（Fitz）の全体矩形を行数で割る
                const baseRect = entity.coordinates;
                const lineHeight = (baseRect.y1 - baseRect.y0) / lines.length;
                
                lines.forEach((lineText, index) => {
                    if (lineText.trim()) {
                        lineRects.push({
                            rect: {
                                x0: baseRect.x0,
                                y0: baseRect.y0 + (index * lineHeight),
                                x1: baseRect.x1,
                                y1: baseRect.y0 + ((index + 1) * lineHeight)
                            },
                            coord_space: 'fitz',
                            text: lineText,
                            line_number: index + 1
                        });
                    }
                });
            } else {
                // 単一行だが複数行として扱われている場合
                lineRects.push({
                    rect: entity.coordinates,
                    coord_space: 'fitz',
                    text: entity.text,
                    line_number: 1
                });
            }
            
            return lineRects;
        }

        async detectEntities() {
            if (!this.currentPdfPath) return this.showError('PDFファイルを選択してください');
            this.showLoading(true, '個人情報を検出中...');

            try {
                const response = await fetch('/api/detect', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    // 手動追加分と新しい設定をサーバへ同期してから検出
                    body: JSON.stringify({
                        ...this.settings,
                        manual_entities: this.detectionResults.filter(e => e.manual),
                        exclude_words: this.settings.exclude_words || [],
                        additional_words: this.settings.additional_words || {}
                    })
                });
                const data = await response.json();
                if (!data.success) throw new Error(data.message);

                this.detectionResults = data.entities || [];
                this.renderEntityList();
                this.renderHighlights();
                this.updateSaveButtonState();   // 検出後に保存可
                
                const manualCount = data.manual_count || 0;
                const newCount = data.new_count || 0;
                const totalCount = data.count || this.detectionResults.length;
                
                let statusMessage = `検出完了: 新規${newCount}件`;
                if (manualCount > 0) {
                    statusMessage += `, 手動保護${manualCount}件`;
                }
                statusMessage += `, 合計${totalCount}件`;
                
                this.updateStatus(statusMessage);

            } catch (error) {
                console.error('Detection error:', error);
                this.showError(error.message || '個人情報の検出に失敗しました');
            } finally {
                this.showLoading(false);
            }
        }

        renderEntityList() {
            const listEl = this.elements.entityList;
            listEl.innerHTML = '';
            this.elements.resultCount.textContent = this.detectionResults.length;

            if (this.detectionResults.length === 0) {
                listEl.innerHTML = `<div class="list-group-item text-muted">検出結果がここに表示されます</div>`;
                return;
            }

            this.detectionResults.forEach((entity, index) => {
                const item = document.createElement('div');
                item.className = `list-group-item list-group-item-action d-flex align-items-start gap-2`;
                if (index === this.selectedEntityIndex) {
                    item.classList.add('active');
                }
                
                const isManual = entity.manual || false;
                const manualBadge = isManual ? '<span class="badge bg-success ms-1">手動</span>' : '<span class="badge bg-info ms-1">自動</span>';
                
                const contentDiv = document.createElement('div');
                contentDiv.className = 'flex-grow-1';
                contentDiv.style.cursor = 'pointer';
                
                // 詳細位置情報の表示
                const positionText = this.formatPositionInfo(entity);
                
                contentDiv.innerHTML = `
                    <div class="d-flex w-100 justify-content-between">
                        <h6 class="mb-1">${this.getEntityTypeJapanese(entity.entity_type)}${manualBadge}</h6>
                    </div>
                    <p class="mb-1 text-truncate">${entity.text}</p>
                    <small class="position-info">${positionText}</small>`;
                
                contentDiv.addEventListener('click', (e) => {
                    e.preventDefault();
                    this.selectEntity(index);
                });
                
                const deleteBtn = document.createElement('button');
                deleteBtn.className = 'btn btn-outline-danger btn-sm';
                deleteBtn.innerHTML = '<i class="fas fa-trash"></i>';
                deleteBtn.title = '削除';
                deleteBtn.addEventListener('click', async (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    await this.deleteEntity(index);
                });
                
                item.appendChild(deleteBtn);     // 先にボタン
                item.appendChild(contentDiv);    // 内容を右側へ
                listEl.appendChild(item);
            });
        }
        
        selectEntity(index) {
            this.selectedEntityIndex = index;
            const entity = this.detectionResults[index];
            
            // ページ番号の統一的な取得（renderHighlightsと同じロジック）
            const entityPage = (entity.page_num !== undefined) ? entity.page_num + 1 :
                               (entity.start_page !== undefined) ? entity.start_page :
                               (entity.page !== undefined) ? entity.page :
                               (entity.page_number !== undefined) ? entity.page_number : 1;
            
            console.log('selectEntity:', {
                index,
                entityPage,
                currentPage: this.currentPage,
                entity: entity
            });
            
            if (entityPage !== this.currentPage) {
                console.log('Changing page from', this.currentPage, 'to', entityPage);
                this.changePage(entityPage);
            } else {
                console.log('Same page, updating UI');
                this.renderEntityList();
                this.renderHighlights();
                this.scrollToEntityInPDF(index);
            }
        }

        changePage(newPage) {
            if (this.currentPdfDocument && newPage > 0 && newPage <= this.totalPages) {
                this.currentPage = newPage;
                this.renderPage(this.currentPage).then(() => {
                    // ページ変更後にエンティティが選択されている場合はスクロール
                    if (this.selectedEntityIndex >= 0) {
                        const entity = this.detectionResults[this.selectedEntityIndex];
                        const entityPage = entity && (entity.start_page || entity.page);
                        if (entity && entityPage === this.currentPage) {
                            this.scrollToEntityInPDF(this.selectedEntityIndex);
                        }
                    }
                });
            }
        }

        previousPage() { this.changePage(this.currentPage - 1); }
        nextPage() { this.changePage(this.currentPage + 1); }

        updatePageInfo() {
            this.elements.pageInfo.textContent = `${this.currentPage} / ${this.totalPages}`;
            this.elements.prevPageBtn.disabled = this.currentPage <= 1;
            this.elements.nextPageBtn.disabled = this.currentPage >= this.totalPages;
        }

        updateZoom(value) {
            this.zoomLevel = value;
            this.elements.zoomValue.textContent = `${value}%`;
            this.elements.zoomDisplay.textContent = `${value}%`;
            if (this.currentPdfDocument) {
                this.renderPage(this.currentPage);
            }
        }

        async generateAndDownloadPdf() {
            if (!this.currentPdfPath) return this.showError('PDFファイルが選択されていません');
            this.showLoading(true, 'マスキング適用中...');
            try {
                // クライアント側の最新レコード + 現在の設定も一緒に送る
                const maskingTextModeEl = document.getElementById('maskingTextMode');
                const masking_text_mode = maskingTextModeEl ? maskingTextModeEl.value : (this.settings.masking_text_mode || 'verbose');
                const payload = {
                    entities: this.detectionResults,
                    settings: {
                        masking_method: this.settings.masking_method,
                        masking_text_mode,
                        entities: this.settings.entities,
                        spacy_model: this.settings.spacy_model
                    }
                };
                const res = await fetch('/api/generate_pdf', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await res.json();
                if (!data.success) throw new Error(data.message);

                this.updateStatus('ダウンロード準備完了');
                const link = document.createElement('a');
                link.href = `/api/download_pdf/${data.filename}`;
                link.download = data.download_filename || 'masked_document.pdf';
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
            } catch (e) {
                this.showError(e.message || 'PDFの保存に失敗しました');
            } finally { 
                this.showLoading(false); 
            }
        }

        saveSettings() {
            this.settings.entities = Array.from(document.querySelectorAll('#settingsModal .form-check-input:checked')).map(cb => cb.value);
            this.settings.masking_method = document.getElementById('maskingMethod').value;
            this.settings.spacy_model = document.getElementById('spacyModel').value;
            const mtm = document.getElementById('maskingTextMode');
            this.settings.masking_text_mode = mtm ? mtm.value : 'verbose';
            
            // 重複除去設定を取得
            this.settings.deduplication_enabled = document.getElementById('deduplicationEnabled').checked;
            this.settings.deduplication_method = document.getElementById('deduplicationMethod').value;
            this.settings.deduplication_priority = document.getElementById('deduplicationPriority').value;
            this.settings.deduplication_overlap_mode = document.getElementById('deduplicationOverlapMode').value;

            // 除外単語と追加単語設定を取得
            this.settings.exclude_words = this.elements.excludeWords.value.split('\n').filter(word => word.trim());
            this.settings.additional_words = {
                PERSON: this.elements.additionalPersonWords.value.split(',').map(w => w.trim()).filter(w => w),
                LOCATION: this.elements.additionalLocationWords.value.split(',').map(w => w.trim()).filter(w => w),
                PHONE_NUMBER: this.elements.additionalPhoneWords.value.split(',').map(w => w.trim()).filter(w => w),
                DATE_TIME: this.elements.additionalDateWords.value.split(',').map(w => w.trim()).filter(w => w),
                INDIVIDUAL_NUMBER: this.elements.additionalIndividualWords.value.split(',').map(w => w.trim()).filter(w => w),
                YEAR: this.elements.additionalYearWords.value.split(',').map(w => w.trim()).filter(w => w),
                PROPER_NOUN: this.elements.additionalProperNounWords.value.split(',').map(w => w.trim()).filter(w => w)
            };
            
            console.log('重複除去設定を保存:', {
                enabled: this.settings.deduplication_enabled,
                method: this.settings.deduplication_method,
                priority: this.settings.deduplication_priority,
                overlap_mode: this.settings.deduplication_overlap_mode
            });
            
            this.updateStatus('設定を保存しました');
            const modal = bootstrap.Modal.getInstance(document.getElementById('settingsModal'));
            if(modal) modal.hide();
        }

        loadSettings() {
            this.settings.entities.forEach(entityValue => {
                const checkbox = document.querySelector(`#settingsModal input[value="${entityValue}"]`);
                if (checkbox) checkbox.checked = true;
            });
            document.getElementById('maskingMethod').value = this.settings.masking_method;
            document.getElementById('spacyModel').value = this.settings.spacy_model;
            const mtm = document.getElementById('maskingTextMode');
            if (mtm) mtm.value = this.settings.masking_text_mode || 'verbose';
            
            // 重複除去設定をロード
            document.getElementById('deduplicationEnabled').checked = this.settings.deduplication_enabled || false;
            document.getElementById('deduplicationMethod').value = this.settings.deduplication_method || 'overlap';
            document.getElementById('deduplicationPriority').value = this.settings.deduplication_priority || 'wider_range';
            document.getElementById('deduplicationOverlapMode').value = this.settings.deduplication_overlap_mode || 'partial_overlap';

            // 除外単語と追加単語設定をロード
            if (this.settings.exclude_words) {
                this.elements.excludeWords.value = this.settings.exclude_words.join('\n');
            }
            if (this.settings.additional_words) {
                this.elements.additionalPersonWords.value = (this.settings.additional_words.PERSON || []).join(', ');
                this.elements.additionalLocationWords.value = (this.settings.additional_words.LOCATION || []).join(', ');
                this.elements.additionalPhoneWords.value = (this.settings.additional_words.PHONE_NUMBER || []).join(', ');
                this.elements.additionalDateWords.value = (this.settings.additional_words.DATE_TIME || []).join(', ');
                this.elements.additionalIndividualWords.value = (this.settings.additional_words.INDIVIDUAL_NUMBER || []).join(', ');
                this.elements.additionalYearWords.value = (this.settings.additional_words.YEAR || []).join(', ');
                this.elements.additionalProperNounWords.value = (this.settings.additional_words.PROPER_NOUN || []).join(', ');
            }
            
            console.log('重複除去設定をロード:', {
                enabled: this.settings.deduplication_enabled,
                method: this.settings.deduplication_method,
                priority: this.settings.deduplication_priority,
                overlap_mode: this.settings.deduplication_overlap_mode
            });
        }

        exportSettings() {
            try {
                const settingsData = {
                    ...this.settings,
                    version: "1.0",
                    exported_at: new Date().toISOString()
                };
                
                const blob = new Blob([JSON.stringify(settingsData, null, 2)], { type: 'application/json' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `presidio_settings_${new Date().toISOString().slice(0, 10)}.json`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
                
                this.updateStatus('設定をエクスポートしました');
            } catch (error) {
                this.showError('設定のエクスポートに失敗しました');
            }
        }

        importSettings(event) {
            const file = event.target.files[0];
            if (!file) return;

            const reader = new FileReader();
            reader.onload = (e) => {
                try {
                    const settingsData = JSON.parse(e.target.result);
                    
                    // 設定をマージ
                    this.settings = { ...this.settings, ...settingsData };
                    
                    // UIに反映
                    this.loadSettings();
                    
                    this.updateStatus('設定をインポートしました');
                } catch (error) {
                    this.showError('設定ファイルの読み込みに失敗しました');
                }
            };
            reader.readAsText(file);
            
            // ファイル選択をリセット
            event.target.value = '';
        }

        getEntityTypeJapanese(entityType) {
            const mapping = { 
                "PERSON": "人名", 
                "LOCATION": "場所", 
                "PHONE_NUMBER": "電話番号", 
                "DATE_TIME": "日時", 
                "INDIVIDUAL_NUMBER": "個人番号",
                "YEAR": "年号",
                "PROPER_NOUN": "固有名詞",
                "CUSTOM": "カスタム" 
            };
            return mapping[entityType] || entityType;
        }

        formatCoordinateInfo(entity) {
            // 座標情報がある場合、PDF座標系(0,0-1.0,1.0)で開始座標のみ表示
            if (entity.coordinates && entity.coordinates.x0 !== undefined) {
                const x0 = (entity.coordinates.x0 / 1000).toFixed(3); // 座標を正規化
                const y0 = (entity.coordinates.y0 / 1000).toFixed(3);
                return `座標: (${x0},${y0})`;
            }
            return '';
        }

        formatPositionInfo(entity) {
            // ページ数のみを表示
            const page = entity.start_page || entity.page || 1;
            let positionInfo = `P${page}`;
            
            // 座標情報を追加
            const coordinateInfo = this.formatCoordinateInfo(entity);
            if (coordinateInfo) {
                positionInfo += ` ${coordinateInfo}`;
            }
            
            return positionInfo;
        }

        updateStatus(message, isError = false) {
            this.elements.statusMessage.textContent = message;
            this.elements.statusMessage.style.color = isError ? '#dc3545' : '#212529';
            this.elements.statusMessage.style.borderColor = isError ? '#dc3545' : '#17a2b8';
        }
        
        showError(message) {
            this.updateStatus(`エラー: ${message}`, true);
        }

        showLoading(show, message = '処理中...') {
            if (show) {
                this.elements.loadingOverlay.querySelector('p').textContent = message;
                this.elements.loadingOverlay.style.display = 'flex';
            } else {
                this.elements.loadingOverlay.style.display = 'none';
            }
        }

        hideContextMenu() {
            if (this.elements.contextMenu) {
                this.elements.contextMenu.style.display = 'none';
            }
            this.clearTextSelection();
        }
        
        handleSelection(e, isContextMenu = false) {
            try {
                const selection = window.getSelection();
                if (!selection || selection.rangeCount === 0) {
                    if (isContextMenu) this.hideContextMenu();
                    return;
                }

                const range = selection.getRangeAt(0);
                const selectedText = range.toString().trim();
                
                // テキストが空、または選択範囲がtextLayerの外なら何もしない
                if (!selectedText || !this.elements.textLayer.contains(range.commonAncestorContainer)) {
                    if (isContextMenu) this.hideContextMenu();
                    return;
                }

                const rect = range.getBoundingClientRect();
                // ★ 変更点：座標の基準をtextLayerに変更
                const referenceRect = this.elements.textLayer.getBoundingClientRect();
                
                const relativeX = rect.left - referenceRect.left;
                const relativeY = rect.top - referenceRect.top;

                this.currentSelection = {
                    text: selectedText,
                    range: range.cloneRange(),
                    rect: rect,
                    pdfX: relativeX,
                    pdfY: relativeY,
                    pageNumber: this.currentPage
                };

                if (isContextMenu) {
                    this.showContextMenu(e.clientX, e.clientY);
                } else {
                    this.handleModeBasedSelection();
                }

            } catch (error) {
                console.error('Selection handling error:', error);
                this.hideContextMenu();
            }
        }

        showContextMenu(x, y) {
            console.log('showContextMenu called with:', { x, y });
            console.log('contextMenu element:', this.elements.contextMenu);
            console.log('currentSelection:', this.currentSelection);
            
            if (!this.elements.contextMenu || !this.currentSelection) {
                console.log('Early return: missing contextMenu or currentSelection');
                return;
            }
            
            console.log('Setting context menu display to block');
            this.elements.contextMenu.style.display = 'block';
            
            const menuRect = this.elements.contextMenu.getBoundingClientRect();
            const windowWidth = window.innerWidth;
            const windowHeight = window.innerHeight;
            
            let menuX = x;
            let menuY = y;
            
            if (x + menuRect.width > windowWidth) {
                menuX = windowWidth - menuRect.width - 10;
            }
            if (y + menuRect.height > windowHeight) {
                menuY = windowHeight - menuRect.height - 10;
            }
            
            this.elements.contextMenu.style.left = menuX + 'px';
            this.elements.contextMenu.style.top = menuY + 'px';
            
            this.bindContextMenuEvents();
        }

        bindContextMenuEvents() {
            const menuItems = this.elements.contextMenu.querySelectorAll('.context-menu-item[data-entity-type]');
            
            menuItems.forEach(item => {
                const newItem = item.cloneNode(true);
                item.parentNode.replaceChild(newItem, item);
                
                newItem.addEventListener('click', async (e) => {
                    e.stopPropagation();
                    const entityType = newItem.getAttribute('data-entity-type');
                    this.hideContextMenu();
                    await this.addManualEntity(entityType);
                });
            });

            const cancelBtn = this.elements.contextMenu.querySelector('#cancelSelection');
            if (cancelBtn) {
                const newCancelBtn = cancelBtn.cloneNode(true);
                cancelBtn.parentNode.replaceChild(newCancelBtn, cancelBtn);
                
                newCancelBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    this.hideContextMenu();
                });
            }
        }

        async handleModeBasedSelection() {
            const selectedMode = document.querySelector('input[name="entityMode"]:checked');
            const entityType = selectedMode ? selectedMode.value : '';
            if (entityType === 'none' || entityType === '') {
                const t = this.currentSelection?.text?.trim();
                if (!t) { this.updateStatus('コピー対象の選択がありません'); return; }
                try { await navigator.clipboard.writeText(t); this.updateStatus(`「${t}」をコピーしました`); }
                catch { this.updateStatus('コピーに失敗しました'); }
                this.clearTextSelection();
                return;
            }
            this.addManualEntity(entityType);
        }

        async addManualEntity(entityType) {
            if (!this.currentSelection || !this.pdfPage || !this.viewport) return;

            const vp = this.viewport;
            const textLayerRect = this.elements.textLayer.getBoundingClientRect();
            const pageHeightPt = this.pdfPage.getViewport({ scale: 1 }).height;

            // 選択範囲（複数行対応）
            const range = this.currentSelection.range;
            const clientRects = Array.from(range.getClientRects());

            // 各行のクライアント矩形 → viewport相対 → PDFユーザ空間（左下原点）
            const lineRectsPdf = clientRects.map(r => {
                const vx0 = r.left   - textLayerRect.left;
                const vy0 = r.top    - textLayerRect.top;
                const vx1 = r.right  - textLayerRect.left;
                const vy1 = r.bottom - textLayerRect.top;
                return this.viewportRectToPdfRect(vp, vx0, vy0, vx1, vy1);
            });

            // 全体のバウンディング（PDFユーザ空間）
            const pdfRect =
              lineRectsPdf.length
                ? [
                    Math.min(...lineRectsPdf.map(r => r[0])),
                    Math.min(...lineRectsPdf.map(r => r[1])),
                    Math.max(...lineRectsPdf.map(r => r[2])),
                    Math.max(...lineRectsPdf.map(r => r[3]))
                  ]
                : null;

            // Fitz系（左上原点）も保持（保存・PDF生成用）
            const rectFitz = pdfRect ? this.pdfjsRectToFitzRect(pdfRect, pageHeightPt) : null;

            const newEntity = {
                entity_type: entityType,
                text: this.currentSelection.text,
                manual: true,
                page: this.currentPage,
                page_num: this.currentPage - 1,
                rect_pdf: rectFitz,          // 注意：中身はFitz（後方互換のためキー名は据え置き）
                rect_norm: this.normRectFromPdfRect(
                    this.pdfPage.getViewport({ scale: 1 }).width,
                    this.pdfPage.getViewport({ scale: 1 }).height,
                    pdfRect || [0,0,0,0]
                ),
                coordinates: rectFitz
                  ? { x0: rectFitz[0], y0: rectFitz[1], x1: rectFitz[2], y1: rectFitz[3] }
                  : undefined,
                // 各行の"タイトな"矩形（PDFユーザ空間, 左下原点）＋座標系フラグ
                line_rects: lineRectsPdf.map((r, i) => ({
                    rect: { x0: r[0], y0: r[1], x1: r[2], y1: r[3] },
                    coord_space: 'pdf',
                    line_number: i + 1,
                    page_num: this.currentPage - 1
                }))
            };

            // 楽観的UI更新（サーバ失敗でも表示は維持）
            const idx = this.detectionResults.length;
            this.detectionResults.push({ ...newEntity, _unsynced: true });
            this.updateSaveButtonState(); // ★追加：ボタンの状態を更新
            this.renderEntityList(); this.renderHighlights(); this.updateResultCount();
            this.updateStatus(`手動追加を反映: ${this.getEntityTypeLabel(entityType)} "${newEntity.text}"（保存中）`);

            fetch('/api/highlights/add', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(newEntity)
            })
            .then(async (res) => {
                const ct = res.headers.get('content-type') || '';
                if (!ct.includes('application/json')) throw new Error(await res.text());
                return res.json();
            })
            .then(data => {
                if (data.success && data.entity) {
                    this.detectionResults[idx] = data.entity;
                    this.updateSaveButtonState(); // 念のため同期後も更新
                    this.renderEntityList(); this.renderHighlights(); this.updateResultCount();
                    this.updateStatus('手動追加完了');
                } else if (data.message) {
                    this.updateStatus(`手動追加は表示済み（サーバ保存未完了）: ${data.message}`, false);
                }
            })
            .catch(err => console.error('Add highlight error:', err));
        }

        // 追加：保存ボタンの活性/非活性を一元管理
        updateSaveButtonState() {
            const hasPdf = !!this.currentPdfPath;
            const hasEntities = Array.isArray(this.detectionResults) && this.detectionResults.length > 0;
            if (this.elements && this.elements.saveBtn) {
                this.elements.saveBtn.disabled = !(hasPdf && hasEntities);
            }
        }

        async deleteEntity(index) {
        }

        getEntityTypeLabel(entityType) {
            const labels = {
                'PERSON': '人名',
                'LOCATION': '場所',
                'PHONE_NUMBER': '電話番号',
                'DATE_TIME': '日時',
                'CUSTOM': 'その他'
            };
            return labels[entityType] || entityType;
        }

        addToSelectionHistory(selectionData) {
            // 重複チェック（同じテキストと座標の場合は追加しない）
            const isDuplicate = this.selectionHistory.some(item => 
                item.text === selectionData.text &&
                Math.abs(item.pdfX - selectionData.pdfX) < 5 &&
                Math.abs(item.pdfY - selectionData.pdfY) < 5 &&
                item.pageNumber === selectionData.pageNumber
            );
            
            if (!isDuplicate) {
                this.selectionHistory.unshift(selectionData);
                
                // 最大数を超えた場合は古いものを削除
                if (this.selectionHistory.length > this.maxSelectionHistory) {
                    this.selectionHistory = this.selectionHistory.slice(0, this.maxSelectionHistory);
                }
                
                console.log(`Selection history updated: ${this.selectionHistory.length} items`);
            }
        }
        
        getLatestValidSelection() {
            // 最新の有効な選択を取得（過去5秒以内のもの）
            const fiveSecondsAgo = Date.now() - 5000;
            
            for (let selection of this.selectionHistory) {
                if (selection.timestamp > fiveSecondsAgo && 
                    selection.pageNumber === this.currentPage &&
                    selection.text && selection.text.length > 0) {
                    console.log(`Found valid selection from history: "${selection.text}"`);
                    return selection;
                }
            }
            
            console.log('No valid selection found in history');
            return null;
        }

        clearTextSelection() {
            if (window.getSelection) {
                window.getSelection().removeAllRanges();
            }
            this.currentSelection = null;
        }

        updateResultCount() {
            if (this.elements.resultCount) {
                this.elements.resultCount.textContent = this.detectionResults.length;
            }
        }

        scrollToEntityInList(index) {
            const listEl = this.elements.entityList;
            const items = listEl.querySelectorAll('.list-group-item');
            
            if (index >= 0 && index < items.length) {
                const item = items[index];
                item.scrollIntoView({
                    behavior: 'smooth',
                    block: 'center'
                });
            }
        }

        scrollToEntityInPDF(index) {
            const entity = this.detectionResults[index];
            
            // ページ番号の統一的な取得
            const entityPage = entity ? ((entity.page_num !== undefined) ? entity.page_num + 1 :
                                        (entity.start_page !== undefined) ? entity.start_page :
                                        (entity.page !== undefined) ? entity.page :
                                        (entity.page_number !== undefined) ? entity.page_number : 1) : null;
            
            console.log('scrollToEntityInPDF:', {
                index,
                hasEntity: !!entity,
                hasCoordinates: !!(entity && entity.coordinates),
                entityPage,
                currentPage: this.currentPage
            });
            
            if (!entity || !entity.coordinates || entityPage !== this.currentPage) {
                console.log('Early return from scrollToEntityInPDF');
                return;
            }

            // ハイライト要素を取得
            const highlightEl = this.elements.highlightOverlay.querySelector(`[data-index="${index}"]`);
            if (!highlightEl) {
                return;
            }

            // PDFビューアコンテナを取得
            const pdfViewer = this.elements.pdfViewer;
            const pdfContainer = this.elements.pdfCanvasContainer;
            
            // ハイライト要素の位置を取得
            const highlightRect = highlightEl.getBoundingClientRect();
            const viewerRect = pdfViewer.getBoundingClientRect();
            
            // ハイライトがビューアの表示範囲内にあるかチェック
            const isVisible = (
                highlightRect.top >= viewerRect.top &&
                highlightRect.bottom <= viewerRect.bottom &&
                highlightRect.left >= viewerRect.left &&
                highlightRect.right <= viewerRect.right
            );
            
            // 表示範囲外の場合はスクロール
            if (!isVisible) {
                // ハイライト要素がビューアの中央に来るようにスクロール
                const targetTop = highlightRect.top - viewerRect.top + pdfViewer.scrollTop - (viewerRect.height / 2) + (highlightRect.height / 2);
                const targetLeft = highlightRect.left - viewerRect.left + pdfViewer.scrollLeft - (viewerRect.width / 2) + (highlightRect.width / 2);
                
                pdfViewer.scrollTo({
                    top: Math.max(0, targetTop),
                    left: Math.max(0, targetLeft),
                    behavior: 'smooth'
                });
            }
        }
        
        async deleteEntity(index) {
            try {
                if (index < 0 || index >= this.detectionResults.length) {
                    this.showError('無効なエンティティです');
                    return;
                }
                
                const entity = this.detectionResults[index];
                
                this.showLoading(true, 'エンティティを削除中...');
                
                const response = await fetch(`/api/delete_entity/${index}`, {
                    method: 'DELETE'
                });
                
                const data = await response.json();
                if (!data.success) throw new Error(data.message);
                
                this.detectionResults.splice(index, 1);
                
                if (this.selectedEntityIndex === index) {
                    this.selectedEntityIndex = -1;
                } else if (this.selectedEntityIndex > index) {
                    this.selectedEntityIndex--;
                }
                
                this.renderEntityList();
                this.renderHighlights();
                this.updateResultCount();
                this.updateStatus(`削除完了: ${data.deleted_entity.text}`);
                this.updateSaveButtonState();   // 件数変化に追従
                
            } catch (error) {
                console.error('Delete entity error:', error);
                this.showError(error.message || 'エンティティの削除に失敗しました');
            } finally {
                this.showLoading(false);
            }
        }
    }

    window.app = new PresidioPDFWebApp();
    };

    // Try to initialize immediately, or wait for library to load
    if (typeof pdfjsLib !== 'undefined') {
        initializePDFViewer();
    } else {
        console.log('PDF.js not yet loaded, waiting...');
        // Wait a bit for the script to load, then try again
        setTimeout(() => {
            initializePDFViewer();
        }, 1000);
    }
});