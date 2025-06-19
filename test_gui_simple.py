#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
簡単なGUIテスト
"""

try:
    import FreeSimpleGUI as sg
    print("FreeSimpleGUI imported successfully")
    
    # テーマ設定
    sg.theme('LightBlue3')
    print("Theme set successfully")
    
    # 簡単なウィンドウを作成
    layout = [
        [sg.Text('Hello World!')],
        [sg.Button('OK'), sg.Button('Cancel')]
    ]
    
    window = sg.Window('Test Window', layout)
    print("Window created successfully")
    
    # イベントループ
    while True:
        event, values = window.read()
        print(f"Event: {event}, Values: {values}")
        
        if event in (sg.WIN_CLOSED, 'Cancel'):
            break
        elif event == 'OK':
            sg.popup('Hello from FreeSimpleGUI!')
    
    window.close()
    print("Window closed successfully")
    
except ImportError as e:
    print(f"Import error: {e}")
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()