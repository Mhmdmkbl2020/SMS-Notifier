import tkinter as tk
from tkinter import ttk, messagebox
import pyodbc
import serial
import time
import threading

# تخزين الإعدادات في متغير عام
db_settings = {}

# دالة لإنشاء الاتصال بقاعدة بيانات SQL Server باستخدام الإعدادات المخزنة.
def connect_to_database():
    try:
        conn_str = (
            f"DRIVER={{SQL Server}};"
            f"SERVER={db_settings['server']};"
            f"DATABASE={db_settings['database']};"
            f"UID={db_settings['username']};"
            f"PWD={db_settings['password']};"
        )
        conn = pyodbc.connect(conn_str)
        return conn
    except Exception as e:
        print("خطأ الاتصال بقاعدة البيانات:", e)
        return None

# دالة لاسترجاع الرسائل غير المرسلة من جدول SMSQueue.
# يُفترض أن الجدول يحتوي على الأعمدة: id, phone_number, sms_message, sent
def fetch_unsent_messages():
    conn = connect_to_database()
    if conn is None:
        return []
    try:
        cursor = conn.cursor()
        query = "SELECT id, phone_number, sms_message FROM SMSQueue WHERE sent = 0"
        cursor.execute(query)
        records = cursor.fetchall()
        conn.close()
        return records
    except Exception as e:
        print("خطأ في تنفيذ الاستعلام:", e)
        conn.close()
        return []

# دالة لتحديث حالة الرسالة بعد الإرسال (تعيين sent = 1).
def update_message_status(message_id):
    conn = connect_to_database()
    if conn is None:
        return False
    try:
        cursor = conn.cursor()
        update_query = "UPDATE SMSQueue SET sent = 1 WHERE id = ?"
        cursor.execute(update_query, message_id)
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print("خطأ في تحديث حالة الرسالة:", e)
        conn.close()
        return False

# دالة لإرسال رسالة SMS عبر مودم GSM باستخدام أوامر AT.
def send_sms(com_port, phone_number, message_text):
    try:
        modem = serial.Serial(com_port, 9600, timeout=1)
        time.sleep(1)  # الانتظار لبعض الوقت لجاهزية المودم

        # إرسال أمر AT للتأكد من استجابة المودم
        modem.write(b'AT\r')
        time.sleep(0.5)
        response = modem.readlines()
        print("استجابة المودم:", response)

        # تحويل المودم إلى وضع النصوص (Text Mode)
        modem.write(b'AT+CMGF=1\r')
        time.sleep(0.5)
        
        # إرسال أمر تحديد رقم الهاتف المستقبل
        command = 'AT+CMGS="{}"\r'.format(phone_number)
        modem.write(command.encode())
        time.sleep(0.5)
        
        # إرسال نص الرسالة مع رمز Ctrl+Z ( \x1A ) لإنهاء الرسالة
        full_message = message_text + "\x1A"
        modem.write(full_message.encode())
        time.sleep(3)  # الانتظار لإتمام الإرسال

        modem.close()
        print("تم إرسال الرسالة إلى:", phone_number)
        return True
    except Exception as e:
        print("خطأ أثناء إرسال SMS:", e)
        return False

# الدالة التي تعمل في الخيط الخلفي لتفقد قاعدة البيانات بشكل دوري.
def poll_database():
    com_port = db_settings['com_port']
    while db_settings.get('monitoring', False):
        print("تفقد قاعدة البيانات للرسائل الجديدة...")
        records = fetch_unsent_messages()
        for record in records:
            message_id = record[0]
            phone = record[1]
            msg = record[2]
            print(f"إرسال رسالة لـ {phone} ...")
            if send_sms(com_port, phone, msg):
                update_message_status(message_id)
        time.sleep(10)  # الانتظار 10 ثوانٍ قبل التفقد مرة أخرى

# دالة بدء المراقبة في الخلفية.
def start_monitoring():
    global db_settings
    # قراءة بيانات الاتصال من الواجهة
    server = server_entry.get().strip()
    database = database_entry.get().strip()
    username = username_entry.get().strip()
    password = password_entry.get().strip()
    com_port = com_port_entry.get().strip()
    
    if not (server and database and username and password and com_port):
        messagebox.showerror("خطأ", "يرجى ملء جميع الحقول!")
        return
    
    # تخزين الإعدادات
    db_settings['server'] = server
    db_settings['database'] = database
    db_settings['username'] = username
    db_settings['password'] = password
    db_settings['com_port'] = com_port
    db_settings['monitoring'] = True
    
    # بدء الخيط الخلفي للمراقبة
    threading.Thread(target=poll_database, daemon=True).start()
    messagebox.showinfo("تم التشغيل", "تم تشغيل المراقبة في الخلفية.")

# دالة إيقاف المراقبة.
def stop_monitoring():
    db_settings['monitoring'] = False
    messagebox.showinfo("متوقف", "تم إيقاف المراقبة.")

# إنشاء الواجهة الرئيسية باستخدام tkinter.
root = tk.Tk()
root.title("SMS Notifier - Background Monitoring")

frame = ttk.Frame(root, padding="10")
frame.grid(row=0, column=0, sticky=(tk.W, tk.E))

# مدخلات إعدادات قاعدة البيانات.
ttk.Label(frame, text="عنوان الخادم:").grid(row=0, column=0, sticky=tk.W, pady=2)
server_entry = ttk.Entry(frame, width=30)
server_entry.grid(row=0, column=1, pady=2)

ttk.Label(frame, text="اسم قاعدة البيانات:").grid(row=1, column=0, sticky=tk.W, pady=2)
database_entry = ttk.Entry(frame, width=30)
database_entry.grid(row=1, column=1, pady=2)

ttk.Label(frame, text="اسم المستخدم:").grid(row=2, column=0, sticky=tk.W, pady=2)
username_entry = ttk.Entry(frame, width=30)
username_entry.grid(row=2, column=1, pady=2)

ttk.Label(frame, text="كلمة المرور:").grid(row=3, column=0, sticky=tk.W, pady=2)
password_entry = ttk.Entry(frame, width=30, show="*")
password_entry.grid(row=3, column=1, pady=2)

# مدخل منفذ المودم.
ttk.Label(frame, text="رقم منفذ GSM (مثلاً COM3):").grid(row=4, column=0, sticky=tk.W, pady=2)
com_port_entry = ttk.Entry(frame, width=30)
com_port_entry.grid(row=4, column=1, pady=2)

# أزرار بدء وإيقاف المراقبة.
start_button = ttk.Button(frame, text="بدء المراقبة", command=start_monitoring)
start_button.grid(row=5, column=0, pady=10)

stop_button = ttk.Button(frame, text="إيقاف المراقبة", command=stop_monitoring)
stop_button.grid(row=5, column=1, pady=10)

root.mainloop()
