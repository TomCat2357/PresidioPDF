#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ConfigManagerのテスト
"""

import pytest
import tempfile
import os
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from config_manager import ConfigManager


class TestConfigManager:
    """ConfigManagerのテストクラス"""
    
    def test_default_config(self):
        """デフォルト設定のテスト"""
        config_manager = ConfigManager()
        
        # デフォルト値の確認
        assert config_manager.get_masking_text_display_mode() == "verbose"
        assert config_manager.get_operation_mode() == "append"
        assert config_manager.should_remove_identical_annotations() == True
        assert config_manager.get_annotation_comparison_tolerance() == 0.1
    
    def test_operation_modes(self):
        """操作モードの設定テスト"""
        # append モード
        args = {'operation_mode': 'append'}
        config_manager = ConfigManager(args=args)
        assert config_manager.get_operation_mode() == "append"
        
        # clear_all モード
        args = {'operation_mode': 'clear_all'}
        config_manager = ConfigManager(args=args)
        assert config_manager.get_operation_mode() == "clear_all"
        
        # reset_and_append モード
        args = {'operation_mode': 'reset_and_append'}
        config_manager = ConfigManager(args=args)
        assert config_manager.get_operation_mode() == "reset_and_append"
    
    def test_masking_text_modes(self):
        """文字表示モードの設定テスト"""
        # silent モード
        args = {'masking_text_mode': 'silent'}
        config_manager = ConfigManager(args=args)
        assert config_manager.get_masking_text_display_mode() == "silent"
        
        # minimal モード
        args = {'masking_text_mode': 'minimal'}
        config_manager = ConfigManager(args=args)
        assert config_manager.get_masking_text_display_mode() == "minimal"
        
        # verbose モード
        args = {'masking_text_mode': 'verbose'}
        config_manager = ConfigManager(args=args)
        assert config_manager.get_masking_text_display_mode() == "verbose"
    
    def test_duplicate_removal_settings(self):
        """重複除去設定のテスト"""
        config_manager = ConfigManager()
        
        # デフォルト値
        assert config_manager.should_remove_identical_annotations() == True
        assert config_manager.get_annotation_comparison_tolerance() == 0.1
    
    def test_yaml_config_loading(self):
        """YAML設定ファイル読み込みテスト"""
        # テスト用のYAMLファイルを作成
        test_config = """
pdf_processing:
  masking:
    operation_mode: "clear_all"
    text_display_mode: "minimal"
    duplicate_removal:
      remove_identical: false
      comparison_tolerance: 0.5
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(test_config)
            temp_config_path = f.name
        
        try:
            config_manager = ConfigManager(config_file=temp_config_path)
            
            assert config_manager.get_operation_mode() == "clear_all"
            assert config_manager.get_masking_text_display_mode() == "minimal"
            assert config_manager.should_remove_identical_annotations() == False
            assert config_manager.get_annotation_comparison_tolerance() == 0.5
            
        finally:
            os.unlink(temp_config_path)
    
    def test_command_line_priority(self):
        """コマンドライン引数の優先度テスト"""
        # YAML設定
        test_config = """
pdf_processing:
  masking:
    operation_mode: "append"
    text_display_mode: "verbose"
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(test_config)
            temp_config_path = f.name
        
        try:
            # コマンドライン引数で上書き
            args = {
                'operation_mode': 'clear_all',
                'masking_text_mode': 'silent'
            }
            config_manager = ConfigManager(config_file=temp_config_path, args=args)
            
            # コマンドライン引数が優先されることを確認
            assert config_manager.get_operation_mode() == "clear_all"
            assert config_manager.get_masking_text_display_mode() == "silent"
            
        finally:
            os.unlink(temp_config_path)


if __name__ == "__main__":
    pytest.main([__file__])