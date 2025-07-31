import customtkinter as ctk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import datetime
import uuid
import json
import os
import tempfile

# --- مكتبات جديدة للباركود والطباعة ---
try:
    import barcode
    from barcode.writer import ImageWriter
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import inch
    from reportlab.pdfgen import canvas
    LIBRARIES_INSTALLED = True
except ImportError:
    LIBRARIES_INSTALLED = False
# ----------------------------------------

# =================================================================================
# لوحة الألوان
# =================================================================================
BACKGROUND_COLOR = "#F5F6FA"
TEXT_COLOR = "#2C3E50"
PRIMARY_COLOR = "#4169E1"
BUTTON_HOVER_COLOR = "#34495E"
ACCENT_GOLD = "#F1C40F"
SUCCESS_COLOR = "#2ECC71"
ERROR_COLOR = "#E74C3C"
WHITE_COLOR = "#FFFFFF"

# =================================================================================
# 0. وظائف إدارة الملفات والبيانات
# =================================================================================
USER_DOCUMENTS_PATH = os.path.join(os.path.expanduser('~'), 'Documents')
APP_BASE_FOLDER = os.path.join(USER_DOCUMENTS_PATH, 'بيانات_برنامج_التسيير')
DATA_DIR = os.path.join(APP_BASE_FOLDER, 'data')

def create_data_files():
    if not os.path.exists(APP_BASE_FOLDER):
        os.makedirs(APP_BASE_FOLDER)
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    
    files_to_create = {
        "cash.json": {"balance": 0.0, "log": []},
        "products.json": {"products": {}},
        "debts.json": {"debts": {}},
        "repair.json": {"balance": 0.0, "log": [], "workers": {"علاء": 0.0, "حمزة": 0.0}, "debts": {}},
        "flexy.json": {"main_balance": 0.0, "credit_balance": 0.0, "profits_balance": 0.0, "credit_log": {}, "operations_log": []},
        "worker_payouts.json": {"payouts": []},
        "barcodes.json": {"printed_barcodes": []}
    }
    
    for filename, content in files_to_create.items():
        filepath = os.path.join(DATA_DIR, filename)
        if not os.path.exists(filepath):
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(content, f, ensure_ascii=False, indent=4)

def save_data(manager, filename):
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    
    filepath = os.path.join(DATA_DIR, filename)
    data = {}
    
    if filename == "cash.json":
        data = {"balance": manager.balance, "log": manager.log}
    elif filename == "products.json":
        data = {"products": manager.products}
    elif filename == "debts.json":
        data = {"debts": manager.debts}
    elif filename == "repair.json":
        data = {"balance": manager.balance, "log": manager.log, "workers": manager.workers, "debts": manager.debts}
    elif filename == "flexy.json":
        data = {"main_balance": manager.main_balance, "credit_balance": manager.credit_balance, 
                "profits_balance": manager.profits_balance, "credit_log": manager.credit_log, 
                "operations_log": manager.operations_log}
    elif filename == "barcodes.json":
        data = {"printed_barcodes": manager.printed_barcodes}
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def load_data(manager, filename):
    filepath = os.path.join(DATA_DIR, filename)
    if not os.path.exists(filepath):
        return
    
    with open(filepath, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
            if filename == "cash.json":
                manager.balance, manager.log = data.get("balance", 0.0), data.get("log", [])
            elif filename == "products.json":
                manager.products = data.get("products", {})
            elif filename == "debts.json":
                manager.debts = data.get("debts", {})
            elif filename == "repair.json":
                manager.balance, manager.log, manager.workers, manager.debts = (
                    data.get("balance", 0.0), data.get("log", []), 
                    data.get("workers", {"علاء": 0.0, "حمزة": 0.0}), 
                    data.get("debts", {})
                )
            elif filename == "flexy.json":
                manager.main_balance, manager.credit_balance, manager.profits_balance, manager.credit_log, manager.operations_log = (
                    data.get("main_balance", 0.0), data.get("credit_balance", 0.0), 
                    data.get("profits_balance", 0.0), data.get("credit_log", {}), 
                    data.get("operations_log", [])
                )
            elif filename == "barcodes.json":
                manager.printed_barcodes = data.get("printed_barcodes", [])
        except json.JSONDecodeError:
            pass

# =================================================================================
# 1. فئات إدارة البيانات (المنطق الخلفي - Models)
# =================================================================================
class CashBoxManager:
    def __init__(self):
        self.balance = 0.0
        self.log = []
        load_data(self, "cash.json")
    
    def add_funds(self, amount, description):
        if amount <= 0:
            return False, "المبلغ يجب أن يكون أكبر من صفر"
        self.balance += amount
        self._add_log_entry("إيداع", amount, description)
        return True, ""
    
    def record_expense(self, amount, description):
        if amount <= 0:
            return False, "المبلغ يجب أن يكون أكبر من صفر"
        if self.balance < amount:
            return False, f"رصيد الصندوق غير كافٍ. الرصيد الحالي: {self.balance:.2f}"
        self.balance -= amount
        self._add_log_entry("مصروف", -amount, description)
        return True, ""
    
    def _add_log_entry(self, op_type, amount, description):
        entry = {
            "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "type": op_type,
            "amount": amount,
            "description": description,
            "balance_after": self.balance
        }
        self.log.append(entry)
        save_data(self, "cash.json")

class ProductManager:
    def __init__(self, cash_box_manager):
        self.products = {}
        self.cash_box = cash_box_manager
        self._loaded_images = {}  # قاموس لتخزين الصور المحملة
        load_data(self, "products.json")
    
    def purchase_product(self, name, image_path, qr, quantity, purchase_price, sale_price):
        if not name:
            return False, "اسم المنتج لا يمكن أن يكون فارغًا."
        if name in self.products:
            return False, f"المنتج '{name}' موجود بالفعل. يمكنك تعديله من قسم المنتجات."
        
        total_cost = purchase_price * quantity
        if total_cost > 0:
            success, message = self.cash_box.record_expense(total_cost, f"شراء: {quantity}x {name}")
            if not success:
                return False, message
        
        self.products[name] = {
            'image': image_path,
            'qr': qr,
            'quantity': quantity,
            'purchase_price': purchase_price,
            'sale_price': sale_price
        }
        save_data(self, "products.json")
        return True, "تمت إضافة المنتج بنجاح."
    
    def update_product(self, old_name, new_data):
        new_name = new_data.get('name')
        if not new_name:
            return False, "اسم المنتج الجديد لا يمكن أن يكون فارغًا."
        if old_name != new_name and new_name in self.products:
            return False, f"الاسم الجديد '{new_name}' مستخدم بالفعل لمنتج آخر."
        
        product_data = {k: v for k, v in new_data.items() if k != 'name'}
        if old_name != new_name:
            del self.products[old_name]
        
        self.products[new_name] = product_data
        save_data(self, "products.json")
        return True, "تم تحديث المنتج بنجاح."
    
    def sell_product(self, name, quantity):
        if name not in self.products or self.products[name]['quantity'] < quantity:
            return False, "الكمية المطلوبة غير متوفرة في المخزون."
        self.products[name]['quantity'] -= quantity
        save_data(self, "products.json")
        return True, ""
    
    def delete_product(self, name):
        if name not in self.products:
            return False, "المنتج غير موجود."
        
        product = self.products[name]
        refund_value = product.get('quantity', 0) * product.get('purchase_price', 0)
        if refund_value > 0:
            self.cash_box.add_funds(refund_value, f"إرجاع قيمة حذف منتج: {product.get('quantity', 0)}x {name}")
        
        del self.products[name]
        save_data(self, "products.json")
        return True, ""
    
    def get_product_by_qr(self, qr):
        for name, data in self.products.items():
            if data['qr'] == qr:
                return name, data
        return None, None
    
    def get_product_image(self, image_path, size=(120, 120)):
        if not image_path or not os.path.exists(image_path):
            return None
        
        # تحقق إذا كانت الصورة محملة بالفعل في الذاكرة
        if image_path in self._loaded_images:
            return self._loaded_images[image_path]
        
        try:
            img = Image.open(image_path)
            img.thumbnail(size)
            photo = ImageTk.PhotoImage(img)
            self._loaded_images[image_path] = photo  # تخزين الصورة في الذاكرة
            return photo
        except Exception:
            return None
    
    def clear_image_cache(self):
        self._loaded_images.clear()

class DebtManager:
    def __init__(self, cash_box_manager):
        self.debts = {}
        self.cash_box = cash_box_manager
        load_data(self, "debts.json")
    
    def add_debt(self, client_name, total_debt, initial_payment=0.0):
        if client_name in self.debts:
            # إذا كان العميل موجود بالفعل، نضيف الدين الجديد إلى الدين القديم
            self.debts[client_name]['total'] += total_debt
            self.debts[client_name]['remaining'] += (total_debt - initial_payment)
            self.debts[client_name]['paid'] += initial_payment
        else:
            # إذا كان العميل جديد، ننشئ سجل دين جديد
            if initial_payment > 0:
                self.cash_box.add_funds(initial_payment, f"دفعة مقدمة من دين {client_name}")
            
            remaining = total_debt - initial_payment
            self.debts[client_name] = {
                'total': total_debt,
                'paid': initial_payment,
                'remaining': remaining,
                'date': datetime.datetime.now().strftime("%Y-%m-%d")
            }
        
        self.cash_box._add_log_entry("دين", initial_payment, f"تسجيل دين لـ {client_name} (مدفوع: {initial_payment})")
        save_data(self, "debts.json")
        return True, ""
    
    def settle_payment(self, client_name, amount):
        if client_name not in self.debts:
            return False, "العميل غير موجود."
        if amount > self.debts[client_name]['remaining']:
            return False, "المبلغ المدفوع أكبر من الدين المتبقي."
        
        self.debts[client_name]['paid'] += amount
        self.debts[client_name]['remaining'] -= amount
        self.cash_box.add_funds(amount, f"تسوية دين من {client_name}")
        save_data(self, "debts.json")
        return True, ""
    
    def delete_debt(self, client_name):
        if client_name in self.debts:
            del self.debts[client_name]
            save_data(self, "debts.json")
            return True, ""
        return False, "العميل غير موجود."

class RepairManager:
    def __init__(self):
        self.balance = 0.0
        self.log = []
        self.workers = {"علاء": 0.0, "حمزة": 0.0}
        self.debts = {}
        load_data(self, "repair.json")
    
    def _add_log(self, op_type, amount, description):
        entry = {
            "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "type": op_type,
            "amount": amount,
            "description": description,
            "balance_after": self.balance
        }
        self.log.append(entry)
        save_data(self, "repair.json")
    
    def _log_worker_payout(self, worker_name, amount):
        payout_data_file = os.path.join(DATA_DIR, "worker_payouts.json")
        try:
            with open(payout_data_file, 'r+', encoding='utf-8') as f:
                data = json.load(f) if os.path.getsize(payout_data_file) > 0 else {"payouts": []}
        except FileNotFoundError:
            data = {"payouts": []}
        
        payout_entry = {
            "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "worker_name": worker_name,
            "payout_amount": amount
        }
        data["payouts"].append(payout_entry)
        
        with open(payout_data_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    
    def record_purchase(self, amount):
        if amount <= 0:
            return False, "المبلغ يجب أن يكون أكبر من صفر."
        if self.balance < amount:
            return False, "رصيد الصندوق غير كافٍ."
        
        self.balance -= amount
        self._add_log("شراء (تصليح)", -amount, "تسجيل فاتورة شراء مستلزمات")
        return True, "تم تسجيل الشراء بنجاح."
    
    def record_sale(self, amount):
        if amount <= 0:
            return False, "المبلغ يجب أن يكون أكبر من صفر."
        
        self.balance += amount
        self._add_log("بيع (تصليح)", amount, "تسجيل مبلغ بيع/تصليح")
        return True, "تم تسجيل البيع بنجاح."
    
    def worker_withdrawal(self, worker_name, amount):
        if amount <= 0:
            return False, "المبلغ يجب أن يكون أكبر من صفر."
        if self.balance < amount:
            return False, "رصيد الصندوق غير كافٍ."
        
        self.balance -= amount
        self.workers[worker_name] += amount
        self._add_log(f"سحب العامل {worker_name}", -amount, f"أخذ العامل {worker_name} مبلغ {amount:.2f}")
        
        payouts_made = 0
        while self.workers[worker_name] >= 5000:
            self._log_worker_payout(worker_name, 5000.0)
            self.workers[worker_name] -= 5000
            payouts_made += 1
        
        save_data(self, "repair.json")
        message = f"تم تسجيل سحب مبلغ {amount:.2f} بنجاح."
        if payouts_made > 0:
            settlement_amount = payouts_made * 5000
            message += (f"\n\nتمت تسوية {payouts_made} دفعة (إجمالي {settlement_amount:.2f} د.ج) "
                       f"للعامل {worker_name}.\nالرصيد المتبقي: {self.workers[worker_name]:.2f} د.ج")
        return True, message
    
    def add_debt(self, client_name, amount):
        if client_name in self.debts:
            return False, "هذا العميل لديه دين سابق."
        
        self.debts[client_name] = {'total': amount, 'paid': 0, 'remaining': amount}
        self._add_log("دين تصليح", 0, f"تسجيل دين لـ {client_name} بمبلغ {amount:.2f}")
        return True, "تم تسجيل الدين بنجاح."
    
    def settle_debt(self, client_name, amount):
        if client_name not in self.debts:
            return False, "العميل غير موجود."
        if amount > self.debts[client_name]['remaining']:
            return False, "المبلغ المدفوع أكبر من الدين المتبقي."
        
        self.debts[client_name]['paid'] += amount
        self.debts[client_name]['remaining'] -= amount
        self.balance += amount
        self._add_log("تسديد دين", amount, f"سدد العميل {client_name} مبلغًا")
        
        if self.debts[client_name]['remaining'] == 0:
            del self.debts[client_name]
        
        save_data(self, "repair.json")
        return True, "تم تسجيل الدفعة بنجاح."

class FlexyManager:
    def __init__(self):
        self.main_balance, self.credit_balance, self.profits_balance = 0.0, 0.0, 0.0
        self.credit_log, self.operations_log = {}, []
        load_data(self, "flexy.json")
    
    def _add_op_log(self, op_type, amount, description):
        entry = {
            "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "type": op_type,
            "amount": f"{amount:.2f}",
            "description": description
        }
        self.operations_log.append(entry)
        save_data(self, "flexy.json")
    
    def add_main_funds(self, amount):
        if amount <= 0:
            return False, "المبلغ يجب أن يكون أكبر من صفر."
        
        self.main_balance += amount
        self._add_op_log("إيداع رئيسي", amount, "إضافة رصيد للصندوق الرئيسي")
        return True, "تم الإيداع بنجاح."
    
    def add_credit(self, amount):
        if amount <= 0:
            return False, "المبلغ يجب أن يكون أكبر من صفر."
        if self.main_balance < amount:
            return False, "رصيد الصندوق الرئيسي غير كافٍ."
        
        self.main_balance -= amount
        self.credit_balance += amount
        op_id = str(uuid.uuid4())
        self.credit_log[op_id] = {
            "amount": amount,
            "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        self._add_op_log("شراء رصيد", amount, "شراء رصيد شحن")
        return True, "تم شراء الرصيد بنجاح."
    
    def delete_credit(self, op_id):
        if op_id not in self.credit_log:
            return False, "العملية غير موجودة."
        
        amount_to_refund = self.credit_log[op_id]['amount']
        self.credit_balance -= amount_to_refund
        self.main_balance += amount_to_refund
        del self.credit_log[op_id]
        self._add_op_log("حذف شحن", -amount_to_refund, "إلغاء شحن وإرجاع المبلغ")
        return True, "تم حذف الشحن."
    
    def add_manual_profit(self, amount):
        # تم تعديل هذه الدالة لقبول المبالغ السالبة
        if amount == 0:
            return False, "المبلغ يجب أن يكون مختلفًا عن الصفر."
        
        self.profits_balance += amount
        op_type = "فائدة يدوية" if amount > 0 else "خصم يدوي"
        self._add_op_log(op_type, amount, "تعديل يدوي على صندوق الفوائد")
        return True, f"تمت {'إضافة' if amount > 0 else 'خصم'} الفائدة."
    
    def perform_transfer(self, transfer_type, amount):
        if amount <= 0:
            return False, "المبلغ يجب أن يكون أكبر من صفر."
        if self.credit_balance < amount:
            return False, "رصيد الشحن غير كافٍ."
        
        profit = 10 if transfer_type == "فلكسي" and amount < 500 else (
            20 if transfer_type == "فلكسي" else 50)
        
        self.credit_balance -= amount
        self.main_balance += amount
        self.profits_balance += profit
        self._add_op_log(f"تحويل {transfer_type}", amount, f"تحويل بمبلغ {amount:.2f} وفائدة {profit:.2f}")
        return True, "تم التحويل بنجاح."
    
    def perform_game_topup(self, game_name, amount, profit):
        if amount <= 0:
            return False, "المبلغ يجب أن يكون أكبر من صفر."
        if self.credit_balance < amount:
            return False, "رصيد الشحن غير كافٍ."
        
        self.credit_balance -= amount
        self.main_balance += amount
        self.profits_balance += profit
        self._add_op_log(f"شحن ألعاب", amount, f"شحن {game_name} بمبلغ {amount:.2f} وفائدة {profit:.2f}")
        return True, "تم الشحن بنجاح."

class BackupManager:
    def save_backup(self, data_to_save):
        default_filename = f"backup_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.json"
        filepath = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")],
            initialfile=default_filename,
            title="حفظ نسخة احتياطية"
        )
        if not filepath:
            return
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, ensure_ascii=False, indent=4)
            messagebox.showinfo("نجاح", "تم حفظ النسخة الاحتياطية بنجاح.")
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل حفظ النسخة الاحتياطية:\n{e}")
    
    def load_backup(self):
        filepath = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json")],
            title="استرجاع نسخة احتياطية"
        )
        if not filepath:
            return None
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if not all(k in data for k in ['shop_cash_box', 'products', 'shop_debts', 'repair', 'flexy']):
                messagebox.showerror("خطأ", "ملف النسخة الاحتياطية غير صالح.")
                return None
            
            return data
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل تحميل النسخة الاحتياطية:\n{e}")
            return None

class BarcodeManager:
    def __init__(self, product_manager):
        self.printed_barcodes = []
        self.product_manager = product_manager
        load_data(self, "barcodes.json")
    
    def generate_unique_barcode_value(self):
        while True:
            barcode_val = str(uuid.uuid4().int)[:12]
            if not self.is_barcode_used(barcode_val):
                return barcode_val
    
    def is_barcode_used(self, barcode_val):
        for product_data in self.product_manager.products.values():
            if product_data.get('qr') == barcode_val:
                return True
        
        for printed_barcode in self.printed_barcodes:
            if printed_barcode.get('barcode') == barcode_val:
                return True
        
        return False
    
    def log_printed_barcodes(self, barcodes_to_log):
        for barcode_val in barcodes_to_log:
            entry = {
                "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                "barcode": barcode_val,
            }
            self.printed_barcodes.append(entry)
        save_data(self, "barcodes.json")
    
    def print_barcodes(self, barcodes_to_print):
        if not LIBRARIES_INSTALLED:
            messagebox.showerror("خطأ", "المكتبات المطلوبة (python-barcode, reportlab) غير مثبتة.")
            return
        
        if not isinstance(barcodes_to_print, list):
            barcodes_to_print = [str(barcodes_to_print)]
        
        barcodes_to_print = [str(item) for item in barcodes_to_print]
        
        try:
            temp_pdf_path = os.path.join(tempfile.gettempdir(), f"barcodes_{uuid.uuid4().hex}.pdf")
            c = canvas.Canvas(temp_pdf_path, pagesize=A4)
            width, height = A4
            x_start, y_start = 0.5 * inch, height - 1 * inch
            x, y = x_start, y_start
            barcode_width, barcode_height = 2.0 * inch, 0.75 * inch
            x_gap, y_gap = 0.25 * inch, 0.25 * inch
            
            for barcode_val in barcodes_to_print:
                if y < barcode_height + y_gap:
                    x += barcode_width + x_gap
                    y = y_start
                    if x > width - (barcode_width + x_gap):
                        c.showPage()
                        x, y = x_start, y_start
                
                with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_img:
                    barcode.get('code128', barcode_val, writer=ImageWriter()).write(temp_img, 
                        options={"module_height": 10, "font_size": 10, "text_distance": 2})
                    temp_img_path = temp_img.name
                
                c.drawImage(temp_img_path, x, y, width=barcode_width, height=barcode_height)
                os.remove(temp_img_path)
                y -= (barcode_height + y_gap)
            
            c.save()
            os.startfile(temp_pdf_path)  # تم تغييرها من الطباعة مباشرة إلى الفتح
        except Exception as e:
            messagebox.showerror("خطأ في الطباعة", f"حدث خطأ أثناء محاولة طباعة الباركود:\n{e}")

# =================================================================================
# 3. إطارات العرض (Views)
# =================================================================================
class ShopView(ctk.CTkFrame):
    def __init__(self, parent, cash_box, products, debts, show_main_menu_callback):
        super().__init__(parent, fg_color=BACKGROUND_COLOR)
        self.cash_box_manager = cash_box
        self.product_manager = products
        self.debt_manager = debts
        self.show_main_menu_callback = show_main_menu_callback
        self.text_color = TEXT_COLOR
        self._create_layout()
        self.show_frame("products")
    
    def _create_layout(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0, fg_color=WHITE_COLOR)
        sidebar_frame.grid(row=0, column=0, sticky="nsw")
        sidebar_frame.grid_rowconfigure(7, weight=1)
        
        buttons_info = {
            "products": "📦 المنتجات",
            "sales": "🧾 البيع",
            "debts": "💳 الديون",
            "expenses": "💸 المصاريف",
            "cash_box": "🧮 الصندوق"
        }
        
        for i, (key, text) in enumerate(buttons_info.items()):
            ctk.CTkButton(
                sidebar_frame, text=text, font=("Arial", 16),
                fg_color=PRIMARY_COLOR, text_color=WHITE_COLOR,
                hover_color=BUTTON_HOVER_COLOR,
                command=lambda k=key: self.show_frame(k)
            ).grid(row=i, column=0, padx=20, pady=10, sticky="ew")
        
        ctk.CTkButton(
            sidebar_frame, text="🔙 الرجوع للقائمة الرئيسية",
            fg_color=ERROR_COLOR, text_color=WHITE_COLOR,
            hover_color=BUTTON_HOVER_COLOR,
            command=self.show_main_menu_callback
        ).grid(row=7, column=0, padx=20, pady=20, sticky="s")
        
        self.main_frame = ctk.CTkFrame(self, fg_color=BACKGROUND_COLOR)
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        
        self.frames = {
            key: ctk.CTkFrame(self.main_frame, fg_color="transparent")
            for key in buttons_info.keys()
        }
        
        self._create_products_frame()
        self._create_sales_frame()
        self._create_debts_frame()
        self._create_expenses_frame()
        self._create_cash_box_frame()
    
    def show_frame(self, frame_key):
        for key, frame in self.frames.items():
            if key == frame_key:
                frame.pack(fill="both", expand=True)
                refresh_func = getattr(self, f"refresh_{key}_data", None)
                if callable(refresh_func):
                    refresh_func()
            else:
                frame.pack_forget()
    
    def _create_cash_box_frame(self):
        frame = self.frames["cash_box"]
        
        balance_frame = ctk.CTkFrame(frame, fg_color=WHITE_COLOR, corner_radius=8)
        balance_frame.pack(pady=10, padx=10, fill="x")
        
        ctk.CTkLabel(balance_frame, text="الرصيد الحالي:", font=("Arial", 24, "bold"), text_color=self.text_color).pack(side="left", padx=10, pady=10)
        self.cash_box_balance_label = ctk.CTkLabel(balance_frame, text="0.00", font=("Arial", 24, "bold"), text_color=SUCCESS_COLOR)
        self.cash_box_balance_label.pack(side="right", padx=10, pady=10)
        
        add_funds_frame = ctk.CTkFrame(frame, fg_color="transparent")
        add_funds_frame.pack(pady=10, padx=10, fill="x")
        
        self.add_funds_entry = ctk.CTkEntry(add_funds_frame, placeholder_text="أدخل المبلغ للإضافة", text_color=self.text_color)
        self.add_funds_entry.pack(side="left", expand=True, fill="x", padx=5)
        
        ctk.CTkButton(
            add_funds_frame, text="إضافة رصيد", command=self.manual_add_funds,
            fg_color=PRIMARY_COLOR, hover_color=BUTTON_HOVER_COLOR,
            text_color=WHITE_COLOR
        ).pack(side="right")
        
        cols = ('التاريخ', 'النوع', 'المبلغ', 'الوصف', 'الرصيد بعد')
        self.cash_box_tree = ttk.Treeview(frame, columns=cols, show='headings')
        for col in cols:
            self.cash_box_tree.heading(col, text=col)
        self.cash_box_tree.pack(pady=10, padx=10, expand=True, fill="both")
        
        return frame
    
    def _create_products_frame(self):
        frame = self.frames["products"]
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(1, weight=1)
        
        top_bar = ctk.CTkFrame(frame, fg_color="transparent")
        top_bar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        
        ctk.CTkLabel(top_bar, text="مخزون المنتجات", font=("Arial", 22, "bold"), text_color=self.text_color).pack(side="right", padx=10)
        ctk.CTkButton(top_bar, text="➕ إضافة منتج جديد", command=self.open_add_product_window,
                     fg_color=SUCCESS_COLOR, text_color=WHITE_COLOR,
                     hover_color=BUTTON_HOVER_COLOR).pack(side="left", padx=10)
        
        self.products_scroll_frame = ctk.CTkScrollableFrame(frame, fg_color=BACKGROUND_COLOR, label_text="", corner_radius=8)
        self.products_scroll_frame.grid(row=1, column=0, sticky="nsew")
        self.products_scroll_frame.grid_columnconfigure(0, weight=1)
        
        return frame
    
    def _create_sales_frame(self):
        frame = self.frames["sales"]
        frame.grid_columnconfigure(0, weight=1); frame.grid_columnconfigure(1, weight=1)
        frame.grid_rowconfigure(0, weight=1)
        
        products_for_sale_frame = ctk.CTkFrame(frame, fg_color="transparent")
        products_for_sale_frame.grid(row=0, column=0, padx=(0, 10), sticky="nsew")
        
        qr_entry_frame = ctk.CTkFrame(products_for_sale_frame, fg_color="transparent")
        qr_entry_frame.pack(fill="x", padx=5, pady=5)
        
        self.sale_qr_entry = ctk.CTkEntry(qr_entry_frame, placeholder_text="أو أدخل كود QR هنا", text_color=self.text_color)
        self.sale_qr_entry.pack(side="left", expand=True, fill="x")
        self.sale_qr_entry.bind("<Return>", self.add_to_cart_by_qr)
        
        self.sales_scroll_frame = ctk.CTkScrollableFrame(
            products_for_sale_frame, label_text="قائمة المنتجات للبيع",
            label_text_color=self.text_color, fg_color=BACKGROUND_COLOR
        )
        self.sales_scroll_frame.pack(expand=True, fill="both", padx=5, pady=5)
        
        cart_frame = ctk.CTkFrame(frame, fg_color=WHITE_COLOR, corner_radius=8)
        cart_frame.grid(row=0, column=1, sticky="nsew")
        
        ctk.CTkLabel(cart_frame, text="سلة البيع", font=("Arial", 18, "bold"), text_color=self.text_color).pack(pady=10)
        
        cols = ('المنتج', 'الكمية', 'السعر', 'المجموع الفرعي')
        self.cart_tree = ttk.Treeview(cart_frame, columns=cols, show='headings')
        for col in cols:
            self.cart_tree.heading(col, text=col)
        self.cart_tree.pack(pady=10, padx=10, expand=True, fill="both")
        
        summary_frame = ctk.CTkFrame(cart_frame, fg_color="transparent")
        summary_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(summary_frame, text="الإجمالي:", text_color=self.text_color).grid(row=0, column=0, padx=5, pady=2)
        self.cart_total_label = ctk.CTkLabel(summary_frame, text="0.00", text_color=self.text_color)
        self.cart_total_label.grid(row=0, column=1, padx=5, pady=2)
        
        cart_buttons_frame = ctk.CTkFrame(cart_frame, fg_color="transparent")
        cart_buttons_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkButton(
            cart_buttons_frame, text="✅ تأكيد البيع", command=self.confirm_sale,
            fg_color=SUCCESS_COLOR, text_color=WHITE_COLOR,
            hover_color=BUTTON_HOVER_COLOR
        ).pack(side="left", expand=True, padx=5)
        
        ctk.CTkButton(
            cart_buttons_frame, text="💳 البيع بدين", 
            fg_color=ACCENT_GOLD, text_color=WHITE_COLOR,
            hover_color=BUTTON_HOVER_COLOR, command=self.sell_on_debt
        ).pack(side="left", expand=True, padx=5)
        
        ctk.CTkButton(
            cart_buttons_frame, text="❌ حذف من السلة", 
            fg_color=ERROR_COLOR, text_color=WHITE_COLOR,
            hover_color=BUTTON_HOVER_COLOR, command=self.remove_from_cart
        ).pack(side="left", expand=True, padx=5)
        
        self.cart = {}
        return frame
    
    def _create_debts_frame(self):
        frame = self.frames["debts"]
        
        ctk.CTkLabel(frame, text="إدارة الديون", font=("Arial", 18, "bold"), text_color=self.text_color).pack(pady=10)
        
        cols = ('اسم العميل', 'المبلغ الإجمالي', 'المدفوع', 'المتبقي', 'التاريخ')
        self.debts_tree = ttk.Treeview(frame, columns=cols, show='headings')
        for col in cols:
            self.debts_tree.heading(col, text=col)
        self.debts_tree.pack(pady=10, padx=10, expand=True, fill="both")
        
        buttons_frame = ctk.CTkFrame(frame, fg_color="transparent")
        buttons_frame.pack(fill="x", pady=10)
        
        ctk.CTkButton(
            buttons_frame, text="💸 تسوية دفعة", command=self.settle_debt_payment,
            fg_color=PRIMARY_COLOR, text_color=WHITE_COLOR,
            hover_color=BUTTON_HOVER_COLOR
        ).pack(side="left", padx=5, expand=True)
        
        ctk.CTkButton(
            buttons_frame, text="➕ إضافة مدين", command=self.add_manual_debtor,
            fg_color=PRIMARY_COLOR, text_color=WHITE_COLOR,
            hover_color=BUTTON_HOVER_COLOR
        ).pack(side="left", padx=5, expand=True)
        
        ctk.CTkButton(
            buttons_frame, text="🗑️ حذف المحدد", 
            fg_color=ERROR_COLOR, text_color=WHITE_COLOR,
            hover_color=BUTTON_HOVER_COLOR, command=self.delete_selected_debtor
        ).pack(side="left", padx=5, expand=True)
        
        return frame
    
    def _create_expenses_frame(self):
        frame = self.frames["expenses"]
        
        ctk.CTkLabel(frame, text="تسجيل مصروف جديد", font=("Arial", 18, "bold"), text_color=self.text_color).pack(pady=20)
        
        self.exp_desc = ctk.CTkEntry(frame, placeholder_text="وصف المصروف", width=400, text_color=self.text_color)
        self.exp_desc.pack(pady=10)
        
        self.exp_amount = ctk.CTkEntry(frame, placeholder_text="المبلغ", width=400, text_color=self.text_color)
        self.exp_amount.pack(pady=10)
        
        ctk.CTkButton(
            frame, text="تسجيل المصروف", command=self.record_new_expense,
            fg_color=PRIMARY_COLOR, text_color=WHITE_COLOR,
            hover_color=BUTTON_HOVER_COLOR
        ).pack(pady=20)
        
        return frame
    
    def refresh_all_data(self):
        self.refresh_products_data()
        self.refresh_sales_data()
        self.refresh_debts_data()
        self.refresh_cash_box_data()
    
    def refresh_products_data(self):
        # مسح الذاكرة المؤقتة للصور قبل التحديث
        self.product_manager.clear_image_cache()
        
        for widget in self.products_scroll_frame.winfo_children():
            widget.destroy()
        
        for name, data in self.product_manager.products.items():
            card = ctk.CTkFrame(self.products_scroll_frame, fg_color=WHITE_COLOR, border_width=1, border_color="#EAECEE", corner_radius=8)
            card.pack(fill="x", padx=10, pady=10)
            card.grid_columnconfigure(1, weight=1)
            
            try:
                img = self.product_manager.get_product_image(data.get('image', ''), size=(120, 120))
                if img:
                    image_label = ctk.CTkLabel(card, image=img, text="")
                else:
                    image_label = ctk.CTkLabel(card, text="لا توجد صورة", width=120, height=120, fg_color="#F0F0F0", corner_radius=6, text_color=self.text_color)
            except Exception:
                image_label = ctk.CTkLabel(card, text="لا توجد صورة", width=120, height=120, fg_color="#F0F0F0", corner_radius=6, text_color=self.text_color)
            
            image_label.grid(row=0, column=0, rowspan=4, padx=10, pady=10)
            
            info_frame = ctk.CTkFrame(card, fg_color="transparent")
            info_frame.grid(row=0, column=1, rowspan=4, sticky="nsew", padx=10)
            
            ctk.CTkLabel(info_frame, text=name, font=("Arial", 20, "bold"), text_color=PRIMARY_COLOR, anchor="e").pack(fill="x", pady=(5, 2))
            
            details_frame = ctk.CTkFrame(info_frame, fg_color="transparent")
            details_frame.pack(fill="both", expand=True)
            details_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)
            
            ctk.CTkLabel(details_frame, text=f"الكمية: {data.get('quantity', 0)}", text_color=self.text_color, font=("Arial", 14)).grid(row=0, column=3, sticky="e", padx=5)
            ctk.CTkLabel(details_frame, text="الكمية", text_color="#7F8C8D", font=("Arial", 12, "bold")).grid(row=1, column=3, sticky="e", padx=5)
            
            ctk.CTkLabel(details_frame, text=f"{data.get('sale_price', 0):.2f} د.ج", text_color=self.text_color, font=("Arial", 14)).grid(row=0, column=2, sticky="e", padx=5)
            ctk.CTkLabel(details_frame, text="سعر البيع", text_color="#7F8C8D", font=("Arial", 12, "bold")).grid(row=1, column=2, sticky="e", padx=5)
            
            ctk.CTkLabel(details_frame, text=f"{data.get('purchase_price', 0):.2f} د.ج", text_color=self.text_color, font=("Arial", 14)).grid(row=0, column=1, sticky="e", padx=5)
            ctk.CTkLabel(details_frame, text="سعر الشراء", text_color="#7F8C8D", font=("Arial", 12, "bold")).grid(row=1, column=1, sticky="e", padx=5)
            
            ctk.CTkLabel(details_frame, text=f"QR: {data.get('qr', 'لا يوجد')}", text_color=self.text_color, font=("Arial", 12)).grid(row=2, column=1, columnspan=3, sticky="e", pady=(10,0), padx=5)
            
            buttons_frame = ctk.CTkFrame(card, fg_color="transparent")
            buttons_frame.grid(row=0, column=2, rowspan=4, padx=10, pady=10, sticky="ns")
            
            ctk.CTkButton(
                buttons_frame, text="✏️ تعديل", command=lambda n=name: self.open_edit_product_window(n),
                fg_color=ACCENT_GOLD, text_color=WHITE_COLOR,
                hover_color=BUTTON_HOVER_COLOR, width=100
            ).pack(pady=5)
            
            ctk.CTkButton(
                buttons_frame, text="🗑️ حذف", command=lambda n=name: self.delete_product_from_card(n),
                fg_color=ERROR_COLOR, text_color=WHITE_COLOR,
                hover_color=BUTTON_HOVER_COLOR, width=100
            ).pack(pady=5)
    
    def open_add_product_window(self):
        self.open_edit_product_window(None)
    
    def open_edit_product_window(self, product_name):
        is_edit_mode = product_name is not None
        edit_window = ctk.CTkToplevel(self)
        title = "تعديل المنتج" if is_edit_mode else "إضافة منتج جديد"
        edit_window.title(title)
        edit_window.geometry("450x550")
        edit_window.resizable(False, False)
        edit_window.transient(self)
        edit_window.grab_set()
        
        product_data = self.product_manager.products.get(product_name, {}) if is_edit_mode else {}
        
        main_frame = ctk.CTkFrame(edit_window, fg_color=BACKGROUND_COLOR)
        main_frame.pack(expand=True, fill="both", padx=20, pady=20)
        
        ctk.CTkLabel(main_frame, text=title, font=("Arial", 18, "bold"), text_color=self.text_color).pack(pady=(0, 20))
        
        entries = {}
        fields = {
            'name': 'اسم المنتج',
            'image': 'مسار الصورة',
            'qr': 'كود QR',
            'quantity': 'الكمية',
            'purchase_price': 'سعر الشراء',
            'sale_price': 'سعر البيع'
        }
        
        for key, placeholder in fields.items():
            frame = ctk.CTkFrame(main_frame, fg_color='transparent')
            frame.pack(fill='x', pady=5)
            
            ctk.CTkLabel(frame, text=placeholder, text_color=self.text_color).pack(side='right', padx=10)
            
            entry = ctk.CTkEntry(frame, placeholder_text=placeholder, text_color=self.text_color)
            if key == 'name':
                entry.insert(0, product_name if is_edit_mode else "")
            else:
                entry.insert(0, str(product_data.get(key, "")))
            
            entry.pack(side='left', expand=True, fill='x')
            entries[key] = entry
            
            if key == 'image':
                ctk.CTkButton(frame, text="...", width=30, command=lambda e=entry: self.browse_for_image_path(e)).pack(side='left', padx=(5,0))
        
        def save_changes():
            try:
                new_data = {
                    'name': entries['name'].get(),
                    'image': entries['image'].get(),
                    'qr': entries['qr'].get(),
                    'quantity': int(entries['quantity'].get() or 0),
                    'purchase_price': float(entries['purchase_price'].get() or 0.0),
                    'sale_price': float(entries['sale_price'].get() or 0.0),
                }
                
                if is_edit_mode:
                    success, msg = self.product_manager.update_product(product_name, new_data)
                else:
                    success, msg = self.product_manager.purchase_product(
                        new_data['name'], new_data['image'], new_data['qr'],
                        new_data['quantity'], new_data['purchase_price'],
                        new_data['sale_price']
                    )
                
                if success:
                    messagebox.showinfo("نجاح", msg)
                    edit_window.destroy()
                    self.refresh_all_data()
                else:
                    messagebox.showerror("فشل", msg, parent=edit_window)
            except ValueError:
                messagebox.showerror("خطأ", "الرجاء التأكد من إدخال أرقام صحيحة للكمية والأسعار.", parent=edit_window)
        
        save_button = ctk.CTkButton(main_frame, text="حفظ", command=save_changes,
                                   fg_color=SUCCESS_COLOR, text_color=WHITE_COLOR,
                                   hover_color=BUTTON_HOVER_COLOR)
        save_button.pack(pady=20, fill='x')
    
    def browse_for_image_path(self, entry_widget):
        filepath = filedialog.askopenfilename(
            title="اختر صورة المنتج",
            filetypes=[("Image Files", "*.png *.jpg *.jpeg *.gif")]
        )
        if filepath:
            entry_widget.delete(0, 'end')
            entry_widget.insert(0, filepath)
    
    def delete_product_from_card(self, product_name):
        if messagebox.askyesno("تأكيد الحذف", f"هل أنت متأكد من حذف المنتج '{product_name}'؟\nسيتم إرجاع قيمة المخزون إلى الصندوق."):
            success, msg = self.product_manager.delete_product(product_name)
            if success:
                messagebox.showinfo("نجاح", f"تم حذف المنتج '{product_name}' بنجاح.")
                self.refresh_all_data()
            else:
                messagebox.showerror("فشل", msg)
    
    def refresh_cash_box_data(self):
        if hasattr(self, 'cash_box_balance_label'):
            self.cash_box_balance_label.configure(text=f"{self.cash_box_manager.balance:.2f} DZD")
        
        if hasattr(self, 'cash_box_tree'):
            for i in self.cash_box_tree.get_children():
                self.cash_box_tree.delete(i)
            
            for log in reversed(self.cash_box_manager.log):
                self.cash_box_tree.insert('', 'end', values=(
                    log['date'], log['type'], f"{log['amount']:.2f}",
                    log['description'], f"{log['balance_after']:.2f}"
                ))
    
    def manual_add_funds(self):
        try:
            amount = float(self.add_funds_entry.get())
            success, msg = self.cash_box_manager.add_funds(amount, "إيداع يدوي")
            if success:
                messagebox.showinfo("نجاح", "تمت إضافة المبلغ.")
                self.add_funds_entry.delete(0, 'end')
                self.refresh_cash_box_data()
            else:
                messagebox.showerror("خطأ", msg)
        except ValueError:
            messagebox.showerror("خطأ", "الرجاء إدخال مبلغ صحيح.")
    
    def refresh_sales_data(self):
        for widget in self.sales_scroll_frame.winfo_children():
            widget.destroy()
        
        for name, data in self.product_manager.products.items():
            if data['quantity'] > 0:
                card = ctk.CTkFrame(self.sales_scroll_frame, fg_color=WHITE_COLOR, corner_radius=8)
                card.pack(fill="x", padx=5, pady=5)
                
                try:
                    img = self.product_manager.get_product_image(data.get('image', ''), size=(60, 60))
                    if img:
                        image_label = ctk.CTkLabel(card, image=img, text="")
                    else:
                        image_label = ctk.CTkLabel(card, text="صورة", width=60, height=60, fg_color="gray90")
                except:
                    image_label = ctk.CTkLabel(card, text="صورة", width=60, height=60, fg_color="gray90")
                
                image_label.pack(side="right", padx=10, pady=5)
                
                ctk.CTkLabel(
                    card, 
                    text=f"{name}\nالسعر: {data['sale_price']:.2f} | المتوفر: {data['quantity']}",
                    text_color=self.text_color, justify="right"
                ).pack(side="right", fill="x", expand=True, padx=10)
                
                ctk.CTkButton(card, text="➕", width=40, command=lambda n=name: self.add_to_cart(n)).pack(side="left", padx=10)
        
        for i in self.cart_tree.get_children():
            self.cart_tree.delete(i)
        
        total = sum(self.product_manager.products[n]['sale_price'] * q for n, q in self.cart.items())
        
        for name, qty in self.cart.items():
            self.cart_tree.insert('', 'end', values=(
                name, qty, 
                f"{self.product_manager.products[name]['sale_price']:.2f}",
                f"{qty * self.product_manager.products[name]['sale_price']:.2f}"
            ))
        
        self.cart_total_label.configure(text=f"{total:.2f} DZD")
    
    def add_to_cart(self, product_name):
        if self.cart.get(product_name, 0) < self.product_manager.products[product_name]['quantity']:
            self.cart[product_name] = self.cart.get(product_name, 0) + 1
            self.refresh_sales_data()
        else:
            messagebox.showwarning("الكمية نفدت", "لا يمكن إضافة المزيد.")
    
    def add_to_cart_by_qr(self, event=None):
        qr_code = self.sale_qr_entry.get()
        if not qr_code:
            return
        
        name, data = self.product_manager.get_product_by_qr(qr_code)
        if name:
            self.add_to_cart(name)
            self.sale_qr_entry.delete(0, 'end')
        else:
            messagebox.showerror("خطأ", "لم يتم العثور على منتج بهذا الكود.")
    
    def remove_from_cart(self):
        selected_item = self.cart_tree.focus()
        if not selected_item:
            return
        
        product_name = self.cart_tree.item(selected_item)['values'][0]
        if self.cart[product_name] > 1:
            self.cart[product_name] -= 1
        else:
            del self.cart[product_name]
        
        self.refresh_sales_data()
    
    def _finalize_sale(self, is_debt=False, client_name=None, initial_payment=None):
        if not self.cart:
            return
        
        total_sale_value = sum(self.product_manager.products[n]['sale_price'] * q for n, q in self.cart.items())
        
        discount_str = ctk.CTkInputDialog(text="أدخل قيمة التخفيض:", title="تخفيض").get_input()
        discount = float(discount_str) if discount_str and discount_str.replace('.', '', 1).isdigit() else 0.0
        final_price = total_sale_value - discount
        
        if is_debt:
            success, msg = self.debt_manager.add_debt(client_name, final_price, initial_payment)
            if not success:
                messagebox.showerror("فشل", msg)
                return
        else:
            self.cash_box_manager.add_funds(final_price, f"عملية بيع (تخفيض {discount:.2f})")
        
        for name, qty in self.cart.items():
            self.product_manager.sell_product(name, qty)
        
        messagebox.showinfo("نجاح", "تمت عملية البيع بنجاح.")
        self.cart.clear()
        self.refresh_all_data()
    
    def confirm_sale(self):
        if not self.cart:
            messagebox.showwarning("تنبيه", "سلة البيع فارغة.")
            return
        
        self._finalize_sale()
    
    def sell_on_debt(self):
        if not self.cart:
            messagebox.showwarning("تنبيه", "سلة البيع فارغة.")
            return
        
        client_name = ctk.CTkInputDialog(text="أدخل اسم العميل:", title="بيع بدين").get_input()
        if not client_name:
            return
        
        payment_str = ctk.CTkInputDialog(text="أدخل المبلغ المدفوع مقدمًا:", title="دفعة مقدمة").get_input()
        initial_payment = float(payment_str) if payment_str and payment_str.replace('.', '', 1).isdigit() else 0.0
        
        self._finalize_sale(is_debt=True, client_name=client_name, initial_payment=initial_payment)
    
    def refresh_debts_data(self):
        for i in self.debts_tree.get_children():
            self.debts_tree.delete(i)
        
        for name, data in self.debt_manager.debts.items():
            self.debts_tree.insert('', 'end', values=(
                name, f"{data['total']:.2f}", f"{data['paid']:.2f}",
                f"{data['remaining']:.2f}", data['date']
            ))
    
    def settle_debt_payment(self):
        selected_item = self.debts_tree.focus()
        if not selected_item:
            return
        
        client_name = self.debts_tree.item(selected_item)['values'][0]
        payment_str = ctk.CTkInputDialog(text=f"أدخل المبلغ المدفوع من {client_name}:", title="تسوية دين").get_input()
        if not payment_str:
            return
        
        try:
            amount = float(payment_str)
            success, msg = self.debt_manager.settle_payment(client_name, amount)
            if success:
                messagebox.showinfo("نجاح", "تم تسجيل الدفعة.")
                self.refresh_all_data()
            else:
                messagebox.showerror("فشل", msg)
        except ValueError:
            messagebox.showerror("خطأ", "مبلغ غير صحيح.")
    
    def delete_selected_debtor(self):
        selected_item = self.debts_tree.focus()
        if not selected_item:
            return
        
        client_name = self.debts_tree.item(selected_item)['values'][0]
        if messagebox.askyesno("تأكيد الحذف", f"هل أنت متأكد من حذف دين '{client_name}'؟"):
            self.debt_manager.delete_debt(client_name)
            self.refresh_debts_data()
    
    def add_manual_debtor(self):
        name = ctk.CTkInputDialog(text="أدخل اسم العميل:", title="إضافة مدين").get_input()
        if not name:
            return
        
        amount_str = ctk.CTkInputDialog(text=f"أدخل مبلغ الدين لـ {name}:", title="مبلغ الدين").get_input()
        if not amount_str:
            return
        
        try:
            amount = float(amount_str)
            self.debt_manager.add_debt(name, amount)
            self.refresh_debts_data()
        except ValueError:
            messagebox.showerror("خطأ", "مبلغ غير صحيح.")
    
    def record_new_expense(self):
        desc, amount_str = self.exp_desc.get(), self.exp_amount.get()
        if not desc or not amount_str:
            messagebox.showerror("خطأ", "الرجاء ملء الحقول.")
            return
        
        try:
            amount = float(amount_str)
            success, msg = self.cash_box_manager.record_expense(amount, desc)
            if success:
                messagebox.showinfo("نجاح", "تم تسجيل المصروف.")
                self.exp_desc.delete(0, 'end')
                self.exp_amount.delete(0, 'end')
                self.refresh_all_data()
            else:
                messagebox.showerror("فشل", msg)
        except ValueError:
            messagebox.showerror("خطأ", "مبلغ غير صحيح.")

class RepairView(ctk.CTkFrame):
    def __init__(self, parent, repair_manager, show_main_menu_callback):
        super().__init__(parent, fg_color=BACKGROUND_COLOR)
        self.manager = repair_manager
        self.show_main_menu_callback = show_main_menu_callback
        self.text_color = TEXT_COLOR
        
        self.grid_columnconfigure((0, 1, 2), weight=1)
        self.grid_rowconfigure(2, weight=1)
        
        top_frame = ctk.CTkFrame(self, fg_color="transparent")
        top_frame.grid(row=0, column=0, columnspan=3, sticky="ew", padx=10, pady=(10,0))
        
        ctk.CTkButton(
            top_frame, text="🔙 الرجوع", 
            fg_color=ERROR_COLOR, text_color=WHITE_COLOR,
            hover_color=BUTTON_HOVER_COLOR,
            command=self.show_main_menu_callback
        ).pack(side="left")
        
        # إضافة زر صندوق التصليح
        ctk.CTkButton(
            top_frame, text="💰 صندوق التصليح", 
            fg_color=PRIMARY_COLOR, text_color=WHITE_COLOR,
            hover_color=BUTTON_HOVER_COLOR,
            command=self.show_repair_cash_box
        ).pack(side="right", padx=10)
        
        self.cash_box_frame = self._create_main_display_frame(self, "الصندوق", "0.00 DZD", SUCCESS_COLOR)
        self.cash_box_frame.grid(row=1, column=0, columnspan=3, padx=10, pady=10, sticky="ew")
        
        content_frame = ctk.CTkFrame(self, fg_color="transparent")
        content_frame.grid(row=2, column=0, columnspan=3, sticky="nsew", padx=10, pady=10)
        content_frame.grid_columnconfigure((0, 1, 2), weight=1)
        content_frame.grid_rowconfigure(1, weight=1)
        
        self.purchase_frame = self._create_operation_frame(content_frame, "شراء", "مبلغ الشراء", "شراء", self.execute_purchase)
        self.purchase_frame.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        
        self.sale_frame = self._create_operation_frame(content_frame, "بيع", "مبلغ البيع", "بيع", self.execute_sale)
        self.sale_frame.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")
        
        worker_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        worker_frame.grid(row=0, column=2, padx=5, pady=5, sticky="nsew")
        worker_frame.grid_rowconfigure((0, 1), weight=1)
        
        self.alaa_frame = self._create_worker_frame(worker_frame, "علاء", "علاء", self.execute_worker_withdrawal)
        self.alaa_frame.pack(expand=True, fill="both", pady=(0, 5))
        
        self.hamza_frame = self._create_worker_frame(worker_frame, "حمزة", "حمزة", self.execute_worker_withdrawal)
        self.hamza_frame.pack(expand=True, fill="both", pady=(5, 0))
        
        self.debts_frame = self._create_debts_frame(content_frame)
        self.debts_frame.grid(row=1, column=0, columnspan=3, padx=5, pady=5, sticky="nsew")
        
        # إطار صندوق التصليح (مخفي في البداية)
        self.repair_cash_box_frame = ctk.CTkFrame(self, fg_color=BACKGROUND_COLOR)
        self.repair_cash_box_frame.grid_columnconfigure(0, weight=1)
        self.repair_cash_box_frame.grid_rowconfigure(1, weight=1)
        
        # شريط العنوان
        cash_box_top_frame = ctk.CTkFrame(self.repair_cash_box_frame, fg_color="transparent")
        cash_box_top_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        
        ctk.CTkButton(
            cash_box_top_frame, text="🔙 الرجوع", 
            fg_color=ERROR_COLOR, text_color=WHITE_COLOR,
            hover_color=BUTTON_HOVER_COLOR,
            command=self.hide_repair_cash_box
        ).pack(side="left")
        
        ctk.CTkLabel(
            cash_box_top_frame, text="سجل صندوق التصليح", 
            font=("Arial", 20, "bold"), text_color=self.text_color
        ).pack(side="right", padx=10)
        
        # عرض الرصيد
        balance_frame = ctk.CTkFrame(self.repair_cash_box_frame, fg_color=WHITE_COLOR, corner_radius=8)
        balance_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=10)
        
        ctk.CTkLabel(
            balance_frame, text="الرصيد الحالي:", 
            font=("Arial", 20, "bold"), text_color=self.text_color
        ).pack(side="left", padx=10, pady=10)
        
        self.repair_cash_balance_label = ctk.CTkLabel(
            balance_frame, text="0.00 DZD", 
            font=("Arial", 20, "bold"), text_color=SUCCESS_COLOR
        )
        self.repair_cash_balance_label.pack(side="right", padx=10, pady=10)
        
        # شجرة السجل
        cols = ('التاريخ', 'النوع', 'المبلغ', 'الوصف', 'الرصيد بعد')
        self.repair_cash_tree = ttk.Treeview(
            self.repair_cash_box_frame, columns=cols, show='headings'
        )
        for col in cols:
            self.repair_cash_tree.heading(col, text=col)
        
        self.repair_cash_tree.grid(row=2, column=0, sticky="nsew", padx=10, pady=10)
        
        # إخفاء إطار صندوق التصليح في البداية
        self.repair_cash_box_frame.grid_forget()
        
        self.refresh_ui()
    
    def show_repair_cash_box(self):
        # إخفاء الإطار الرئيسي وإظهار إطار صندوق التصليح
        self.cash_box_frame.grid_forget()
        content_frame = self.grid_slaves(row=2, column=0)[0]
        content_frame.grid_forget()
        
        # تحديث بيانات صندوق التصليح
        self.repair_cash_balance_label.configure(text=f"{self.manager.balance:.2f} DZD")
        
        for i in self.repair_cash_tree.get_children():
            self.repair_cash_tree.delete(i)
        
        for log in reversed(self.manager.log):
            self.repair_cash_tree.insert('', 'end', values=(
                log['date'], log['type'], f"{log['amount']:.2f}",
                log['description'], f"{log['balance_after']:.2f}"
            ))
        
        self.repair_cash_box_frame.grid(row=1, column=0, columnspan=3, sticky="nsew", padx=10, pady=10)
        self.repair_cash_box_frame.lift()
    
    def hide_repair_cash_box(self):
        # إخفاء إطار صندوق التصليح وإظهار الإطار الرئيسي
        self.repair_cash_box_frame.grid_forget()
        self.cash_box_frame.grid(row=1, column=0, columnspan=3, padx=10, pady=10, sticky="ew")
        content_frame = self.grid_slaves(row=2, column=0)[0]
        content_frame.grid(row=2, column=0, columnspan=3, sticky="nsew", padx=10, pady=10)
    
    def _create_main_display_frame(self, parent, title, initial_text, color):
        frame = ctk.CTkFrame(parent, border_width=1, fg_color=WHITE_COLOR, corner_radius=8)
        ctk.CTkLabel(frame, text=title, font=("Arial", 16, "bold"), text_color=self.text_color).pack(pady=(5,0))
        label = ctk.CTkLabel(frame, text=initial_text, font=("Arial", 22, "bold"), text_color=color)
        label.pack(pady=10, padx=10)
        frame.value_label = label
        return frame
    
    def _create_operation_frame(self, parent, title, placeholder, button_text, command):
        frame = ctk.CTkFrame(parent, border_width=1, fg_color=WHITE_COLOR, corner_radius=8)
        ctk.CTkLabel(frame, text=title, font=("Arial", 16, "bold"), text_color=self.text_color).pack(pady=10)
        entry = ctk.CTkEntry(frame, placeholder_text=placeholder, text_color=self.text_color)
        entry.pack(pady=5, padx=10, fill="x")
        ctk.CTkButton(frame, text=button_text, command=lambda e=entry: command(e),
                     fg_color=PRIMARY_COLOR, text_color=WHITE_COLOR,
                     hover_color=BUTTON_HOVER_COLOR).pack(pady=10, padx=10, fill="x")
        return frame
    
    def _create_worker_frame(self, parent, title, worker_name, command):
        frame = ctk.CTkFrame(parent, border_width=1, fg_color=WHITE_COLOR, corner_radius=8)
        
        top_frame = ctk.CTkFrame(frame, fg_color="transparent")
        top_frame.pack(fill="x", padx=5, pady=5)
        
        ctk.CTkLabel(top_frame, text=title, font=("Arial", 14, "bold"), text_color=self.text_color).pack(side="left")
        total_label = ctk.CTkLabel(top_frame, text="0.00", font=("Arial", 12), text_color=self.text_color)
        total_label.pack(side="right")
        
        entry = ctk.CTkEntry(frame, placeholder_text="المبلغ المأخوذ", text_color=self.text_color)
        entry.pack(pady=5, padx=10, fill="x")
        
        ctk.CTkButton(frame, text="تسجيل سحب", command=lambda w=worker_name, e=entry: command(w, e),
                     fg_color=PRIMARY_COLOR, text_color=WHITE_COLOR,
                     hover_color=BUTTON_HOVER_COLOR).pack(pady=5, padx=10, fill="x")
        
        frame.total_label = total_label
        return frame
    
    def _create_debts_frame(self, parent):
        frame = ctk.CTkFrame(parent, border_width=1, fg_color=WHITE_COLOR, corner_radius=8)
        frame.grid_columnconfigure(0, weight=1); frame.grid_rowconfigure(1, weight=1)
        
        ctk.CTkLabel(frame, text="ديون التصليح (العملاء)", font=("Arial", 16, "bold"), text_color=self.text_color).grid(row=0, column=0, columnspan=2, pady=5)
        
        cols = ('اسم العميل', 'المبلغ المتبقي')
        tree = ttk.Treeview(frame, columns=cols, show='headings')
        for col in cols:
            tree.heading(col, text=col)
        tree.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
        self.debts_tree = tree
        
        buttons_frame = ctk.CTkFrame(frame, fg_color="transparent")
        buttons_frame.grid(row=1, column=1, padx=10, sticky="ns")
        
        ctk.CTkButton(buttons_frame, text="➕ دين جديد", command=self.add_new_debt,
                     fg_color=PRIMARY_COLOR, text_color=WHITE_COLOR,
                     hover_color=BUTTON_HOVER_COLOR).pack(pady=5, fill="x")
        
        ctk.CTkButton(buttons_frame, text="💸 تسديد دفعة", command=self.settle_debt_payment,
                     fg_color=PRIMARY_COLOR, text_color=WHITE_COLOR,
                     hover_color=BUTTON_HOVER_COLOR).pack(pady=5, fill="x")
        
        return frame
    
    def refresh_ui(self):
        self.cash_box_frame.value_label.configure(text=f"{self.manager.balance:.2f} DZD")
        self.alaa_frame.total_label.configure(text=f"المجموع: {self.manager.workers['علاء']:.2f}")
        self.hamza_frame.total_label.configure(text=f"المجموع: {self.manager.workers['حمزة']:.2f}")
        
        for i in self.debts_tree.get_children():
            self.debts_tree.delete(i)
        
        for name, data in self.manager.debts.items():
            self.debts_tree.insert('', 'end', values=(name, f"{data['remaining']:.2f}"))
    
    def _execute_and_refresh(self, command, entry):
        try:
            amount = float(entry.get())
            success, message = command(amount)
            if success:
                messagebox.showinfo("نجاح", message)
                entry.delete(0, 'end')
                self.refresh_ui()
            else:
                messagebox.showerror("فشل", message)
        except ValueError:
            messagebox.showerror("خطأ", "مبلغ غير صحيح.")
    
    def execute_purchase(self, entry):
        self._execute_and_refresh(self.manager.record_purchase, entry)
    
    def execute_sale(self, entry):
        self._execute_and_refresh(self.manager.record_sale, entry)
    
    def execute_worker_withdrawal(self, worker_name, entry):
        try:
            amount = float(entry.get())
            success, message = self.manager.worker_withdrawal(worker_name, amount)
            if success:
                messagebox.showinfo("معلومات", message)
                entry.delete(0, 'end')
                self.refresh_ui()
            else:
                messagebox.showerror("فشل", message)
        except ValueError:
            messagebox.showerror("خطأ", "مبلغ غير صحيح.")
    
    def add_new_debt(self):
        name = ctk.CTkInputDialog(text="أدخل اسم العميل:", title="إضافة دين").get_input()
        if not name:
            return
        
        amount_str = ctk.CTkInputDialog(text=f"أدخل مبلغ الدين لـ {name}:", title="مبلغ الدين").get_input()
        if not amount_str:
            return
        
        try:
            amount = float(amount_str)
            success, msg = self.manager.add_debt(name, amount)
            if success:
                messagebox.showinfo("نجاح", msg)
                self.refresh_ui()
            else:
                messagebox.showerror("فشل", msg)
        except ValueError:
            messagebox.showerror("خطأ", "مبلغ غير صحيح.")
    
    def settle_debt_payment(self):
        selected_item = self.debts_tree.focus()
        if not selected_item:
            messagebox.showwarning("تنبيه", "حدد عميلًا.")
            return
        
        client_name = self.debts_tree.item(selected_item)['values'][0]
        payment_str = ctk.CTkInputDialog(text=f"المبلغ المسدد من {client_name}:", title="تسديد دين").get_input()
        if not payment_str:
            return
        
        try:
            amount = float(payment_str)
            success, msg = self.manager.settle_debt(client_name, amount)
            if success:
                messagebox.showinfo("نجاح", msg)
                self.refresh_ui()
            else:
                messagebox.showerror("فشل", msg)
        except ValueError:
            messagebox.showerror("خطأ", "مبلغ غير صحيح.")

class FlexyView(ctk.CTkFrame):
    def __init__(self, parent, flexy_manager, show_main_menu_callback):
        super().__init__(parent, fg_color=BACKGROUND_COLOR)
        self.manager = flexy_manager
        self.show_main_menu_callback = show_main_menu_callback
        self.text_color = TEXT_COLOR
        self._create_layout()
        self.show_frame("main_cash_box")
    
    def _create_layout(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0, fg_color=WHITE_COLOR)
        sidebar_frame.grid(row=0, column=0, sticky="nsw")
        sidebar_frame.grid_rowconfigure(7, weight=1)
        
        buttons_info = {
            "main_cash_box": "الصندوق الرئيسي",
            "credit_recharge": "شحن الرصيد",
            "transfer": "التحويل",
            "games_topup": "شحن الألعاب",
            "profits": "الفوائد"
        }
        
        for i, (key, text) in enumerate(buttons_info.items()):
            ctk.CTkButton(sidebar_frame, text=text, font=("Arial", 16),
                          command=lambda k=key: self.show_frame(k),
                          fg_color=PRIMARY_COLOR, text_color=WHITE_COLOR,
                          hover_color=BUTTON_HOVER_COLOR).grid(row=i, column=0, padx=20, pady=10, sticky="ew")
        
        ctk.CTkButton(sidebar_frame, text="🔙 الرجوع",
                     fg_color=ERROR_COLOR, text_color=WHITE_COLOR,
                     hover_color=BUTTON_HOVER_COLOR,
                     command=self.show_main_menu_callback).grid(row=7, column=0, padx=20, pady=20, sticky="s")
        
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        
        self.frames = {key: ctk.CTkFrame(self.main_frame, fg_color="transparent") for key in buttons_info.keys()}
        
        self._create_main_cash_box_frame()
        self._create_credit_recharge_frame()
        self._create_transfer_frame()
        self._create_games_topup_frame()
        self._create_profits_frame()
    
    def show_frame(self, frame_key):
        for key, frame in self.frames.items():
            if key == frame_key:
                frame.pack(fill="both", expand=True)
                refresh_func = getattr(self, f"refresh_{key}_data", None)
                if callable(refresh_func):
                    refresh_func()
            else:
                frame.pack_forget()
    
    def _create_main_cash_box_frame(self):
        frame = self.frames["main_cash_box"]
        
        ctk.CTkLabel(frame, text="الصندوق الرئيسي للفلكسي", font=("Arial", 20, "bold"), text_color=self.text_color).pack(pady=10)
        
        self.flexy_main_balance_label = ctk.CTkLabel(frame, text="", font=("Arial", 28, "bold"), text_color=SUCCESS_COLOR)
        self.flexy_main_balance_label.pack(pady=10)
        
        add_funds_frame = ctk.CTkFrame(frame, fg_color="transparent")
        add_funds_frame.pack(pady=10, padx=50, fill="x")
        
        self.flexy_add_funds_entry = ctk.CTkEntry(add_funds_frame, placeholder_text="مبلغ الإيداع", text_color=self.text_color)
        self.flexy_add_funds_entry.pack(side="left", expand=True, fill="x", padx=(0,10))
        
        ctk.CTkButton(add_funds_frame, text="إيداع", command=self.add_main_funds,
                     fg_color=PRIMARY_COLOR, text_color=WHITE_COLOR,
                     hover_color=BUTTON_HOVER_COLOR).pack(side="right")
        
        cols = ('التاريخ', 'النوع', 'المبلغ', 'الوصف')
        self.flexy_ops_tree = ttk.Treeview(frame, columns=cols, show='headings')
        for col in cols:
            self.flexy_ops_tree.heading(col, text=col)
        self.flexy_ops_tree.pack(expand=True, fill="both", padx=10, pady=10)
    
    def _create_credit_recharge_frame(self):
        frame = self.frames["credit_recharge"]
        frame.grid_columnconfigure(1, weight=3); frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=1)
        
        left_frame = ctk.CTkFrame(frame, fg_color=WHITE_COLOR, corner_radius=8)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        
        ctk.CTkLabel(left_frame, text="رصيد الشحن", font=("Arial", 18), text_color=self.text_color).pack(pady=10)
        
        self.flexy_credit_balance_label = ctk.CTkLabel(left_frame, text="", font=("Arial", 24, "bold"), text_color=PRIMARY_COLOR)
        self.flexy_credit_balance_label.pack(pady=5)
        
        self.credit_amount_entry = ctk.CTkEntry(left_frame, placeholder_text="مبلغ الشحن لشرائه", text_color=self.text_color)
        self.credit_amount_entry.pack(pady=20, padx=10, fill="x")
        
        ctk.CTkButton(left_frame, text="➕ شراء رصيد", command=self.add_credit,
                     fg_color=PRIMARY_COLOR, text_color=WHITE_COLOR,
                     hover_color=BUTTON_HOVER_COLOR).pack(pady=5, padx=10, fill="x")
        
        ctk.CTkButton(left_frame, text="🗑️ حذف المحدد", 
                     fg_color=ERROR_COLOR, text_color=WHITE_COLOR,
                     hover_color=BUTTON_HOVER_COLOR, command=self.delete_credit).pack(pady=5, padx=10, fill="x")
        
        right_frame = ctk.CTkFrame(frame, fg_color="transparent")
        right_frame.grid(row=0, column=1, sticky="nsew")
        
        ctk.CTkLabel(right_frame, text="جدول عمليات شراء الشحن", font=("Arial", 18), text_color=self.text_color).pack(pady=10)
        
        cols = ('التاريخ', 'المبلغ')
        self.flexy_credit_tree = ttk.Treeview(right_frame, columns=cols, show='headings')
        for col in cols:
            self.flexy_credit_tree.heading(col, text=col)
        self.flexy_credit_tree.pack(expand=True, fill="both", padx=10, pady=10)
    
    def _create_transfer_frame(self):
        frame = self.frames["transfer"]
        
        tabview = ctk.CTkTabview(frame, fg_color=BACKGROUND_COLOR,
                                segmented_button_selected_color=PRIMARY_COLOR,
                                segmented_button_unselected_color=WHITE_COLOR,
                                segmented_button_unselected_hover_color=BUTTON_HOVER_COLOR,
                                segmented_button_selected_hover_color=BUTTON_HOVER_COLOR,
                                text_color=TEXT_COLOR)
        tabview.pack(expand=True, fill="both")
        
        def create_tab_content(parent, transfer_type, amounts):
            parent.configure(fg_color=BACKGROUND_COLOR)
            ctk.CTkLabel(parent, text=f"تحويل {transfer_type}", font=("Arial", 18), text_color=self.text_color).pack(pady=10)
            
            amount_var = ctk.StringVar(value=amounts[0])
            custom_entry = ctk.CTkEntry(parent, placeholder_text="أدخل مبلغًا آخر", text_color=self.text_color)
            
            def on_option_change(choice):
                if choice == "مبلغ آخر":
                    custom_entry.pack(pady=5, padx=10, fill="x")
                else:
                    custom_entry.pack_forget()
            
            ctk.CTkOptionMenu(parent, variable=amount_var, values=amounts,
                             command=on_option_change,
                             fg_color=PRIMARY_COLOR, button_color=PRIMARY_COLOR,
                             button_hover_color=BUTTON_HOVER_COLOR,
                             text_color=WHITE_COLOR).pack(pady=10, padx=10)
            
            ctk.CTkButton(parent, text="تأكيد التحويل",
                         command=lambda: self.on_transfer_confirm(transfer_type, amount_var, custom_entry),
                         fg_color=PRIMARY_COLOR, text_color=WHITE_COLOR,
                         hover_color=BUTTON_HOVER_COLOR).pack(pady=20, padx=10)
        
        create_tab_content(tabview.add("فلكسي"), "فلكسي", ["50", "100", "200", "500", "1000", "1500", "مبلغ آخر"])
        create_tab_content(tabview.add("انترنت"), "انترنت", ["500", "1000", "1500", "2000", "3500", "مبلغ آخر"])
    
    def on_transfer_confirm(self, transfer_type, amount_var, custom_entry):
        try:
            amount = float(custom_entry.get() if amount_var.get() == "مبلغ آخر" else amount_var.get())
            success, msg = self.manager.perform_transfer(transfer_type, amount)
            if success:
                messagebox.showinfo("نجاح", msg)
                self.refresh_all_flexy_data()
            else:
                messagebox.showerror("فشل", msg)
        except (ValueError, TypeError):
            messagebox.showerror("خطأ", "مبلغ غير صحيح.")
    
    def _create_games_topup_frame(self):
        frame = self.frames["games_topup"]
        
        ctk.CTkLabel(frame, text="شحن الألعاب", font=("Arial", 18), text_color=self.text_color).pack(pady=10, padx=10)
        
        game_var = ctk.StringVar(value="Free Fire")
        custom_game_entry = ctk.CTkEntry(frame, placeholder_text="أدخل اسم اللعبة", text_color=self.text_color)
        
        def on_game_change(choice):
            if choice == "لعبة اخرى":
                custom_game_entry.pack(pady=5, padx=10, fill="x")
            else:
                custom_game_entry.pack_forget()
        
        ctk.CTkOptionMenu(frame, variable=game_var, values=["Free Fire", "PUBG", "لعبة اخرى"],
                         command=on_game_change,
                         fg_color=PRIMARY_COLOR, button_color=PRIMARY_COLOR,
                         button_hover_color=BUTTON_HOVER_COLOR,
                         text_color=WHITE_COLOR).pack(pady=10, padx=10)
        
        amount_entry = ctk.CTkEntry(frame, placeholder_text="مبلغ الشحن", text_color=self.text_color)
        amount_entry.pack(pady=5, padx=10, fill="x")
        
        profit_entry = ctk.CTkEntry(frame, placeholder_text="مبلغ الفائدة", text_color=self.text_color)
        profit_entry.pack(pady=5, padx=10, fill="x")
        
        def on_confirm():
            try:
                game = custom_game_entry.get() if game_var.get() == "لعبة اخرى" else game_var.get()
                amount = float(amount_entry.get())
                profit = float(profit_entry.get())
                
                if not game:
                    messagebox.showerror("خطأ", "حدد اسم اللعبة.")
                    return
                
                success, msg = self.manager.perform_game_topup(game, amount, profit)
                if success:
                    messagebox.showinfo("نجاح", msg)
                    self.refresh_all_flexy_data()
                else:
                    messagebox.showerror("فشل", msg)
            except (ValueError, TypeError):
                messagebox.showerror("خطأ", "مبالغ غير صحيحة.")
        
        ctk.CTkButton(frame, text="تأكيد الشحن", command=on_confirm,
                     fg_color=PRIMARY_COLOR, text_color=WHITE_COLOR,
                     hover_color=BUTTON_HOVER_COLOR).pack(pady=20, padx=10)
    
    def _create_profits_frame(self):
        frame = self.frames["profits"]
        
        ctk.CTkLabel(frame, text="صندوق الفوائد والأرباح", font=("Arial", 20, "bold"), text_color=self.text_color).pack(pady=10)
        
        self.flexy_profits_balance_label = ctk.CTkLabel(frame, text="", font=("Arial", 28, "bold"), text_color=ACCENT_GOLD)
        self.flexy_profits_balance_label.pack(pady=10)
        
        manual_profit_frame = ctk.CTkFrame(frame, fg_color="transparent")
        manual_profit_frame.pack(pady=20, padx=50, fill="x")
        
        self.manual_profit_entry = ctk.CTkEntry(manual_profit_frame, placeholder_text="إدخال مبلغ فائدة يدوي", text_color=self.text_color)
        self.manual_profit_entry.pack(side="left", expand=True, fill="x", padx=(0,10))
        
        ctk.CTkButton(manual_profit_frame, text="تسجيل", command=self.record_manual_profit,
                     fg_color=PRIMARY_COLOR, text_color=WHITE_COLOR,
                     hover_color=BUTTON_HOVER_COLOR).pack(side="right")
    
    def refresh_all_flexy_data(self):
        self.refresh_main_cash_box_data()
        self.refresh_credit_recharge_data()
        self.refresh_profits_data()
    
    def refresh_main_cash_box_data(self):
        self.flexy_main_balance_label.configure(text=f"{self.manager.main_balance:.2f} DZD")
        
        for i in self.flexy_ops_tree.get_children():
            self.flexy_ops_tree.delete(i)
        
        for log in reversed(self.manager.operations_log):
            self.flexy_ops_tree.insert('', 'end', values=list(log.values()))
    
    def refresh_credit_recharge_data(self):
        self.flexy_credit_balance_label.configure(text=f"{self.manager.credit_balance:.2f} DZD")
        
        for i in self.flexy_credit_tree.get_children():
            self.flexy_credit_tree.delete(i)
        
        for op_id, data in self.manager.credit_log.items():
            self.flexy_credit_tree.insert('', 'end', iid=op_id, values=(data['date'], f"{data['amount']:.2f}"))
    
    def refresh_profits_data(self):
        self.flexy_profits_balance_label.configure(text=f"{self.manager.profits_balance:.2f} DZD")
    
    def add_main_funds(self):
        try:
            amount = float(self.flexy_add_funds_entry.get())
            success, msg = self.manager.add_main_funds(amount)
            if success:
                self.flexy_add_funds_entry.delete(0, 'end')
                self.refresh_all_flexy_data()
                messagebox.showinfo("معلومة", msg)
        except ValueError:
            messagebox.showerror("خطأ", "مبلغ غير صحيح.")
    
    def add_credit(self):
        try:
            amount = float(self.credit_amount_entry.get())
            success, msg = self.manager.add_credit(amount)
            if success:
                self.credit_amount_entry.delete(0, 'end')
                self.refresh_all_flexy_data()
                messagebox.showinfo("معلومة", msg)
        except ValueError:
            messagebox.showerror("خطأ", "مبلغ غير صحيح.")
    
    def delete_credit(self):
        selected_id = self.flexy_credit_tree.focus()
        if not selected_id:
            messagebox.showwarning("تنبيه", "حدد عملية لحذفها.")
            return
        
        if messagebox.askyesno("تأكيد", "هل أنت متأكد من حذف العملية؟"):
            success, msg = self.manager.delete_credit(selected_id)
            if success:
                self.refresh_all_flexy_data()
                messagebox.showinfo("معلومة", msg)
    
    def record_manual_profit(self):
        try:
            amount = float(self.manual_profit_entry.get())
            success, msg = self.manager.add_manual_profit(amount)
            if success:
                self.manual_profit_entry.delete(0, 'end')
                self.refresh_profits_data()
                messagebox.showinfo("معلومة", msg)
        except ValueError:
            messagebox.showerror("خطأ", "مبلغ غير صحيح.")

class BarcodeView(ctk.CTkFrame):
    def __init__(self, parent, barcode_manager, show_main_menu_callback):
        super().__init__(parent, fg_color=BACKGROUND_COLOR)
        self.barcode_manager = barcode_manager
        self.show_main_menu_callback = show_main_menu_callback
        self.text_color = TEXT_COLOR
        self._create_layout()
    
    def _create_layout(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        
        top_frame = ctk.CTkFrame(self, fg_color="transparent")
        top_frame.grid(row=0, column=0, sticky="ew", pady=10)
        
        ctk.CTkLabel(top_frame, text="طباعة الباركود", font=("Arial", 22, "bold"), text_color=self.text_color).pack(side="right", padx=10)
        ctk.CTkButton(top_frame, text="➕ توليد باركود جديد", command=self.open_generate_barcode_window,
                     fg_color=PRIMARY_COLOR, text_color=WHITE_COLOR,
                     hover_color=BUTTON_HOVER_COLOR).pack(side="left", padx=10)
        
        log_frame = ctk.CTkFrame(self, fg_color=WHITE_COLOR, corner_radius=8)
        log_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=10)
        log_frame.grid_rowconfigure(1, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)
        
        search_frame = ctk.CTkFrame(log_frame, fg_color="transparent")
        search_frame.grid(row=0, column=0, sticky="ew", pady=5, padx=5)
        
        self.search_entry = ctk.CTkEntry(search_frame, placeholder_text="ابحث عن باركود...")
        self.search_entry.pack(side="right", expand=True, fill="x", padx=5)
        self.search_entry.bind("<Return>", lambda event: self.search_barcode())
        
        ctk.CTkButton(search_frame, text="🔍", width=40, command=self.search_barcode).pack(side="right")
        
        cols = ('التاريخ', 'الباركود')
        self.barcode_tree = ttk.Treeview(log_frame, columns=cols, show='headings')
        for col in cols:
            self.barcode_tree.heading(col, text=col)
        self.barcode_tree.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        
        ctk.CTkButton(log_frame, text="🖨️ إعادة طباعة المحدد", command=self.reprint_barcode,
                     fg_color=ACCENT_GOLD, text_color=WHITE_COLOR,
                     hover_color=BUTTON_HOVER_COLOR).grid(row=2, column=0, pady=10, padx=5, sticky="ew")
        
        ctk.CTkButton(self, text="🔙 الرجوع", 
                     fg_color=ERROR_COLOR, text_color=WHITE_COLOR,
                     hover_color=BUTTON_HOVER_COLOR,
                     command=self.show_main_menu_callback).grid(row=3, column=0, padx=10, pady=10, sticky="w")
        
        self.refresh_log()
    
    def refresh_log(self, search_term=""):
        for i in self.barcode_tree.get_children():
            self.barcode_tree.delete(i)
        
        search_term = search_term.strip().lower()
        for item in reversed(self.barcode_manager.printed_barcodes):
            if not search_term or search_term in item['barcode'].lower():
                self.barcode_tree.insert('', 'end', values=(item['date'], item['barcode']))
    
    def search_barcode(self):
        self.refresh_log(self.search_entry.get())
    
    def open_generate_barcode_window(self):
        dialog = ctk.CTkInputDialog(text="أدخل عدد الباركودات المطلوب توليدها:", title="توليد باركود")
        num_str = dialog.get_input()
        if not num_str:
            return
        
        try:
            num = int(num_str)
            if num <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("خطأ", "الرجاء إدخال عدد صحيح أكبر من صفر.")
            return
        
        if not messagebox.askyesno("تأكيد الطباعة", f"هل أنت متأكد من طباعة {num} باركود جديد؟"):
            return
        
        new_barcodes = []
        for _ in range(num):
            new_barcodes.append(self.barcode_manager.generate_unique_barcode_value())
        
        self.barcode_manager.log_printed_barcodes(new_barcodes)
        self.barcode_manager.print_barcodes(new_barcodes)
        self.refresh_log()
        messagebox.showinfo("نجاح", f"تم إرسال {num} باركود للطباعة.")
    
    def reprint_barcode(self):
        selected_item = self.barcode_tree.focus()
        if not selected_item:
            messagebox.showwarning("تنبيه", "الرجاء تحديد باركود من السجل أولاً.")
            return
        
        barcode_to_reprint = self.barcode_tree.item(selected_item)['values'][1]
        dialog = ctk.CTkInputDialog(text=f"أدخل عدد النسخ للباركود:\n{barcode_to_reprint}", title="إعادة طباعة")
        num_str = dialog.get_input()
        if not num_str:
            return
        
        try:
            num_copies = int(num_str)
            if num_copies <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("خطأ", "الرجاء إدخال عدد صحيح أكبر من صفر.")
            return
        
        if not messagebox.askyesno("تأكيد الطباعة", f"هل تريد طباعة {num_copies} نسخة من الباركود المحدد؟"):
            return
        
        self.barcode_manager.print_barcodes([barcode_to_reprint] * num_copies)
        messagebox.showinfo("نجاح", f"تم إرسال {num_copies} نسخة للطباعة.")

class MainApplication(ctk.CTk):
    def __init__(self):
        super().__init__(fg_color=BACKGROUND_COLOR)
        
        if not LIBRARIES_INSTALLED:
            messagebox.showerror("خطأ في المكتبات", "الرجاء تثبيت المكتبات المطلوبة:\npip install python-barcode reportlab")
            self.after(100, self.destroy)
            return
        
        create_data_files()
        
        self.title("برنامج التسيير")
        self.is_fullscreen = False
        self.password_visible = False
        self.current_lang = "ar"
        self._setup_translations()
        
        self.shop_cash_box_manager = CashBoxManager()
        self.product_manager = ProductManager(self.shop_cash_box_manager)
        self.shop_debt_manager = DebtManager(self.shop_cash_box_manager)
        self.repair_manager = RepairManager()
        self.flexy_manager = FlexyManager()
        self.backup_manager = BackupManager()
        self.barcode_manager = BarcodeManager(self.product_manager)
        
        self.main_container = ctk.CTkFrame(self, fg_color=BACKGROUND_COLOR)
        self.main_container.pack(fill="both", expand=True)
        
        self.current_view = None
        self.show_login_view()
    
    def clear_container(self):
        for widget in self.main_container.winfo_children():
            widget.destroy()
    
    def show_login_view(self):
        self.clear_container()
        self.geometry("450x550")
        self.resizable(False, False)
        self.title(self.translations[self.current_lang]["login_title"])
        
        login_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        login_frame.pack(expand=True, padx=40, pady=20)
        
        username_label = ctk.CTkLabel(login_frame, text="", font=("Arial", 16), text_color=TEXT_COLOR)
        username_entry = ctk.CTkEntry(login_frame, width=300, height=40, font=("Arial", 20, "bold"), justify='center',
                                    fg_color=WHITE_COLOR, border_width=2, border_color=PRIMARY_COLOR, text_color=TEXT_COLOR)
        
        password_label = ctk.CTkLabel(login_frame, text="", font=("Arial", 16), text_color=TEXT_COLOR)
        password_frame = ctk.CTkFrame(login_frame, fg_color="transparent")
        password_entry = ctk.CTkEntry(password_frame, width=255, height=40, font=("Arial", 20, "bold"), justify='center', show="*",
                                     fg_color=WHITE_COLOR, border_width=2, border_color=PRIMARY_COLOR, text_color=TEXT_COLOR)
        toggle_pass_button = ctk.CTkButton(password_frame, text="👁️", width=40, height=40, font=("Arial", 24),
                                         command=lambda: self.toggle_password_visibility(password_entry),
                                         fg_color=PRIMARY_COLOR, text_color=WHITE_COLOR, hover_color=BUTTON_HOVER_COLOR)
        
        login_button = ctk.CTkButton(login_frame, text="", width=300, height=40, font=("Arial", 16, "bold"),
                                   command=lambda: self.check_login(username_entry, password_entry, error_label),
                                   fg_color=PRIMARY_COLOR, text_color=WHITE_COLOR, hover_color=BUTTON_HOVER_COLOR)
        
        error_label = ctk.CTkLabel(login_frame, text="", text_color=ERROR_COLOR, font=("Arial", 14))
        
        username_label.pack(pady=(10, 5), anchor="w")
        username_entry.pack(pady=5)
        password_label.pack(pady=(20, 5), anchor="w")
        password_frame.pack(pady=5)
        password_entry.pack(side="left")
        toggle_pass_button.pack(side="left", padx=(5, 0))
        login_button.pack(pady=(30, 10))
        error_label.pack(pady=5)
        
        bottom_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        bottom_frame.pack(side="bottom", fill="x", pady=10, padx=20)
        
        language_button = ctk.CTkButton(bottom_frame, text="", width=100,
                                      command=self.toggle_language,
                                      fg_color=PRIMARY_COLOR, text_color=WHITE_COLOR,
                                      hover_color=BUTTON_HOVER_COLOR)
        language_button.pack(side="left")
        
        fullscreen_button = ctk.CTkButton(bottom_frame, text="", font=("Arial", 16),
                                        command=self.toggle_fullscreen,
                                        fg_color=PRIMARY_COLOR, text_color=WHITE_COLOR,
                                        hover_color=BUTTON_HOVER_COLOR)
        fullscreen_button.pack(side="left", expand=True, padx=10)
        
        exit_button = ctk.CTkButton(bottom_frame, text="", width=100,
                                   command=self.safe_exit,
                                   fg_color=ERROR_COLOR, text_color=WHITE_COLOR,
                                   hover_color=BUTTON_HOVER_COLOR)
        exit_button.pack(side="right")
        
        self.ui_elements_to_translate = {
            'login': [username_label, password_label, login_button, language_button, fullscreen_button, exit_button]
        }
        self.update_ui_texts()
    
    def show_main_menu_view(self):
        self.clear_container()
        self.geometry("450x550")
        self.resizable(False, False)
        self.title(self.translations[self.current_lang]["main_title"])
        
        main_menu_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        main_menu_frame.pack(expand=True, padx=40, pady=20)
        
        buttons_data = {
            "shop_button": self.show_shop_view,
            "repair_button": self.show_repair_view,
            "flexy_button": self.show_flexy_view,
            "barcode_button": self.show_barcode_view,
            "backup_button": self._execute_save_backup,
            "restore_button": self._execute_restore_backup
        }
        
        lang = self.translations[self.current_lang]
        for key, command in buttons_data.items():
            ctk.CTkButton(
                main_menu_frame, text=lang[key], width=300, height=55,
                font=("Arial", 22, "bold"), fg_color=PRIMARY_COLOR,
                text_color=WHITE_COLOR, hover_color=BUTTON_HOVER_COLOR,
                command=command
            ).pack(pady=8)
    
    def show_shop_view(self):
        self.clear_container()
        self.geometry("1200x700")
        self.resizable(True, True)
        self.title("🏪 قسم المحل")
        self.current_view = ShopView(
            self.main_container, self.shop_cash_box_manager,
            self.product_manager, self.shop_debt_manager,
            self.show_main_menu_view
        )
        self.current_view.pack(fill="both", expand=True)
    
    def show_repair_view(self):
        self.clear_container()
        self.geometry("1000x750")
        self.resizable(True, True)
        self.title("🛠️ قسم التصليح")
        self.current_view = RepairView(
            self.main_container, self.repair_manager,
            self.show_main_menu_view
        )
        self.current_view.pack(fill="both", expand=True)
    
    def show_flexy_view(self):
        self.clear_container()
        self.geometry("1100x700")
        self.resizable(True, True)
        self.title("💳 قسم الفلكسي")
        self.current_view = FlexyView(
            self.main_container, self.flexy_manager,
            self.show_main_menu_view
        )
        self.current_view.pack(fill="both", expand=True)
    
    def show_barcode_view(self):
        self.clear_container()
        self.geometry("800x600")
        self.resizable(True, True)
        self.title("🖨️ طباعة الباركود")
        self.current_view = BarcodeView(
            self.main_container, self.barcode_manager,
            self.show_main_menu_view
        )
        self.current_view.pack(fill="both", expand=True)
    
    def _setup_translations(self):
        self.translations = {
            "ar": {
                "login_title": "واجهة الدخول",
                "main_title": "القائمة الرئيسية",
                "username_label": "اسم المستخدم:",
                "password_label": "كلمة المرور:",
                "login_button": "دخول",
                "exit_button": "خروج",
                "language_button": "English",
                "error_message": "اسم المستخدم أو كلمة المرور غير صحيحة",
                "shop_button": "🏪 المحل",
                "repair_button": "🛠️ التصليح",
                "flexy_button": "💳 الفلكسي",
                "barcode_button": "🖨️ طباعة الباركود",
                "backup_button": "💾 حفظ نسخة",
                "restore_button": "🔁 استرجاع نسخة",
                "fullscreen_button_expand": "تكبير ↔️",
                "fullscreen_button_restore": "تصغير ↙️"
            },
            "en": {
                "login_title": "Login",
                "main_title": "Main Menu",
                "username_label": "Username:",
                "password_label": "Password:",
                "login_button": "Login",
                "exit_button": "Exit",
                "language_button": "العربية",
                "error_message": "Incorrect credentials",
                "shop_button": "🏪 Shop",
                "repair_button": "🛠️ Repairs",
                "flexy_button": "💳 Flexy",
                "barcode_button": "🖨️ Print Barcode",
                "backup_button": "💾 Save Backup",
                "restore_button": "🔁 Restore Backup",
                "fullscreen_button_expand": "Fullscreen ↔️",
                "fullscreen_button_restore": "Restore ↙️"
            }
        }
    
    def check_login(self, username_entry, password_entry, error_label):
        if username_entry.get() == "2025" and password_entry.get() == "2025":
            self.show_main_menu_view()
        else:
            error_label.configure(text=self.translations[self.current_lang]["error_message"])
    
    def update_ui_texts(self):
        lang = self.translations[self.current_lang]
        
        if hasattr(self, 'ui_elements_to_translate') and 'login' in self.ui_elements_to_translate:
            elements = self.ui_elements_to_translate['login']
            elements[0].configure(text=lang["username_label"])
            elements[1].configure(text=lang["password_label"])
            elements[2].configure(text=lang["login_button"])
            elements[3].configure(text=lang["language_button"])
            elements[4].configure(text=lang["fullscreen_button_restore"] if self.is_fullscreen else lang["fullscreen_button_expand"])
            elements[5].configure(text=lang["exit_button"])
            
            anchor_side = "w" if self.current_lang == "en" else "e"
            elements[0].pack_configure(anchor=anchor_side)
            elements[1].pack_configure(anchor=anchor_side)
    
    def toggle_fullscreen(self):
        self.is_fullscreen = not self.is_fullscreen
        self.attributes("-fullscreen", self.is_fullscreen)
        self.update_ui_texts()
    
    def toggle_language(self):
        self.current_lang = "en" if self.current_lang == "ar" else "ar"
        self.update_ui_texts()
    
    def toggle_password_visibility(self, password_entry):
        self.password_visible = not self.password_visible
        if self.password_visible:
            password_entry.configure(show="")
        else:
            password_entry.configure(show="*")
    
    def _execute_save_backup(self):
        data_to_save = {
            'shop_cash_box': {'balance': self.shop_cash_box_manager.balance, 'log': self.shop_cash_box_manager.log},
            'products': {'products': self.product_manager.products},
            'shop_debts': {'debts': self.shop_debt_manager.debts},
            'repair': {'balance': self.repair_manager.balance, 'log': self.repair_manager.log, 
                      'workers': self.repair_manager.workers, 'debts': self.repair_manager.debts},
            'flexy': {'main_balance': self.flexy_manager.main_balance, 
                     'credit_balance': self.flexy_manager.credit_balance, 
                     'profits_balance': self.flexy_manager.profits_balance, 
                     'credit_log': self.flexy_manager.credit_log, 
                     'operations_log': self.flexy_manager.operations_log},
            'barcodes': {'printed_barcodes': self.barcode_manager.printed_barcodes}
        }
        self.backup_manager.save_backup(data_to_save)
    
    def _execute_restore_backup(self):
        data = self.backup_manager.load_backup()
        if data:
            try:
                # Shop Data
                self.shop_cash_box_manager.balance = data['shop_cash_box']['balance']
                self.shop_cash_box_manager.log = data['shop_cash_box']['log']
                self.product_manager.products = data['products']['products']
                self.shop_debt_manager.debts = data['shop_debts']['debts']
                
                # Repair Data
                self.repair_manager.balance = data['repair']['balance']
                self.repair_manager.log = data['repair']['log']
                self.repair_manager.workers = data['repair']['workers']
                self.repair_manager.debts = data['repair']['debts']
                
                # Flexy Data
                self.flexy_manager.main_balance = data['flexy']['main_balance']
                self.flexy_manager.credit_balance = data['flexy']['credit_balance']
                self.flexy_manager.profits_balance = data['flexy']['profits_balance']
                self.flexy_manager.credit_log = data['flexy']['credit_log']
                self.flexy_manager.operations_log = data['flexy']['operations_log']
                
                # Barcodes Data
                self.barcode_manager.printed_barcodes = data.get('barcodes', {}).get('printed_barcodes', [])
                
                # Save restored data to individual files
                save_data(self.shop_cash_box_manager, "cash.json")
                save_data(self.product_manager, "products.json")
                save_data(self.shop_debt_manager, "debts.json")
                save_data(self.repair_manager, "repair.json")
                save_data(self.flexy_manager, "flexy.json")
                save_data(self.barcode_manager, "barcodes.json")
                
                messagebox.showinfo("نجاح", "تم استرجاع النسخة الاحتياطية بنجاح.")
            except KeyError as e:
                messagebox.showerror("خطأ", f"ملف النسخة الاحتياطية غير مكتمل أو تالف. الحقل المفقود: {e}")
            except Exception as e:
                messagebox.showerror("خطأ", f"حدث خطأ أثناء استرجاع البيانات: {e}")
    
    def safe_exit(self):
        self.destroy()

if __name__ == "__main__":
    app = MainApplication()
    app.mainloop()
