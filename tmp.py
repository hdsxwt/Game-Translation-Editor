def on_double_click(self, event):
    region = self.tree.identify_region(event.x, event.y)
    if region != "cell":
        return
    column = self.tree.identify_column(event.x)
    item = self.tree.selection()[0] if self.tree.selection() else None
    if not item:
        return
    col_index = int(column.replace("#", "")) - 1  # 0=No, 1=Key, 2=Source, 3=Target, 4=Revised
    if col_index <= 1:  # No和Key不可编辑
        self.log("No 列和 Key 列不可直接编辑")
        return

    current_values = list(self.tree.item(item, "values"))
    line_no = current_values[0]
    key = current_values[1]
    current_val = current_values[col_index]

    new_val = self.show_edit_dialog("编辑", f"修改 {key} 的值:", current_val, event=event)
    if new_val is not None and new_val != current_val:
        # 更新内部字典（仅 source 和 target）
        if col_index == 2:
            self.source_data[key] = new_val
        elif col_index == 3:
            self.target_data[key] = new_val
            self.target_modified = True
        # 更新 rows 中的对应值（包括 revised 列）
        for row in self.rows:
            if row[0] == line_no:
                row[col_index] = new_val
                break
        current_values[col_index] = new_val
        self.tree.item(item, values=current_values)
        col_name = {2: "Source", 3: "Target", 4: "Revised"}.get(col_index, "")
        self.log(f"更新行 {line_no} 键 '{key}' 的 {col_name} 值")