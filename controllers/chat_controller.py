from flask import Blueprint, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from utils.database import get_db_connection
import mysql.connector

chat_controller = Blueprint('chat_controller', __name__)

@chat_controller.route('/api/chat/send', methods=['POST'])
def comprof_send_chat():
    """Handle chat messages from Comprof pages"""
    try:
        data = request.get_json()
        message = data.get('message', '').strip()
        
        if not message:
            return jsonify({'success': False, 'error': 'Message is required'}), 400

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500

        try:
            cur = conn.cursor()
            
            if data.get('user_id'):
                # User is logged in
                user_id = data['user_id']
                cur.execute(
                    "INSERT INTO chat_messages (user_id, message, message_type) VALUES (%s, %s, 'user_to_admin')",
                    (user_id, message)
                )
            else:
                # Guest user
                guest_name = data.get('guest_name', '').strip()
                guest_email = data.get('guest_email', '').strip()
                
                if not guest_name or not guest_email:
                    return jsonify({'success': False, 'error': 'Name and email are required for guests'}), 400
                
                cur.execute(
                    "INSERT INTO chat_messages (guest_name, guest_email, message, message_type) VALUES (%s, %s, %s, 'guest_to_admin')",
                    (guest_name, guest_email, message)
                )
            
            conn.commit()
            cur.close()
            
            # TODO: Send email notification to admin
            print(f"📩 New chat message received: {message}")
            
            return jsonify({'success': True, 'message': 'Message sent successfully'})
            
        except mysql.connector.Error as e:
            print(f"Database error in chat: {e}")
            return jsonify({'success': False, 'error': 'Database error'}), 500
        finally:
            if conn:
                conn.close()
                
    except Exception as e:
        print(f"Error in chat endpoint: {e}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

# Chat Management APIs for Admin
@chat_controller.route('/api/chats/reply/<int:chat_id>', methods=['POST'])
@login_required
def eggmin_api_chats_reply(chat_id):
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
            cur = conn.cursor()
            
            # Get original message details
            cur.execute('''
                SELECT user_id, guest_email, guest_name, message_type 
                FROM chat_messages 
                WHERE id = %s
            ''', (chat_id,))
            original_msg = cur.fetchone()
            
            if not original_msg:
                return jsonify({'success': False, 'error': 'Original message not found'}), 404
            
            # Determine reply type and recipient
            if original_msg[0]:  # user_id exists (registered user)
                reply_type = 'admin_to_user'
                user_id = original_msg[0]
                guest_email = None
                guest_name = None
            else:  # guest user
                reply_type = 'admin_to_guest'
                user_id = None
                guest_email = original_msg[1]
                guest_name = original_msg[2]
            
            # Insert reply message
            cur.execute('''
                INSERT INTO chat_messages 
                (user_id, guest_name, guest_email, message, message_type, parent_message_id, status) 
                VALUES (%s, %s, %s, %s, %s, %s, 'read')
            ''', (user_id, guest_name, guest_email, message, reply_type, chat_id))
            
            # Update original message status to replied
            cur.execute('''
                UPDATE chat_messages 
                SET status = 'replied' 
                WHERE id = %s
            ''', (chat_id,))
            
            conn.commit()
            cur.close()
            
            # TODO: Send email notification to the user/guest
            print(f"📩 Admin replied to chat {chat_id}: {message}")
            
            return jsonify({'success': True, 'message': 'Reply sent successfully'})
            
        except mysql.connector.Error as e:
            print(f"Database error in chat reply: {e}")
            return jsonify({'success': False, 'error': 'Database error'}), 500
        finally:
            if conn:
                conn.close()
                
    except Exception as e:
        print(f"Error in chat reply: {e}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

@chat_controller.route('/api/chats/mark-read/<int:chat_id>', methods=['POST'])
@login_required
def eggmin_api_chats_mark_read(chat_id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': 'Database connection failed'}), 500
    
    try:
        cur = conn.cursor()
        
        # Check if message exists
        cur.execute("SELECT * FROM chat_messages WHERE id = %s", (chat_id,))
        if not cur.fetchone():
            return jsonify({'success': False, 'error': 'Message not found'}), 404
        
        cur.execute(
            "UPDATE chat_messages SET status = 'read' WHERE id = %s",
            (chat_id,)
        )
        conn.commit()
        cur.close()
        
        return jsonify({'success': True, 'message': 'Message marked as read'})
        
    except mysql.connector.Error as e:
        print(f"Database error in mark read: {e}")
        return jsonify({'success': False, 'error': 'Database error'}), 500
    finally:
        if conn:
            conn.close()

@chat_controller.route('/api/chats/delete/<int:chat_id>', methods=['POST'])
@login_required
def eggmin_api_chats_delete(chat_id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': 'Database connection failed'}), 500
    
    try:
        cur = conn.cursor()
        
        # Check if message exists
        cur.execute("SELECT * FROM chat_messages WHERE id = %s", (chat_id,))
        if not cur.fetchone():
            return jsonify({'success': False, 'error': 'Message not found'}), 404
        
        cur.execute("DELETE FROM chat_messages WHERE id = %s", (chat_id,))
        conn.commit()
        cur.close()
        
        return jsonify({'success': True, 'message': 'Message deleted successfully'})
        
    except mysql.connector.Error as e:
        print(f"Database error in chat delete: {e}")
        return jsonify({'success': False, 'error': 'Database error'}), 500
    finally:
        if conn:
            conn.close()