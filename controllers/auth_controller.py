from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models.user_model import User
from utils.database import get_db_connection
import mysql.connector

auth_controller = Blueprint('auth_controller', __name__)

@auth_controller.route('/login', methods=['GET', 'POST'])
def auth_login():
    # Redirect if already logged in
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('eggmin_controller.eggmin'))
        elif current_user.role == 'pengusaha':
            return redirect(url_for('eggmonitor_controller.eggmonitor'))
        elif current_user.role == 'pembeli':
            return redirect(url_for('eggmart_controller.eggmart'))
        else:
            return redirect(url_for('comprof_controller.comprof_beranda'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False
        
        user = User.get_by_email(email)
        
        if user and check_password_hash(user.password, password):
            login_user(user, remember=remember)
            next_page = request.args.get('next')
            
            # FIX: Added explicit check for Admin
            if current_user.role == 'admin':
                return redirect(next_page or url_for('eggmin_controller.eggmin'))
            elif current_user.role == 'pengusaha':
                return redirect(next_page or url_for('eggmonitor_controller.eggmonitor'))
            elif current_user.role == 'pembeli':
                return redirect(next_page or url_for('eggmart_controller.eggmart'))
            else:
                return redirect(next_page or url_for('comprof_controller.comprof_beranda'))
        else:
            flash('Email atau password salah!', 'error')
    
    return render_template('auth/login.html')

@auth_controller.route('/register', methods=['GET', 'POST'])
def auth_register():
    if current_user.is_authenticated:
        return redirect(url_for('eggmonitor_controller.eggmonitor'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        
        # Check if user already exists
        existing_user = User.get_by_email(email)
        if existing_user:
            flash('Email sudah terdaftar!', 'error')
            return render_template('auth/register.html')
        
        # Create new user as Pembeli
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        conn = get_db_connection()
        if not conn:
            flash('Database connection error!', 'error')
            return render_template('auth/register.html')
            
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)",
                (name, email, hashed_password, 'pembeli')
            )
            conn.commit()
            cur.close()
            
            # Get the new user and log them in
            new_user = User.get_by_email(email)
            if new_user:
                login_user(new_user)
                flash('Registrasi berhasil! Selamat datang di EggVision.', 'success')
                # Redirect new users (pembeli) to EggMart, not EggMonitor
                return redirect(url_for('eggmart_controller.eggmart'))
            else:
                flash('Error creating user account.', 'error')
                
        except mysql.connector.Error as e:
            flash('Database error during registration.', 'error')
            print(f"Registration error: {e}")
        finally:
            if conn:
                conn.close()
    
    return render_template('auth/register.html')

@auth_controller.route('/logout')
@login_required
def auth_logout():
    logout_user()
    flash('Anda telah logout.', 'info')
    return redirect(url_for('comprof_controller.comprof_beranda'))

@auth_controller.route('/dashboard')
@login_required
def dashboard():
    """Redirect user to their respective dashboard based on role"""
    if current_user.role == 'admin':
        return redirect(url_for('eggmin_controller.eggmin'))
    elif current_user.role == 'pengusaha':
        return redirect(url_for('eggmonitor_controller.eggmonitor'))
    elif current_user.role == 'pembeli':
        # FIX: Fixed typo 'eggmort' to 'eggmart'
        return redirect(url_for('eggmart_controller.eggmart'))
    else:
        return redirect(url_for('comprof_controller.comprof_beranda'))