import datetime
import os
import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk


class SmartPOSApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Smart Grocery POS & Inventory Management System")
        self.root.geometry("1180x700")
        self.root.minsize(1050, 620)
        self.root.resizable(True, True)

        # In-memory cart: {product_id: {"name": str, "price": float, "qty": int, "max_stock": int}}
        self.cart = {}

        # Initialize SQLite database
        self.init_database()

        # Build UI
        self.create_widgets()

        # Load initial inventory into view
        self.load_inventory()

    # ---------------- DATABASE METHODS ----------------
    def init_database(self):
        """Initializes database and seeds sample products if empty."""
        self.conn = sqlite3.connect("inventory_pos.db")
        self.cursor = self.conn.cursor()

        # Inventory Table
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_code TEXT UNIQUE,
                item_name TEXT,
                category TEXT,
                price REAL,
                stock INTEGER
            )
            """
        )

        # Sales History Table
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS sales (
                bill_no TEXT PRIMARY KEY,
                customer_name TEXT,
                date_time TEXT,
                subtotal REAL,
                discount REAL,
                tax REAL,
                total REAL
            )
            """
        )
        self.conn.commit()

        # Seed initial grocery data if table is fresh
        self.cursor.execute("SELECT COUNT(*) FROM inventory")
        if self.cursor.fetchone()[0] == 0:
            sample_items = [
                ("ITM-101", "Basmati Rice (1kg)", "Grains", 120.0, 50),
                ("ITM-102", "Whole Wheat Flour (5kg)", "Grains", 240.0, 30),
                ("ITM-103", "Refined Sunflower Oil (1L)", "Oil", 155.0, 40),
                ("ITM-104", "Full Cream Milk (500ml)", "Dairy", 33.0, 60),
                ("ITM-105", "Farm Fresh Eggs (12 pcs)", "Dairy", 85.0, 25),
                ("ITM-106", "Granulated Sugar (1kg)", "Groceries", 45.0, 80),
                ("ITM-107", "Organic Iodized Salt (1kg)", "Groceries", 25.0, 90),
                ("ITM-108", "Assam Black Tea (250g)", "Beverages", 140.0, 35),
                ("ITM-109", "Instant Coffee (100g)", "Beverages", 210.0, 20),
                ("ITM-110", "Potato Chips (Family Pack)", "Snacks", 50.0, 45),
            ]
            self.cursor.executemany(
                "INSERT INTO inventory (item_code, item_name, category, price, stock) VALUES (?, ?, ?, ?, ?)",
                sample_items,
            )
            self.conn.commit()

    # ---------------- UI CONSTRUCTION ----------------
    def create_widgets(self):
        # 1. Top Header Banner
        header = tk.Frame(self.root, bg="#1B365D", height=60)
        header.pack(fill=tk.X)

        title_lbl = tk.Label(
            header,
            text="Smart Grocery Point-of-Sale (POS) & Inventory Engine",
            font=("Helvetica", 16, "bold"),
            fg="white",
            bg="#1B365D",
        )
        title_lbl.pack(pady=14)

        # 2. Main Workspace Layout
        main_container = tk.Frame(self.root, padx=12, pady=10)
        main_container.pack(fill=tk.BOTH, expand=True)

        # Left Panel: Inventory Catalog & Management (60% width)
        left_panel = tk.LabelFrame(
            main_container,
            text="Store Inventory & Catalog",
            font=("Helvetica", 11, "bold"),
            padx=10,
            pady=8,
        )
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))

        # Search / Filter Bar
        search_frame = tk.Frame(left_panel)
        search_frame.pack(fill=tk.X, pady=(0, 6))

        tk.Label(search_frame, text="Search Item / Code:", font=("Helvetica", 9, "bold")).pack(
            side=tk.LEFT, padx=(0, 5)
        )
        self.search_var = tk.StringVar()
        self.search_var.trace("w", lambda *args: self.filter_inventory())
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=22)
        search_entry.pack(side=tk.LEFT, padx=5)

        refresh_btn = tk.Button(
            search_frame,
            text="Refresh Inventory",
            bg="#34495E",
            fg="white",
            font=("Helvetica", 8, "bold"),
            command=self.load_inventory,
        )
        refresh_btn.pack(side=tk.RIGHT)

        # Inventory Table (Treeview)
        inv_cols = ("id", "code", "name", "category", "price", "stock")
        self.inv_tree = ttk.Treeview(left_panel, columns=inv_cols, show="headings", height=14)
        self.inv_tree.heading("id", text="ID")
        self.inv_tree.heading("code", text="Item Code")
        self.inv_tree.heading("name", text="Product Name")
        self.inv_tree.heading("category", text="Category")
        self.inv_tree.heading("price", text="Price (₹)")
        self.inv_tree.heading("stock", text="In-Stock")

        self.inv_tree.column("id", width=35, anchor="center")
        self.inv_tree.column("code", width=85, anchor="center")
        self.inv_tree.column("name", width=180)
        self.inv_tree.column("category", width=95)
        self.inv_tree.column("price", width=75, anchor="e")
        self.inv_tree.column("stock", width=65, anchor="center")

        inv_scroll = ttk.Scrollbar(left_panel, orient=tk.VERTICAL, command=self.inv_tree.yview)
        self.inv_tree.configure(yscroll=inv_scroll.set)
        inv_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.inv_tree.pack(fill=tk.BOTH, expand=True)

        # Tag for low stock visual alert (< 10 units)
        self.inv_tree.tag_configure("low_stock", background="#FADBD8")

        # Cart Addition Toolbar
        cart_add_frame = tk.Frame(left_panel, pady=8)
        cart_add_frame.pack(fill=tk.X)

        tk.Label(cart_add_frame, text="Select Quantity:", font=("Helvetica", 9, "bold")).pack(
            side=tk.LEFT, padx=(0, 6)
        )
        self.qty_spinbox = tk.Spinbox(cart_add_frame, from_=1, to=100, width=6, font=("Helvetica", 10))
        self.qty_spinbox.pack(side=tk.LEFT, padx=(0, 10))

        add_cart_btn = tk.Button(
            cart_add_frame,
            text="+ Add to Cart",
            bg="#27AE60",
            fg="white",
            font=("Helvetica", 9, "bold"),
            command=self.add_to_cart,
            padx=10,
        )
        add_cart_btn.pack(side=tk.LEFT)

        # Item Restock Form (Folded at Bottom of Left Panel)
        stock_frame = tk.LabelFrame(left_panel, text="Quick Product Restock / Price Update", pady=5, padx=5)
        stock_frame.pack(fill=tk.X, pady=(6, 0))

        tk.Label(stock_frame, text="Code:").grid(row=0, column=0, padx=2)
        self.m_code_entry = ttk.Entry(stock_frame, width=10)
        self.m_code_entry.grid(row=0, column=1, padx=4)

        tk.Label(stock_frame, text="Name:").grid(row=0, column=2, padx=2)
        self.m_name_entry = ttk.Entry(stock_frame, width=14)
        self.m_name_entry.grid(row=0, column=3, padx=4)

        tk.Label(stock_frame, text="Price:").grid(row=0, column=4, padx=2)
        self.m_price_entry = ttk.Entry(stock_frame, width=8)
        self.m_price_entry.grid(row=0, column=5, padx=4)

        tk.Label(stock_frame, text="Stock:").grid(row=0, column=6, padx=2)
        self.m_stock_entry = ttk.Entry(stock_frame, width=8)
        self.m_stock_entry.grid(row=0, column=7, padx=4)

        save_prod_btn = tk.Button(
            stock_frame,
            text="Save / Restock",
            bg="#2980B9",
            fg="white",
            font=("Helvetica", 8, "bold"),
            command=self.save_product_record,
        )
        save_prod_btn.grid(row=0, column=8, padx=6)

        # 3. Right Panel: Active Billing Cart (40% width)
        right_panel = tk.LabelFrame(
            main_container, text="Current Bill / Checkout Cart", font=("Helvetica", 11, "bold"), padx=10, pady=8
        )
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Customer Meta
        cust_frame = tk.Frame(right_panel)
        cust_frame.pack(fill=tk.X, pady=(0, 6))
        tk.Label(cust_frame, text="Customer:").pack(side=tk.LEFT)
        self.cust_name_entry = ttk.Entry(cust_frame, width=18)
        self.cust_name_entry.insert(0, "Walk-in Guest")
        self.cust_name_entry.pack(side=tk.LEFT, padx=6)

        # Cart Table
        cart_cols = ("code", "name", "price", "qty", "total")
        self.cart_tree = ttk.Treeview(right_panel, columns=cart_cols, show="headings", height=8)
        self.cart_tree.heading("code", text="Code")
        self.cart_tree.heading("name", text="Item")
        self.cart_tree.heading("price", text="Price")
        self.cart_tree.heading("qty", text="Qty")
        self.cart_tree.heading("total", text="Total (₹)")

        self.cart_tree.column("code", width=65, anchor="center")
        self.cart_tree.column("name", width=120)
        self.cart_tree.column("price", width=55, anchor="e")
        self.cart_tree.column("qty", width=45, anchor="center")
        self.cart_tree.column("total", width=65, anchor="e")

        cart_scroll = ttk.Scrollbar(right_panel, orient=tk.VERTICAL, command=self.cart_tree.yview)
        self.cart_tree.configure(yscroll=cart_scroll.set)
        cart_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.cart_tree.pack(fill=tk.BOTH, expand=True)

        # Cart action buttons
        cart_btn_row = tk.Frame(right_panel, pady=4)
        cart_btn_row.pack(fill=tk.X)
        remove_item_btn = tk.Button(
            cart_btn_row,
            text="Remove Item",
            bg="#E67E22",
            fg="white",
            font=("Helvetica", 8, "bold"),
            command=self.remove_cart_item,
        )
        remove_item_btn.pack(side=tk.LEFT, padx=2)

        clear_cart_btn = tk.Button(
            cart_btn_row,
            text="Clear Cart",
            bg="#95A5A6",
            fg="white",
            font=("Helvetica", 8, "bold"),
            command=self.clear_cart,
        )
        clear_cart_btn.pack(side=tk.LEFT, padx=4)

        # Summary Calculation Box
        calc_box = tk.Frame(right_panel, relief=tk.RIDGE, bd=1, padx=8, pady=8, bg="#F8F9FA")
        calc_box.pack(fill=tk.X, pady=(6, 8))

        # Subtotal
        tk.Label(calc_box, text="Subtotal:", font=("Helvetica", 9), bg="#F8F9FA").grid(row=0, column=0, sticky="w")
        self.subtotal_lbl = tk.Label(calc_box, text="₹ 0.00", font=("Helvetica", 9, "bold"), bg="#F8F9FA")
        self.subtotal_lbl.grid(row=0, column=1, sticky="e")

        # Discount %
        tk.Label(calc_box, text="Discount (%):", font=("Helvetica", 9), bg="#F8F9FA").grid(row=1, column=0, sticky="w")
        self.disc_spin = tk.Spinbox(
            calc_box, from_=0, to=50, width=5, font=("Helvetica", 9), command=self.update_bill_totals
        )
        self.disc_spin.grid(row=1, column=1, sticky="e")
        self.disc_spin.bind("<KeyRelease>", lambda e: self.update_bill_totals())

        # GST / Tax (5% Standard)
        tk.Label(calc_box, text="GST Tax (5%):", font=("Helvetica", 9), bg="#F8F9FA").grid(row=2, column=0, sticky="w")
        self.tax_lbl = tk.Label(calc_box, text="₹ 0.00", font=("Helvetica", 9), bg="#F8F9FA")
        self.tax_lbl.grid(row=2, column=1, sticky="e")

        ttk.Separator(calc_box, orient=tk.HORIZONTAL).grid(row=3, column=0, columnspan=2, sticky="ew", pady=4)

        # Net Payable
        tk.Label(calc_box, text="Net Payable:", font=("Helvetica", 11, "bold"), fg="#1B365D", bg="#F8F9FA").grid(
            row=4, column=0, sticky="w"
        )
        self.total_lbl = tk.Label(
            calc_box, text="₹ 0.00", font=("Helvetica", 12, "bold"), fg="#27AE60", bg="#F8F9FA"
        )
        self.total_lbl.grid(row=4, column=1, sticky="e")
        calc_box.columnconfigure(1, weight=1)

        # Checkout Button
        checkout_btn = tk.Button(
            right_panel,
            text="COMPLETE SALE & PRINT BILL",
            bg="#27AE60",
            fg="white",
            font=("Helvetica", 10, "bold"),
            pady=6,
            command=self.checkout_bill,
        )
        checkout_btn.pack(fill=tk.X)

    # ---------------- CONTROLLER LOGIC ----------------
    def load_inventory(self, query=None, params=()):
        """Fetches and renders inventory items."""
        for row in self.inv_tree.get_children():
            self.inv_tree.delete(row)

        if query is None:
            query = "SELECT id, item_code, item_name, category, price, stock FROM inventory ORDER BY item_code ASC"

        self.cursor.execute(query, params)
        for item in self.cursor.fetchall():
            i_id, code, name, cat, price, stock = item
            tag = "low_stock" if stock < 10 else ""
            self.inv_tree.insert(
                "",
                tk.END,
                values=(i_id, code, name, cat, f"{price:.2f}", stock),
                tags=(tag,),
            )

    def filter_inventory(self):
        """Filters catalog in real-time as user types in search box."""
        term = f"%{self.search_var.get().strip()}%"
        query = """
            SELECT id, item_code, item_name, category, price, stock 
            FROM inventory 
            WHERE item_code LIKE ? OR item_name LIKE ? OR category LIKE ?
            ORDER BY item_code ASC
        """
        self.load_inventory(query, (term, term, term))

    def add_to_cart(self):
        selected = self.inv_tree.selection()
        if not selected:
            messagebox.showwarning("Selection Missing", "Please select an item from the inventory catalog first.")
            return

        item_values = self.inv_tree.item(selected[0])["values"]
        item_id, code, name, cat, price_str, current_stock = item_values
        price = float(price_str)

        try:
            qty_to_add = int(self.qty_spinbox.get())
            if qty_to_add <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid Input", "Quantity must be a positive integer.")
            return

        already_in_cart = self.cart.get(code, {}).get("qty", 0)
        if already_in_cart + qty_to_add > current_stock:
            messagebox.showerror(
                "Stock Shortage",
                f"Insufficient stock for '{name}'.\nAvailable: {current_stock}\nAlready in Cart: {already_in_cart}",
            )
            return

        if code in self.cart:
            self.cart[code]["qty"] += qty_to_add
        else:
            self.cart[code] = {
                "name": name,
                "price": price,
                "qty": qty_to_add,
                "max_stock": current_stock,
            }

        self.refresh_cart_view()

    def remove_cart_item(self):
        selected = self.cart_tree.selection()
        if not selected:
            messagebox.showwarning("Notice", "Select an item inside the checkout cart to remove.")
            return

        code = self.cart_tree.item(selected[0])["values"][0]
        if code in self.cart:
            del self.cart[code]
            self.refresh_cart_view()

    def clear_cart(self):
        self.cart.clear()
        self.refresh_cart_view()

    def refresh_cart_view(self):
        for row in self.cart_tree.get_children():
            self.cart_tree.delete(row)

        for code, details in self.cart.items():
            line_total = details["price"] * details["qty"]
            self.cart_tree.insert(
                "",
                tk.END,
                values=(code, details["name"], f"{details['price']:.2f}", details["qty"], f"{line_total:.2f}"),
            )
        self.update_bill_totals()

    def update_bill_totals(self):
        subtotal = sum(d["price"] * d["qty"] for d in self.cart.values())
        try:
            disc_pct = float(self.disc_spin.get())
        except ValueError:
            disc_pct = 0.0

        discount_val = (subtotal * disc_pct) / 100.0
        taxable_amount = max(0.0, subtotal - discount_val)
        tax_val = taxable_amount * 0.05  # 5% GST
        grand_total = taxable_amount + tax_val

        self.subtotal_lbl.config(text=f"₹ {subtotal:.2f}")
        self.tax_lbl.config(text=f"₹ {tax_val:.2f}")
        self.total_lbl.config(text=f"₹ {grand_total:.2f}")

        return subtotal, discount_val, tax_val, grand_total

    def save_product_record(self):
        """Adds a new product or updates stock if product code already exists."""
        code = self.m_code_entry.get().strip().upper()
        name = self.m_name_entry.get().strip()
        try:
            price = float(self.m_price_entry.get())
            stock = int(self.m_stock_entry.get())
            if price <= 0 or stock < 0 or not code or not name:
                raise ValueError
        except ValueError:
            messagebox.showerror("Input Error", "Please fill valid Code, Name, positive Price, and Stock.")
            return

        # Check existing
        self.cursor.execute("SELECT id FROM inventory WHERE item_code = ?", (code,))
        existing = self.cursor.fetchone()

        if existing:
            self.cursor.execute(
                "UPDATE inventory SET item_name = ?, price = ?, stock = stock + ? WHERE item_code = ?",
                (name, price, stock, code),
            )
            action = "updated/restocked"
        else:
            self.cursor.execute(
                "INSERT INTO inventory (item_code, item_name, category, price, stock) VALUES (?, ?, 'General', ?, ?)",
                (code, name, price, stock),
            )
            action = "added"

        self.conn.commit()
        messagebox.showinfo("Success", f"Product '{code}' successfully {action}!")
        self.load_inventory()

        # Clear input boxes
        self.m_code_entry.delete(0, tk.END)
        self.m_name_entry.delete(0, tk.END)
        self.m_price_entry.delete(0, tk.END)
        self.m_stock_entry.delete(0, tk.END)

    def checkout_bill(self):
        if not self.cart:
            messagebox.showwarning("Empty Cart", "Cannot checkout an empty cart.")
            return

        subtotal, disc_amt, tax_amt, total = self.update_bill_totals()
        cust_name = self.cust_name_entry.get().strip() or "Walk-in Guest"
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        bill_no = f"INV-{datetime.datetime.now().strftime('%y%m%d-%H%M%S')}"

        # 1. Deduct Stock in Database
        for code, data in self.cart.items():
            self.cursor.execute(
                "UPDATE inventory SET stock = stock - ? WHERE item_code = ?", (data["qty"], code)
            )

        # 2. Record Sales Log
        self.cursor.execute(
            """
            INSERT INTO sales (bill_no, customer_name, date_time, subtotal, discount, tax, total)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (bill_no, cust_name, timestamp, subtotal, disc_amt, tax_amt, total),
        )
        self.conn.commit()

        # 3. Generate Printable Receipt Text
        receipt_text = self.build_receipt_string(bill_no, cust_name, timestamp, subtotal, disc_amt, tax_amt, total)

        # 4. Show Receipt Modal
        self.show_receipt_window(bill_no, receipt_text)

        # 5. Reset Cart and Refresh Catalog
        self.clear_cart()
        self.load_inventory()

    def build_receipt_string(self, bill_no, cust_name, timestamp, subtotal, discount, tax, total):
        line = "=" * 42
        dashed = "-" * 42
        r = [
            line,
            "       SMART GROCERY MART - POS RECEIPT",
            "   Campus Store, Tech Complex, Mohali",
            line,
            f" Invoice No : {bill_no}",
            f" Date/Time  : {timestamp}",
            f" Customer   : {cust_name}",
            dashed,
            f"{'Item':<18}{'Price':>6}{'Qty':>5}{'Total':>10}",
            dashed,
        ]

        for code, item in self.cart.items():
            name_snip = item["name"][:16]
            line_tot = item["price"] * item["qty"]
            r.append(f"{name_snip:<18}{item['price']:>6.2f}{item['qty']:>5}  ₹{line_tot:>7.2f}")

        r.extend(
            [
                dashed,
                f"{'Subtotal:':<28}₹ {subtotal:>9.2f}",
                f"{'Discount Applied:':<28}₹ {discount:>9.2f}",
                f"{'GST Tax (5%):':<28}₹ {tax:>9.2f}",
                line,
                f"{'NET PAYABLE TOTAL:':<28}₹ {total:>9.2f}",
                line,
                "      Thank you for shopping with us!",
                "       Please visit again soon :)",
                line,
            ]
        )
        return "\n".join(r)

    def show_receipt_window(self, bill_no, receipt_text):
        """Displays formatted bill in a Toplevel modal with an Export option."""
        modal = tk.Toplevel(self.root)
        modal.title(f"Receipt - {bill_no}")
        modal.geometry("450x540")
        modal.resizable(False, False)

        txt = tk.Text(modal, font=("Courier New", 10), padx=10, pady=10)
        txt.insert(tk.END, receipt_text)
        txt.config(state=tk.DISABLED)
        txt.pack(fill=tk.BOTH, expand=True)

        def save_receipt_file():
            filename = f"receipt_{bill_no}.txt"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(receipt_text)
            messagebox.showinfo("Export Successful", f"Saved receipt file as:\n{filename}")
            modal.destroy()

        btn_row = tk.Frame(modal, pady=8)
        btn_row.pack(fill=tk.X)

        tk.Button(
            btn_row,
            text="Save Receipt (.txt)",
            bg="#27AE60",
            fg="white",
            font=("Helvetica", 9, "bold"),
            command=save_receipt_file,
            width=18,
        ).pack(side=tk.LEFT, padx=20)

        tk.Button(
            btn_row,
            text="Close",
            bg="#7F8C8D",
            fg="white",
            font=("Helvetica", 9, "bold"),
            command=modal.destroy,
            width=12,
        ).pack(side=tk.RIGHT, padx=20)


if __name__ == "__main__":
    root = tk.Tk()
    app = SmartPOSApp(root)
    root.mainloop()