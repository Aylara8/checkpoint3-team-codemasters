import os
import json
import random
import requests
import uuid
import csv
import re
from io import StringIO
from datetime import datetime
from functools import wraps
import ssl
import httpx
from supabase import create_client, Client
from supabase.lib.client_options import ClientOptions # Add this import
from flask import Flask, render_template, redirect, url_for, request, flash, send_from_directory, jsonify, session, make_response
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename



# Import models from your models.py
from models import db, User, Profile, Resource, Comment, CommunityMessage

app = Flask(__name__)

# --- CONFIGURATIONS ---
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(BASE_DIR, 'checkpoint2.db')
app.config['SECRET_KEY'] = 'dev-key-123'

# Replace with your actual Supabase URL and Anon Key found in Project Settings > API
SUPABASE_URL = "https://cpuvtafaedjlgcruiuff.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNwdXZ0YWZhZWRqbGdjcnVpdWZmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzM1OTI4ODQsImV4cCI6MjA4OTE2ODg4NH0.q7m_80c2EPyC4nOJH0Q5WdVDayf25KP_ZAdh2TECt4s"
ssl._create_default_https_context = ssl._create_unverified_context
custom_client = httpx.Client(verify=False, timeout=120.0)
options = ClientOptions(httpx_client=custom_client)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY, options=options)
# Initialize DB
db.init_app(app)

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    # This uses the modern SQLAlchemy 2.0 session method
    return db.session.get(User, int(user_id))

# --- HELPERS & DECORATORS ---
def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash("Access denied: Admins only.", "danger")
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def is_password_strong(password):
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r"\d", password):
        return False, "Password must contain at least one number."
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter."
    if not re.search(r"[ !@#$%^&*()_+={}\[\]:;<>,.?~\\-]", password):
        return False, "Password must contain at least one special character."
    return True, ""

# --- CONTEXT PROCESSOR ---
@app.context_processor
def inject_quote():
    display_quote = {"content": "Knowledge is power.", "author": "Francis Bacon"}
    try:
        response = requests.get("https://zenquotes.io/api/random", timeout=2)
        if response.status_code == 200:
            api_data = response.json()[0]
            display_quote = {"content": api_data['q'], "author": api_data['a']}
    except:
        pass
    return dict(quote=display_quote)

# --- ROUTES ---

@app.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    per_page = 10
    q = request.args.get('q', '').strip()
    cat_filter = request.args.get('category', '').strip()
    sort_by = request.args.get('sort', 'newest') 

    query = Resource.query
    if q:
        query = query.filter((Resource.title.ilike(f'%{q}%')) | (Resource.description.ilike(f'%{q}%')))
    if cat_filter:
        query = query.filter(Resource.category == cat_filter)
    
    if sort_by == 'name':
        query = query.order_by(Resource.title.asc())
    else:
        query = query.order_by(Resource.id.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    results = pagination.items
    
    stats_summary = {
        'total': Resource.query.count(),
        'categories': db.session.query(Resource.category, db.func.count(Resource.id)).group_by(Resource.category).all(),
        'recent': Resource.query.order_by(Resource.id.desc()).limit(5).all()
    }

    return render_template('index.html', results=results, pagination=pagination, stats=stats_summary, query=q, cat_filter=cat_filter, sort_by=sort_by)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        user_name = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        is_strong, message = is_password_strong(password)
        if not is_strong:
            flash(message, "danger")
            return redirect(url_for('signup'))

        if User.query.filter_by(email=email).first():
            flash('This email is already registered!', 'warning')
            return redirect(url_for('signup'))

        hashed_pw = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(username=user_name, email=email, password=hashed_pw)
        
        try:
            db.session.add(new_user)
            db.session.flush() 
            new_profile = Profile(user_id=new_user.id)
            db.session.add(new_profile)
            db.session.commit()
            flash('Account created! Please login.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            flash("System error during signup.", "danger")
            
    return render_template('signup.html')



@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'failures' not in session:
        session['failures'] = 0

    if request.method == 'POST':
        if session['failures'] >= 3:
            user_answer = request.form.get('captcha_answer')
            if not user_answer or int(user_answer) != session.get('captcha_result'):
                flash("Incorrect CAPTCHA!", "danger")
                return render_template('login.html', show_captcha=True)

        login_input = request.form.get('username') 
        password = request.form.get('password')
        user = User.query.filter_by(email=login_input).first()

        if user and check_password_hash(user.password, password):
            session['failures'] = 0
            login_user(user)
            return redirect(url_for('profile'))
        else:
            session['failures'] += 1
            flash(f"Invalid email or password. Attempt {session['failures']}/3", "warning")

    show_captcha = session.get('failures', 0) >= 3
    if show_captcha:
        num1, num2 = random.randint(1, 10), random.randint(1, 10)
        session['captcha_result'] = num1 + num2
        session['captcha_text'] = f"What is {num1} + {num2}?"

    return render_template('login.html', show_captcha=show_captcha)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.pop('failures', None)
    return redirect(url_for('login'))

@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html', user=current_user)

@app.route('/community', methods=['GET', 'POST'])
@login_required
def community():
    if request.method == 'POST':
        content = request.form.get('message')
        if content:
            new_msg = CommunityMessage(content=content, user_id=current_user.id)
            db.session.add(new_msg)
            db.session.commit()
            return redirect(url_for('community'))
    
    messages = CommunityMessage.query.order_by(CommunityMessage.timestamp.desc()).limit(50).all()
    return render_template('community.html', messages=messages)

from urllib.parse import unquote

@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    file = request.files.get('file')
    title = request.form.get('title')
    
    if not file or not title:
        flash("Missing file or title", "warning")
        return redirect(url_for('profile'))

    try:
        filename = secure_filename(file.filename)
        ext = os.path.splitext(filename)[1].lower()
        
        # 1. Determine if it's "Heavy" before reading content
        # Check if it's a video or large file
        is_video = ext in ['.mp4', '.mov', '.avi', '.wmv']
        
        if is_video:
            # SAVE LOCALLY IMMEDIATELY (Streaming save)
            # Create the directory if it doesn't exist
            local_dir = os.path.join(app.root_path, 'static', 'uploads')
            os.makedirs(local_dir, exist_ok=True)
            
            unique_name = f"{int(datetime.now().timestamp())}_{filename}"
            save_path = os.path.join(local_dir, unique_name)
            
            file.save(save_path) # Flask's save() is more efficient for heavy files
            file_url = f"/static/uploads/{unique_name}"
            flash('Video saved locally to ensure stability.', 'info')
            
        else:
            # Small file: Try Supabase
            file_content = file.read() # Only read small files into memory
            file_path = f"{current_user.id}/{int(datetime.now().timestamp())}_{filename}"
            
            url = f"{SUPABASE_URL}/storage/v1/object/resources/{file_path}"
            headers = {
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "ApiKey": SUPABASE_KEY,
                "Content-Type": file.content_type,
                "x-upsert": "true"
            }
            
            # Fast timeout for Supabase
            try:
                response = requests.post(url, headers=headers, data=file_content, verify=False, timeout=10)
                if response.status_code == 200:
                    file_url = f"{SUPABASE_URL}/storage/v1/object/public/resources/{file_path}"
                    flash('Small file synced to Supabase!', 'success')
                else:
                    raise Exception("Supabase rejected")
            except:
                # FALLBACK: Save locally if Supabase fails/times out
                local_dir = os.path.join(app.root_path, 'static', 'uploads')
                os.makedirs(local_dir, exist_ok=True)
                unique_name = f"{int(datetime.now().timestamp())}_{filename}"
                save_path = os.path.join(local_dir, unique_name)
                with open(save_path, 'wb') as f:
                    f.write(file_content)
                file_url = f"/static/uploads/{unique_name}"
                flash('Saved locally (Supabase unavailable).', 'warning')

        # 3. Final Database Save
        new_res = Resource(
            title=title,
            description=request.form.get('description'),
            filename=file_url,
            category=request.form.get('category', 'General'),
            user_id=current_user.id
        )
        db.session.add(new_res)
        db.session.commit()

    except Exception as e:
        db.session.rollback()
        print(f"DEBUG ERROR: {str(e)}") # Watch your terminal!
        flash(f"Upload Error: {str(e)}", "danger")

    return redirect(url_for('profile'))

    return redirect(url_for('profile'))

@app.route('/download/<path:filename>')
def download_file(filename):
    # Since filename is already a full Supabase URL, we just redirect to it
    return redirect(filename)


@app.route('/api/delete/<int:resource_id>', methods=['POST'])
@login_required
def delete_resource(resource_id):
    resource = db.get_or_404(Resource, resource_id)
    if resource.user_id != current_user.id and current_user.role != 'admin':
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    try:
        # Delete from Supabase first
        if "supabase.co" in resource.filename:
            # Extract the path from the URL
            file_path = resource.filename.split('/resources/')[-1]
            supabase.storage.from_('resources').remove([file_path])

        db.session.delete(resource)
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/favorite/<int:res_id>')
@login_required
def toggle_favorite(res_id):
    res = Resource.query.get_or_404(res_id)
    if res in current_user.liked_resources:
        current_user.liked_resources.remove(res)
    else:
        current_user.liked_resources.append(res)
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/comment/<int:resource_id>', methods=['POST'])
@login_required
def add_comment(resource_id):
    text = request.form.get('comment_text')
    if text:
        new_comment = Comment(text=text, user_id=current_user.id, resource_id=resource_id)
        db.session.add(new_comment)
        db.session.commit()
        flash('Comment added!', 'success')
    return redirect(url_for('index'))


@app.route('/export/csv')
@login_required
@admin_only
def export_csv():
    # Fetch all resources
    resources = Resource.query.all()
    
    # Create a string buffer to hold the CSV data
    si = StringIO()
    cw = csv.writer(si)
    
    # Write the header row
    cw.writerow(['ID', 'Title', 'Category', 'Uploader ID', 'URL'])
    
    # Write data rows
    for res in resources:
        cw.writerow([res.id, res.title, res.category, res.user_id, res.filename])
    
    # Create the response
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=resources_export.csv"
    output.headers["Content-type"] = "text/csv"
    
    return output

@app.route('/change_password', methods=['POST'])
@login_required
def change_password():
    old_password = request.form.get('old_password')
    new_password = request.form.get('new_password')
    
    if not check_password_hash(current_user.password, old_password):
        flash("Old password incorrect!", "danger")
        return redirect(url_for('profile'))
    
    is_strong, msg = is_password_strong(new_password)
    if not is_strong:
        flash(msg, "danger")
        return redirect(url_for('profile'))
        
    current_user.password = generate_password_hash(new_password, method='pbkdf2:sha256')
    db.session.commit()
    flash("Password updated successfully!", "success")
    return redirect(url_for('profile'))

@app.route('/delete_account', methods=['POST'])
@login_required
def delete_account():
    user = User.query.get(current_user.id)
    logout_user()
    db.session.delete(user)
    db.session.commit()
    flash("Your account has been deleted.", "info")
    return redirect(url_for('index'))

@app.route('/edit_profile', methods=['POST'])
@login_required
def edit_profile():
    profile = current_user.profile
    if not profile:
        profile = Profile(user_id=current_user.id)
        db.session.add(profile)
    
    profile.job_title = request.form.get('job_title')
    profile.hobby = request.form.get('hobby')
    profile.contacts = request.form.get('contacts')
    
    db.session.commit()
    flash("Profile updated!", "success")
    return redirect(url_for('profile'))

def promote_first_user():
    with app.app_context():
        user = User.query.first()
        if user:
            user.role = 'admin'
            db.session.commit()
            print(f"Promoted {user.username} to Admin!")

# Call it here
promote_first_user()


# --- ADMIN PANEL ---
@app.route('/admin')
@login_required
@admin_only
def admin_panel():
    users = User.query.all()
    resources = Resource.query.all()
    return render_template('admin.html', users=users, resources=resources)


import os

@app.route('/admin/delete/<int:resource_id>', methods=['POST'])
@login_required
def admin_delete_resource(resource_id):
    if current_user.role != 'admin':
        flash("Unauthorized", "danger")
        return redirect(url_for('index'))
        
    res = Resource.query.get_or_404(resource_id)
    
    try:
        # Check if the file is stored locally
        # Local files usually start with 'static/uploads/' or '/static/uploads/'
        if 'static/uploads/' in res.filename:
            # Convert URL path to a real system path
            # We strip the leading slash if it exists
            relative_path = res.filename.lstrip('/')
            if os.path.exists(relative_path):
                os.remove(relative_path)
                print(f"Deleted local file: {relative_path}")

        # Delete from Database
        db.session.delete(res)
        db.session.commit()
        flash('Resource and associated file removed!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error during deletion: {str(e)}', 'danger')
        
    return redirect(url_for('admin_dashboard'))



# --- START THE APP ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)