#!/usr/bin/env python3
"""Simple test to verify GridLayout behavior with empty columns."""

from kivy.app import App
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label


class GridLayoutTestApp(App):
    def build(self):
        # Main container
        main = BoxLayout(orientation="vertical", padding=10, spacing=10)

        # Title
        title = Label(text="GridLayout Empty Column Test", size_hint_y=None, height=40)
        main.add_widget(title)

        # Test 1: GridLayout with cols=4, only 1 widget
        test1_label = Label(
            text="Test 1: GridLayout cols=4, only 1 widget", size_hint_y=None, height=30
        )
        main.add_widget(test1_label)

        grid1 = GridLayout(cols=4, spacing=5, size_hint_y=None, height=60)
        grid1.canvas.before.clear()
        from kivy.graphics import Color, Rectangle

        with grid1.canvas.before:
            Color(0.2, 0.2, 0.2, 1)
            Rectangle(pos=grid1.pos, size=grid1.size)

        # Add only 1 button to 4-column grid
        btn1 = Button(text="Only Widget", background_color=(0.3, 0.8, 0.3, 1))
        grid1.add_widget(btn1)

        main.add_widget(grid1)

        # Test 2: GridLayout with cols=4, 2 widgets
        test2_label = Label(
            text="Test 2: GridLayout cols=4, 2 widgets", size_hint_y=None, height=30
        )
        main.add_widget(test2_label)

        grid2 = GridLayout(cols=4, spacing=5, size_hint_y=None, height=60)
        with grid2.canvas.before:
            Color(0.2, 0.2, 0.2, 1)
            Rectangle(pos=grid2.pos, size=grid2.size)

        # Add 2 buttons to 4-column grid
        btn2a = Button(text="Widget 1", background_color=(0.3, 0.6, 0.8, 1))
        btn2b = Button(text="Widget 2", background_color=(0.8, 0.6, 0.3, 1))
        grid2.add_widget(btn2a)
        grid2.add_widget(btn2b)

        main.add_widget(grid2)

        # Test 3: GridLayout with cols=4, 4 widgets (full)
        test3_label = Label(
            text="Test 3: GridLayout cols=4, 4 widgets (full)",
            size_hint_y=None,
            height=30,
        )
        main.add_widget(test3_label)

        grid3 = GridLayout(cols=4, spacing=5, size_hint_y=None, height=60)
        with grid3.canvas.before:
            Color(0.2, 0.2, 0.2, 1)
            Rectangle(pos=grid3.pos, size=grid3.size)

        # Add 4 buttons to 4-column grid
        colors = [
            (0.8, 0.3, 0.3, 1),
            (0.3, 0.8, 0.3, 1),
            (0.3, 0.3, 0.8, 1),
            (0.8, 0.8, 0.3, 1),
        ]
        for i, color in enumerate(colors):
            btn = Button(text=f"Widget {i+1}", background_color=color)
            grid3.add_widget(btn)

        main.add_widget(grid3)

        # Test 4: GridLayout with cols=4, 1 visible + 3 opacity=0 widgets
        test4_label = Label(
            text="Test 4: 1 visible + 3 opacity=0 widgets", size_hint_y=None, height=30
        )
        main.add_widget(test4_label)

        grid4 = GridLayout(cols=4, spacing=5, size_hint_y=None, height=60)
        with grid4.canvas.before:
            Color(0.2, 0.2, 0.2, 1)
            Rectangle(pos=grid4.pos, size=grid4.size)

        # Add 1 visible button
        btn4a = Button(text="Visible", background_color=(0.3, 0.8, 0.3, 1))
        grid4.add_widget(btn4a)

        # Add 3 invisible buttons
        for i in range(3):
            btn = Button(text=f"Invisible {i+1}", background_color=(0.8, 0.3, 0.3, 1))
            btn.opacity = 0
            grid4.add_widget(btn)

        main.add_widget(grid4)

        # Instructions
        instructions = Label(
            text="Resize the window to see how each grid behaves.\n"
            "Do empty columns reserve space? Do opacity=0 widgets reserve space?",
            size_hint_y=None,
            height=60,
            text_size=(400, None),
            halign="center",
        )
        main.add_widget(instructions)

        return main


if __name__ == "__main__":
    GridLayoutTestApp().run()
