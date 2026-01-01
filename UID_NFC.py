import tkinter as tk
from tkinter import filedialog, messagebox, ttk, Toplevel
from fpdf import FPDF
from PIL import Image, ImageTk
import pytesseract
import sqlite3
import smtplib
from email.message import EmailMessage
import datetime
import os
import threading
import time
import fitz  # PyMuPDF for PDF preview

# CONFIGURATION
LOGO_PATH = "srm-institute-of-science-and-technology-logo-png_seeklogo-381994.png"
DB_NAME = "healthcare.db"
SMTP_EMAIL = "sk9024@srmist.edu.in"
SMTP_PASSWORD = "itlt zblu bvae xjlp"
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# --- Database Setup ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS patients (
            uid TEXT PRIMARY KEY,
            doctor_name TEXT, patient_name TEXT, patient_number TEXT,
            patient_address TEXT, diagnosis TEXT, past_treatment TEXT,
            medications TEXT, prescription TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS email_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uid TEXT, email TEXT, sent_at TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS medication_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uid TEXT,
            disease TEXT,
            timestamp TEXT
        )
    """)
    conn.commit()
    conn.close()

# --- UID NFC Polling Thread (Simulated) ---
def poll_nfc():
    while True:
        try:
            with open("/dev/hidraw0", "rb") as f:
                data = f.read(16)
                uid = ''.join([f"{b:02X}" for b in data[:4]])
                entry_uid.delete(0, tk.END)
                entry_uid.insert(0, uid)
                load_patient_data()
                break
        except Exception:
            time.sleep(2)
            continue

def start_nfc_thread():
    threading.Thread(target=poll_nfc, daemon=True).start()

# --- Load Data ---
def load_patient_data(event=None):
    uid = entry_uid.get().strip()
    if not uid: return
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT * FROM patients WHERE uid = ?", (uid,))
    row = cur.fetchone()
    conn.close()
    if row:
        keys = list(form_fields.keys())
        for i, val in enumerate(row[1:]):
            widget = form_fields[keys[i]]
            if isinstance(widget, tk.Text):
                widget.delete("1.0", tk.END)
                widget.insert(tk.END, val)
            else:
                widget.delete(0, tk.END)
                widget.insert(0, val)
    else:
        messagebox.showinfo("Info", "New UID. Enter patient info.")

# --- OCR ---
def scan_prescription_image():
    path = filedialog.askopenfilename(filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp")])
    if path:
        try:
            img = Image.open(path)
            text = pytesseract.image_to_string(img)
            form_fields["Prescription"].delete("1.0", tk.END)
            form_fields["Prescription"].insert(tk.END, text)
        except Exception as e:
            messagebox.showerror("OCR Error", str(e))

# --- Save Patient Data ---
def save_to_db(uid):
    data = (
        uid,
        form_fields["Doctor Name"].get(),
        form_fields["Patient Name"].get(),
        form_fields["Patient Number"].get(),
        form_fields["Patient Address"].get(),
        form_fields["Diagnosis"].get("1.0", tk.END).strip(),
        form_fields["Past Treatment"].get("1.0", tk.END).strip(),
        form_fields["Medications"].get("1.0", tk.END).strip(),
        form_fields["Prescription"].get("1.0", tk.END).strip()
    )
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("REPLACE INTO patients VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", data)
    conn.commit()
    conn.close()
    messagebox.showinfo("Saved", "Patient data saved to database.")

# --- Export PDF ---
def export_to_pdf(filepath=None, preview=False):
    pdf = FPDF()
    pdf.add_page()
    if os.path.exists(LOGO_PATH):
        pdf.image(LOGO_PATH, x=160, y=10, w=35)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, "SRM GLOBAL HOSPITAL", ln=True, align="C")
    pdf.set_font("Arial", '', 12)
    pdf.cell(0, 10, "PATIENT HEALTH REPORT", ln=True, align="C")
    pdf.ln(20)

    pdf.set_font("Arial", '', 11)
    for label, widget in form_fields.items():
        value = widget.get("1.0", tk.END).strip() if isinstance(widget, tk.Text) else widget.get()
        pdf.set_fill_color(240, 240, 240)
        pdf.cell(50, 10, f"{label}:", border=1, fill=True)
        pdf.multi_cell(0, 10, value, border=1)
    pdf.ln(10)

    pdf.set_y(-40)
    pdf.set_font("Arial", 'I', 10)
    pdf.cell(0, 10, "SRM Global Hospital - Helpline: 044 4743 2350", ln=True, align="C")
    pdf.cell(0, 10, "Generated on: " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), ln=True, align="C")

    if not filepath:
        filepath = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
    if filepath:
        pdf.output(filepath)
        if preview:
            preview_pdf(filepath)
        else:
            messagebox.showinfo("PDF", f"Saved: {filepath}")
        return filepath

# --- PDF Preview ---
def preview_pdf(pdf_path):
    try:
        doc = fitz.open(pdf_path)
        page = doc.load_page(0)
        pix = page.get_pixmap()
        img_path = "preview.png"
        pix.save(img_path)
        doc.close()

        top = Toplevel(root)
        top.title("PDF Preview")
        img = Image.open(img_path)
        img = img.resize((600, 800))
        photo = ImageTk.PhotoImage(img)
        label = tk.Label(top, image=photo)
        label.image = photo
        label.pack()
    except Exception as e:
        messagebox.showerror("Preview Error", str(e))

# --- Email ---
def send_email():
    uid = entry_uid.get().strip()
    recipient = email_entry.get().strip()
    if not uid or not recipient:
        return messagebox.showerror("Missing Info", "Provide UID and email.")

    try:
        tmp_pdf = "temp_report.pdf"
        export_to_pdf(filepath=tmp_pdf)

        msg = EmailMessage()
        msg["Subject"] = "SRM Patient Report"
        msg["From"] = SMTP_EMAIL
        msg["To"] = recipient
        msg.set_content("Find attached patient report.")
        with open(tmp_pdf, "rb") as f:
            msg.add_attachment(f.read(), maintype='application', subtype='pdf', filename="Patient_Report.pdf")

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.send_message(msg)

        os.remove(tmp_pdf)

        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("INSERT INTO email_logs (uid, email, sent_at) VALUES (?, ?, ?)", (uid, recipient, datetime.datetime.now()))
        conn.commit()
        conn.close()
        messagebox.showinfo("Sent", f"Email sent to {recipient}")
    except Exception as e:
        messagebox.showerror("Email Error", str(e))

# --- View Email Logs ---
def view_email_logs():
    logs_window = tk.Toplevel(root)
    logs_window.title("Email Logs")
    logs_window.geometry("500x300")

    tree = ttk.Treeview(logs_window, columns=("UID", "Email", "Sent At"), show='headings')
    tree.heading("UID", text="UID")
    tree.heading("Email", text="Email")
    tree.heading("Sent At", text="Sent At")
    tree.pack(fill=tk.BOTH, expand=True)

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT uid, email, sent_at FROM email_logs ORDER BY sent_at DESC")
    for row in cur.fetchall():
        tree.insert('', tk.END, values=row)
    conn.close()

# --- Medication History ---
def open_medication_history():
    uid = entry_uid.get().strip()
    if not uid:
        return messagebox.showerror("Error", "Enter UID first.")

    win = Toplevel(root)
    win.title("History of Medications")
    win.geometry("600x400")

    columns = ("Disease", "DateTime")
    tree = ttk.Treeview(win, columns=columns, show="headings")
    tree.heading("Disease", text="Disease/Treatment")
    tree.heading("DateTime", text="Date & Time")
    tree.pack(fill=tk.BOTH, expand=True, pady=10)

    def refresh_history():
        for row in tree.get_children():
            tree.delete(row)
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT disease, timestamp FROM medication_history WHERE uid=? ORDER BY timestamp DESC", (uid,))
        for disease, timestamp in cur.fetchall():
            tree.insert('', tk.END, values=(disease, timestamp))
        conn.close()

    def add_history():
        disease = disease_entry.get().strip()
        if disease:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn = sqlite3.connect(DB_NAME)
            cur = conn.cursor()
            cur.execute("INSERT INTO medication_history (uid, disease, timestamp) VALUES (?, ?, ?)", (uid, disease, timestamp))
            conn.commit()
            conn.close()
            disease_entry.delete(0, tk.END)
            refresh_history()

    def delete_selected():
        selected = tree.selection()
        if selected:
            values = tree.item(selected[0], "values")
            conn = sqlite3.connect(DB_NAME)
            cur = conn.cursor()
            cur.execute("DELETE FROM medication_history WHERE uid=? AND disease=? AND timestamp=?", (uid, values[0], values[1]))
            conn.commit()
            conn.close()
            refresh_history()

    frm = ttk.Frame(win)
    frm.pack(pady=5)

    ttk.Label(frm, text="Disease/Treatment:").grid(row=0, column=0, padx=5)
    disease_entry = ttk.Entry(frm, width=30)
    disease_entry.grid(row=0, column=1, padx=5)
    ttk.Button(frm, text="Add", command=add_history).grid(row=0, column=2, padx=5)
    ttk.Button(frm, text="Delete Selected", command=delete_selected).grid(row=0, column=3, padx=5)

    refresh_history()

# --- GUI ---
root = tk.Tk()
root.title("SRM NFC Healthcare System")
root.geometry("700x1000")
root.configure(bg="#f5f7fa")

style = ttk.Style()
style.theme_use("clam")
style.configure("TButton", font=("Segoe UI", 11), foreground="white", background="#0052cc")
style.configure("TLabel", font=("Segoe UI", 11, "bold"), background="#f5f7fa")
style.configure("TEntry", font=("Segoe UI", 11))

# Header
logo_img = Image.open(LOGO_PATH)
logo_img = logo_img.resize((100, 100))
logo_photo = ImageTk.PhotoImage(logo_img)
tk.Label(root, image=logo_photo, bg="#f5f7fa").pack(pady=5)

header = ttk.Label(root, text="SRM NFC Healthcare System", font=("Segoe UI", 18, "bold"), foreground="#0052cc")
header.pack(pady=5)

entry_uid = ttk.Entry(root, width=50)
entry_uid.pack(pady=10)
entry_uid.bind("<Return>", load_patient_data)

form_fields = {}

def add_field(label, multiline=False):
    ttk.Label(root, text=label + ":").pack(anchor="w", padx=20, pady=(10, 0))
    widget = tk.Text(root, height=4, width=70) if multiline else ttk.Entry(root, width=70)
    widget.pack(padx=20, pady=2)
    form_fields[label] = widget
    return widget

add_field("Doctor Name")
add_field("Patient Name")
add_field("Patient Number")
add_field("Patient Address")
add_field("Diagnosis", multiline=True)
add_field("Past Treatment", multiline=True)
add_field("Medications", multiline=True)
add_field("Prescription", multiline=True)

btn_frame = ttk.Frame(root)
btn_frame.pack(pady=15)

ttk.Button(btn_frame, text="📥 Scan Prescription", command=scan_prescription_image).grid(row=0, column=0, padx=5, pady=5)
ttk.Button(btn_frame, text="💾 Save", command=lambda: save_to_db(entry_uid.get())).grid(row=0, column=1, padx=5, pady=5)
ttk.Button(btn_frame, text="📤 Export PDF & Preview", command=lambda: export_to_pdf(preview=True)).grid(row=0, column=2, padx=5, pady=5)

email_label = ttk.Label(root, text="Recipient Email:")
email_label.pack()
email_entry = ttk.Entry(root, width=50)
email_entry.pack()
ttk.Button(root, text="📤 Send Email", command=send_email).pack(pady=10)
ttk.Button(root, text="📜 View Email Logs", command=view_email_logs).pack(pady=5)
ttk.Button(root, text="📚 History of Medications", command=open_medication_history).pack(pady=5)

init_db()
start_nfc_thread()
root.mainloop()