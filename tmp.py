def show_edit_dialog(self, title, prompt, initial_value, event=None):
	"""返回用户输入的新值，点击确定返回新值，取消返回 None。
	对话框按钮始终可见，即使窗口被缩小也不会被遮挡。
	按 Enter 确定，按 Esc 取消。"""
	dialog = tk.Toplevel(self.root)
	dialog.title(title)
	dialog.geometry("500x200")
	dialog.resizable(True, True)
	dialog.transient(self.root)
	dialog.grab_set()
	dialog.minsize(300, 150)

	# 根据鼠标位置放置窗口
	if event:
		x = event.x_root + 20
		y = event.y_root + 20
		screen_w = self.root.winfo_screenwidth()
		screen_h = self.root.winfo_screenheight()
		w, h = 500, 200
		if x + w > screen_w:
			x = screen_w - w - 20
		if y + h > screen_h:
			y = screen_h - h - 40
		dialog.geometry(f"+{x}+{y}")

	# 提示标签
	ttk.Label(dialog, text=prompt).pack(padx=10, pady=(10, 0), anchor="w")

	result = [None]

	def on_ok():
		result[0] = text_widget.get("1.0", "end-1c")
		dialog.destroy()

	def on_cancel():
		dialog.destroy()

	# 按钮样式（取消红色，确定绿色）
	style = ttk.Style(dialog)
	style.configure("Red.TButton", foreground="red", font=("TkDefaultFont", 9, "bold"))
	style.configure("Green.TButton", foreground="green", font=("TkDefaultFont", 9, "bold"))

	# 按钮框架固定在底部
	btn_frame = ttk.Frame(dialog)
	btn_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=(0, 10))
	ttk.Button(btn_frame, text="确定", command=on_ok, style="Green.TButton").pack(side=tk.RIGHT, padx=5)
	ttk.Button(btn_frame, text="取消", command=on_cancel, style="Red.TButton").pack(side=tk.RIGHT, padx=5)

	# 文本编辑区域
	text_widget = tk.Text(dialog, wrap=tk.WORD, font=("TkDefaultFont", 11))
	text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
	text_widget.insert("1.0", initial_value)

	# ---------- 新增热键 ----------
	dialog.bind("<Escape>", lambda e: on_cancel())          # Esc -> 取消
	def on_text_return(event):
		on_ok()
		return "break"   # 阻止默认换行，使 Enter 变为确定
	text_widget.bind("<Return>", on_text_return)            # Enter -> 确定
	# -----------------------------

	self.root.wait_window(dialog)
	return result[0]