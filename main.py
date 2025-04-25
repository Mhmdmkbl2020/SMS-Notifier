import tkinter as tk
from tkinter import ttk, messagebox
import pyodbc
import serial
import time
import threading
import os
from dotenv import load_dotenv  # إضافة dotenv لتحميل المتغيرات من ملف .env

# تحميل المتغيرات من ملف .env
load_dotenv()

# تخزين الإعدادات باستخدام متغيرات البيئة (أكثر أمانًا)
db_settings = {
    'server': os.getenv('DB_SERVER', ''),
    'database': os.getenv('DB_NAME', ''),
    'username': os.getenv('DB_USER', ''),
    'password': os.getenv('DB_PASSWORD', ''),
    'com_port': os.getenv('COM_PORT', ''),
    'monitoring': False
}

def connect_to_database():
    try:
        conn_str = (
            f"DRIVER={{SQL Server}};"
            f"SERVER={db_settings['server']};"
            f"DATABASE={db_settings['database']};"
            f"UID={db_settings['username']};"
            f"PWD={db_settings['password']};"
        )
        return pyodbc.connect(conn_str)
    except pyodbc.Error as e:
        messagebox.showerror("خطأ قاعدة البيانات", f"فشل الاتصال: {str(e)}")
        return None

def fetch_unsent_messages():
    try:
        with connect_to_database() as conn:  # استخدام with لضمان إغلاق الاتصال
            cursor = conn.cursor()
            cursor.execute("SELECT id, phone_number, sms_message FROM SMSQueue WHERE sent = 0")
            return cursor.fetchall()
    except Exception as e:
        messagebox.showerror("خطأ", f"فشل استرداد الرسائل: {str(e)}")
        return []

def update_message_status(message_id):
    try:
        with connect_to_database() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE SMSQueue SET sent = 1 WHERE id = ?", (message_id,))
            conn.commit()
            return True
    except Exception as e:
        messagebox.showerror("خطأ", f"فشل تحديث الحالة: {str(e)}")
        return False

def send_sms(com_port, phone_number, message_text):
    try:
        with serial.Serial(com_port, 9600, timeout=1) as modem:
            time.sleep(1)
            modem.write(b'AT\r')
            time.sleep(0.5)
            response = modem.read_all().decode('utf-8', errors='ignore')
            
            modem.write(b'AT+CMGF=1\r')  # تفعيل وضع النص
            time.sleep(0.5)
            
            modem.write(f'AT+CMGS="{phone_number}"\r'.encode())
            time.sleep(0.5)
            
            modem.write(f"{message_text}\x1A".encode())  # إضافة Ctrl+Z لإرسال الرسالة
            time.sleep(3)
            
            response = modem.read_all().decode('utf-8', errors='ignore')
            return "OK" in response  # التحقق من نجاح الإرسال
    except serial.SerialException as e:
        messagebox.showerror("خطأ في الاتصال", f"فشل إرسال SMS: {str(e)}")
        return False

def poll_database():
    while db_settings['monitoring']:
        try:
            records = fetch_unsent_messages()
            for record in records:
                message_id, phone, msg = record
                if send_sms(db_settings['com_port'], phone, msg):
                    update_message_status(message_id)
        except Exception as e:
            messagebox.showerror("خطأ عام", f"حدث خطأ: {str(e)}")
        time.sleep(10)

def start_monitoring():
    # التحقق من صحة المدخلات
    required_fields = [
        (server_entry, "عنوان الخادم"),
        (database_entry, "اسم قاعدة البيانات"),
        (username_entry, "اسم المستخدم"),
        (password_entry, "كلمة المرور"),
        (com_port_entry, "رقم المنفذ")
    ]
    
    for entry, field_name in required_fields:
        if not entry.get().strip():
            messagebox.showerror("خطأ", f"الرجاء إدخال {field_name}!")
            return
    
    # تحديث الإعدادات
    db_settings.update({
        'server': server_entry.get().strip(),
        'database': database_entry.get().strip(),
        'username': username_entry.get().strip(),
        'password': password_entry.get().strip(),
        'com_port': com_port_entry.get().strip(),
        'monitoring': True
    })
    
    # بدء المراقبة في خيط منفصل
    threading.Thread(target=poll_database, daemon=True).start()
    messagebox.showinfo("نجاح", "تم بدء المراقبة بنجاح!")

def stop_monitoring():
    db_settings['monitoring'] = False
    messagebox.showinfo("نجاح", "تم إيقاف المراقبة.")

# إنشاء الواجهة
root = tk.Tk()
root.title("SMS Notifier - مراقبة الخلفية")

frame = ttk.Frame(root, padding="20")
frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

# إضافة الحقول والزرار
fields = [
    ("عنوان الخادم:", "server_entry"),
    ("اسم قاعدة البيانات:", "database_entry"),
    ("اسم المستخدم:", "username_entry"),
    ("كلمة المرور:", "password_entry", "*"),
    ("رقم منفذ GSM (مثال: COM3):", "com_port_entry")
]

for i, (label_text, entry_name) in enumerate(fields):
    ttk.Label(frame, text=label_text).grid(row=i, column=0, padx=5, pady=5, sticky=tk.W)
    entry = ttk.Entry(frame, width=40, show=fields[i][2] if len(fields[i]) > 2 else None)
    entry.grid(row=i, column=1, padx=5, pady=5)
    setattr(frame, entry_name, entry)

ttk.Button(frame, text="بدء المراقبة", command=start_monitoring).grid(row=5, column=0, pady=15)
ttk.Button(frame, text="إيقاف المراقبة", command=stop_monitoring).grid(row=5, column=1, pady=15)

root.mainloop()
