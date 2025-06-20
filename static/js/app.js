/**
 * PDF個人情報マスキングツール - Webアプリケーション
 * JavaScript フロントエンド（インタラクティブハイライト編集機能付き）
 */

class PresidioPDFWebApp {
    constructor() {
        this.currentPdf = null;
        this.currentPage = 0;
        this.totalPages = 0;
        this.zoomLevel = 100; // パーセンテージで管理
        this.detectionResults = [];
        this.selectedEntityIndex = -1;
        this.selectedHighlight = null;
        this.editMode = false;
        this.adjustmentQueue = [];
        this.adjustmentTimer = null;
        this.adjustmentDelay = 800; // 800ms のデレイ
        this.savedScrollPosition = { top: 0, left: 0 };
        this.settings = {
            entities: ["PERSON", "LOCATION", "PHONE_NUMBER", "DATE_TIME"],
            threshold: 0.5,
            masking_method: "highlight"
        };
        
        this.initializeElements();
        this.bindEvents();
        this.loadSettings();
        this.setupZoomSlider();
    }
    
    initializeElements() {
        // DOM要素の参照を取得（存在しない要素は null のまま）
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

            deleteBtn: document.getElementById('deleteBtn'),
            saveBtn: document.getElementById('saveBtn'),
            downloadBtn: document.getElementById('downloadBtn'),
            statusMessage: document.getElementById('statusMessage'),
            loadingOverlay: document.getElementById('loadingOverlay'),
            pdfViewer: document.getElementById('pdfViewer'),
            // 設定モーダル要素
            thresholdSlider: document.getElementById('thresholdSlider'),
            thresholdValue: document.getElementById('thresholdValue'),
            saveSettingsBtn: document.getElementById('saveSettingsBtn'),
            // ハイライト編集要素
            highlightEditPanel: document.getElementById('highlightEditPanel'),
            selectedHighlightText: document.getElementById('selectedHighlightText'),
            selectedHighlightType: document.getElementById('selectedHighlightType'),
            selectedHighlightConfidence: document.getElementById('selectedHighlightConfidence'),
            selectedHighlightPage: document.getElementById('selectedHighlightPage'),
            selectedHighlightPosition: document.getElementById('selectedHighlightPosition'),
            extendLeftBtn: document.getElementById('extendLeftBtn'),
            extendRightBtn: document.getElementById('extendRightBtn'),
            shrinkLeftBtn: document.getElementById('shrinkLeftBtn'),
            shrinkRightBtn: document.getElementById('shrinkRightBtn'),
            clearSelectionBtn: document.getElementById('clearSelectionBtn'),
            deleteHighlightBtn: document.getElementById('deleteHighlightBtn')
        };
        
        // 必須要素の存在チェック
        const requiredElements = ['uploadArea', 'pdfFileInput', 'detectBtn', 'pdfViewer', 'entityList'];
        const missingElements = requiredElements.filter(id => !this.elements[id]);
        
        if (missingElements.length > 0) {
            console.error('Missing required elements:', missingElements);
        }
    }
    
    bindEvents() {
        // ファイルアップロード関連
        this.elements.uploadArea.addEventListener('click', () => {
            this.elements.pdfFileInput.click();
        });
        
        this.elements.pdfFileInput.addEventListener('change', (e) => {
            this.handleFileSelect(e.target.files[0]);
        });
        
        // ドラッグ&ドロップ
        this.elements.uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            this.elements.uploadArea.classList.add('dragover');
        });
        
        this.elements.uploadArea.addEventListener('dragleave', () => {
            this.elements.uploadArea.classList.remove('dragover');
        });
        
        this.elements.uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            this.elements.uploadArea.classList.remove('dragover');
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                this.handleFileSelect(files[0]);
            }
        });
        
        // ボタンイベント
        this.elements.detectBtn.addEventListener('click', () => {
            this.detectEntities();
        });
        
        this.elements.prevPageBtn.addEventListener('click', () => {
            this.previousPage();
        });
        
        this.elements.nextPageBtn.addEventListener('click', () => {
            this.nextPage();
        });
        
        this.elements.zoomSlider.addEventListener('input', (e) => {
            this.updateZoom(parseInt(e.target.value));
        });
        
        this.elements.showHighlights.addEventListener('change', () => {
            this.loadPageImage();
        });
        
        // PDFビューアのクリックイベント（ハイライト選択用）
        this.elements.pdfViewer.addEventListener('click', (e) => {
            this.handlePdfClick(e);
        });
        
        // キーボードショートカット
        document.addEventListener('keydown', (e) => {
            this.handleKeyDown(e);
        });
        
        // エンティティ操作 (delete button removed from entity details)
        
        this.elements.saveBtn.addEventListener('click', () => {
            this.savePdf();
        });
        
        // 設定モーダル
        this.elements.thresholdSlider.addEventListener('input', (e) => {
            this.elements.thresholdValue.textContent = e.target.value;
        });
        
        this.elements.saveSettingsBtn.addEventListener('click', () => {
            this.saveSettings();
        });
        
        // ハイライト編集ボタン
        if (this.elements.extendLeftBtn) {
            this.elements.extendLeftBtn.addEventListener('click', () => {
                this.adjustHighlight('extend_left');
            });
        }
        
        if (this.elements.extendRightBtn) {
            this.elements.extendRightBtn.addEventListener('click', () => {
                this.adjustHighlight('extend_right');
            });
        }
        
        if (this.elements.shrinkLeftBtn) {
            this.elements.shrinkLeftBtn.addEventListener('click', () => {
                this.adjustHighlight('shrink_left');
            });
        }
        
        if (this.elements.shrinkRightBtn) {
            this.elements.shrinkRightBtn.addEventListener('click', () => {
                this.adjustHighlight('shrink_right');
            });
        }
        
        if (this.elements.clearSelectionBtn) {
            this.elements.clearSelectionBtn.addEventListener('click', () => {
                this.clearSelection();
            });
        }
        
        if (this.elements.deleteHighlightBtn) {
            this.elements.deleteHighlightBtn.addEventListener('click', () => {
                this.deleteHighlight();
            });
        }
    }
    
    handleFileSelect(file) {
        if (!file) return;
        
        if (file.type !== 'application/pdf') {
            this.showError('PDFファイルを選択してください');
            return;
        }
        
        const formData = new FormData();
        formData.append('pdf_file', file);
        
        this.showLoading(true);
        this.updateStatus('PDFファイルをアップロード中...');
        
        fetch('/api/upload', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            this.showLoading(false);
            
            if (data.success) {
                this.currentPdf = data.filename;
                this.totalPages = data.total_pages;
                this.currentPage = 0;
                this.detectionResults = [];
                this.selectedEntityIndex = -1;
                
                this.elements.selectedFileName.textContent = file.name;
                if (this.elements.detectBtn) {
                    this.elements.detectBtn.disabled = false;
                }
                this.updatePageInfo();
                
                // 少し遅延してからPDFページ画像を読み込み（DOM更新の後）
                console.log('PDF uploaded, loading first page...');
                setTimeout(() => {
                    this.loadPageImage();
                }, 100);
                
                this.renderEntityList();
                this.updateStatus('PDFファイルのアップロードが完了しました');
            } else {
                this.showError(data.message);
            }
        })
        .catch(error => {
            this.showLoading(false);
            console.error('アップロードエラー:', error);
            this.showError('アップロードに失敗しました');
        });
    }
    
    detectEntities() {
        if (!this.currentPdf) {
            this.showError('PDFファイルを選択してください');
            return;
        }
        
        this.showLoading(true);
        this.updateStatus('個人情報を検出中...');
        
        fetch('/api/detect', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(this.settings)
        })
        .then(response => response.json())
        .then(data => {
            this.showLoading(false);
            
            if (data.success) {
                this.detectionResults = data.results;
                this.renderEntityList();
                this.loadPageImage();
                
                // PDFを保存ボタンを有効にする
                if (this.elements.saveBtn) {
                    this.elements.saveBtn.disabled = false;
                }
                
                this.updateStatus(`検出完了: ${data.results.length}件の個人情報が見つかりました`);
            } else {
                this.showError(data.message);
            }
        })
        .catch(error => {
            this.showLoading(false);
            console.error('検出エラー:', error);
            this.showError('個人情報の検出に失敗しました');
        });
    }
    
    loadPageImage() {
        if (!this.currentPdf) {
            console.log('loadPageImage: currentPdf is null');
            return;
        }
        
        const showHighlights = this.elements.showHighlights ? this.elements.showHighlights.checked : false;
        const apiUrl = `/api/page/${this.currentPage}?zoom=${this.zoomLevel / 100}&highlights=${showHighlights}`;
        
        console.log('loadPageImage:', {
            currentPdf: this.currentPdf,
            currentPage: this.currentPage,
            zoomLevel: this.zoomLevel,
            zoomRatio: this.zoomLevel / 100,
            showHighlights: showHighlights,
            apiUrl: apiUrl
        });
        
        this.updateStatus('ページ画像を読み込み中...');
        
        fetch(apiUrl)
        .then(response => {
            console.log('Page image response status:', response.status);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('Page image response data:', data);
            
            if (data.success && data.image) {
                const img = document.createElement('img');
                img.src = 'data:image/png;base64,' + data.image;
                
                // ズーム100%以下の場合は制約、それ以上では自由に拡大
                if (this.zoomLevel <= 100) {
                    img.style.maxWidth = '100%';
                    img.style.width = 'auto';
                } else {
                    img.style.maxWidth = 'none';
                    img.style.width = 'auto';
                }
                
                img.style.height = 'auto';
                img.style.display = 'block';
                img.style.margin = '0 auto';
                
                // 既存の画像を削除して新しい画像を追加
                if (this.elements.pdfViewer) {
                    this.elements.pdfViewer.innerHTML = '';
                    this.elements.pdfViewer.appendChild(img);
                    
                    // 画像の位置調整
                    img.onload = () => {
                        console.log('Image loaded:', {
                            naturalWidth: img.naturalWidth,
                            naturalHeight: img.naturalHeight,
                            clientWidth: img.clientWidth,
                            clientHeight: img.clientHeight,
                            zoomLevel: this.zoomLevel
                        });
                        this.adjustImagePosition(img);
                        this.updateStatus('ページ画像を読み込みました');
                    };
                    
                    img.onerror = () => {
                        console.error('Image load error');
                        this.showError('画像の表示に失敗しました');
                    };
                } else {
                    console.error('pdfViewer element not found');
                    this.showError('PDF表示エリアが見つかりません');
                }
            } else {
                console.error('Invalid response data:', data);
                this.showError(data.message || 'ページ画像の読み込みに失敗しました');
            }
        })
        .catch(error => {
            console.error('ページ画像読み込みエラー:', error);
            this.showError(`ページ画像の読み込みに失敗しました: ${error.message}`);
        });
    }
    
    renderEntityList() {
        this.elements.entityList.innerHTML = '';
        this.elements.resultCount.textContent = this.detectionResults.length;
        
        this.detectionResults.forEach((entity, index) => {
            const listItem = document.createElement('div');
            listItem.className = `list-group-item list-group-item-action ${index === this.selectedEntityIndex ? 'active' : ''}`;
            listItem.style.cursor = 'pointer';
            
            const entityTypeJa = this.getEntityTypeJapanese(entity.entity_type || entity.type);
            const confidencePercent = Math.round(entity.confidence * 100);
            
            listItem.innerHTML = `
                <div class="d-flex justify-content-between align-items-start">
                    <div class="flex-grow-1">
                        <h6 class="mb-1">${entityTypeJa}</h6>
                        <p class="mb-1 text-truncate">${entity.text}</p>
                        <small class="text-muted">信頼度: ${confidencePercent}% | ページ: ${entity.page}</small>
                    </div>
                    <div class="ms-2">
                        <span class="badge bg-primary">${confidencePercent}%</span>
                    </div>
                </div>
            `;
            
            listItem.addEventListener('click', () => {
                this.selectEntity(index);
            });
            
            this.elements.entityList.appendChild(listItem);
        });
        
    }
    
    selectEntity(index) {
        this.selectedEntityIndex = index;
        this.selectedHighlight = this.detectionResults[index];
        this.renderEntityList();
        
        // 該当ページに移動
        const entity = this.detectionResults[index];
        const targetPage = entity.page - 1; // 0ベースに変換
        if (targetPage !== this.currentPage) {
            this.currentPage = targetPage;
            this.updatePageInfo();
            this.loadPageImage();
        }
        
        // 編集コントロールを表示
        if (this.selectedHighlight) {
            this.showHighlightEditControls(this.selectedHighlight);
        }
    }
    
    previousPage() {
        if (this.currentPage > 0) {
            this.currentPage--;
            this.updatePageInfo();
            this.loadPageImage();
        }
    }
    
    nextPage() {
        if (this.currentPage < this.totalPages - 1) {
            this.currentPage++;
            this.updatePageInfo();
            this.loadPageImage();
        }
    }
    
    updatePageInfo() {
        this.elements.pageInfo.textContent = `${this.currentPage + 1} / ${this.totalPages}`;
        this.elements.prevPageBtn.disabled = this.currentPage === 0;
        this.elements.nextPageBtn.disabled = this.currentPage === this.totalPages - 1;
    }
    
    updateZoom(value) {
        this.zoomLevel = parseInt(value);
        console.log('updateZoom called with value:', value, 'new zoomLevel:', this.zoomLevel);
        
        if (this.elements.zoomValue) {
            this.elements.zoomValue.textContent = this.zoomLevel + '%';
        }
        if (this.elements.zoomDisplay) {
            this.elements.zoomDisplay.textContent = this.zoomLevel + '%';
        }
        
        this.loadPageImage();
    }
    

    
    savePdf() {
        if (!this.currentPdf) {
            this.showError('PDFファイルが選択されていません');
            return;
        }
        
        this.showLoading(true);
        this.updateStatus('PDFを保存中...');
        
        fetch('/api/generate_pdf', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                entities: this.detectionResults,
                masking_method: this.settings.masking_method
            })
        })
        .then(response => response.json())
        .then(data => {
            this.showLoading(false);
            
            if (data.success) {
                this.updateStatus('PDFの保存が完了しました');
                
                // ダウンロードリンクを作成
                const link = document.createElement('a');
                link.href = `/api/download_pdf/${data.filename}`;
                link.download = data.download_filename || data.filename;
                link.click();
            } else {
                this.showError(data.message);
            }
        })
        .catch(error => {
            this.showLoading(false);
            console.error('保存エラー:', error);
            this.showError('PDFの保存に失敗しました');
        });
    }
    
    saveSettings() {
        // チェックボックスから選択されたエンティティを取得
        const selectedEntities = [];
        ['PERSON', 'LOCATION', 'PHONE_NUMBER', 'DATE_TIME'].forEach(entity => {
            const checkbox = document.getElementById('entity' + entity.charAt(0) + entity.slice(1).toLowerCase().replace('_', ''));
            if (checkbox && checkbox.checked) {
                selectedEntities.push(entity);
            }
        });
        
        this.settings.entities = selectedEntities;
        this.settings.threshold = parseFloat(this.elements.thresholdSlider.value);
        this.settings.masking_method = document.getElementById('maskingMethod').value;
        
        // サーバーに設定を保存
        fetch('/api/settings', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(this.settings)
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                this.updateStatus('設定を保存しました');
                // モーダルを閉じる
                const modal = bootstrap.Modal.getInstance(document.getElementById('settingsModal'));
                modal.hide();
            } else {
                this.showError(data.message);
            }
        })
        .catch(error => {
            console.error('設定保存エラー:', error);
            this.showError('設定の保存に失敗しました');
        });
    }
    
    loadSettings() {
        fetch('/api/settings')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                this.settings = data.settings;
                
                // UIに設定を反映
                this.elements.thresholdSlider.value = this.settings.threshold;
                this.elements.thresholdValue.textContent = this.settings.threshold;
                
                // エンティティチェックボックスを設定
                ['PERSON', 'LOCATION', 'PHONE_NUMBER', 'DATE_TIME'].forEach(entity => {
                    const checkbox = document.getElementById('entity' + entity.charAt(0) + entity.slice(1).toLowerCase().replace('_', ''));
                    if (checkbox) {
                        checkbox.checked = this.settings.entities.includes(entity);
                    }
                });
            }
        })
        .catch(error => {
            console.error('設定読み込みエラー:', error);
        });
    }
    
    getEntityTypeJapanese(entityType) {
        const mapping = {
            "PERSON": "人名",
            "LOCATION": "場所",
            "PHONE_NUMBER": "電話番号",
            "DATE_TIME": "日時"
        };
        return mapping[entityType] || entityType;
    }
    
    updateStatus(message) {
        if (this.elements.statusMessage) {
            this.elements.statusMessage.textContent = message;
        } else {
            console.log('Status:', message);
        }
    }
    
    showError(message) {
        this.updateStatus('エラー: ' + message);
        console.error(message);
    }
    
    showLoading(show) {
        if (this.elements.loadingOverlay) {
            if (show) {
                this.elements.loadingOverlay.classList.add('show');
            } else {
                this.elements.loadingOverlay.classList.remove('show');
            }
        }
    }
    
    setupZoomSlider() {
        if (!this.elements.zoomSlider) {
            console.warn('Zoom slider element not found');
            return;
        }
        
        // ズームスライダーの属性を確実に設定
        this.elements.zoomSlider.min = 25;
        this.elements.zoomSlider.max = 400;
        this.elements.zoomSlider.step = 25;
        this.elements.zoomSlider.value = this.zoomLevel;
        
        // 初期表示を更新
        if (this.elements.zoomValue) {
            this.elements.zoomValue.textContent = this.zoomLevel + '%';
        }
        if (this.elements.zoomDisplay) {
            this.elements.zoomDisplay.textContent = this.zoomLevel + '%';
        }
        
        console.log('Zoom slider setup:', {
            min: this.elements.zoomSlider.min,
            max: this.elements.zoomSlider.max,
            value: this.elements.zoomSlider.value,
            zoomLevel: this.zoomLevel
        });
    }
    
    adjustImagePosition(img) {
        // 位置調整を確実に実行するため、少し遅延
        setTimeout(() => {
            const viewer = this.elements.pdfViewer;
            
            // 正確なサイズを取得（パディングを考慮）
            const viewerStyle = getComputedStyle(viewer);
            const paddingTop = parseInt(viewerStyle.paddingTop) || 0;
            const paddingLeft = parseInt(viewerStyle.paddingLeft) || 0;
            const paddingRight = parseInt(viewerStyle.paddingRight) || 0;
            const paddingBottom = parseInt(viewerStyle.paddingBottom) || 0;
            
            const viewerWidth = viewer.clientWidth - paddingLeft - paddingRight;
            const viewerHeight = viewer.clientHeight - paddingTop - paddingBottom;
            const imgWidth = img.offsetWidth;
            const imgHeight = img.offsetHeight;
            
            console.log('Position adjustment:', {
                viewer: [viewerWidth, viewerHeight],
                image: [imgWidth, imgHeight],
                padding: [paddingTop, paddingLeft, paddingRight, paddingBottom],
                zoom: this.zoomLevel + '%'
            });
            
            // 垂直位置調整
            if (imgHeight <= viewerHeight) {
                // 画像が小さい場合は上部マージンで中央に
                const topMargin = Math.max(0, (viewerHeight - imgHeight) / 2);
                img.style.marginTop = topMargin + 'px';
                img.style.marginBottom = topMargin + 'px';
                console.log('Image smaller than viewer, adding top margin:', topMargin);
            } else {
                // 画像が大きい場合はマージンをリセットしてスクロール調整
                img.style.marginTop = '0px';
                img.style.marginBottom = '0px';
                
                // スクロール位置を中央に（少し遅延して確実に）
                setTimeout(() => {
                    const scrollTop = Math.max(0, (imgHeight - viewerHeight) / 2);
                    const scrollLeft = Math.max(0, (imgWidth - viewerWidth) / 2);
                    
                    viewer.scrollTop = scrollTop;
                    viewer.scrollLeft = scrollLeft;
                    
                    console.log('Image larger than viewer, scroll to:', [scrollLeft, scrollTop]);
                }, 50);
            }
        }, 100);
    }
    
    // インタラクティブハイライト編集機能
    handlePdfClick(event) {
        if (!this.elements.showHighlights.checked) {
            return; // ハイライト表示がOFFの場合は無効
        }
        
        const rect = this.elements.pdfViewer.getBoundingClientRect();
        const x = event.clientX - rect.left + this.elements.pdfViewer.scrollLeft;
        const y = event.clientY - rect.top + this.elements.pdfViewer.scrollTop;
        
        // ズーム補正
        const actualX = x / (this.zoomLevel / 100);
        const actualY = y / (this.zoomLevel / 100);
        
        this.selectHighlightAtPosition(actualX, actualY);
    }
    
    selectHighlightAtPosition(x, y) {
        fetch('/api/highlights/select', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                page_num: this.currentPage,
                x: x,
                y: y,
                zoom: this.zoomLevel / 100
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                this.selectedHighlight = data.highlight;
                this.selectedEntityIndex = data.highlight_id;
                this.showHighlightEditControls(data.highlight);
                this.updateStatus(`ハイライトを選択: ${data.highlight.text}`);
            } else {
                this.selectedHighlight = null;
                this.selectedEntityIndex = -1;
                this.hideHighlightEditControls();
                this.updateStatus('ハイライトが選択されていません');
            }
        })
        .catch(error => {
            console.error('ハイライト選択エラー:', error);
            this.showError('ハイライト選択に失敗しました');
        });
    }
    
    showHighlightEditControls(highlight) {
        // パネルは常に表示状態なのでdisplayの変更は不要
        this.editMode = true;
        
        console.log('showHighlightEditControls called with:', highlight);
        console.log('Elements exist:', {
            text: !!this.elements.selectedHighlightText,
            type: !!this.elements.selectedHighlightType,
            confidence: !!this.elements.selectedHighlightConfidence,
            page: !!this.elements.selectedHighlightPage,
            position: !!this.elements.selectedHighlightPosition
        });
        
        // 選択されたハイライト情報を表示
        if (this.elements.selectedHighlightText) {
            this.elements.selectedHighlightText.textContent = highlight.text;
            console.log('Set text to:', highlight.text);
        }
        if (this.elements.selectedHighlightType) {
            const typeText = this.getEntityTypeJapanese(highlight.entity_type || highlight.type);
            this.elements.selectedHighlightType.textContent = typeText;
            console.log('Set type to:', typeText);
        }
        if (this.elements.selectedHighlightConfidence) {
            const confText = (highlight.confidence * 100).toFixed(1) + '%';
            this.elements.selectedHighlightConfidence.textContent = confText;
            console.log('Set confidence to:', confText);
        }
        if (this.elements.selectedHighlightPage) {
            const pageText = highlight.page || '-';
            this.elements.selectedHighlightPage.textContent = pageText;
            console.log('Set page to:', pageText);
        }
        if (this.elements.selectedHighlightPosition) {
            if (highlight.coordinates) {
                const posText = `(${Math.round(highlight.coordinates.x0)}, ${Math.round(highlight.coordinates.y0)})`;
                this.elements.selectedHighlightPosition.textContent = posText;
                console.log('Set position to:', posText);
            } else {
                this.elements.selectedHighlightPosition.textContent = '座標不明';
                console.log('Set position to: 座標不明');
            }
        }
    }
    
    hideHighlightEditControls() {
        // パネルは常に表示、内容をリセット
        this.editMode = false;
        
        if (this.elements.selectedHighlightText) {
            this.elements.selectedHighlightText.textContent = 'ハイライトをクリックしてください';
        }
        if (this.elements.selectedHighlightType) {
            this.elements.selectedHighlightType.textContent = '-';
        }
        if (this.elements.selectedHighlightConfidence) {
            this.elements.selectedHighlightConfidence.textContent = '-';
        }
        if (this.elements.selectedHighlightPage) {
            this.elements.selectedHighlightPage.textContent = '-';
        }
        if (this.elements.selectedHighlightPosition) {
            this.elements.selectedHighlightPosition.textContent = '-';
        }
    }
    

    
    adjustHighlight(adjustmentType) {
        if (!this.selectedHighlight) {
            this.showError('ハイライトが選択されていません');
            return;
        }
        
        // 調整操作をキューに追加
        this.adjustmentQueue.push({
            type: adjustmentType,
            timestamp: Date.now()
        });
        
        // 既存のタイマーをクリア
        if (this.adjustmentTimer) {
            clearTimeout(this.adjustmentTimer);
        }
        
        // 即座にテキスト表示を更新（仮の状態）
        this.updateHighlightTextPreview(adjustmentType);
        
        // デバウンスタイマーを設定
        this.adjustmentTimer = setTimeout(() => {
            this.executeQueuedAdjustments();
        }, this.adjustmentDelay);
        
        this.updateStatus(`調整中... (${this.adjustmentQueue.length}回操作)`);
    }
    
    updateHighlightTextPreview(adjustmentType) {
        // 簡易的なテキスト変更プレビュー（改行なしで表示）
        if (this.selectedHighlight && this.selectedHighlight.text) {
            const currentText = this.selectedHighlight.text;
            let previewText = currentText;
            
            // 簡易プレビュー（実際の変更結果とは異なる場合があります）
            if (adjustmentType === 'extend_left') {
                previewText = '◀' + currentText;
            } else if (adjustmentType === 'extend_right') {
                previewText = currentText + '▶';
            } else if (adjustmentType === 'shrink_left' && currentText.length > 1) {
                previewText = currentText.substring(1);
            } else if (adjustmentType === 'shrink_right' && currentText.length > 1) {
                previewText = currentText.substring(0, currentText.length - 1);
            }
            
            // 改行を削除してインライン表示
            previewText = previewText.replace(/\n/g, ' ').replace(/\s+/g, ' ').trim();
            
            // プレビューテキストを表示
            if (this.elements.selectedHighlightText) {
                this.elements.selectedHighlightText.textContent = previewText;
                this.elements.selectedHighlightText.style.color = '#6c757d'; // グレー表示で仮の状態を示す
                this.elements.selectedHighlightText.style.fontStyle = 'italic';
                this.elements.selectedHighlightText.style.whiteSpace = 'nowrap'; // 改行禁止
                this.elements.selectedHighlightText.style.overflow = 'hidden';
                this.elements.selectedHighlightText.style.textOverflow = 'ellipsis';
            }
        }
    }
    
    executeQueuedAdjustments() {
        if (this.adjustmentQueue.length === 0) {
            return;
        }
        
        console.log(`Executing ${this.adjustmentQueue.length} queued adjustments`);
        
        // スクロール位置を保存
        this.saveScrollPosition();
        
        this.showLoading(true);
        
        // キューをまとめて処理
        const adjustments = [...this.adjustmentQueue];
        this.adjustmentQueue = []; // キューをクリア
        
        // サーバーに一括調整リクエストを送信
        fetch('/api/highlights/adjust_batch', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                highlight_id: this.selectedEntityIndex,
                page_num: this.currentPage,
                adjustments: adjustments
            })
        })
        .then(response => response.json())
        .then(data => {
            this.showLoading(false);
            
            if (data.success) {
                // ハイライト情報を更新
                this.selectedHighlight = data.updated_highlight;
                this.detectionResults[this.selectedEntityIndex] = data.updated_highlight;
                
                // ページ画像を更新
                if (data.updated_image) {
                    const img = this.elements.pdfViewer.querySelector('img');
                    if (img) {
                        img.src = 'data:image/png;base64,' + data.updated_image;
                        // 画像読み込み後にスクロール位置を復元
                        img.onload = () => {
                            this.restoreScrollPosition();
                        };
                    }
                }
                
                // UI更新
                this.showHighlightEditControls(this.selectedHighlight);
                this.renderEntityList();
                this.updateStatus(`調整完了: ${adjustments.length}回の操作を適用`);
                
                // テキスト表示を元に戻す
                this.resetHighlightTextDisplay();
            } else {
                this.showError(data.message);
                this.resetHighlightTextDisplay();
            }
        })
        .catch(error => {
            this.showLoading(false);
            console.error('ハイライト調整エラー:', error);
            
            // エラー時は従来の単発処理にフォールバック
            this.executeSingleAdjustment(adjustments[adjustments.length - 1].type);
        });
    }
    
    executeSingleAdjustment(adjustmentType) {
        // 従来の単発調整処理（フォールバック用）
        fetch('/api/highlights/adjust', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                highlight_id: this.selectedEntityIndex,
                page_num: this.currentPage,
                adjustment_type: adjustmentType,
                amount: 1
            })
        })
        .then(response => response.json())
        .then(data => {
            this.showLoading(false);
            
            if (data.success) {
                this.selectedHighlight = data.updated_highlight;
                this.detectionResults[this.selectedEntityIndex] = data.updated_highlight;
                
                if (data.updated_image) {
                    const img = this.elements.pdfViewer.querySelector('img');
                    if (img) {
                        img.src = 'data:image/png;base64,' + data.updated_image;
                        // 画像読み込み後にスクロール位置を復元
                        img.onload = () => {
                            this.restoreScrollPosition();
                        };
                    }
                }
                
                this.showHighlightEditControls(this.selectedHighlight);
                this.renderEntityList();
                this.updateStatus(data.message);
                this.resetHighlightTextDisplay();
            } else {
                this.showError(data.message);
                this.resetHighlightTextDisplay();
            }
        })
        .catch(error => {
            this.showLoading(false);
            console.error('ハイライト調整エラー:', error);
            this.showError('ハイライト調整に失敗しました');
            this.resetHighlightTextDisplay();
        });
    }
    
    resetHighlightTextDisplay() {
        // テキスト表示を正常な状態に戻す
        if (this.elements.selectedHighlightText && this.selectedHighlight) {
            // 改行を保持してテキストを表示
            const displayText = this.selectedHighlight.text;
            this.elements.selectedHighlightText.textContent = displayText;
            
            // スタイルをリセット
            this.elements.selectedHighlightText.style.color = '';
            this.elements.selectedHighlightText.style.fontStyle = '';
            this.elements.selectedHighlightText.style.whiteSpace = '';
            this.elements.selectedHighlightText.style.overflow = '';
            this.elements.selectedHighlightText.style.textOverflow = '';
        }
    }
    
    clearSelection() {
        // 進行中の調整をキャンセル
        this.cancelPendingAdjustments();
        
        this.selectedHighlight = null;
        this.selectedEntityIndex = -1;
        this.hideHighlightEditControls();
        this.renderEntityList(); // リストの選択状態をクリア
        this.updateStatus('選択を解除しました');
    }
    
    deleteHighlight() {
        if (this.selectedEntityIndex >= 0 && this.selectedEntityIndex < this.detectionResults.length) {
            // 進行中の調整をキャンセル
            this.cancelPendingAdjustments();
            
            const deletedEntity = this.detectionResults[this.selectedEntityIndex];
            const entityIndex = this.selectedEntityIndex;
            
            // バックエンドAPIを呼び出してエンティティを削除
            fetch(`/api/delete_entity/${entityIndex}`, {
                method: 'DELETE'
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // フロントエンドの配列からも削除
                    this.detectionResults.splice(entityIndex, 1);
                    
                    // 選択状態をクリア
                    this.selectedHighlight = null;
                    this.selectedEntityIndex = -1;
                    this.hideHighlightEditControls();
                    
                    // UIを更新
                    this.renderEntityList();
                    
                    // ページ画像を強制的に再読み込み（削除を反映）
                    this.loadPageImage();
                    
                    this.updateStatus(`ハイライトを削除しました: ${deletedEntity.text}`);
                } else {
                    this.showError(data.message || 'ハイライト削除に失敗しました');
                }
            })
            .catch(error => {
                console.error('ハイライト削除エラー:', error);
                this.showError('ハイライト削除に失敗しました');
            });
        } else {
            this.showError('削除するハイライトが選択されていません');
        }
    }
    
    handleKeyDown(event) {
        if (!this.editMode || !this.selectedHighlight) {
            return;
        }
        
        // キーボードショートカット
        switch(event.key) {
            case 'ArrowLeft':
                if (event.shiftKey) {
                    this.adjustHighlight('shrink_right');
                } else {
                    this.adjustHighlight('extend_left');
                }
                event.preventDefault();
                break;
            case 'ArrowRight':
                if (event.shiftKey) {
                    this.adjustHighlight('shrink_left');
                } else {
                    this.adjustHighlight('extend_right');
                }
                event.preventDefault();
                break;
            case 'Escape':
                // 進行中の調整をキャンセル
                this.cancelPendingAdjustments();
                this.clearSelection();
                event.preventDefault();
                break;
        }
    }
    
    cancelPendingAdjustments() {
        // 待機中の調整をキャンセル
        if (this.adjustmentTimer) {
            clearTimeout(this.adjustmentTimer);
            this.adjustmentTimer = null;
        }
        this.adjustmentQueue = [];
        this.resetHighlightTextDisplay();
        this.updateStatus('調整をキャンセルしました');
    }
    
    saveScrollPosition() {
        // 現在のスクロール位置を保存
        if (this.elements.pdfViewer) {
            this.savedScrollPosition = {
                top: this.elements.pdfViewer.scrollTop,
                left: this.elements.pdfViewer.scrollLeft
            };
            console.log('Scroll position saved:', this.savedScrollPosition);
        }
    }
    
    restoreScrollPosition() {
        // スクロール位置を復元
        if (this.elements.pdfViewer && this.savedScrollPosition) {
            // 少し遅延してからスクロール位置を復元（画像読み込み完了を待つ）
            setTimeout(() => {
                this.elements.pdfViewer.scrollTop = this.savedScrollPosition.top;
                this.elements.pdfViewer.scrollLeft = this.savedScrollPosition.left;
                console.log('Scroll position restored:', this.savedScrollPosition);
            }, 100);
        }
    }
}

// グローバルアプリインスタンス
let app;

// アプリケーションの初期化
document.addEventListener('DOMContentLoaded', () => {
    app = new PresidioPDFWebApp();
});