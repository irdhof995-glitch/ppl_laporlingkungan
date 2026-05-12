import os
import time
import datetime
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from werkzeug.utils import secure_filename
import firebase_admin
from firebase_admin import credentials, firestore, auth

app = Flask(__name__)
app.secret_key = "lapor_lingkungan_secret_key"

# Inisialisasi Firebase Admin
# Pastikan file serviceAccountKey.json ada di root directory
try:
    if os.path.exists('serviceAccountKey.json'):
        cred = credentials.Certificate("serviceAccountKey.json")
        firebase_admin.initialize_app(cred)
        db = firestore.client(database_id="ai-studio-bc3770dc-ab4a-474e-a3fb-c148205d9008")
        USING_FIRESTORE = True
        print("Firebase Berhasil Terhubung")
    else:
        print("Peringatan: serviceAccountKey.json tidak ditemukan.")
        USING_FIRESTORE = False
except Exception as e:
    print(f"Error Firebase: {e}")
    USING_FIRESTORE = False

# Konfigurasi Upload
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Mock Data (Fallback)
mock_users = [
    {"id": "user1", "name": "Irdho Fibra", "email": "admin@lapor.com", "role": "ADMIN", "avatar": "https://api.dicebear.com/7.x/avataaars/svg?seed=Irdho"},
    {"id": "user2", "name": "Arda Fibra", "email": "arda@lapor.com", "role": "PENGURUS", "rt_rw": "RT 05 / RW 03", "avatar": "https://api.dicebear.com/7.x/avataaars/svg?seed=Arda"},
    {"id": "user3", "name": "Budi Santoso", "email": "warga@lapor.com", "role": "WARGA", "rt_rw": "RT 05 / RW 03", "avatar": "https://api.dicebear.com/7.x/avataaars/svg?seed=Budi"}
]

mock_reports = [
    {"id": "rep1", "title": "Jalan Berlubang", "description": "Kalan berlubang didepan ruko ktt sehingga menyebabkan keluhan warga", "status": "SELESAI", "category": "INFRASTRUKTUR", "rt_rw": "RT 05 / RW 03", "user_id": "user3", "timestamp": "11 Mei"},
    {"id": "rep2", "title": "Kurangnya Pemeliharaan Fasilitas", "description": "Saat mau menggunakan fasilitas wc umum krannya tidak berfungsi", "status": "SELESAI", "category": "KEBERSIHAN", "rt_rw": "RT 05 / RW 03", "user_id": "user3", "timestamp": "5 Mei"}
]

system_info = {"running_text": "keputih hari ini terpantau mendung"}

@app.route('/')
def index():
    if 'user' in session:
        role = session['user'].get('role', '').upper()
        if role == 'ADMIN': return redirect(url_for('admin_pengguna'))
        if role == 'PENGURUS': return redirect(url_for('dashboard_pengurus'))
        if role == 'WARGA': return redirect(url_for('dashboard_warga'))
    return render_template('login.html')

@app.route('/api/login', methods=['POST'])
def api_login():
    token = request.json.get('idToken')
    try:
        # Verifikasi Firebase ID Token
        decoded_token = auth.verify_id_token(token)
        email = decoded_token.get('email')
        
        user_data = None
        if USING_FIRESTORE:
            # Cari user di Firestore berdasarkan email (document id)
            user_ref = db.collection('users').document(email).get()
            if user_ref.exists:
                user_data = user_ref.to_dict()
                user_data['id'] = user_ref.id
            else:
                # Registrasi otomatis sebagai WARGA jika belum ada di DB
                user_data = {
                    "name": decoded_token.get('name', 'User Baru'),
                    "email": email,
                    "role": "WARGA",
                    "avatar": decoded_token.get('picture', ''),
                    "rt_rw": "RT 00 / RW 00"
                }
                db.collection('users').document(email).set(user_data)
                user_data['id'] = email
        else:
            # Fallback mock berdasarkan email
            user_data = next((u for u in mock_users if u['email'] == email), None)
            if not user_data:
                user_data = {"id": decoded_token.get('uid'), "name": decoded_token.get('name'), "email": email, "role": "WARGA", "avatar": decoded_token.get('picture')}

        session['user'] = user_data
        return jsonify({"success": True, "role": user_data['role']})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        if USING_FIRESTORE:
            try:
                # Cari user di koleksi 'users' berdasarkan email
                users_ref = db.collection('users')
                query = users_ref.where('email', '==', email).limit(1).stream()
                
                user_doc = None
                for doc in query:
                    user_doc = doc
                    break
                
                if user_doc:
                    user_data = user_doc.to_dict()
                    if user_data.get('password') == password:
                        session['user'] = {
                            'id': user_doc.id,
                            'name': user_data.get('name'),
                            'email': user_data.get('email'),
                            'role': user_data.get('role', 'WARGA').upper(),
                            'avatar': user_data.get('avatar', ''),
                            'rt_rw': user_data.get('rt_rw', '')
                        }
                        
                        role = session['user']['role']
                        if role == 'ADMIN': return redirect(url_for('admin_pengguna'))
                        elif role == 'PENGURUS': return redirect(url_for('dashboard_pengurus'))
                        else: return redirect(url_for('dashboard_warga'))
                    else:
                        flash('Password yang Anda masukkan salah.', 'error')
                else:
                    # LOGIKA AKUN BARU: Otomatis Registrasi sebagai WARGA
                    new_user_data = {
                        "name": email.split('@')[0].capitalize(), # Ambil nama dari email
                        "email": email,
                        "password": password,
                        "role": "WARGA",
                        "avatar": f"https://api.dicebear.com/7.x/avataaars/svg?seed={email}",
                        "rt_rw": "RT 00 / RW 00"
                    }
                    db.collection('users').document(email).set(new_user_data)
                    
                    session['user'] = {
                        'id': email,
                        'name': new_user_data['name'],
                        'email': email,
                        'role': 'WARGA',
                        'avatar': new_user_data['avatar'],
                        'rt_rw': new_user_data['rt_rw']
                    }
                    flash('Akun baru berhasil dibuat sebagai Warga!', 'success')
                    return redirect(url_for('dashboard_warga'))
            except Exception as e:
                flash(f'Terjadi kesalahan sistem: {str(e)}', 'error')
        else:
            # Fallback jika Firestore tidak aktif (untuk testing)
            user = next((u for u in mock_users if u['email'] == email), None)
            if user:
                session['user'] = user
                return redirect(url_for('index'))
            flash('Mode Fallback: User tidak ditemukan.', 'error')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('index'))

# --- DASHBOARD ROUTES ---
@app.route('/admin')
def admin_pengguna():
    if 'user' not in session or session['user'].get('role', '').upper() != 'ADMIN': return redirect(url_for('index'))
    
    users_list = []
    if USING_FIRESTORE:
        try:
            docs = db.collection('users').stream()
            seen_emails = set()
            for doc in docs:
                u = doc.to_dict()
                email = u.get('email')
                if email in seen_emails:
                    continue
                seen_emails.add(email)
                
                u['id'] = doc.id
                # Pastikan role dalam format UPPERCASE untuk template
                if 'role' in u:
                    u['role'] = u['role'].upper()
                users_list.append(u)
        except Exception as e:
            print(f"Error Firestore Users: {e}")
            users_list = mock_users
    else:
        users_list = mock_users
        
    return render_template('admin_pengguna.html', users=users_list, active_tab='pengguna', info=system_info)

@app.route('/admin/aduan')
def admin_aduan():
    if 'user' not in session or session['user'].get('role', '').upper() != 'ADMIN': return redirect(url_for('index'))
    try:
        # Mengambil data dari koleksi 'reports' di Firestore
        docs = db.collection('reports').stream() if USING_FIRESTORE else []
        daftar_laporan = []
        
        if USING_FIRESTORE:
            for doc in docs:
                data = doc.to_dict()
                daftar_laporan.append({
                    'id': doc.id,
                    'title': data.get('judul') or data.get('title') or 'Tanpa Judul', 
                    'description': data.get('deskripsi') or data.get('description') or 'Tidak ada deskripsi', 
                    'category': (data.get('kategori') or data.get('category') or 'UMUM').upper(),
                    'status': (data.get('status', 'MENUNGGU')).upper(),
                    'rt_rw': data.get('rt_rw', 'RT -- / RW --'),
                    'image': data.get('image')
                })
        else:
            daftar_laporan = mock_reports
            
        return render_template('admin_aduan.html', 
                               reports=daftar_laporan, 
                               active_tab='aduan',
                               info=system_info)
    except Exception as e:
        print(f"Error Firestore: {e}")
        return render_template('admin_aduan.html', reports=[], info=system_info)

@app.route('/pengurus')
def dashboard_pengurus():
    if 'user' not in session or session['user'].get('role', '').upper() != 'PENGURUS': return redirect(url_for('index'))
    user = session['user']
    
    reports_list = []
    if USING_FIRESTORE:
        try:
            # Mengambil semua laporan agar pengurus bisa melihat antrean (sementara filter RT/RW dinonaktifkan agar data muncul)
            docs = db.collection('reports').stream()
            for doc in docs:
                data = doc.to_dict()
                reports_list.append({
                    'id': doc.id,
                    'title': data.get('judul') or data.get('title') or 'Tanpa Judul',
                    'description': data.get('deskripsi') or data.get('description') or 'Tidak ada deskripsi',
                    'category': (data.get('kategori') or data.get('category') or 'UMUM').upper(),
                    'status': (data.get('status', 'MENUNGGU')).upper(),
                    'image': data.get('image'),
                    'rt_rw': data.get('rt_rw', 'RT -- / RW --'),
                    'timestamp': data.get('timestamp', 'Baru Saja')
                })
        except Exception as e:
            print(f"Error Firestore Pengurus: {e}")
            reports_list = mock_reports
    else:
        reports_list = mock_reports

    stats = {
        'masuk': len([r for r in reports_list if r['status'] == 'MENUNGGU']),
        'proses': len([r for r in reports_list if r['status'] in ['VALIDASI', 'DIPROSES']]),
        'tuntas': len([r for r in reports_list if r['status'] == 'SELESAI'])
    }
    return render_template('dashboard_pengurus.html', reports=reports_list, stats=stats, info=system_info)

@app.route('/warga')
def dashboard_warga():
    if 'user' not in session or session['user'].get('role', '').upper() != 'WARGA': return redirect(url_for('index'))
    user = session['user']
    
    reports_list = []
    if USING_FIRESTORE:
        try:
            docs = db.collection('reports').where('user_id', '==', user['id']).stream()
            for doc in docs:
                data = doc.to_dict()
                reports_list.append({
                    'id': doc.id,
                    'title': data.get('title') or 'Tanpa Judul',
                    'description': data.get('description') or 'Tidak ada deskripsi',
                    'category': data.get('category', 'UMUM').upper(),
                    'status': data.get('status', 'MENUNGGU').upper(),
                    'image': data.get('image'),
                    'timestamp': data.get('timestamp', 'Baru Saja')
                })
        except Exception as e:
            print(f"Error Firestore Warga: {e}")
            reports_list = [r for r in mock_reports if r.get('user_id') == user['id']]
    else:
        reports_list = [r for r in mock_reports if r.get('user_id') == user['id']]

    stats = {
        'total': len(reports_list),
        'menunggu': len([r for r in reports_list if r['status'] == 'MENUNGGU']),
        'proses': len([r for r in reports_list if r['status'] in ['VALIDASI', 'DIPROSES']]),
        'tuntas': len([r for r in reports_list if r['status'] == 'SELESAI'])
    }
    return render_template('dashboard_warga.html', reports=reports_list, stats=stats, user=user, info=system_info)

# --- API ---
@app.route('/api/kirim-aduan', methods=['POST'])
@app.route('/api/tambah-laporan', methods=['POST'])
def tambah_laporan():
    if 'user' not in session: return jsonify({"success": False, "message": "Unauthorized"}), 401
    
    # Menggunakan form data karena ada upload file
    title = request.form.get('title')
    description = request.form.get('description')
    category = request.form.get('category', 'UMUM').upper()
    
    image_filename = None
    if 'photo' in request.files:
        file = request.files['photo']
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            filename = f"{int(time.time())}_{filename}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            image_filename = filename
    
    new_report = {
        'user_id': session['user']['id'],
        'title': title,
        'description': description,
        'category': category,
        'status': 'MENUNGGU',
        'rt_rw': session['user']['rt_rw'],
        'image': image_filename,
        'timestamp': datetime.datetime.now().strftime("%d %b %Y, %H:%M")
    }
    
    if USING_FIRESTORE:
        try:
            db.collection('reports').add(new_report)
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"success": False, "message": str(e)}), 500
    
    # Fallback to mock
    new_report['id'] = f"rep{len(mock_reports) + 1}"
    mock_reports.append(new_report)
    return jsonify({"success": True})

@app.route('/api/system/update_news', methods=['POST'])
def update_news():
    if 'user' not in session: return jsonify({"success": False}), 401
    data = request.json
    system_info['running_text'] = data.get('text')
    return jsonify({"success": True})

@app.route('/api/report/update_status', methods=['POST'])
def update_status():
    if 'user' not in session: return jsonify({"success": False}), 401
    data = request.json
    report_id = data.get('id')
    new_status = data.get('status')
    
    if USING_FIRESTORE:
        try:
            db.collection('reports').document(report_id).update({'status': new_status})
        except Exception as e:
            print(f"Update Firestore Error: {e}")
    
    for r in mock_reports:
        if r['id'] == report_id:
            r['status'] = new_status
            return jsonify({"success": True})
    return jsonify({"success": True}) # Return true even if only Firestore updated

@app.route('/api/report/delete', methods=['POST'])
def delete_report():
    if 'user' not in session: return jsonify({"success": False}), 401
    data = request.json
    report_id = data.get('id')
    
    if USING_FIRESTORE:
        try:
            db.collection('reports').document(report_id).delete()
        except Exception as e:
            print(f"Delete Firestore Error: {e}")
            
    global mock_reports
    mock_reports = [r for r in mock_reports if r['id'] != report_id]
    return jsonify({"success": True})

if __name__ == '__main__':
    app.run(debug=True, port=8080)
