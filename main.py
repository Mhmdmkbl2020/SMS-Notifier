# main.py
import tkinter as tk
from tkinter import ttk, messagebox
import pyodbc
import serial
import time
import threading
import logging

# إعدادات التسجيل للأخطاء
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# تخزين الإعدادات مع قيم افتراضية
db_settings = {
    'monitoring': False,
    'server': '',
    'database': '',
    'username': '',
    'password': '',
    'com_port': 'COM3'
}

# دالة الاتصال بقاعدة البيانات مع معالجة الأخطاء المحسنة
def connect_to_database():
    try:
        conn_str = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={db_settings['server']};"
            f"DATABASE={db_settings['database']};"
            f"UID={db_settings['username']};"
            f"PWD={db_settings['password']};"
        )
        conn = pyodbc.connect(conn_str)
        return conn
    except pyodbc.Error as e:
        logging.error(f"فشل الاتصال بقاعدة البيانات: {str(e)}")
        messagebox.showerror("خطأ", f"فشل الاتصال بقاعدة البيانات:\n{str(e)}")
        return None

# استرجاع الرسائل غير المرسلة مع معالجة الأخطاء
def fetch_unsent_messages():
    conn = connect_to_database()
    if conn is None:
        return []
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, phone_number, sms_message FROM SMSQueue WHERE sent = 0")
        records = cursor.fetchall()
        return records
    except pyodbc.Error as e:
        logging.error(f"خطأ في الاستعلام: {str(e)}")
        return []
    finally:
        conn.close()

# تحديث حالة الرسالة مع معالجة الأخطاء
def update_message_status(message_id):
    conn = connect_to_database()
    if conn is None:
        return False
    
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE SMSQueue SET sent = 1 WHERE id = ?", message_id)
        conn.commit()
        return True
    except pyodbc.Error as e:
        logging.error(f"خطأ في التحديث: {str(e)}")
        return False
    finally:
        conn.close()

# إرسال SMS مع تحسينات التحكم في المودم
def send_sms(com_port, phone_number, message_text):
    try:
        modem = serial.Serial(com_port, 9600, timeout=2)
        time.sleep(1)
        
        # اختبار استجابة المودم
        modem.write(b'AT\r\n')
        response = modem.read_until(b'OK\r\n', timeout=3)
        if b'OK' not in response:
            logging.error("المودم لا يستجيب لأوامر AT")
            return False
        
        # التبديل إلى وضع النص
        modem.write(b'AT+CMGF=1\r\n')
        response = modem.read_until(b'OK\r\n', timeout=3)
        if b'OK' not in response:
            logging.error("فشل التبديل إلى وضع النص")
            return False
        
