import os
import json
import random
import requests
import uuid
from flask import Flask, render_template, redirect, url_for, request, flash, send_from_directory, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import csv
from io import StringIO
from flask import make_response
import re
from flask import session
from functools import wraps
from werkzeug.security import check_password_hash

# Other imports...
from models import db, User, Profile, Resource, Comment

app = Flask(__name__)

# --- CONFIGURATIONS ---
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
# 1. Define the folder path
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')

# 2. Tell Flask about the folder and the database
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(BASE_DIR, 'checkpoint2.db')
app.config['SECRET_KEY'] = 'dev-key-123'

# 3. Now initialize the DB
db.init_app(app)


login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- CONTEXT PROCESSOR (Quotes) ---
# --- CONTEXT PROCESSOR (Simplified) ---
@app.context_processor
def inject_quote():
    # This is our backup quote if the internet is down
    display_quote = {"content": "Knowledge is power.", "author": "Francis Bacon"}
    
    try:
        # Try to get a fresh quote from the internet
        response = requests.get("https://zenquotes.io/api/random", timeout=2)
        if response.status_code == 200:
            api_data = response.json()[0]
            display_quote = {"content": api_data['q'], "author": api_data['a']}
    except:
        # If the internet fails, it just stays as "Knowledge is power"
        pass
    
    return dict(quote=display_quote)

# --- ROUTES ---
@app.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    q = request.args.get('q', '').strip()
    cat_filter = request.args.get('category', '').strip()
    # ADD THIS LINE:
    sort_by = request.args.get('sort', 'newest') 

    query = Resource.query
    if q:
        query = query.filter((Resource.title.ilike(f'%{q}%')) | (Resource.description.ilike(f'%{q}%')))
    if cat_filter:
        query = query.filter(Resource.category == cat_filter)
    
    # UPDATE THE ORDERING LOGIC:
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

    return render_template('index.html', 
                           results=results, 
                           pagination=pagination,
                           stats=stats_summary,
                           query=q, 
                           cat_filter=cat_filter,
                           sort_by=sort_by) # ADD THIS TO RETURN

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        # Get all fields from the form
        user_name = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        # 1. Check Password Strength
        is_strong, message = is_password_strong(password)
        if not is_strong:
            flash(message, "danger")
            return redirect(url_for('signup'))

        # 2. Check if EMAIL already exists
        if User.query.filter_by(email=email).first():
            flash('This email is already registered!', 'warning')
            return redirect(url_for('signup'))

        # 3. Create User and Profile together
        hashed_pw = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(username=user_name, email=email, password=hashed_pw)
        
        try:
            db.session.add(new_user)
            db.session.flush() # This gets the new_user.id without finishing the save yet
            
            new_profile = Profile(user_id=new_user.id)
            db.session.add(new_profile)
            
            db.session.commit() # Save both at once!
            flash('Account created! Please login.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            flash("System error during signup. Try again.", "danger")
            
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

        # LOGIN BY EMAIL (Standard practice)
        login_input = request.form.get('username') # This is what they typed in the box
        password = request.form.get('password')
        
        # We search the EMAIL column!
        user = User.query.filter_by(email=login_input).first()

        if user and check_password_hash(user.password, password):
            session['failures'] = 0
            login_user(user)
            return redirect(url_for('profile'))
        else:
            session['failures'] += 1
            flash(f"Invalid email or password. Attempt {session['failures']}/3", "warning")

    # Generate CAPTCHA if needed...
    show_captcha = session.get('failures', 0) >= 3
    if show_captcha:
        num1, num2 = random.randint(1, 10), random.randint(1, 10)
        session['captcha_result'] = num1 + num2
        session['captcha_text'] = f"What is {num1} + {num2}?"

    return render_template('login.html', show_captcha=show_captcha)

    # If they are over the limit, generate a math problem for the HTML
    show_captcha = False
    if session.get('failures', 0) >= 3:
        show_captcha = True
        num1 = random.randint(1, 10)
        num2 = random.randint(1, 10)
        session['captcha_result'] = num1 + num2
        session['captcha_text'] = f"What is {num1} + {num2}?"

    return render_template('login.html', show_captcha=show_captcha)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.pop('login_attempts', None) # Clear the security counter
    return redirect(url_for('login'))

@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html', user=current_user)

@app.route('/edit_profile', methods=['POST'])
@login_required
def edit_profile():
    # 1. Get the data from the form
    job = request.form.get('job_title')
    hobby = request.form.get('hobby')
    contacts = request.form.get('contacts')

    # 2. Check if the user already has a profile record
    if not current_user.profile:
        # If no profile exists, create a new Profile object
        from models import Profile # Ensure this matches your model file name
        new_profile = Profile(
            job_title=job, 
            hobby=hobby, 
            contacts=contacts, 
            user_id=current_user.id
        )
        db.session.add(new_profile)
    else:
        # If profile exists, just update the existing fields
        current_user.profile.job_title = job
        current_user.profile.hobby = hobby
        current_user.profile.contacts = contacts

    # 3. Save to database
    try:
        db.session.commit()
        flash("Profile updated successfully!", "success")
    except Exception as e:
        db.session.rollback()
        flash("Error saving profile.", "danger")
        print(f"Database Error: {e}")

    return redirect(url_for('profile'))

@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    file = request.files.get('file')
    title = request.form.get('title')
    category = request.form.get('category', 'General') # NEW: Category capture

    if file and title:
        cover_url = None
        try:
            search_url = f"https://www.googleapis.com/books/v1/volumes?q={title}"
            api_resp = requests.get(search_url, timeout=5)
            if api_resp.status_code == 200:
                data = api_resp.json()
                if 'items' in data:
                    volume_info = data['items'][0].get('volumeInfo', {})
                    cover_url = volume_info.get('imageLinks', {}).get('thumbnail')
        except Exception as e:
            print(f"Metadata API Error: {e}")

        original_filename = secure_filename(file.filename)
        filename = f"{uuid.uuid4().hex}_{original_filename}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        new_res = Resource(
            title=title, 
            description=request.form.get('description'), 
            filename=filename, 
            cover_image=cover_url,
            category=category, # NEW: Save category
            user_id=current_user.id
        )
        db.session.add(new_res)
        db.session.commit()
        flash('Successfully uploaded!', 'success')
    return redirect(url_for('profile'))

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

@app.route('/api/delete/<int:resource_id>', methods=['POST'], strict_slashes=False)
@login_required
def delete_resource(resource_id):
    resource = Resource.query.get_or_404(resource_id)
    if resource.user_id != current_user.id:
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    file_path = os.path.join(app.config['UPLOAD_FOLDER'], resource.filename)
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception as e:
            print(f"Error deleting file: {e}")

    db.session.delete(resource)
    db.session.commit()
    return jsonify({"success": True})

# ... all your other routes ...

@app.route('/export_csv')
@login_required
def export_csv():
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['Title', 'Category', 'Description'])
    for res in current_user.resources:
        cw.writerow([res.title, res.category, res.description])
    
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=export.csv"
    output.headers["Content-type"] = "text/csv"
    return output

@app.route('/comment/<int:resource_id>', methods=['POST'])
@login_required
def add_comment(resource_id):
    # 1. Check if the form is actually sending data
    text = request.form.get('comment_text')
    print(f"--- DEBUG: Attempting to comment on Resource #{resource_id} ---")
    print(f"--- DEBUG: Received text: {text}")

    if not text:
        print("--- DEBUG: No text found in form!")
        flash("Comment cannot be empty", "danger")
        return redirect(url_for('index'))

    try:
        new_comment = Comment(
            text=text, 
            user_id=current_user.id, 
            resource_id=resource_id
        )
        db.session.add(new_comment)
        db.session.commit()
        print("--- DEBUG: Success! Comment saved to database.")
        flash('Comment added!', 'success')
    except Exception as e:
        db.session.rollback()
        print(f"--- DEBUG: Database Error: {e}")
        flash("Error saving comment", "danger")

    return redirect(url_for('index'))

@app.route('/edit/<int:resource_id>', methods=['POST'])
@login_required
def edit_resource(resource_id):
    resource = Resource.query.get_or_404(resource_id)
    # Check if the user owns this item
    if resource.user_id != current_user.id:
        flash("You cannot edit this!", "danger")
        return redirect(url_for('index'))
    
    resource.title = request.form.get('title')
    resource.description = request.form.get('description')
    db.session.commit()
    flash("Updated successfully!", "success")
    return redirect(url_for('index'))

@app.route('/favorite/<int:res_id>')
@login_required
def toggle_favorite(res_id):
    res = Resource.query.get_or_404(res_id)
    if res in current_user.liked_resources:
        current_user.liked_resources.remove(res)
        flash("Removed from favorites", "info")
    else:
        current_user.liked_resources.append(res)
        flash("Added to favorites!", "success")
    db.session.commit()
    return redirect(url_for('index'))


def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash("Access denied: Admins only.", "danger")
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# Example of an Advanced Security route
@app.route('/admin/dashboard')
@admin_only
def admin_dashboard():
    all_users = User.query.all()
    return render_template('admin.html', users=all_users)


def is_password_strong(password):
    # Requirements: 8+ chars, 1 number, 1 uppercase, 1 special char
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r"\d", password):
        return False, "Password must contain at least one number."
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter."
    if not re.search(r"[ !@#$%^&*()_+={}\[\]:;<>,.?~\\-]", password):
        return False, "Password must contain at least one special character."
    return True, ""



@app.route('/security/reset-session')
def reset_session():
    # This completely nukes the session dictionary
    session.clear()
    logout_user() # Also logs the user out
    flash("Session has been completely cleared and reset.", "info")
    return redirect(url_for('index'))


@app.route('/admin')
@login_required
@admin_only
def admin_panel():
    # Fetch all users and all resources to show in the Command Center
    users = User.query.all()
    resources = Resource.query.all()
    return render_template('admin.html', users=users, resources=resources)

@app.route('/admin/delete_resource/<int:resource_id>', methods=['POST'])
@login_required
@admin_only
def admin_delete_resource(resource_id):
    resource = Resource.query.get_or_404(resource_id)
    
    # Delete the physical file first
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], resource.filename)
    if os.path.exists(file_path):
        os.remove(file_path)
        
    db.session.delete(resource)
    db.session.commit()
    flash(f"Moderator Action: '{resource.title}' has been removed.", "warning")
    return redirect(url_for('admin_panel'))


    # --- FEATURE 1: PASSWORD RESET (SIMULATION) ---
@app.route('/change-password', methods=['POST'])
@login_required
def change_password():
    old_pw = request.form.get('old_password')
    new_pw = request.form.get('new_password')
    
    if not check_password_hash(current_user.password, old_pw):
        flash("Current password incorrect!", "danger")
        return redirect(url_for('profile'))
    
    # Reuse your password strength check here if you have one!
    current_user.password = generate_password_hash(new_pw, method='pbkdf2:sha256')
    db.session.commit()
    flash("Password updated successfully!", "success")
    return redirect(url_for('profile'))

# --- FEATURE 2: ACCOUNT DELETION ---
@app.route('/delete-account', methods=['POST'])
@login_required
def delete_account():
    user = User.query.get(current_user.id)
    # Optional: Delete their files first
    for res in user.resources:
        db.session.delete(res)
    
    db.session.delete(user)
    db.session.commit()
    logout_user() # Log them out after deleting
    flash("Your account and data have been permanently deleted.", "info")
    return redirect(url_for('index'))

# --- FEATURE 3: ADMIN PROMOTION ---
@app.route('/admin/promote/<int:user_id>', methods=['POST'])
@login_required
@admin_only
def promote_user(user_id):
    user = User.query.get_or_404(user_id)
    user.role = 'admin'
    db.session.commit()
    flash(f"{user.username} has been promoted to Admin!", "success")
    return redirect(url_for('admin_panel'))



# --- START THE APP (THIS MUST BE THE LAST THING IN THE FILE) ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not os.path.exists(app.config['UPLOAD_FOLDER']):
            os.makedirs(app.config['UPLOAD_FOLDER'])
            
    app.run(debug=True)