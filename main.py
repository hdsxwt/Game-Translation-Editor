import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import hashlib
import random
import requests
import threading
import json
import os

from datetime import datetime

CONFIG_FILE = "config.json"

# ===================== 百度翻译 API 封装 =====================
def baidu_translate(q, from_lang, to_lang, appid, secret_key):
	"""调用百度通用翻译API，返回翻译后的文本"""
	if not q or not q.strip():
		return ""
	salt = str(random.randint(32768, 65536))
	sign_str = appid + q + salt + secret_key
	sign = hashlib.md5(sign_str.encode()).hexdigest()
	url = "https://api.fanyi.baidu.com/api/trans/vip/translate"
	params = {
		"q": q,
		"from": from_lang,
		"to": to_lang,
		"appid": appid,
		"salt": salt,
		"sign": sign,
	}
	resp = requests.get(url, params=params, timeout=5)
	result = resp.json()
	if "trans_result" in result:
		return result["trans_result"][0]["dst"]
	else:
		error_msg = result.get("error_msg", "Unknown error")
		raise Exception(f"Baidu API error: {error_msg}")

# ===================== 主应用程序 =====================
class TransEditorApp:
	def __init__(self, root):
		self.root = root
		self.root.title("游戏翻译编辑器 - Game Translation Editor")
		self.root.geometry("1000x650")

		# 数据存储
		self.source_data = {}   # 源语言键值对
		self.target_data = {}   # 目标语言键值对
		self.rows = []          # 表格显示用: [key, source_text, target_text]
		self.source_lang = "EN"
		self.target_lang = "CN"
		self.source_file = None
		self.target_file = None

		# 排序状态
		self.sort_column = None
		self.sort_reverse = False

		# 百度API配置
		self.baidu_appid = ""
		self.baidu_secret = ""

		# 创建界面组件
		self.create_menu()
		self.create_toolbar()
		self.create_filter_frame()
		self.create_table()
		self.create_log_frame()

		self.load_config()
		# 自动加载上次打开的文件（如果存在）
		if self.source_file and os.path.exists(self.source_file):
			self.load_source_file(silent=True)   # 稍后定义 silent 参数
		if self.target_file and os.path.exists(self.target_file):
			self.load_target_file(silent=True)
		
		# 初始化日志
		self.log("应用启动成功。")
		self.root.protocol("WM_DELETE_WINDOW", self.on_close)

	# ---------- 界面布局 ----------
	def create_menu(self):
		menubar = tk.Menu(self.root)
		file_menu = tk.Menu(menubar, tearoff=0)
		file_menu.add_command(label="加载源文件 (Source)", command=self.load_source_file)
		file_menu.add_command(label="加载目标文件 (Target)", command=self.load_target_file)
		file_menu.add_separator()
		file_menu.add_command(label="退出", command=self.root.quit)
		menubar.add_cascade(label="文件", menu=file_menu)

		settings_menu = tk.Menu(menubar, tearoff=0)
		settings_menu.add_command(label="百度翻译API设置", command=self.setup_baidu_api)
		menubar.add_cascade(label="设置", menu=settings_menu)
		self.root.config(menu=menubar)

	def create_toolbar(self):
		toolbar = ttk.Frame(self.root)
		toolbar.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

		ttk.Button(toolbar, text="加载源文件", command=self.load_source_file).pack(side=tk.LEFT, padx=2)
		ttk.Button(toolbar, text="加载目标文件", command=self.load_target_file).pack(side=tk.LEFT, padx=2)
		ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
		ttk.Button(toolbar, text="交换语言方向", command=self.swap_languages).pack(side=tk.LEFT, padx=2)
		ttk.Button(toolbar, text="翻译选中行", command=self.translate_selected).pack(side=tk.LEFT, padx=2)
		ttk.Button(toolbar, text="百度API设置", command=self.setup_baidu_api).pack(side=tk.LEFT, padx=2)

	def create_filter_frame(self):
		filter_frame = ttk.Frame(self.root)
		filter_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=2)

		# 筛选
		ttk.Label(filter_frame, text="筛选:").pack(side=tk.LEFT)
		self.filter_var = tk.StringVar()
		self.filter_var.trace_add("write", self.on_filter_changed)
		ttk.Entry(filter_frame, textvariable=self.filter_var, width=40).pack(side=tk.LEFT, padx=5)

		ttk.Label(filter_frame, text="(匹配Key或当前源/目标文本)").pack(side=tk.LEFT)

		# 搜索
		ttk.Label(filter_frame, text="搜索:").pack(side=tk.LEFT)
		self.search_var = tk.StringVar()
		search_entry = ttk.Entry(filter_frame, textvariable=self.search_var, width=30)
		search_entry.pack(side=tk.LEFT, padx=5)
		search_entry.bind("<Return>", self.on_search_enter)   # 回车触发搜索

		search_btn = ttk.Button(filter_frame, text="查找下一个", command=self.search_in_table)
		search_btn.pack(side=tk.LEFT, padx=2)

	def create_table(self):
		table_frame = ttk.Frame(self.root)
		table_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5)

		# Treeview 表格
		columns = ("no", "key", "source", "target")
		self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="extended")
		self.tree.heading("no", text="No", command=lambda: self.sort_by("no"))
		self.tree.heading("key", text="Key", command=lambda: self.sort_by("key"))
		self.tree.heading("source", text=f"Source ({self.source_lang})", command=lambda: self.sort_by("source"))
		self.tree.heading("target", text=f"Target ({self.target_lang})", command=lambda: self.sort_by("target"))
		self.tree.column("no", width=50, anchor="center")
		self.tree.column("key", width=200)
		self.tree.column("source", width=350)
		self.tree.column("target", width=350)

		# 滚动条
		vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
		hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
		self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

		self.tree.grid(row=0, column=0, sticky="nsew")
		vsb.grid(row=0, column=1, sticky="ns")
		hsb.grid(row=1, column=0, sticky="ew")
		table_frame.rowconfigure(0, weight=1)
		table_frame.columnconfigure(0, weight=1)

		# 绑定双击编辑事件
		self.tree.bind("<Double-1>", self.on_double_click)

	def create_log_frame(self):
		log_frame = ttk.LabelFrame(self.root, text="日志 (Log)", padding=5)
		log_frame.pack(side=tk.BOTTOM, fill=tk.BOTH, padx=5, pady=5)
		log_frame.columnconfigure(0, weight=1)
		log_frame.rowconfigure(0, weight=1)

		self.log_text = tk.Text(log_frame, height=8, state=tk.DISABLED, wrap=tk.WORD)
		log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
		self.log_text.configure(yscrollcommand=log_scroll.set)

		self.log_text.grid(row=0, column=0, sticky="nsew")
		log_scroll.grid(row=0, column=1, sticky="ns")

	# ---------- 日志方法 ----------
	def log(self, msg):
		timestamp = datetime.now().strftime("%H:%M:%S")
		line = f"[{timestamp}] {msg}\n"
		self.log_text.configure(state=tk.NORMAL)
		self.log_text.insert(tk.END, line)
		self.log_text.see(tk.END)
		self.log_text.configure(state=tk.DISABLED)

	# ---------- 文件解析 ----------
	def parse_file(self, filepath, lang_label):
		"""解析翻译文件，返回 (键值对字典, 注释数, 标注数)"""
		data = {}
		comments = 0
		labels = 0
		try:
			with open(filepath, "r", encoding="utf-8") as f:
				lines = f.readlines()
		except Exception as e:
			messagebox.showerror("错误", f"无法读取文件 {filepath} : {e}")
			self.log(f"读取文件失败: {filepath} - {e}")
			return None, 0, 0

		for line in lines:
			line = line.strip()
			if not line:
				continue
			if line.startswith("//"):
				comments += 1
				continue
			if line.startswith("==") and line.endswith("=="):
				labels += 1
				continue
			# 键值对
			if "=" in line:
				key, _, value = line.partition("=")
				key = key.strip()
				value = value.strip()
				if key:
					data[key] = value
				# key为空的行忽略
			# 其他无等号的行忽略，不视为错误
		self.log(f"解析 {lang_label} 文件完成: {filepath} -> {len(data)} 个键值对, 注释 {comments} 行, 标注 {labels} 行")
		return data, comments, labels

	def load_source_file(self, path=None, silent=False):
		"""加载源语言文件。若提供 path 则直接使用，否则弹出选择对话框"""
		if not path:
			if not silent:
				path = filedialog.askopenfilename(title="选择源语言文件 (如 EN.txt)",
												filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
			else:
				path = self.source_file  # 使用上次路径
		if not path:
			return
		self.source_file = path
		data, _, _ = self.parse_file(path, "源语言(Source)")
		if data is not None:
			self.source_data = data
			self.log(f"源语言文件已加载，共 {len(self.source_data)} 条记录")
			self.refresh_table()

	def load_target_file(self, path=None, silent=False):
		"""加载目标语言文件"""
		if not path:
			if not silent:
				path = filedialog.askopenfilename(title="选择目标语言文件 (如 CN.txt)",
												filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
			else:
				path = self.target_file
		if not path:
			return
		self.target_file = path
		data, _, _ = self.parse_file(path, "目标语言(Target)")
		if data is not None:
			self.target_data = data
			self.log(f"目标语言文件已加载，共 {len(self.target_data)} 条记录")
			self.refresh_table()

	# ---------- 表格数据构建与刷新 ----------
	def build_rows(self):
		"""根据当前 source_data 和 target_data 以及语言方向构建行列表"""
		all_keys = set(self.source_data.keys()) | set(self.target_data.keys())
		rows = []
		for key in sorted(all_keys):   # 默认按键排序
			src_val = self.source_data.get(key, "")
			tgt_val = self.target_data.get(key, "")
			rows.append([key, src_val, tgt_val])
		return rows

	def refresh_table(self):
		if not self.source_data and not self.target_data:
			self.rows = []
		else:
			self.rows = self.build_rows()
		self.apply_filter_and_sort()

	def apply_filter_and_sort(self):
		filter_text = self.filter_var.get().strip().lower()
		
		# 筛选
		filtered = []
		for row in self.rows:   # row: [key, source, target]
			if not filter_text:
				filtered.append(row)
			else:
				if (filter_text in str(row[0]).lower() or 
					filter_text in str(row[1]).lower() or 
					filter_text in str(row[2]).lower()):
					filtered.append(row)
		
		# 排序
		if self.sort_column is not None:
			col_idx = {"no": None, "key": 0, "source": 1, "target": 2}.get(self.sort_column)
			if col_idx is not None:   # 不是 no 列
				filtered.sort(key=lambda x: str(x[col_idx]).lower(), reverse=self.sort_reverse)
			else:  # no 列特殊处理：按数字排序
				# filtered 已是有序列表，但需要根据 self.sort_reverse 反转
				if self.sort_reverse:
					filtered.reverse()
				# 否则保持原顺序
		# 更新treeview
		self.tree.delete(*self.tree.get_children())
		for i, row in enumerate(filtered):
			self.tree.insert("", tk.END, values=[i+1] + row)  # row = [key, source, target]

		self.tree.heading("source", text=f"Source ({self.source_lang})")
		self.tree.heading("target", text=f"Target ({self.target_lang})")
		self.log(f"表格已刷新，当前显示 {len(filtered)} 行")

	def on_filter_changed(self, *args):
		self.apply_filter_and_sort()

	def sort_by(self, column):
		if self.sort_column == column:
			self.sort_reverse = not self.sort_reverse
		else:
			self.sort_column = column
			self.sort_reverse = False
		self.apply_filter_and_sort()
		direction = "降序" if self.sort_reverse else "升序"
		self.log(f"按 {column} 列{direction}排序")

	# ---------- 单元格编辑 ----------
	def on_double_click(self, event):
		region = self.tree.identify_region(event.x, event.y)
		if region != "cell":
			return
		column = self.tree.identify_column(event.x)   # 返回 '#1' ~ '#4'
		item = self.tree.selection()[0] if self.tree.selection() else None
		if not item:
			return

		col_index = int(column.replace("#", "")) - 1  # 0=No, 1=Key, 2=Source, 3=Target
		if col_index <= 1:  # No 列和 Key 列不可编辑
			self.log("No 列和 Key 列不可直接编辑")
			return

		current_values = list(self.tree.item(item, "values"))
		current_val = current_values[col_index]  # 例如 source 或 target

		new_val = self.show_edit_dialog("编辑", f"修改当前值:", current_val, event=event)
		if new_val is not None and new_val != current_val:
			key = current_values[1]  # Key 在索引1
			# 更新内部 rows
			for row in self.rows:
				if row[0] == key:
					row[col_index - 1] = new_val     # row 只有 [key, source, target]，source索引1，target索引2
					break
			# 同步字典
			if col_index == 2:  # Source
				self.source_data[key] = new_val
			elif col_index == 3:  # Target
				self.target_data[key] = new_val

			current_values[col_index] = new_val
			self.tree.item(item, values=current_values)
			self.log(f"更新键 '{key}' 的 {'Source' if col_index==2 else 'Target'} 值")

	def on_search_enter(self, event):
		self.search_in_table()

	# ---------- 语言交换 ----------
	def swap_languages(self):
		# 交换字典
		self.source_data, self.target_data = self.target_data, self.source_data
		# 交换语言标签
		self.source_lang, self.target_lang = self.target_lang, self.source_lang
		# 重建行数据
		self.rows = self.build_rows()
		self.apply_filter_and_sort()
		self.log(f"已交换语言方向。当前 Source: {self.source_lang}, Target: {self.target_lang}")

	def search_in_table(self, event=None):
		"""
		在当前显示的行中（筛选之后的）查找下一个匹配项，
		匹配列：Key、Source、Target（模糊匹配，不区分大小写）
		"""
		search_text = self.search_var.get().strip()
		if not search_text:
			self.log("请输入搜索关键词")	
			return

		# 获取当前所有可见行的 item ID 列表（顺序与显示一致）
		children = self.tree.get_children()
		if not children:
			self.log("表格为空，无法搜索")
			return

		# 确定当前选中的行索引（如果有），从它的下一个开始查
		current_selection = self.tree.selection()
		if current_selection:
			try:
				start_idx = children.index(current_selection[0])
			except ValueError:
				start_idx = -1
		else:
			start_idx = -1

		# 从下一行开始循环查找
		search_order = range(start_idx + 1, len(children))
		# 如果到末尾还没找到，从头再找（循环）
		found_item = None
		for i in search_order:
			item = children[i]
			values = self.tree.item(item, "values")
			# 在 key, source, target 中任意匹配
			if (search_text.lower() in str(values[1]).lower() or
				search_text.lower() in str(values[2]).lower() or
				search_text.lower() in str(values[3]).lower()):
				found_item = item
				break

		if found_item:
			# 选中并滚动到可见
			self.tree.selection_set(found_item)
			self.tree.see(found_item)
			self.log(f"找到匹配: {search_text}")
		else:
			# 循环到开头再找一遍（如果启用循环）
			# 如果找不到，提示
			self.log(f"未找到包含 '{search_text}' 的行")

	# ---------- 百度翻译选中行 ----------
	def translate_selected(self):
		if not self.baidu_appid or not self.baidu_secret:
			messagebox.showwarning("未配置API", "请先在设置中配置百度翻译API的APP ID和密钥")
			self.setup_baidu_api()
			if not self.baidu_appid or not self.baidu_secret:
				return

		selected_items = self.tree.selection()
		if not selected_items:
			messagebox.showinfo("提示", "请先在表格中选择至少一行")
			return

		# 确定语言代码 (百度API: en, zh)
		lang_map = {"EN": "en", "CN": "zh"}
		from_lang = lang_map.get(self.source_lang, "en")
		to_lang = lang_map.get(self.target_lang, "zh")

		# 在线程中执行翻译，避免界面卡顿
		def do_translate():
			success_count = 0
			fail_count = 0
			for item in selected_items:
				values = self.tree.item(item, "values")
				key = values[1]
				src_text = values[2]  # source列
				if not src_text.strip():
					self.log(f"跳过空文本行: {key}")
					continue
				try:
					translated = baidu_translate(src_text, from_lang, to_lang, 
												self.baidu_appid, self.baidu_secret)
					# 更新数据
					values_list = list(values)
					values_list[3] = translated  # target列
					self.tree.item(item, values=values_list)
					# 更新内部结构
					for row in self.rows:
						if row[0] == key:
							row[2] = translated
							break
					self.target_data[key] = translated
					success_count += 1
					self.log(f"翻译成功: {key}")
				except Exception as e:
					fail_count += 1
					self.log(f"翻译失败 [{key}]: {e}")
			self.log(f"批量翻译完成: 成功 {success_count} 条, 失败 {fail_count} 条")

		threading.Thread(target=do_translate, daemon=True).start()
		self.log("开始翻译选中的行...")

	# ---------- 百度API设置 ----------
	def setup_baidu_api(self):
		dialog = tk.Toplevel(self.root)
		dialog.title("百度翻译API设置")
		dialog.geometry("350x200")
		dialog.resizable(False, False)

		ttk.Label(dialog, text="APP ID:").pack(padx=10, pady=(15,0))
		appid_var = tk.StringVar(value=self.baidu_appid)
		ttk.Entry(dialog, textvariable=appid_var, width=40).pack(padx=10, pady=2)

		ttk.Label(dialog, text="密钥 (Secret Key):").pack(padx=10, pady=(10,0))
		secret_var = tk.StringVar(value=self.baidu_secret)
		ttk.Entry(dialog, textvariable=secret_var, width=40, show="*").pack(padx=10, pady=2)

		def save():
			self.baidu_appid = appid_var.get().strip()
			self.baidu_secret = secret_var.get().strip()
			self.log("百度翻译API配置已更新")
			self.save_config()
			dialog.destroy()

		ttk.Button(dialog, text="保存", command=save).pack(pady=20)
		dialog.transient(self.root)
		dialog.grab_set()
		self.root.wait_window(dialog)

	def show_edit_dialog(self, title, prompt, initial_value, event=None):
		"""返回用户输入的新值，点击确定返回新值，取消返回 None。
		对话框按钮始终可见，即使窗口被缩小也不会被遮挡。"""
		dialog = tk.Toplevel(self.root)
		dialog.title(title)
		dialog.geometry("500x200")
		dialog.resizable(True, True)
		dialog.transient(self.root)
		dialog.grab_set()
		dialog.minsize(300, 150)  # 防止窗口过小

		# 根据鼠标位置放置窗口（原有逻辑）
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

		# ---- 关键改动：先定义结果容器，再布局按钮框架，最后文本控件 ----
		result = [None]

		def on_ok():
			result[0] = text_widget.get("1.0", "end-1c")
			dialog.destroy()

		def on_cancel():
			dialog.destroy()

		# 定义按钮样式
		style = ttk.Style(dialog)
		style.configure("Red.TButton", background="red", font=("TkDefaultFont", 9, "bold"))
		style.configure("Green.TButton", background="green", font=("TkDefaultFont", 9, "bold"))

		# 按钮框架
		btn_frame = ttk.Frame(dialog)
		btn_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=(0, 10))
		ttk.Button(btn_frame, text="确定", command=on_ok, style="Green.TButton").pack(side=tk.RIGHT, padx=5)
		ttk.Button(btn_frame, text="取消", command=on_cancel, style="Red.TButton").pack(side=tk.RIGHT, padx=5)

		# 文本框
		text_widget = tk.Text(dialog, wrap=tk.WORD, font=("TkDefaultFont", 11))
		text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
		text_widget.insert("1.0", initial_value)

		self.root.wait_window(dialog)
		return result[0]

	def load_config(self):
		"""从 config.json 加载持久化设置，如果文件不存在或格式错误则使用默认空值"""
		if os.path.exists(CONFIG_FILE):
			try:
				with open(CONFIG_FILE, "r", encoding="utf-8") as f:
					config = json.load(f)
				self.source_file = config.get("source_file", None)
				self.target_file = config.get("target_file", None)
				self.baidu_appid = config.get("baidu_appid", "")
				self.baidu_secret = config.get("baidu_secret", "")
				self.log(f"配置文件已加载: {CONFIG_FILE}")
			except Exception as e:
				self.log(f"加载配置文件失败: {e}")
				# 使用默认空值
				self.source_file = None
				self.target_file = None
				self.baidu_appid = ""
				self.baidu_secret = ""
		else:
			self.log("未找到配置文件，使用默认设置。")

	def save_config(self):
		"""将当前设置保存到 config.json"""
		config = {
			"source_file": self.source_file,
			"target_file": self.target_file,
			"baidu_appid": self.baidu_appid,
			"baidu_secret": self.baidu_secret
		}
		try:
			with open(CONFIG_FILE, "w", encoding="utf-8") as f:
				json.dump(config, f, indent=4, ensure_ascii=False)
			self.log("设置已保存到配置文件。")
		except Exception as e:
			self.log(f"保存配置文件失败: {e}")

	def on_close(self):
		self.save_config()
		self.root.destroy()


# ===================== 启动入口 =====================
if __name__ == "__main__":
	root = tk.Tk()
	app = TransEditorApp(root)
	root.mainloop()