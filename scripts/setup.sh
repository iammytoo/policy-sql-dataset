#!/bin/bash
# Spider データセットのダウンロード・セットアップ

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DATA_DIR="$PROJECT_ROOT/spider_data"

echo "=== Spider Dataset Setup ==="

# 既に存在する場合はスキップ
if [ -d "$DATA_DIR/spider_data" ]; then
    echo "Spider data already exists at $DATA_DIR"
    echo "To re-download, remove the directory first: rm -rf $DATA_DIR"
    exit 0
fi

mkdir -p "$DATA_DIR"
cd "$DATA_DIR"

echo "Downloading Spider dataset..."
# Spider 公式の Google Drive リンク
# https://yale-lily.github.io/spider
SPIDER_URL="https://drive.usercontent.google.com/download?id=1iRDVHLr4mX2wQKSgA9J8Pire73Jahh0m&confirm=t"

curl -L "$SPIDER_URL" -o spider.zip

echo "Extracting..."
unzip -q spider.zip

echo "Cleaning up..."
rm spider.zip

echo ""
echo "=== Setup Complete ==="
echo "Spider data is now available at: $DATA_DIR/spider_data/"
echo ""
echo "Contents:"
ls -la "$DATA_DIR/spider_data/"
