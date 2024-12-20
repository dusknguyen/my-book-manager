import os
import sqlite3
import subprocess
from tkinter import Tk, StringVar, Label, Button, Entry, ttk, Listbox, MULTIPLE, END, messagebox

DB_FILE = "books_manager.db"
BOOKS_FOLDER = "books"

# Khởi tạo cơ sở dữ liệu
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            path TEXT,
            file_type TEXT,
            status TEXT DEFAULT 'Chưa đọc'
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS book_categories (
            book_id INTEGER,
            category_id INTEGER,
            PRIMARY KEY (book_id, category_id),
            FOREIGN KEY (book_id) REFERENCES books(id),
            FOREIGN KEY (category_id) REFERENCES categories(id)
        )
    ''')
    conn.commit()
    conn.close()

# Quét folder và cập nhật cơ sở dữ liệu
def scan_books_folder():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    for root, _, files in os.walk(BOOKS_FOLDER):
        for file in files:
            if file.endswith(('.pdf', '.epub', '.mobi', '.docx')):
                path = os.path.join(root, file)
                file_type = os.path.splitext(file)[1].lower()
                cursor.execute("SELECT * FROM books WHERE path = ?", (path,))
                if cursor.fetchone() is None:
                    cursor.execute("INSERT INTO books (name, path, file_type) VALUES (?, ?, ?)", (file, path, file_type))

    conn.commit()
    conn.close()

# Lấy danh sách sách
def get_books(filter_categories=None, status_filter=None):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    query = '''
        SELECT DISTINCT books.id, books.name, books.file_type, books.status, books.path,
                        GROUP_CONCAT(categories.name, ', ') as categories
        FROM books
        LEFT JOIN book_categories ON books.id = book_categories.book_id
        LEFT JOIN categories ON book_categories.category_id = categories.id
        WHERE 1=1
    '''
    params = []

    if filter_categories:
        placeholders = ','.join('?' for _ in filter_categories)
        query += f" AND categories.name IN ({placeholders})"
        params.extend(filter_categories)

    if status_filter:
        query += " AND books.status = ?"
        params.append(status_filter)

    query += " GROUP BY books.id"

    cursor.execute(query, params)
    books = cursor.fetchall()
    conn.close()
    return books


# Mở sách
def open_book(file_path):
    try:
        if os.name == 'posix':
            subprocess.run(['xdg-open', file_path], check=True)
        elif os.name == 'nt':
            os.startfile(file_path)
        else:
            messagebox.showerror("Lỗi", "Không hỗ trợ mở file trên hệ điều hành này.")
    except Exception as e:
        messagebox.showerror("Lỗi", f"Không thể mở file: {e}")

# Thêm thể loại
def add_category(category_name):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO categories (name) VALUES (?)", (category_name,))
        conn.commit()
        messagebox.showinfo("Thành công", f"Đã thêm thể loại: {category_name}")
    except sqlite3.IntegrityError:
        messagebox.showerror("Lỗi", "Thể loại đã tồn tại.")
    finally:
        conn.close()

# Thêm thể loại vào sách
def assign_categories_to_book(book_id, category_names):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        for category_name in category_names:
            cursor.execute("SELECT id FROM categories WHERE name = ?", (category_name,))
            category_id = cursor.fetchone()
            if category_id:
                cursor.execute("INSERT OR IGNORE INTO book_categories (book_id, category_id) VALUES (?, ?)", (book_id, category_id[0]))
        conn.commit()
        messagebox.showinfo("Thành công", "Đã thêm thể loại vào sách.")
    except Exception as e:
        messagebox.showerror("Lỗi", f"Không thể thêm thể loại: {e}")
    finally:
        conn.close()

# Giao diện chính
def main():
    init_db()
    scan_books_folder()

    root = Tk()
    root.title("Book Manager")

    status_var = StringVar(value="Tất cả")
    Label(root, text="Lọc theo trạng thái:").pack()
    status_options = ["Tất cả", "Chưa đọc", "Đang đọc", "Đã đọc"]
    status_dropdown = ttk.Combobox(root, textvariable=status_var, values=status_options, state="readonly")
    status_dropdown.pack()

    Label(root, text="Lọc theo thể loại:").pack()
    category_listbox = Listbox(root, selectmode=MULTIPLE, height=10)
    category_listbox.pack(fill="x")

    def update_category_list():
        category_listbox.delete(0, END)
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM categories")
        for category in cursor.fetchall():
            category_listbox.insert(END, category[0])
        conn.close()

    def update_book_list():
        selected_categories = [category_listbox.get(i) for i in category_listbox.curselection()]
        selected_status = status_var.get()
        status_filter = None if selected_status == "Tất cả" else selected_status
        books = get_books(selected_categories, status_filter)
        tree.delete(*tree.get_children())
        for book in books:
            tree.insert("", "end", values=(book[1], book[2], book[3], book[5] or "Không có", book[4]), iid=book[0])


    def open_selected_book():
        selected_books = tree.selection()
        for item in selected_books:
            book_path = tree.item(item, "values")[3]
            open_book(book_path)

    def create_category():
        category_name = category_entry.get().strip()
        if category_name:
            add_category(category_name)
            update_category_list()
        else:
            messagebox.showwarning("Lỗi", "Tên thể loại không được để trống.")

    def assign_categories():
        selected_books = tree.selection()
        if not selected_books:
            messagebox.showwarning("Lỗi", "Vui lòng chọn ít nhất một cuốn sách.")
            return
        selected_categories = [category_listbox.get(i) for i in category_listbox.curselection()]
        if not selected_categories:
            messagebox.showwarning("Lỗi", "Vui lòng chọn ít nhất một thể loại.")
            return
        for book_id in selected_books:
            assign_categories_to_book(book_id, selected_categories)

    category_entry = Entry(root)
    category_entry.pack()
    Button(root, text="Thêm thể loại", command=create_category).pack()
    Button(root, text="Gán thể loại cho sách", command=assign_categories).pack()

    columns = ("name", "file_type", "status", "categories", "path")
    tree = ttk.Treeview(root, columns=columns, show="headings")
    tree.heading("name", text="Tên sách")
    tree.heading("file_type", text="Loại file")
    tree.heading("status", text="Trạng thái")
    tree.heading("categories", text="Thể loại")
    tree.pack(fill="both", expand=True)


    Button(root, text="Lọc sách", command=update_book_list).pack()
    Button(root, text="Mở sách", command=open_selected_book).pack()

    update_category_list()
    update_book_list()
    root.mainloop()

if __name__ == "__main__":
    main()
