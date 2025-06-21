/**
 * PDF個人情報マスキングツール - Webアプリケーション
 * JavaScript フロントエンド（PDF.js統合版）
 */

document.addEventListener('DOMContentLoaded', () => {
    // PDF.jsのグローバルワーカーを設定
    if (typeof pdfjsLib === 'undefined') {
        console.error('PDF.js library not found!');
        return;
    }
    pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';

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
            // isMouseDownを削除し、selectionTimeoutで選択完了を管理
            this.selectionTimeout = null;

            this.settings = {
                entities: ["PERSON", "LOCATION", "PHONE_NUMBER", "DATE_TIME"],
                threshold: 0.5,
                masking_method: "highlight"
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
                zoomSlider: document.getElementById('zoomSlider'),
                zoomValue: document.getElementById('zoomValue'),
                showHighlights: document.getElementById('showHighlights'),
                zoomDisplay: document.getElementById('zoomDisplay'),
                entityList: document.getElementById('entityList'),
                resultCount: document.getElementById('resultCount'),
                saveBtn: document.getElementById('saveBtn'),
                statusMessage: document.getElementById('statusMessage'),
                loadingOverlay: document.getElementById('loadingOverlay'),
                pdfViewer: document.getElementById('pdfViewer'),
                pdfPlaceholder: document.getElementById('pdfPlaceholder'),
                pdfCanvasContainer: document.getElementById('pdfCanvasContainer'),
                pdfCanvas: document.getElementById('pdfCanvas'),
                textLayer: document.getElementById('textLayer'),
                highlightOverlay: document.getElementById('highlightOverlay'),
                thresholdSlider: document.getElementById('thresholdSlider'),
                thresholdValue: document.getElementById('thresholdValue'),
                saveSettingsBtn: document.getElementById('saveSettingsBtn'),
                contextMenu: document.getElementById('contextMenu'),
                cancelSelection: document.getElementById('cancelSelection')
            };
            this.pdfContext = this.elements.pdfCanvas.getContext('2d');
        }

        // =================================================================
        // ==  イベント処理の根本的な修正  ==
        // =================================================================
        bindEvents() {
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
            this.elements.thresholdSlider.addEventListener('input', (e) => { this.elements.thresholdValue.textContent = e.target.value; });
            this.elements.saveSettingsBtn.addEventListener('click', () => this.saveSettings());

            // --- 新しいイベントリスナー ---
            // 右クリックでコンテキストメニューを表示
            this.elements.pdfViewer.addEventListener('contextmenu', (e) => {
                e.preventDefault();
                this.handleSelection(e, true); // isContextMenu = true
            });
            
            // テキスト選択が変化したときの処理を主軸にする
            document.addEventListener('selectionchange', () => {
                const selection = window.getSelection();
                
                // 選択範囲があり、それがPDFビューア内である場合のみ処理
                if (selection && selection.rangeCount > 0 && selection.toString().trim().length > 0) {
                    const range = selection.getRangeAt(0);
                    if (this.elements.pdfViewer.contains(range.commonAncestorContainer)) {
                        
                        // ドラッグ操作中はタイマーをリセットし続ける
                        clearTimeout(this.selectionTimeout);
                        
                        // ドラッグが止まってから300ms後に選択処理を実行
                        this.selectionTimeout = setTimeout(() => {
                            // isContextMenu = false として選択処理を呼び出す
                            this.handleSelection(null, false);
                        }, 300);
                    }
                }
            });
            
            // クリックイベントでコンテキストメニューを閉じたり、不要な選択処理をキャンセル
            document.addEventListener('click', (e) => {
                if (this.elements.contextMenu && !this.elements.contextMenu.contains(e.target)) {
                    this.hideContextMenu();
                }
                const selection = window.getSelection();
                if (selection && selection.isCollapsed) {
                     clearTimeout(this.selectionTimeout);
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
            if (!file || file.type !== 'application/pdf') {
                this.showError('PDFファイルを選択してください');
                return;
            }
            this.showLoading(true, 'PDFをアップロード中...');
            
            try {
                const formData = new FormData();
                formData.append('pdf_file', file);
                const response = await fetch('/api/upload', { method: 'POST', body: formData });
                const data = await response.json();

                if (!data.success) throw new Error(data.message);

                this.currentPdfPath = data.filename;
                this.elements.selectedFileName.textContent = file.name;
                this.updateStatus('PDFを読み込み中...');
                
                const arrayBuffer = await file.arrayBuffer();
                this.currentPdfDocument = await pdfjsLib.getDocument(arrayBuffer).promise;
                this.totalPages = this.currentPdfDocument.numPages;
                this.currentPage = 1;
                this.elements.detectBtn.disabled = false;
                
                await this.renderPage(this.currentPage);
                this.updateStatus(`PDF読み込み完了: ${file.name}`);

            } catch (error) {
                console.error('File handling error:', error);
                this.showError(error.message || 'ファイルの処理中にエラーが発生しました');
            } finally {
                this.showLoading(false);
            }
        }

        async renderPage(pageNum) {
            if (!this.currentPdfDocument || pageNum < 1 || pageNum > this.totalPages) return;
            this.showLoading(true, 'ページを描画中...');
            try {
                const page = await this.currentPdfDocument.getPage(pageNum);
                const scale = this.zoomLevel / 100;
                this.viewport = page.getViewport({ scale });

                const canvas = this.elements.pdfCanvas;
                const container = this.elements.pdfCanvasContainer;

                container.style.setProperty('--scale-factor', this.viewport.scale);
                canvas.width = this.viewport.width;
                canvas.height = this.viewport.height;

                const renderContext = {
                    canvasContext: this.pdfContext,
                    viewport: this.viewport
                };
                await page.render(renderContext).promise;

                await this.renderTextLayer(page);
                this.renderHighlights();

                this.updatePageInfo();
                this.elements.pdfPlaceholder.style.display = 'none';
                this.elements.pdfCanvasContainer.style.display = 'block';

            } catch (error) {
                console.error(`Error rendering page ${pageNum}:`, error);
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

        renderHighlights() {
            const container = this.elements.highlightOverlay;
            container.innerHTML = '';
            container.style.width = `${this.viewport.width}px`;
            container.style.height = `${this.viewport.height}px`;

            if (!this.elements.showHighlights.checked || !this.viewport) return;

            const pageEntities = this.detectionResults.filter(e => e.page === this.currentPage);
            pageEntities.forEach((entity, localIndex) => {
                const globalIndex = this.detectionResults.indexOf(entity);
                const el = this.createHighlightElement(entity, globalIndex);
                if (el) container.appendChild(el);
            });
        }
        
        createHighlightElement(entity, index) {
            if (!entity.coordinates) return null;

            const highlightEl = document.createElement('div');
            highlightEl.className = 'highlight-rect';
            highlightEl.classList.add(entity.entity_type.toLowerCase().replace(/_/g, '-'));

            if (index === this.selectedEntityIndex) {
                highlightEl.classList.add('selected');
            }

            const pageHeight = this.viewport.viewBox[3];
            const pdfRect = [
                entity.coordinates.x0,
                pageHeight - entity.coordinates.y1,
                entity.coordinates.x1,
                pageHeight - entity.coordinates.y0
            ];

            const viewportRect = this.viewport.convertToViewportRectangle(pdfRect);
            
            const left = Math.min(viewportRect[0], viewportRect[2]);
            const top = Math.min(viewportRect[1], viewportRect[3]);
            const right = Math.max(viewportRect[0], viewportRect[2]);
            const bottom = Math.max(viewportRect[1], viewportRect[3]);
            
            const width = right - left;
            const height = bottom - top;
            
            const minHeight = 12;
            const adjustedHeight = Math.max(height, minHeight);

            highlightEl.style.left = `${left}px`;
            highlightEl.style.top = `${top}px`;
            highlightEl.style.width = `${width}px`;
            highlightEl.style.height = `${adjustedHeight}px`;
            highlightEl.dataset.index = index;
            
            highlightEl.addEventListener('click', (e) => {
                e.stopPropagation();
                this.selectEntity(index);
            });

            return highlightEl;
        }

        async detectEntities() {
            if (!this.currentPdfPath) return this.showError('PDFファイルを選択してください');
            this.showLoading(true, '個人情報を検出中...');

            try {
                const response = await fetch('/api/detect', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(this.settings)
                });
                const data = await response.json();
                if (!data.success) throw new Error(data.message);

                this.detectionResults = data.results || [];
                this.renderEntityList();
                this.renderHighlights();
                this.elements.saveBtn.disabled = false;
                
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
                item.className = `list-group-item list-group-item-action d-flex justify-content-between align-items-start`;
                if (index === this.selectedEntityIndex) {
                    item.classList.add('active');
                }
                
                const confidence = (entity.confidence * 100).toFixed(0);
                const isManual = entity.manual || false;
                const manualBadge = isManual ? '<span class="badge bg-success ms-1">手動</span>' : '<span class="badge bg-info ms-1">自動</span>';
                
                const contentDiv = document.createElement('div');
                contentDiv.className = 'flex-grow-1';
                contentDiv.style.cursor = 'pointer';
                contentDiv.innerHTML = `
                    <div class="d-flex w-100 justify-content-between">
                        <h6 class="mb-1">${this.getEntityTypeJapanese(entity.entity_type)}${manualBadge}</h6>
                        <small>信頼度: ${confidence}%</small>
                    </div>
                    <p class="mb-1 text-truncate">${entity.text}</p>
                    <small>ページ: ${entity.page}</small>`;
                
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
                
                item.appendChild(contentDiv);
                item.appendChild(deleteBtn);
                listEl.appendChild(item);
            });
        }
        
        selectEntity(index) {
            this.selectedEntityIndex = index;
            const entity = this.detectionResults[index];
            if (entity.page !== this.currentPage) {
                this.changePage(entity.page);
            } else {
                this.renderEntityList();
                this.renderHighlights();
            }
        }

        changePage(newPage) {
            if (this.currentPdfDocument && newPage > 0 && newPage <= this.totalPages) {
                this.currentPage = newPage;
                this.renderPage(this.currentPage);
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
                const response = await fetch('/api/generate_pdf', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ entities: this.detectionResults })
                });
                const data = await response.json();
                if (!data.success) throw new Error(data.message);

                this.updateStatus('ダウンロード準備完了');
                const link = document.createElement('a');
                link.href = `/api/download_pdf/${data.filename}`;
                link.download = data.download_filename || 'masked_document.pdf';
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);

            } catch (error) {
                console.error('PDF generation/download error:', error);
                this.showError(error.message || 'PDFの保存に失敗しました');
            } finally {
                this.showLoading(false);
            }
        }

        saveSettings() {
            this.settings.entities = Array.from(document.querySelectorAll('#settingsModal .form-check-input:checked')).map(cb => cb.value);
            this.settings.threshold = parseFloat(this.elements.thresholdSlider.value);
            this.settings.masking_method = document.getElementById('maskingMethod').value;
            this.updateStatus('設定を保存しました');
            const modal = bootstrap.Modal.getInstance(document.getElementById('settingsModal'));
            if(modal) modal.hide();
        }

        loadSettings() {
            this.settings.entities.forEach(entityValue => {
                const checkbox = document.querySelector(`#settingsModal input[value="${entityValue}"]`);
                if (checkbox) checkbox.checked = true;
            });
            this.elements.thresholdSlider.value = this.settings.threshold;
            this.elements.thresholdValue.textContent = this.settings.threshold;
            document.getElementById('maskingMethod').value = this.settings.masking_method;
        }

        getEntityTypeJapanese(entityType) {
            const mapping = { "PERSON": "人名", "LOCATION": "場所", "PHONE_NUMBER": "電話番号", "DATE_TIME": "日時", "CUSTOM": "カスタム" };
            return mapping[entityType] || entityType;
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
                
                if (!selectedText || selectedText.length < 2) {
                    if (isContextMenu) this.hideContextMenu();
                    return;
                }

                const pdfViewer = this.elements.pdfViewer;
                if (!pdfViewer || !pdfViewer.contains(range.commonAncestorContainer)) {
                    return;
                }

                const rect = range.getBoundingClientRect();
                const pdfViewerRect = this.elements.pdfViewer.getBoundingClientRect();
                
                const relativeX = rect.left - pdfViewerRect.left;
                const relativeY = rect.top - pdfViewerRect.top;

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
            if (!this.elements.contextMenu || !this.currentSelection) return;
            
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

        handleModeBasedSelection() {
            const selectedMode = document.querySelector('input[name="entityMode"]:checked');
            if (!selectedMode || !selectedMode.value) {
                this.updateStatus('手動追加するには、まずエンティティタイプ（人名など）を選択してください。', false);
                this.clearTextSelection();
                return;
            }

            const entityType = selectedMode.value;
            this.addManualEntity(entityType);
        }

        async addManualEntity(entityType) {
            if (!this.currentSelection || !this.currentSelection.text.trim()) {
                this.showError('テキストが選択されていません。');
                return;
            }
            if (!this.viewport) {
                this.showError('PDFが正しく読み込まれていません。');
                return;
            }

            try {
                const viewportRect = [
                    this.currentSelection.rect.left - this.elements.pdfCanvasContainer.getBoundingClientRect().left,
                    this.currentSelection.rect.top - this.elements.pdfCanvasContainer.getBoundingClientRect().top,
                    this.currentSelection.rect.right - this.elements.pdfCanvasContainer.getBoundingClientRect().left,
                    this.currentSelection.rect.bottom - this.elements.pdfCanvasContainer.getBoundingClientRect().top
                ];
                
                const pdfPoint1 = this.viewport.convertToPdfPoint(viewportRect[0], viewportRect[1]);
                const pdfPoint2 = this.viewport.convertToPdfPoint(viewportRect[2], viewportRect[3]);
                
                const pageHeight = this.viewport.viewBox[3];
                
                const newEntity = {
                    entity_type: entityType,
                    text: this.currentSelection.text,
                    start: 0,
                    end: this.currentSelection.text.length,
                    confidence: 1.0,
                    page: this.currentPage,
                    coordinates: {
                        x0: Math.min(pdfPoint1[0], pdfPoint2[0]),
                        y0: pageHeight - Math.max(pdfPoint1[1], pdfPoint2[1]),
                        x1: Math.max(pdfPoint1[0], pdfPoint2[0]),
                        y1: pageHeight - Math.min(pdfPoint1[1], pdfPoint2[1])
                    },
                    manual: true
                };

                const response = await fetch('/api/highlights/add', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(newEntity),
                });

                const data = await response.json();
                if (!data.success) throw new Error(data.message);

                this.detectionResults.push(data.entity);
                this.renderEntityList();
                this.renderHighlights();
                this.updateResultCount();
                this.updateStatus(`手動追加: ${this.getEntityTypeLabel(entityType)} "${this.currentSelection.text}"`);

            } catch (error) {
                console.error('Error adding manual entity:', error);
                this.showError('手動追加中にエラーが発生しました');
            } finally {
                this.clearTextSelection();
            }
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
        
        async deleteEntity(index) {
            try {
                if (index < 0 || index >= this.detectionResults.length) {
                    this.showError('無効なエンティティです');
                    return;
                }
                
                const entity = this.detectionResults[index];
                const confirmMessage = `以下のエンティティを削除しますか？\n\nタイプ: ${this.getEntityTypeJapanese(entity.entity_type)}\nテキスト: ${entity.text}\nページ: ${entity.page}`;
                
                if (!confirm(confirmMessage)) return;
                
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
                
            } catch (error) {
                console.error('Delete entity error:', error);
                this.showError(error.message || 'エンティティの削除に失敗しました');
            } finally {
                this.showLoading(false);
            }
        }
    }

    new PresidioPDFWebApp();
});