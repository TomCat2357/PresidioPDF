### batch_job.yaml
```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: yolov11-training-job
  labels:
    app: yolov11-training
spec:
  completions: 1
  parallelism: 1
  backoffLimit: 3
  template:
    metadata:
      labels:
        app: yolov11-training
    spec:
      restartPolicy: Never
      serviceAccountName: gcs-service-account  # GCS用サービスアカウント
      containers:
      - name: yolov11-trainer
        image: gcr.io/YOUR_PROJECT_ID/yolov11-trainer:latest
        command: ["python3", "/workspace/scripts/train.py"]
        args:
          - "--bucket=your-ml-bucket"
          - "--dataset_path=datasets/yolo-project"
          - "--config_path=configs/dataset.yaml"
          - "--model=yolov11m.pt"
          - "--pretrained_model=models/pretrained/yolov11m.pt"
          - "--output_path=models/trained/yolov11-project"
          - "--epochs=100"
          - "--batch=16"
          - "--imgsz=640"
          - "--device=0"
          - "--workers=8"
        resources:
          requests:
            memory: "8Gi"
            cpu: "4"
            nvidia.com/gpu: "1"
          limits:
            memory: "16Gi"
            cpu: "8"
            nvidia.com/gpu: "1"
        env:
        - name: NVIDIA_VISIBLE_DEVICES
          value: "all"
        - name: CUDA_VISIBLE_DEVICES
          value: "0"
      nodeSelector:
        accelerator: nvidia-tesla-t4  # 使用するGPUタイプ
      tolerations:
      - key: nvidia.com/gpu
        operator: Exists
        effect: NoSchedule
```# GCP BatchでYOLOv11mトレーニング設定（GCS使用）

## GCS構成

```
# GCSバケット構造
gs://your-ml-bucket/
├── datasets/
│   └── yolo-project/
│       ├── images/
│       │   ├── train/
│       │   │   ├── img1.jpg
│       │   │   └── ...
│       │   └── val/
│       │       ├── img1.jpg
│       │       └── ...
│       └── labels/
│           ├── train/
│           │   ├── img1.txt
│           │   └── ...
│           └── val/
│               ├── img1.txt
│               └── ...
├── models/
│   ├── pretrained/
│   │   ├── yolov11m.pt
│   │   └── yolov8m.pt  # 比較用
│   └── trained/
│       └── your-project/
│           ├── weights/
│           │   ├── best.pt
│           │   └── last.pt
│           └── logs/
└── configs/
    └── dataset.yaml
```

## ローカル構成

```
yolov8-training/
├── scripts/
│   ├── train.py
│   ├── requirements.txt
│   └── gcs_utils.py
├── job/
│   └── batch_job.yaml
├── docker/
│   └── Dockerfile
└── configs/
    └── dataset.yaml
```

## 設定ファイル

### dataset.yaml
```yaml
# configs/dataset.yaml
path: /tmp/dataset  # 一時的なローカルパス
train: images/train
val: images/val

# クラス数
nc: 80  # あなたのクラス数に変更してください

# クラス名
names:
  0: person
  1: bicycle
  2: car
  # あなたのクラス名に変更してください
```

### requirements.txt
```txt
ultralytics>=8.0.0
torch>=2.0.0
torchvision>=0.15.0
Pillow>=9.0.0
PyYAML>=6.0
numpy>=1.21.0
opencv-python>=4.5.0
matplotlib>=3.3.0
seaborn>=0.11.0
pandas>=1.3.0
google-cloud-storage>=2.10.0
```

### gcs_utils.py
```python
#!/usr/bin/env python3
import os
import logging
from google.cloud import storage
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GCSManager:
    def __init__(self, bucket_name):
        self.client = storage.Client()
        self.bucket = self.client.bucket(bucket_name)
        self.bucket_name = bucket_name
    
    def download_folder(self, gcs_prefix, local_path):
        """GCSからフォルダをダウンロード"""
        local_path = Path(local_path)
        local_path.mkdir(parents=True, exist_ok=True)
        
        blobs = self.bucket.list_blobs(prefix=gcs_prefix)
        downloaded_count = 0
        
        for blob in blobs:
            if blob.name.endswith('/'):
                continue
                
            # ローカルファイルパス作成
            relative_path = blob.name[len(gcs_prefix):].lstrip('/')
            local_file_path = local_path / relative_path
            
            # ディレクトリ作成
            local_file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # ファイルダウンロード
            blob.download_to_filename(str(local_file_path))
            downloaded_count += 1
            
            if downloaded_count % 100 == 0:
                logger.info(f"Downloaded {downloaded_count} files...")
        
        logger.info(f"Downloaded {downloaded_count} files from gs://{self.bucket_name}/{gcs_prefix}")
        return downloaded_count
    
    def upload_folder(self, local_path, gcs_prefix):
        """ローカルフォルダをGCSにアップロード"""
        local_path = Path(local_path)
        uploaded_count = 0
        
        for local_file in local_path.rglob('*'):
            if local_file.is_file():
                relative_path = local_file.relative_to(local_path)
                gcs_path = f"{gcs_prefix}/{relative_path}".replace('\\', '/')
                
                blob = self.bucket.blob(gcs_path)
                blob.upload_from_filename(str(local_file))
                uploaded_count += 1
                
                if uploaded_count % 100 == 0:
                    logger.info(f"Uploaded {uploaded_count} files...")
        
        logger.info(f"Uploaded {uploaded_count} files to gs://{self.bucket_name}/{gcs_prefix}")
        return uploaded_count
    
    def download_file(self, gcs_path, local_path):
        """単一ファイルをダウンロード"""
        blob = self.bucket.blob(gcs_path)
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        blob.download_to_filename(local_path)
        logger.info(f"Downloaded gs://{self.bucket_name}/{gcs_path} to {local_path}")
    
    def upload_file(self, local_path, gcs_path):
        """単一ファイルをアップロード"""
        blob = self.bucket.blob(gcs_path)
        blob.upload_from_filename(local_path)
        logger.info(f"Uploaded {local_path} to gs://{self.bucket_name}/{gcs_path}")
    
    def file_exists(self, gcs_path):
        """ファイルが存在するかチェック"""
        blob = self.bucket.blob(gcs_path)
        return blob.exists()
```

### train.py
```python
#!/usr/bin/env python3
import os
import argparse
import shutil
from pathlib import Path
from ultralytics import YOLO
import torch
from gcs_utils import GCSManager

def main():
    parser = argparse.ArgumentParser(description='YOLO Training with GCS')
    parser.add_argument('--bucket', type=str, required=True, help='GCS bucket name')
    parser.add_argument('--dataset_path', type=str, required=True, 
                       help='GCS dataset path (e.g., datasets/yolo-project)')
    parser.add_argument('--config_path', type=str, default='configs/dataset.yaml',
                       help='GCS config path')
    parser.add_argument('--model', type=str, default='yolov11m.pt',
                       help='Model to use (yolov11m.pt, yolov8m.pt, etc.)')
    parser.add_argument('--pretrained_model', type=str, 
                       default='models/pretrained/yolov11m.pt',
                       help='GCS pretrained model path')
    parser.add_argument('--output_path', type=str, required=True,
                       help='GCS output path (e.g., models/trained/your-project)')
    
    # トレーニングパラメータ
    parser.add_argument('--epochs', type=int, default=100, help='number of epochs')
    parser.add_argument('--batch', type=int, default=16, help='batch size')
    parser.add_argument('--imgsz', type=int, default=640, help='image size')
    parser.add_argument('--device', type=str, default='0', help='device to use')
    parser.add_argument('--workers', type=int, default=8, help='number of workers')
    parser.add_argument('--save_period', type=int, default=10, 
                       help='save checkpoint every x epochs')
    
    args = parser.parse_args()
    
    # GPU確認
    print(f"CUDA available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"GPU count: {torch.cuda.device_count()}")
        print(f"Current GPU: {torch.cuda.current_device()}")
        print(f"GPU name: {torch.cuda.get_device_name()}")
    
    # GCSマネージャー初期化
    gcs = GCSManager(args.bucket)
    
    # 作業ディレクトリ準備
    work_dir = Path("/tmp/yolo_work")
    work_dir.mkdir(exist_ok=True)
    
    dataset_dir = work_dir / "dataset"
    config_file = work_dir / "dataset.yaml"
    model_file = work_dir / args.model
    output_dir = work_dir / "runs"
    
    try:
        # 1. データセットダウンロード
        print("Downloading dataset from GCS...")
        gcs.download_folder(args.dataset_path, dataset_dir)
        
        # 2. 設定ファイルダウンロード
        print("Downloading config file...")
        gcs.download_file(args.config_path, config_file)
        
        # 3. 事前訓練モデルダウンロード（存在する場合）
        if gcs.file_exists(args.pretrained_model):
            print(f"Downloading pretrained model from GCS: {args.pretrained_model}")
            gcs.download_file(args.pretrained_model, model_file)
            model_path = str(model_file)
        else:
            print(f"Using default {args.model} model...")
            model_path = args.model
        
        # 4. YOLOモデルロード
        print(f"Loading YOLO model: {model_path}")
        model = YOLO(model_path)
        
        # モデル情報表示
        print(f"Model: {model.model_name if hasattr(model, 'model_name') else args.model}")
        print(f"Parameters: {sum(p.numel() for p in model.model.parameters()):,}")
        
        # 5. トレーニング実行
        print("Starting training...")
        results = model.train(
            data=str(config_file),
            epochs=args.epochs,
            batch=args.batch,
            imgsz=args.imgsz,
            device=args.device,
            workers=args.workers,
            project=str(output_dir),
            name="train",
            save_period=args.save_period,
            patience=50,
            save=True,
            plots=True,
            verbose=True
        )
        
        print("Training completed!")
        
        # 6. 結果をGCSにアップロード
        print("Uploading results to GCS...")
        train_output_dir = output_dir / "train"
        if train_output_dir.exists():
            gcs.upload_folder(train_output_dir, args.output_path)
            print(f"Results uploaded to gs://{args.bucket}/{args.output_path}")
        
        # 7. 最終モデルを特別に保存
        best_model_path = train_output_dir / "weights" / "best.pt"
        if best_model_path.exists():
            final_model_gcs_path = f"{args.output_path}/final_model.pt"
            gcs.upload_file(str(best_model_path), final_model_gcs_path)
            print(f"Final model saved to gs://{args.bucket}/{final_model_gcs_path}")
            
        # 8. 結果サマリー表示
        if hasattr(results, 'results_dict'):
            print("\n=== Training Summary ===")
            for key, value in results.results_dict.items():
                print(f"{key}: {value}")
    
    except Exception as e:
        print(f"Error during training: {e}")
        raise
    
    finally:
        # クリーンアップ
        if work_dir.exists():
            shutil.rmtree(work_dir)
            print("Cleaned up temporary files")

if __name__ == '__main__':
    main()
```

### Dockerfile
```dockerfile
FROM nvidia/cuda:11.8-devel-ubuntu20.04

# 環境変数設定
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV GOOGLE_APPLICATION_CREDENTIALS=/tmp/gcp-key.json
ENV PATH="/root/.local/bin:$PATH"

# 基本パッケージインストール
RUN apt-get update && apt-get install -y \
    python3 \
    python3-dev \
    git \
    wget \
    curl \
    ca-certificates \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgl1-mesa-glx \
    && rm -rf /var/lib/apt/lists/*

# uvインストール
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Python依存関係インストール
COPY scripts/requirements.txt /tmp/requirements.txt
RUN /root/.local/bin/uv pip install --system --no-cache -r /tmp/requirements.txt

# 作業ディレクトリ設定
WORKDIR /workspace

# スクリプトコピー
COPY scripts/ /workspace/scripts/
COPY configs/ /workspace/configs/

# 実行権限付与
RUN chmod +x /workspace/scripts/train.py

# エントリーポイント
ENTRYPOINT ["python3", "/workspace/scripts/train.py"]
```

### batch_job.yaml
```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: yolov8-training-job
  labels:
    app: yolov8-training
spec:
  completions: 1
  parallelism: 1
  backoffLimit: 3
  template:
    metadata:
      labels:
        app: yolov8-training
    spec:
      restartPolicy: Never
      containers:
      - name: yolov8-trainer
        image: gcr.io/YOUR_PROJECT_ID/yolov8-trainer:latest
        command: ["python3", "/workspace/scripts/train.py"]
        args:
          - "--epochs=100"
          - "--batch=16"
          - "--imgsz=640"
          - "--device=0"
          - "--workers=8"
        resources:
          requests:
            memory: "8Gi"
            cpu: "4"
            nvidia.com/gpu: "1"
          limits:
            memory: "16Gi"
            cpu: "8"
            nvidia.com/gpu: "1"
        volumeMounts:
        - name: dataset-volume
          mountPath: /workspace/dataset
        - name: output-volume
          mountPath: /workspace/runs
        env:
        - name: NVIDIA_VISIBLE_DEVICES
          value: "all"
        - name: CUDA_VISIBLE_DEVICES
          value: "0"
      volumes:
      - name: dataset-volume
        persistentVolumeClaim:
          claimName: dataset-pvc
      - name: output-volume
        persistentVolumeClaim:
          claimName: output-pvc
      nodeSelector:
        accelerator: nvidia-tesla-t4  # 使用するGPUタイプ
      tolerations:
      - key: nvidia.com/gpu
        operator: Exists
        effect: NoSchedule
```

## セットアップ手順

### 1. GCSバケット作成とデータアップロード
```bash
# 環境変数設定
export PROJECT_ID=your-project-id
export BUCKET_NAME=your-ml-bucket
export REGION=asia-northeast1

# バケット作成
gsutil mb -p $PROJECT_ID -c STANDARD -l $REGION gs://$BUCKET_NAME

# データセットアップロード
gsutil -m cp -r ./dataset gs://$BUCKET_NAME/datasets/yolo-project/
gsutil cp ./configs/dataset.yaml gs://$BUCKET_NAME/configs/

# 事前訓練モデルアップロード
# YOLOv11の事前訓練モデルをダウンロード・アップロード
wget https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov11m.pt
gsutil cp yolov11m.pt gs://$BUCKET_NAME/models/pretrained/

# 比較用にYOLOv8もアップロード（オプション）
# wget https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8m.pt
# gsutil cp yolov8m.pt gs://$BUCKET_NAME/models/pretrained/
```

### 2. GCS認証設定
```bash
# サービスアカウント作成
gcloud iam service-accounts create gcs-yolo-training \
    --description="Service account for YOLO training with GCS access" \
    --display-name="GCS YOLO Training"

# GCS権限付与
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:gcs-yolo-training@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/storage.admin"

# Kubernetesサービスアカウント作成
kubectl create serviceaccount gcs-service-account

# Workload Identity設定
gcloud iam service-accounts add-iam-policy-binding \
    --role roles/iam.workloadIdentityUser \
    --member "serviceAccount:$PROJECT_ID.svc.id.goog[default/gcs-service-account]" \
    gcs-yolo-training@$PROJECT_ID.iam.gserviceaccount.com

kubectl annotate serviceaccount gcs-service-account \
    iam.gke.io/gcp-service-account=gcs-yolo-training@$PROJECT_ID.iam.gserviceaccount.com
```

### 3. GKE クラスター作成（GPU対応・Workload Identity有効）
```bash
# GPUクラスター作成（Workload Identity有効）
gcloud container clusters create yolov8-cluster \
    --zone=$ZONE \
    --machine-type=n1-standard-4 \
    --accelerator=type=nvidia-tesla-t4,count=1 \
    --enable-autoscaling \
    --min-nodes=0 \
    --max-nodes=3 \
    --enable-autorepair \
    --enable-autoupgrade \
    --workload-pool=$PROJECT_ID.svc.id.goog

# kubectl設定
gcloud container clusters get-credentials yolov8-cluster --zone=$ZONE

# GPU ドライバーインストール
kubectl apply -f https://raw.githubusercontent.com/GoogleCloudPlatform/container-engine-accelerators/master/nvidia-driver-installer/cos/daemonset-preloaded.yaml
```

### 4. Dockerイメージビルド・プッシュ（uvを使用）
```bash
# Container Registryを有効化
gcloud services enable containerregistry.googleapis.com

# イメージビルド（YOLOv11対応）
docker build -t gcr.io/$PROJECT_ID/yolov11-trainer:latest -f docker/Dockerfile .

# イメージプッシュ
docker push gcr.io/$PROJECT_ID/yolov11-trainer:latest
```

### 5. トレーニングジョブ実行
```bash
# batch_job.yamlのPROJECT_IDとバケット名を更新してから実行
kubectl apply -f job/batch_job.yaml

# ジョブ状況確認
kubectl get jobs
kubectl get pods

# ログ確認
kubectl logs -f job/yolov11-training-job
```

### 6. 結果確認
```bash
# 結果をローカルにダウンロード
gsutil -m cp -r gs://$BUCKET_NAME/models/trained/yolov11-project ./results

# 最終モデルのダウンロード
gsutil cp gs://$BUCKET_NAME/models/trained/yolov11-project/final_model.pt ./

# TensorBoardログの確認（オプション）
gsutil -m cp -r gs://$BUCKET_NAME/models/trained/yolov11-project ./tensorboard_logs
tensorboard --logdir=./tensorboard_logs
```

### YOLOv11 vs YOLOv8の比較実行
```bash
# 両方のモデルで比較実験を実行する場合
# YOLOv11実行
kubectl apply -f - <<EOF
apiVersion: batch/v1
kind: Job
metadata:
  name: yolov11-training-job
spec:
  template:
    spec:
      containers:
      - name: yolov11-trainer
        image: gcr.io/$PROJECT_ID/yolov11-trainer:latest
        args:
          - "--model=yolov11m.pt"
          - "--output_path=models/trained/yolov11-experiment"
          # その他のパラメータ...
EOF

# YOLOv8実行（比較用）
kubectl apply -f - <<EOF
apiVersion: batch/v1
kind: Job
metadata:
  name: yolov8-training-job
spec:
  template:
    spec:
      containers:
      - name: yolov8-trainer
        image: gcr.io/$PROJECT_ID/yolov11-trainer:latest
        args:
          - "--model=yolov8m.pt"
          - "--output_path=models/trained/yolov8-experiment"
          # その他のパラメータ...
EOF
```

### 7. データセット準備のヘルパースクリプト
```python
# train.pyでのモデル選択例
SUPPORTED_MODELS = {
    'yolov11n': 'yolov11n.pt',    # Nano - 最軽量
    'yolov11s': 'yolov11s.pt',    # Small
    'yolov11m': 'yolov11m.pt',    # Medium - バランス型
    'yolov11l': 'yolov11l.pt',    # Large
    'yolov11x': 'yolov11x.pt',    # Extra Large - 最高精度
    'yolov8n': 'yolov8n.pt',     # 比較用
    'yolov8s': 'yolov8s.pt',
    'yolov8m': 'yolov8m.pt',
    'yolov8l': 'yolov8l.pt',
    'yolov8x': 'yolov8x.pt',
}
```
```bash
# データセットをYOLO形式に変換するスクリプト例
cat > prepare_dataset.py << 'EOF'
#!/usr/bin/env python3
import os
import shutil
from pathlib import Path
from sklearn.model_selection import train_test_split

def prepare_yolo_dataset(image_dir, label_dir, output_dir, train_ratio=0.8):
    """画像とラベルをYOLO形式で分割"""
    output_dir = Path(output_dir)
    
    # 出力ディレクトリ作成
    for split in ['train', 'val']:
        (output_dir / 'images' / split).mkdir(parents=True, exist_ok=True)
        (output_dir / 'labels' / split).mkdir(parents=True, exist_ok=True)
    
    # 画像ファイル一覧取得
    image_files = list(Path(image_dir).glob('*.jpg')) + list(Path(image_dir).glob('*.png'))
    
    # train/val分割
    train_files, val_files = train_test_split(image_files, train_size=train_ratio, random_state=42)
    
    # ファイルコピー
    for files, split in [(train_files, 'train'), (val_files, 'val')]:
        for img_file in files:
            # 画像コピー
            shutil.copy2(img_file, output_dir / 'images' / split / img_file.name)
            
            # 対応するラベルファイルコピー
            label_file = Path(label_dir) / f"{img_file.stem}.txt"
            if label_file.exists():
                shutil.copy2(label_file, output_dir / 'labels' / split / label_file.name)
    
    print(f"Dataset prepared: {len(train_files)} train, {len(val_files)} val images")

if __name__ == '__main__':
    prepare_yolo_dataset('./raw_images', './raw_labels', './dataset')
EOF

python3 prepare_dataset.py
```

## 注意点とメリット

### YOLOv11の新機能
1. **改善された精度**: YOLOv8比で精度向上
2. **効率的なアーキテクチャ**: より軽量で高速
3. **マルチタスク対応**: 検出、分類、セグメンテーション統合
4. **最適化されたエクスポート**: ONNX、TensorRT等への変換が改善

### GCS使用のメリット
1. **コスト効率**: PersistentVolumeより安価
2. **スケーラビリティ**: 大容量データも問題なし
3. **永続性**: クラスター削除後もデータが残る
4. **共有**: 複数のジョブでデータを共有可能
5. **バックアップ**: 自動的にデータが複製される

### パフォーマンス最適化
- **uv使用**: pipより5-10倍高速なパッケージインストール
- **並列ダウンロード**: `gsutil -m` で高速データ転送
- **一時ストレージ**: `/tmp` でI/O最適化
- **GPU最適化**: CUDA対応コンテナ使用

### 注意点
1. **データ転送時間**: 大きなデータセットは初回ダウンロードに時間がかかる
2. **ネットワーク費用**: リージョン間転送は課金対象
3. **認証設定**: Workload Identityの正しい設定が必要
4. **クリーンアップ**: 一時ファイルの自動削除でディスク容量を管理

### トラブルシューティング
```bash
# Workload Identity確認
kubectl describe sa gcs-service-account

# GCS権限確認
gcloud projects get-iam-policy $PROJECT_ID --flatten="bindings[].members" \
    --filter="bindings.members:gcs-yolo-training*"

# GPU確認
kubectl describe nodes | grep -A 5 "nvidia.com/gpu"

# ログ確認
kubectl logs -f <pod-name> --previous  # 前回実行のログ
```

トレーニング完了後、最適なモデルが `gs://your-bucket/models/trained/yolov11-project/final_model.pt` に保存されます。

### YOLOv11とYOLOv8の性能比較
```bash
# 結果比較スクリプト
python3 - <<EOF
import pandas as pd
from pathlib import Path

def compare_results(v11_path, v8_path):
    """YOLOv11とYOLOv8の結果を比較"""
    print("=== YOLOv11 vs YOLOv8 Performance Comparison ===")
    
    # 結果ファイルから指標を抽出
    # results.csv から mAP, precision, recall等を比較
    
if __name__ == '__main__':
    compare_results('./results/yolov11-experiment', './results/yolov8-experiment')
EOF
```