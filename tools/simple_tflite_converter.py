#!/usr/bin/env python3
"""
軽量版TFLite変換スクリプト
問題のあるKerasモデルを回避するため、HDF5から直接重みを読み込み
"""

import os
import sys
import numpy as np
import h5py
import argparse
import logging

# ログ設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def inspect_h5_model(h5_path):
    """H5ファイルの構造を調査"""
    logger.info(f"H5ファイル構造調査: {h5_path}")
    
    try:
        with h5py.File(h5_path, 'r') as f:
            def print_structure(name, obj):
                logger.info(f"  {name}: {type(obj)}")
                if hasattr(obj, 'shape'):
                    logger.info(f"    shape: {obj.shape}")
                if hasattr(obj, 'dtype'):
                    logger.info(f"    dtype: {obj.dtype}")
            
            logger.info("=== H5ファイル内容 ===")
            f.visititems(print_structure)
            
            # モデル設定の確認
            if 'model_config' in f.attrs:
                config = f.attrs['model_config']
                logger.info(f"モデル設定: {config[:200]}...")  # 最初の200文字
                
            return True
            
    except Exception as e:
        logger.error(f"H5ファイル読み込みエラー: {e}")
        return False

def check_problematic_layers(h5_path):
    """問題のあるレイヤーをチェック"""
    logger.info("問題のあるレイヤーをチェック中...")
    
    try:
        with h5py.File(h5_path, 'r') as f:
            if 'model_config' in f.attrs:
                import json
                config_str = f.attrs['model_config']
                if isinstance(config_str, bytes):
                    config_str = config_str.decode('utf-8')
                
                config = json.loads(config_str)
                
                # DepthwiseConv2Dレイヤーを検索
                def find_problematic_layers(obj, path=""):
                    if isinstance(obj, dict):
                        if obj.get('class_name') == 'DepthwiseConv2D':
                            if 'groups' in obj.get('config', {}):
                                logger.warning(f"問題のあるDepthwiseConv2D発見: {path}")
                                logger.warning(f"  config: {obj['config']}")
                                return True
                        
                        for key, value in obj.items():
                            if find_problematic_layers(value, f"{path}.{key}"):
                                return True
                    
                    elif isinstance(obj, list):
                        for i, item in enumerate(obj):
                            if find_problematic_layers(item, f"{path}[{i}]"):
                                return True
                    
                    return False
                
                has_problems = find_problematic_layers(config)
                
                if has_problems:
                    logger.error("❌ 問題のあるレイヤーが見つかりました")
                    return False
                else:
                    logger.info("✅ 問題のあるレイヤーは見つかりませんでした")
                    return True
                    
    except Exception as e:
        logger.error(f"レイヤーチェックエラー: {e}")
        return False

def suggest_alternative_approach(h5_path):
    """代替アプローチを提案"""
    logger.info("=== 代替アプローチの提案 ===")
    
    # 1. SavedModel形式への変換を提案
    logger.info("1. SavedModel形式への変換:")
    logger.info("   model/ディレクトリでtrain_tensorflow.pyを使用して新しいモデルを学習")
    
    # 2. 重みのみの抽出を提案
    logger.info("2. 重みのみの抽出:")
    logger.info("   H5ファイルから重みを抽出し、新しいモデルアーキテクチャで読み込み")
    
    # 3. TFLiteへの直接変換（もし可能なら）
    logger.info("3. 軽量読み込みの試行:")
    logger.info("   compile=False, カスタムオブジェクトなしで読み込み")

def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description="H5モデルファイルの診断と軽量変換")
    parser.add_argument("--input", "-i", required=True, help="入力H5ファイル")
    parser.add_argument("--inspect", action="store_true", help="ファイル構造のみを調査")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        logger.error(f"ファイルが見つかりません: {args.input}")
        return 1
    
    # ファイルサイズ確認
    file_size = os.path.getsize(args.input) / (1024 * 1024)
    logger.info(f"ファイルサイズ: {file_size:.1f} MB")
    
    # H5ファイル構造の調査
    if not inspect_h5_model(args.input):
        return 1
    
    # 問題のあるレイヤーのチェック
    if not check_problematic_layers(args.input):
        suggest_alternative_approach(args.input)
        return 1
    
    if args.inspect:
        logger.info("✅ 構造調査完了")
        return 0
    
    # 軽量読み込みを試行
    logger.info("軽量読み込みを試行中...")
    try:
        import tensorflow as tf
        
        # 最小限の設定で読み込み
        logger.info("最小限設定で読み込み中...")
        model = tf.keras.models.load_model(args.input, compile=False)
        logger.info("✅ 軽量読み込み成功！")
        
        # モデル概要を表示
        logger.info("=== モデル概要 ===")
        model.summary(print_fn=logger.info)
        
        return 0
        
    except Exception as e:
        logger.error(f"軽量読み込みも失敗: {e}")
        suggest_alternative_approach(args.input)
        return 1

if __name__ == "__main__":
    sys.exit(main())
