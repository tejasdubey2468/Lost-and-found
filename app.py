import os
import uuid
import sqlite3
from functools import wraps
from flask import (Flask, render_template, request, redirect, url_for,
                   session, flash, jsonify, send_from_directory, abort)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from database import get_db, init_db

# ─── App Setup ────────────────────────────────────────────────────────────────
BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
if os.environ.get('VERCEL'):
    UPLOAD_FOLDER = '/tmp/uploads'
else:
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
ALLOWED_EXT   = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'lf-dev-secret-2026-change-in-prod')
app.config['UPLOAD_FOLDER']    = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB

CATEGORIES = ['Electronics', 'Pets', 'Keys', 'Wallets & Bags',
               'Documents', 'Clothing', 'Jewellery', 'Books', 'Other']


# ─── Helpers ──────────────────────────────────────────────────────────────────
def allowed_file(filename):
    return ('.' in filename and
            filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT)


def save_image(file_obj):
    """Save uploaded image with UUID name. Returns relative path or None."""
    if not file_obj or not allowed_file(file_obj.filename):
        return None
    ext      = file_obj.filename.rsplit('.', 1)[1].lower()
    filename = f"item_{uuid.uuid4().hex[:12]}.{ext}"
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    file_obj.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    return filename


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to continue.', 'info')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


# ─── Static / Uploaded Files ───────────────────────────────────────────────────
@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


# ─── Auth Routes ───────────────────────────────────────────────────────────────
@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm  = request.form.get('confirm_password', '')

        errors = []
        if len(username) < 3:
            errors.append('Username must be at least 3 characters.')
        if '@' not in email:
            errors.append('Enter a valid email address.')
        if len(password) < 6:
            errors.append('Password must be at least 6 characters.')
        if password != confirm:
            errors.append('Passwords do not match.')

        if errors:
            for e in errors:
                flash(e, 'error')
            return render_template('register.html',
                                   username=username, email=email)

        db = get_db()
        try:
            db.execute(
                "INSERT INTO users (username, email, password_hash) VALUES (?,?,?)",
                (username, email, generate_password_hash(password, method='pbkdf2:sha256'))
            )
            db.commit()
            flash('Account created! Please log in.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username or email already taken.', 'error')
        except Exception as e:
            print(f"REGISTRATION ERROR: {e}")
            flash('System error during registration. Please try again later or contact support.', 'error')
        finally:
            db.close()

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        db   = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        db.close()

        if user and check_password_hash(user['password_hash'], password):
            session['user_id']  = user['id']
            session['username'] = user['username']
            flash(f'Welcome back, {user["username"]}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password.', 'error')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


# ─── Dashboard ────────────────────────────────────────────────────────────────
@app.route('/')
@login_required
def dashboard():
    db = get_db()
    lost_items  = db.execute(
        """SELECT i.*, u.username FROM items i
           JOIN users u ON i.user_id = u.id
           WHERE i.status='Lost' AND i.claim_status='Available' 
           ORDER BY i.created_at DESC LIMIT 8"""
    ).fetchall()
    found_items = db.execute(
        """SELECT i.*, u.username FROM items i
           JOIN users u ON i.user_id = u.id
           WHERE i.status='Found' AND i.claim_status='Available' 
           ORDER BY i.created_at DESC LIMIT 8"""
    ).fetchall()
    stats = db.execute(
        """SELECT
             COUNT(*) as total,
             SUM(CASE WHEN status='Lost'  THEN 1 ELSE 0 END) as lost_count,
             SUM(CASE WHEN status='Found' THEN 1 ELSE 0 END) as found_count,
             SUM(CASE WHEN claim_status='Claimed' THEN 1 ELSE 0 END) as reunited
           FROM items"""
    ).fetchone()
    db.close()
    return render_template('dashboard.html',
                           lost_items=lost_items,
                           found_items=found_items,
                           stats=stats,
                           categories=CATEGORIES)


# ─── Report Item ──────────────────────────────────────────────────────────────
@app.route('/report', methods=['GET', 'POST'])
@login_required
def report():
    if request.method == 'POST':
        status      = request.form.get('status', '')
        title       = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        category    = request.form.get('category', '')
        location    = request.form.get('location', '').strip()
        image_file  = request.files.get('image')

        errors = []
        if status not in ('Lost', 'Found'):   errors.append('Select a valid status.')
        if len(title) < 3:                    errors.append('Title must be at least 3 characters.')
        if len(description) < 10:             errors.append('Description must be at least 10 characters.')
        if category not in CATEGORIES:        errors.append('Select a valid category.')
        if len(location) < 2:                 errors.append('Enter a location.')

        if errors:
            for e in errors:
                flash(e, 'error')
            return render_template('report.html', categories=CATEGORIES,
                                   form=request.form)

        image_path = save_image(image_file)

        db = get_db()
        cursor = db.execute(
            """INSERT INTO items
               (user_id, status, title, description, category, location, image_path)
               VALUES (?,?,?,?,?,?,?)""",
            (session['user_id'], status, title, description,
             category, location, image_path)
        )
        item_id = cursor.lastrowid
        db.commit()
        db.close()
        return redirect(url_for('confirmation', item_id=item_id))

    return render_template('report.html', categories=CATEGORIES, form={})


@app.route('/confirmation/<int:item_id>')
@login_required
def confirmation(item_id):
    db   = get_db()
    item = db.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
    db.close()
    if not item or item['user_id'] != session['user_id']:
        abort(403)
    return render_template('confirmation.html', item=item)


# ─── Item Detail ──────────────────────────────────────────────────────────────
@app.route('/item/<int:item_id>')
@login_required
def item_detail(item_id):
    db   = get_db()
    item = db.execute(
        """SELECT i.*, u.username FROM items i
           JOIN users u ON i.user_id = u.id
           WHERE i.id=?""", (item_id,)
    ).fetchone()
    db.close()
    if not item:
        abort(404)
    return render_template('item_detail.html', item=item)


# ─── Claim Item ───────────────────────────────────────────────────────────────
@app.route('/claim/<int:item_id>', methods=['POST'])
@login_required
def claim_item(item_id):
    data = request.get_json() or {}
    claim_details = data.get('claim_details', '').strip()

    if not claim_details:
        return jsonify({'ok': False, 'error': 'Please provide claim details.'}), 400

    db   = get_db()
    item = db.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()

    if not item:
        db.close()
        return jsonify({'ok': False, 'error': 'Item not found.'}), 404

    # Temporarily removed 'cannot claim your own item' check for easy testing

    if item['claim_status'] != 'Available':
        db.close()
        return jsonify({'ok': False,
                        'error': f'Item is already {item["claim_status"]}.'}), 400

    db.execute(
        "UPDATE items SET claim_status='Pending', claimant_id=?, claim_details=? WHERE id=?",
        (session['user_id'], claim_details, item_id)
    )
    db.commit()
    db.close()
    return jsonify({'ok': True,
                    'message': 'Claim submitted! The owner has been notified.',
                    'new_status': 'Pending'})


# ─── Approve / Reject Claim ───────────────────────────────────────────────────
@app.route('/resolve/<int:item_id>/<action>', methods=['POST'])
@login_required
def resolve_claim(item_id, action):
    if action not in ('approve', 'reject'):
        abort(400)
    db   = get_db()
    item = db.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
    if not item or item['user_id'] != session['user_id']:
        db.close()
        return jsonify({'ok': False, 'error': 'Forbidden'}), 403

    new_status = 'Claimed' if action == 'approve' else 'Available'
    claimant   = None if action == 'reject' else item['claimant_id']
    db.execute(
        "UPDATE items SET claim_status=?, claimant_id=? WHERE id=?",
        (new_status, claimant, item_id)
    )
    db.commit()
    db.close()
    return jsonify({'ok': True, 'new_status': new_status})


# ─── My Items ─────────────────────────────────────────────────────────────────
@app.route('/my-items')
@login_required
def my_items():
    db    = get_db()
    items = db.execute(
        "SELECT * FROM items WHERE user_id=? ORDER BY created_at DESC",
        (session['user_id'],)
    ).fetchall()
    db.close()
    return render_template('my_items.html', items=items)


# ─── Delete Item ──────────────────────────────────────────────────────────────
@app.route('/delete/<int:item_id>', methods=['POST'])
@login_required
def delete_item(item_id):
    db   = get_db()
    item = db.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
    if not item or item['user_id'] != session['user_id']:
        db.close()
        return jsonify({'ok': False, 'error': 'Forbidden'}), 403

    if item['image_path']:
        try:
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], item['image_path']))
        except FileNotFoundError:
            pass

    db.execute("DELETE FROM items WHERE id=?", (item_id,))
    db.commit()
    db.close()
    return jsonify({'ok': True})


# ─── Search / Filter API ──────────────────────────────────────────────────────
@app.route('/api/search')
@login_required
def api_search():
    q        = request.args.get('q', '').strip()
    category = request.args.get('category', '')
    status   = request.args.get('status', '')

    sql    = """SELECT i.*, u.username FROM items i
                JOIN users u ON i.user_id = u.id
                WHERE (i.title LIKE ? OR i.description LIKE ? OR i.location LIKE ?)
                AND i.claim_status='Available'"""
    params = [f'%{q}%', f'%{q}%', f'%{q}%']

    if category:
        sql += " AND i.category=?"
        params.append(category)
    if status in ('Lost', 'Found'):
        sql += " AND i.status=?"
        params.append(status)

    sql += " ORDER BY i.created_at DESC LIMIT 50"

    db    = get_db()
    rows  = db.execute(sql, params).fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])


# ─── Entry Point ──────────────────────────────────────────────────────────────
if __name__ == '__main__':
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    init_db()
    app.run(debug=True, port=5001)
