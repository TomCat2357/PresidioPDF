#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flet動作テスト用の簡単なアプリケーション
"""

import flet as ft


def main(page: ft.Page):
    """メイン関数"""
    print("Fletアプリケーション開始")
    
    page.title = "Fletテスト"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.window_width = 800
    page.window_height = 600
    
    def button_clicked(e):
        t.value = "Hello, Flet!"
        page.update()
    
    t = ft.Text()
    
    page.add(
        ft.Column([
            ft.Text("PDF個人情報マスキングツール", size=24, weight=ft.FontWeight.BOLD),
            ft.Text("Fletテストアプリケーション", size=16),
            ft.ElevatedButton("クリックしてテスト", on_click=button_clicked),
            t
        ])
    )
    
    print("UIコンポーネント追加完了")


if __name__ == "__main__":
    print("Fletアプリケーション起動中...")
    try:
        ft.app(target=main, port=8889)
        print("アプリケーション終了")
    except Exception as e:
        print(f"エラーが発生しました: {e}")