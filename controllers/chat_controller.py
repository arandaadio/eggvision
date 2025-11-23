from flask import Blueprint, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from utils.database import get_db_connection
import mysql.connector

chat_controller = Blueprint('chat_controller', __name__)

# ==========================================
# 1. PENGIRIMAN PESAN DARI FRONTEND (PUBLIC)
# ==========================================
@chat_controller.route('/api/chat/send', methods=['POST'])
def comprof_send_chat():
    """Handle chat messages from Comprof pages (Session Based)"""
    try:
        data = request.get_json()
        message = data.get('message', '').strip()
        
        if not message:
            return jsonify({'success': False, 'error': 'Message is required'}), 400

        # Tentukan identitas pengirim
        user_id = None
        guest_name = None
        guest_email = None
        message_type = 'guest_to_admin'

        if data.get('user_id'):
            # User Login
            user_id = data['user_id']
            message_type = 'user_to_admin'
        else:
            # Tamu
            guest_name = data.get('guest_name', '').strip()
            guest_email = data.get('guest_email', '').strip()
            if not guest_name or not guest_email:
                return jsonify({'success': False, 'error': 'Name and email required'}), 400

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500

        try:
            cur = conn.cursor(dictionary=True)
            
            # A. CARI SESI YANG SUDAH ADA
            session_id = None
            if user_id:
                cur.execute("SELECT id FROM chat_sessions WHERE user_id = %s LIMIT 1", (user_id,))
            else:
                cur.execute("SELECT id FROM chat_sessions WHERE guest_email = %s LIMIT 1", (guest_email,))
            
            existing_session = cur.fetchone()

            # B. UPDATE ATAU BUAT SESI BARU
            if existing_session:
                session_id = existing_session['id']
                cur.execute("""
                    UPDATE chat_sessions 
                    SET last_message = %s, last_message_at = NOW(), status = 'active'
                    WHERE id = %s
                """, (message, session_id))
            else:
                cur.execute("""
                    INSERT INTO chat_sessions (user_id, guest_email, guest_name, last_message, last_message_at, status)
                    VALUES (%s, %s, %s, %s, NOW(), 'active')
                """, (user_id, guest_email, guest_name, message))
                session_id = cur.lastrowid
            
            # C. INSERT PESAN KE TABEL MESSAGES (DENGAN SESSION_ID)
            cur.execute("""
                INSERT INTO chat_messages 
                (session_id, user_id, guest_name, guest_email, message, message_type, status, created_at) 
                VALUES (%s, %s, %s, %s, %s, %s, 'unread', NOW())
            """, (session_id, user_id, guest_name, guest_email, message, message_type))
            
            conn.commit()
            cur.close()
            
            return jsonify({'success': True, 'message': 'Message sent successfully'})
            
        except mysql.connector.Error as e:
            print(f"Database error in chat: {e}")
            return jsonify({'success': False, 'error': 'Database error'}), 500
        finally:
            if conn: conn.close()
                
    except Exception as e:
        print(f"Error in chat endpoint: {e}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


# ==========================================
# 2. API BALASAN DARI ADMIN (SESSION BASED)
# ==========================================
# Note: Kita ubah parameter dari chat_id menjadi session_id agar konsisten
@chat_controller.route('/api/chats/reply/<int:session_id>', methods=['POST'])
@login_required
def eggmin_api_chats_reply(session_id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    try:
        message = request.form.get('message', '').strip()
        if not message:
            return jsonify({'success': False, 'error': 'Message is required'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500
        
        try:
            cur = conn.cursor(dictionary=True)
            
            # A. Ambil data sesi untuk mengetahui lawan bicara
            cur.execute("SELECT user_id, guest_email, guest_name FROM chat_sessions WHERE id = %s", (session_id,))
            session_data = cur.fetchone()
            
            if not session_data:
                return jsonify({'success': False, 'error': 'Session not found'}), 404
            
            # B. Masukkan Balasan Admin
            cur.execute('''
                INSERT INTO chat_messages 
                (session_id, user_id, guest_name, guest_email, message, message_type, status, created_at) 
                VALUES (%s, %s, %s, %s, %s, 'admin_to_user', 'read', NOW())
            ''', (session_id, session_data['user_id'], session_data['guest_name'], session_data['guest_email'], message))
            
            # C. Update Sesi (Pesan Terakhir)
            cur.execute('''
                UPDATE chat_sessions 
                SET last_message = %s, last_message_at = NOW() 
                WHERE id = %s
            ''', (message, session_id))
            
            conn.commit()
            cur.close()
            
            return jsonify({'success': True, 'message': 'Reply sent successfully'})
            
        except mysql.connector.Error as e:
            print(f"Database error in chat reply: {e}")
            return jsonify({'success': False, 'error': 'Database error'}), 500
        finally:
            if conn: conn.close()
                
    except Exception as e:
        print(f"Error in chat reply: {e}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


# ==========================================
# 3. UTILITIES LAINNYA
# ==========================================

@chat_controller.route('/api/chats/mark-read/<int:chat_id>', methods=['POST'])
@login_required
def eggmin_api_chats_mark_read(chat_id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE chat_messages SET status = 'read' WHERE id = %s", (chat_id,))
        conn.commit()
        cur.close()
        return jsonify({'success': True, 'message': 'Message marked as read'})
    except mysql.connector.Error as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if conn: conn.close()

@chat_controller.route('/api/chats/delete/<int:chat_id>', methods=['POST'])
@login_required
def eggmin_api_chats_delete(chat_id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM chat_messages WHERE id = %s", (chat_id,))
        conn.commit()
        cur.close()
        return jsonify({'success': True, 'message': 'Message deleted successfully'})
    except mysql.connector.Error as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if conn: conn.close()