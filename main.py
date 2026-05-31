"""
Crystalix AI Duel Analyzer
Прозрачный оверлей поверх Minecraft для анализа дуэлей CSH
"""

import json
import os
import sys
import threading
import tkinter as tk
from tkinter import font as tkfont

from analyzer import analyze_screen, check_ollama, check_vision_model, load_config

def _base_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


CONFIG_PATH = os.path.join(_base_dir(), "config.json")


class CrystalixOverlay:
    def __init__(self):
        self.config = load_config()
        self.analyzing = False
        self.root = tk.Tk()
        self._setup_window()
        self._build_ui()
        self._try_bind_hotkey()
        self._check_ollama_status()

    def _setup_window(self):
        ov = self.config["overlay"]
        self.root.title("Crystalix AI")
        self.root.overrideredirect(True)
        self.root.wm_attributes("-topmost", True)
        self.root.wm_attributes("-alpha", ov.get("opacity", 0.92))

        try:
            self.root.wm_attributes("-transparentcolor", "")
        except Exception:
            pass

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        w = ov.get("width", 380)
        h = ov.get("height", 220)

        x_offset = ov.get("position_x", -400)
        y_offset = ov.get("position_y", 10)

        if x_offset < 0:
            x = sw + x_offset - w
        else:
            x = x_offset
        y = y_offset

        self.root.geometry(f"{w}x{h}+{x}+{y}")
        self.root.configure(bg="#0d0d0d")
        self.root.resizable(False, False)

        self._drag_x = 0
        self._drag_y = 0
        self.root.bind("<ButtonPress-1>", self._on_drag_start)
        self.root.bind("<B1-Motion>", self._on_drag_motion)

    def _on_drag_start(self, event):
        self._drag_x = event.x
        self._drag_y = event.y

    def _on_drag_motion(self, event):
        x = self.root.winfo_x() + (event.x - self._drag_x)
        y = self.root.winfo_y() + (event.y - self._drag_y)
        self.root.geometry(f"+{x}+{y}")

    def _build_ui(self):
        ov = self.config["overlay"]
        fs = ov.get("font_size", 11)
        hotkey = self.config.get("hotkey", "F9")

        BG = "#0d0d0d"
        ACCENT = "#00e5ff"
        WARN = "#ff9800"
        GOOD = "#69ff47"
        BAD = "#ff4444"
        TEXT = "#e0e0e0"
        DIM = "#777"

        header = tk.Frame(self.root, bg="#1a1a2e", height=28)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(
            header,
            text="⚔  CRYSTALIX AI  ⚔",
            bg="#1a1a2e",
            fg=ACCENT,
            font=("Consolas", 9, "bold"),
        ).pack(side="left", padx=8, pady=4)

        self.status_dot = tk.Label(
            header,
            text="●",
            bg="#1a1a2e",
            fg=WARN,
            font=("Consolas", 10),
        )
        self.status_dot.pack(side="right", padx=4)

        self.status_label = tk.Label(
            header,
            text="проверка...",
            bg="#1a1a2e",
            fg=DIM,
            font=("Consolas", 8),
        )
        self.status_label.pack(side="right", padx=2)

        close_btn = tk.Label(
            header,
            text="✕",
            bg="#1a1a2e",
            fg="#555",
            font=("Consolas", 10),
            cursor="hand2",
        )
        close_btn.pack(side="right", padx=6)
        close_btn.bind("<Button-1>", lambda e: self.root.destroy())
        close_btn.bind("<Enter>", lambda e: close_btn.configure(fg="#ff4444"))
        close_btn.bind("<Leave>", lambda e: close_btn.configure(fg="#555"))

        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=6, pady=4)

        self.result_text = tk.Text(
            body,
            bg=BG,
            fg=TEXT,
            font=("Consolas", fs),
            relief="flat",
            bd=0,
            wrap="word",
            cursor="arrow",
            state="disabled",
            height=7,
        )
        self.result_text.pack(fill="both", expand=True)

        self.result_text.tag_configure("verdict_win", foreground=GOOD, font=("Consolas", fs, "bold"))
        self.result_text.tag_configure("verdict_lose", foreground=BAD, font=("Consolas", fs, "bold"))
        self.result_text.tag_configure("verdict_equal", foreground=WARN, font=("Consolas", fs, "bold"))
        self.result_text.tag_configure("accent", foreground=ACCENT)
        self.result_text.tag_configure("dim", foreground=DIM)
        self.result_text.tag_configure("warn", foreground=WARN)
        self.result_text.tag_configure("error", foreground=BAD)

        self._show_idle(hotkey)

        footer = tk.Frame(self.root, bg="#111", height=30)
        footer.pack(fill="x")
        footer.pack_propagate(False)

        self.analyze_btn = tk.Button(
            footer,
            text=f"⚡ Анализ [{hotkey}]",
            bg="#1a3a4a",
            fg=ACCENT,
            font=("Consolas", 9, "bold"),
            relief="flat",
            bd=0,
            cursor="hand2",
            activebackground="#0d2535",
            activeforeground=ACCENT,
            command=self.trigger_analysis,
        )
        self.analyze_btn.pack(side="left", fill="y", padx=(4, 2), pady=3)

        self.opacity_btn = tk.Button(
            footer,
            text="◐",
            bg="#1a1a2e",
            fg=DIM,
            font=("Consolas", 10),
            relief="flat",
            bd=0,
            cursor="hand2",
            command=self._toggle_opacity,
            width=2,
        )
        self.opacity_btn.pack(side="right", fill="y", padx=(2, 4), pady=3)
        self.opacity_btn.bind("<Enter>", lambda e: self.opacity_btn.configure(fg=ACCENT))
        self.opacity_btn.bind("<Leave>", lambda e: self.opacity_btn.configure(fg=DIM))

        self._opacity_states = [0.92, 0.6, 0.3]
        self._opacity_idx = 0

    def _toggle_opacity(self):
        self._opacity_idx = (self._opacity_idx + 1) % len(self._opacity_states)
        self.root.wm_attributes("-alpha", self._opacity_states[self._opacity_idx])

    def _show_idle(self, hotkey=None):
        if hotkey is None:
            hotkey = self.config.get("hotkey", "F9")
        self._set_text(
            f"Наведи игру на инвентарь противника\nи нажми [{hotkey}] или кнопку ниже.\n\n"
            f"ИИ проанализирует экран и скажет:\n"
            f"• Кто победит и с каким шансом\n"
            f"• Уровень угрозы\n"
            f"• Тактику победы",
            tag="dim",
        )

    def _set_text(self, text: str, tag: str = None):
        self.result_text.configure(state="normal")
        self.result_text.delete("1.0", "end")
        if tag:
            self.result_text.insert("end", text, tag)
        else:
            self._insert_colored(text)
        self.result_text.configure(state="disabled")

    def _insert_colored(self, text: str):
        lines = text.split("\n")
        for i, line in enumerate(lines):
            tag = None
            if "ВЕРДИКТ:" in line:
                if any(w in line for w in ["победишь", "Ты победишь", "Победа"]):
                    tag = "verdict_win"
                elif any(w in line for w in ["Противник", "проиграешь"]):
                    tag = "verdict_lose"
                else:
                    tag = "verdict_equal"
            elif "УГРОЗА:" in line:
                if "Критическая" in line or "Высокая" in line:
                    tag = "error"
                elif "Средняя" in line:
                    tag = "warn"
                else:
                    tag = "accent"
            elif "ШАНС" in line:
                tag = "accent"
            elif "СОВЕТ:" in line:
                tag = "accent"
            elif "АНАЛИЗ:" in line:
                tag = None

            if i > 0:
                self.result_text.insert("end", "\n")
            if tag:
                self.result_text.insert("end", line, tag)
            else:
                self.result_text.insert("end", line)

    def _check_ollama_status(self):
        def _check():
            cfg = self.config
            url = cfg.get("ollama_url", "http://localhost:11434")
            model = cfg.get("model", "llava")
            ok, models = check_ollama(url)
            if not ok:
                self.root.after(0, lambda: self._set_status("offline", "Ollama не запущена"))
            elif not any(model in m for m in models):
                self.root.after(0, lambda: self._set_status("warn", f"Нет модели {model}"))
            else:
                self.root.after(0, lambda: self._set_status("online", f"{model} готов"))

        threading.Thread(target=_check, daemon=True).start()

    def _set_status(self, state: str, msg: str):
        colors = {"online": "#69ff47", "warn": "#ff9800", "offline": "#ff4444"}
        color = colors.get(state, "#777")
        self.status_dot.configure(fg=color)
        self.status_label.configure(text=msg)

    def _try_bind_hotkey(self):
        hotkey = self.config.get("hotkey", "F9")
        try:
            import keyboard
            keyboard.add_hotkey(hotkey, self.trigger_analysis)
        except Exception:
            pass

    def trigger_analysis(self):
        if self.analyzing:
            return
        self.analyzing = True
        self.analyze_btn.configure(text="⏳ Анализ...", state="disabled")
        self._set_text("Захватываю экран...", tag="dim")

        def _run():
            def _progress(msg):
                self.root.after(0, lambda: self._set_text(msg + "\n(это займёт до 60 сек)", tag="dim"))

            result = analyze_screen(on_progress=_progress)
            self.root.after(0, lambda: self._on_result(result))

        threading.Thread(target=_run, daemon=True).start()

    def _on_result(self, result: dict):
        self.analyzing = False
        hotkey = self.config.get("hotkey", "F9")
        self.analyze_btn.configure(text=f"⚡ Анализ [{hotkey}]", state="normal")

        if result.get("error"):
            self._set_text(f"❌ {result['error']}", tag="error")
        else:
            text = result.get("text", "Нет ответа от модели")
            elapsed = result.get("elapsed", 0)
            self.result_text.configure(state="normal")
            self.result_text.delete("1.0", "end")
            self._insert_colored(text)
            self.result_text.insert("end", f"\n\n⏱ {elapsed}с", "dim")
            self.result_text.configure(state="disabled")

    def run(self):
        self.root.mainloop()


def main():
    print("Запуск Crystalix AI Overlay...")
    app = CrystalixOverlay()
    app.run()


if __name__ == "__main__":
    main()
