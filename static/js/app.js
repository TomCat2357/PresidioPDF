/**
 * PDF個人情報マスキングツール - Webアプリケーション
 * JavaScript フロントエンド
 */

class PresidioPDFWebApp {
    constructor() {
        this.currentPdf = null;
        this.currentPage = 0;
        this.totalPages = 0;
        this.zoomLevel = 1.0;
        this.detectionResults = [];
        this.selectedEntityIndex = -1;
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
        // DOM要素の参照を取得
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
            entityDetails: document.getElementById('entityDetails'),
            entityType: document.getElementById('entityType'),
            entityText: document.getElementById('entityText'),
            entityConfidence: document.getElementById('entityConfidence'),
            entityPage: document.getElementById('entityPage'),
            entityPosition: document.getElementById('entityPosition'),
            deleteBtn: document.getElementById('deleteBtn'),
            saveBtn: document.getElementById('saveBtn'),
            statusMessage: document.getElementById('statusMessage'),
            pdfViewer: document.getElementById('pdfViewer'),
            loadingOverlay: document.getElementById('loadingOverlay'),
            settingsModal: document.getElementById('settingsModal'),
            thresholdSlider: document.getElementById('thresholdSlider'),
            thresholdValue: document.getElementById('thresholdValue'),
            saveSettingsBtn: document.getElementById('saveSettingsBtn'),
            maskingMethod: document.getElementById('maskingMethod')
        };
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
        
        // 操作ボタン
        this.elements.detectBtn.addEventListener('click', () => {
            this.startDetection();
        });
        
        this.elements.settingsBtn.addEventListener('click', () => {
            this.showSettings();
        });
        
        // PDF表示コントロール
        this.elements.prevPageBtn.addEventListener('click', () => {
            this.goToPreviousPage();
        });
        
        this.elements.nextPageBtn.addEventListener('click', () => {
            this.goToNextPage();
        });
        
        this.elements.zoomSlider.addEventListener('input', (e) => {
            this.updateZoom(parseInt(e.target.value));
        });
        
        this.elements.showHighlights.addEventListener('change', () => {
            this.loadPageImage();
        });
        
        // エンティティ操作
        this.elements.deleteBtn.addEventListener('click', () => {
            this.deleteSelectedEntity();
        });
        
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
    }
    
    handleFileSelect(file) {
        if (!file) return;
        
        if (file.type !== 'application/pdf') {
            this.showError('PDFファイルを選択してください');
            return;
        }
        
        this.showLoading(true);
        this.updateStatus('ファイルアップロード中...');
        
        const formData = new FormData();
        formData.append('pdf_file', file);
        
        fetch('/api/upload', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            this.showLoading(false);
            if (data.success) {
                this.currentPdf = file.name;
                this.totalPages = data.total_pages;
                this.currentPage = 0;
                this.elements.selectedFileName.textContent = data.filename;
                this.elements.detectBtn.disabled = false;
                this.updatePageInfo();
                this.updateNavigationButtons();
                this.loadPageImage();
                this.updateStatus(data.message);
            } else {
                this.showError(data.message);
            }
        })
        .catch(error => {
            this.showLoading(false);
            this.showError('ファイルアップロードエラー: ' + error.message);
        });
    }
    
    startDetection() {
        if (!this.currentPdf) {
            this.showError('PDFファイルを選択してください');
            return;
        }
        
        this.showLoading(true);
        this.updateStatus('個人情報検出中...');
        
        fetch('/api/detect', {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            this.showLoading(false);
            if (data.success) {
                this.detectionResults = data.results || [];
                this.updateResultsList();
                this.updateStatus(data.message);
                this.elements.saveBtn.disabled = this.detectionResults.length === 0;
                // 検出結果でページを再表示（ハイライト付き）
                this.loadPageImage();
            } else {
                this.showError(data.message);
            }
        })
        .catch(error => {
            this.showLoading(false);
            this.showError('検出エラー: ' + error.message);
        });
    }
    
    loadPageImage() {
        if (!this.currentPdf || this.currentPage >= this.totalPages) return;
        
        // 検出結果がある場合かつチェックボックスがONの場合はハイライト表示
        const showHighlights = this.detectionResults.length > 0 && this.elements.showHighlights.checked;
        const url = `/api/page/${this.currentPage}?zoom=${this.zoomLevel}&highlights=${showHighlights}`;
        
        fetch(url)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const img = document.createElement('img');
                img.className = 'pdf-image';
                img.alt = `Page ${this.currentPage + 1}`;
                
                // 画像読み込み完了後に処理
                img.onload = () => {
                    console.log('Image loaded, adjusting position...');
                    this.adjustImagePosition(img);
                };
                
                // 先にDOMに追加
                this.elements.pdfViewer.innerHTML = '';
                this.elements.pdfViewer.appendChild(img);
                
                // ズームレベルに応じてサイズ設定
                const baseWidth = 600;
                const scaledWidth = baseWidth * this.zoomLevel;
                img.style.width = scaledWidth + 'px';
                img.style.height = 'auto';
                
                console.log('Image scaled to:', scaledWidth + 'px', 'zoom:', this.zoomLevel);
                
                // 画像ソースを設定（これでonloadが発火）
                img.src = 'data:image/png;base64,' + data.image;
            } else {
                this.showError('ページ読み込みエラー: ' + data.message);
            }
        })
        .catch(error => {
            this.showError('ページ読み込みエラー: ' + error.message);
        });
    }
    
    updateResultsList() {
        this.elements.resultCount.textContent = this.detectionResults.length;
        
        if (this.detectionResults.length === 0) {
            this.elements.entityList.innerHTML = `
                <div class="entity-item text-muted">
                    検出結果がありません
                </div>
            `;
            return;
        }
        
        const html = this.detectionResults.map((result, index) => {
            const entityTypeJp = this.getEntityTypeJapanese(result.entity_type);
            return `
                <div class="entity-item" data-index="${index}">
                    <div class="entity-type">${entityTypeJp}</div>
                    <div>${result.text}</div>
                    <div class="entity-confidence">信頼度: ${(result.confidence * 100).toFixed(1)}%</div>
                </div>
            `;
        }).join('');
        
        this.elements.entityList.innerHTML = html;
        
        // エンティティアイテムのクリックイベントを追加
        this.elements.entityList.querySelectorAll('.entity-item').forEach(item => {
            item.addEventListener('click', () => {
                const index = parseInt(item.dataset.index);
                this.selectEntity(index);
            });
        });
    }
    
    selectEntity(index) {
        if (index < 0 || index >= this.detectionResults.length) return;
        
        // 以前の選択を解除
        this.elements.entityList.querySelectorAll('.entity-item').forEach(item => {
            item.classList.remove('selected');
        });
        
        // 新しい選択を適用
        const selectedItem = this.elements.entityList.querySelector(`[data-index="${index}"]`);
        if (selectedItem) {
            selectedItem.classList.add('selected');
        }
        
        this.selectedEntityIndex = index;
        const entity = this.detectionResults[index];
        
        // エンティティ詳細を更新
        this.elements.entityType.textContent = this.getEntityTypeJapanese(entity.entity_type);
        this.elements.entityText.textContent = entity.text;
        this.elements.entityConfidence.textContent = (entity.confidence * 100).toFixed(1) + '%';
        this.elements.entityPage.textContent = entity.page || '1';
        this.elements.entityPosition.textContent = `${entity.start || 0}-${entity.end || 0}`;
        
        this.elements.deleteBtn.disabled = false;
        
        // 該当ページに移動
        const entityPage = (entity.page || 1) - 1;
        if (entityPage !== this.currentPage && entityPage >= 0 && entityPage < this.totalPages) {
            this.currentPage = entityPage;
            this.updatePageInfo();
            this.updateNavigationButtons();
            this.loadPageImage();
        }
    }
    
    deleteSelectedEntity() {
        if (this.selectedEntityIndex < 0) return;
        
        const entity = this.detectionResults[this.selectedEntityIndex];
        if (!confirm(`検出結果「${entity.text}」(${this.getEntityTypeJapanese(entity.entity_type)})を削除しますか？`)) {
            return;
        }
        
        fetch(`/api/delete_entity/${this.selectedEntityIndex}`, {
            method: 'DELETE'
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                this.detectionResults.splice(this.selectedEntityIndex, 1);
                this.selectedEntityIndex = -1;
                this.updateResultsList();
                this.clearEntityDetails();
                this.updateStatus(data.message);
                this.elements.saveBtn.disabled = this.detectionResults.length === 0;
                // エンティティ削除後にページを再表示（ハイライト更新）
                this.loadPageImage();
            } else {
                this.showError(data.message);
            }
        })
        .catch(error => {
            this.showError('削除エラー: ' + error.message);
        });
    }
    
    savePdf() {
        if (this.detectionResults.length === 0) {
            this.showError('保存する検出結果がありません');
            return;
        }
        
        this.showLoading(true);
        this.updateStatus('PDFファイル生成中...');
        
        fetch('/api/generate_pdf', {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            this.showLoading(false);
            if (data.success) {
                this.updateStatus('PDFファイルをダウンロード中...');
                // 生成されたPDFファイルをダウンロード
                const downloadUrl = `/api/download_pdf/${data.filename}`;
                const link = document.createElement('a');
                link.href = downloadUrl;
                link.download = data.download_filename || data.filename;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                
                this.updateStatus(`PDFファイルをダウンロードしました: ${data.download_filename || data.filename}`);
            } else {
                this.showError(data.message);
            }
        })
        .catch(error => {
            this.showLoading(false);
            this.showError('PDF生成エラー: ' + error.message);
        });
    }
    
    goToPreviousPage() {
        if (this.currentPage > 0) {
            this.currentPage--;
            this.updatePageInfo();
            this.updateNavigationButtons();
            this.loadPageImage();
        }
    }
    
    goToNextPage() {
        if (this.currentPage < this.totalPages - 1) {
            this.currentPage++;
            this.updatePageInfo();
            this.updateNavigationButtons();
            this.loadPageImage();
        }
    }
    
    updateZoom(zoomPercent) {
        console.log('Zoom update:', zoomPercent); // デバッグログ
        this.zoomLevel = zoomPercent / 100.0;
        this.elements.zoomValue.textContent = zoomPercent + '%';
        this.elements.zoomDisplay.textContent = zoomPercent + '%';
        this.loadPageImage();
    }
    
    updatePageInfo() {
        this.elements.pageInfo.textContent = `${this.currentPage + 1}/${this.totalPages}`;
    }
    
    updateNavigationButtons() {
        this.elements.prevPageBtn.disabled = this.currentPage <= 0;
        this.elements.nextPageBtn.disabled = this.currentPage >= this.totalPages - 1;
    }
    
    clearEntityDetails() {
        this.elements.entityType.textContent = '-';
        this.elements.entityText.textContent = '-';
        this.elements.entityConfidence.textContent = '-';
        this.elements.entityPage.textContent = '-';
        this.elements.entityPosition.textContent = '-';
        this.elements.deleteBtn.disabled = true;
        this.selectedEntityIndex = -1;
    }
    
    showSettings() {
        // 現在の設定を画面に反映
        const entityCheckboxes = {
            'PERSON': document.getElementById('entityPerson'),
            'LOCATION': document.getElementById('entityLocation'),
            'PHONE_NUMBER': document.getElementById('entityPhone'),
            'DATE_TIME': document.getElementById('entityDate')
        };
        
        Object.keys(entityCheckboxes).forEach(key => {
            entityCheckboxes[key].checked = this.settings.entities.includes(key);
        });
        
        this.elements.thresholdSlider.value = this.settings.threshold;
        this.elements.thresholdValue.textContent = this.settings.threshold;
        this.elements.maskingMethod.value = this.settings.masking_method;
        
        // モーダルを表示
        const modal = new bootstrap.Modal(this.elements.settingsModal);
        modal.show();
    }
    
    saveSettings() {
        // チェックボックスから設定を読み取り
        const entities = [];
        const entityCheckboxes = {
            'PERSON': document.getElementById('entityPerson'),
            'LOCATION': document.getElementById('entityLocation'),
            'PHONE_NUMBER': document.getElementById('entityPhone'),
            'DATE_TIME': document.getElementById('entityDate')
        };
        
        Object.keys(entityCheckboxes).forEach(key => {
            if (entityCheckboxes[key].checked) {
                entities.push(key);
            }
        });
        
        const threshold = parseFloat(this.elements.thresholdSlider.value);
        const maskingMethod = this.elements.maskingMethod.value;
        
        const newSettings = {
            entities: entities,
            threshold: threshold,
            masking_method: maskingMethod
        };
        
        fetch('/api/settings', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(newSettings)
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                this.settings = data.settings;
                this.updateStatus(data.message);
                // モーダルを閉じる
                const modal = bootstrap.Modal.getInstance(this.elements.settingsModal);
                modal.hide();
            } else {
                this.showError(data.message);
            }
        })
        .catch(error => {
            this.showError('設定保存エラー: ' + error.message);
        });
    }
    
    loadSettings() {
        fetch('/api/settings')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                this.settings = data.settings;
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
        this.elements.statusMessage.textContent = message;
    }
    
    showError(message) {
        this.updateStatus('エラー: ' + message);
        console.error(message);
    }
    
    showLoading(show) {
        if (show) {
            this.elements.loadingOverlay.classList.add('show');
        } else {
            this.elements.loadingOverlay.classList.remove('show');
        }
    }
    
    setupZoomSlider() {
        // ズームスライダーの属性を確実に設定
        this.elements.zoomSlider.min = 25;
        this.elements.zoomSlider.max = 400;
        this.elements.zoomSlider.step = 25;
        this.elements.zoomSlider.value = 100;
        console.log('Zoom slider setup:', {
            min: this.elements.zoomSlider.min,
            max: this.elements.zoomSlider.max,
            value: this.elements.zoomSlider.value
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
                zoom: this.zoomLevel
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
}

// アプリケーションの初期化
document.addEventListener('DOMContentLoaded', () => {
    const app = new PresidioPDFWebApp();
});