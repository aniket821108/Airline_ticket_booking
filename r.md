# Flight Management
@app.route('/admin/flights')
@admin_required
def admin_flights():
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 10
        
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # Get total count
            cursor.execute("SELECT COUNT(*) as total FROM flights")
            total = cursor.fetchone()['total']
            
            # Calculate pagination
            offset = (page - 1) * per_page
            
            # Get paginated flights
            cursor.execute("""
                SELECT *, TIMESTAMPDIFF(MINUTE, departure_time, arrival_time) as duration_minutes
                FROM flights 
                ORDER BY departure_time DESC
                LIMIT %s OFFSET %s
            """, (per_page, offset))
            flights = cursor.fetchall()
            
            # Calculate total pages
            total_pages = (total + per_page - 1) // per_page
            
            return render_template('admin.html', 
                                 flights=flights,
                                 pagination={
                                     'page': page,
                                     'per_page': per_page,
                                     'total': total,
                                     'total_pages': total_pages,
                                     'has_prev': page > 1,
                                     'has_next': page < total_pages,
                                     'prev_num': page - 1,
                                     'next_num': page + 1
                                 })
            
    except Exception as e:
        app.logger.error(f"Admin flights error: {str(e)}")
        flash('An error occurred while loading flights', 'danger')
        return redirect(url_for('admin_dashboard'))
    finally:
        if 'conn' in locals():
            conn.close()

# Add Flight
@app.route('/admin/flights/add', methods=['GET', 'POST'])
@admin_required
def admin_add_flight():
    if request.method == 'POST':
        try:
            flight_data = {
                'flight_number': request.form['flight_number'],
                'airline': request.form['airline'],
                'departure_city': request.form['departure_city'],
                'departure_airport_code': request.form['departure_airport'],
                'arrival_city': request.form['arrival_city'],
                'arrival_airport_code': request.form['arrival_airport'],
                'departure_time': request.form['departure_time'],
                'arrival_time': request.form['arrival_time'],
                'price': float(request.form['price']),
                'total_seats': int(request.form['total_seats']),
                'available_seats': int(request.form['total_seats']),  # Initially all seats available
                'status': request.form.get('status', 'Scheduled')
            }
            
            conn = get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO flights (
                        flight_number, airline, departure_city, departure_airport_code,
                        arrival_city, arrival_airport_code, departure_time, arrival_time,
                        price, total_seats, available_seats, status
                    ) VALUES (
                        %(flight_number)s, %(airline)s, %(departure_city)s, %(departure_airport_code)s,
                        %(arrival_city)s, %(arrival_airport_code)s, %(departure_time)s, %(arrival_time)s,
                        %(price)s, %(total_seats)s, %(available_seats)s, %(status)s
                    )
                """, flight_data)
                conn.commit()
                
                flash('Flight added successfully!', 'success')
                return redirect(url_for('admin_flights'))
                
        except Exception as e:
            app.logger.error(f"Add flight error: {str(e)}")
            flash(f'Error adding flight: {str(e)}', 'danger')
            if 'conn' in locals():
                conn.rollback()
        finally:
            if 'conn' in locals():
                conn.close()
    
    return render_template('admin.html')  # This will use the modal in your admin.html

# Edit Flight
@app.route('/admin/flights/edit/<int:flight_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_flight(flight_id):
    if request.method == 'POST':
        try:
            flight_data = {
                'flight_number': request.form['flight_number'],
                'airline': request.form['airline'],
                'departure_city': request.form['departure_city'],
                'departure_airport_code': request.form['departure_airport'],
                'arrival_city': request.form['arrival_city'],
                'arrival_airport_code': request.form['arrival_airport'],
                'departure_time': request.form['departure_time'],
                'arrival_time': request.form['arrival_time'],
                'price': float(request.form['price']),
                'total_seats': int(request.form['total_seats']),
                'status': request.form.get('status', 'Scheduled'),
                'flight_id': flight_id
            }
            
            conn = get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE flights SET
                        flight_number = %(flight_number)s,
                        airline = %(airline)s,
                        departure_city = %(departure_city)s,
                        departure_airport_code = %(departure_airport_code)s,
                        arrival_city = %(arrival_city)s,
                        arrival_airport_code = %(arrival_airport_code)s,
                        departure_time = %(departure_time)s,
                        arrival_time = %(arrival_time)s,
                        price = %(price)s,
                        total_seats = %(total_seats)s,
                        status = %(status)s
                    WHERE id = %(flight_id)s
                """, flight_data)
                conn.commit()
                
                flash('Flight updated successfully!', 'success')
                return redirect(url_for('admin_flights'))
                
        except Exception as e:
            app.logger.error(f"Edit flight error: {str(e)}")
            flash(f'Error updating flight: {str(e)}', 'danger')
            if 'conn' in locals():
                conn.rollback()
        finally:
            if 'conn' in locals():
                conn.close()
    
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM flights WHERE id = %s", (flight_id,))
            flight = cursor.fetchone()
            if not flight:
                flash('Flight not found', 'danger')
                return redirect(url_for('admin_flights'))
            
            return render_template('admin.html', flight_to_edit=flight)
            
    except Exception as e:
        app.logger.error(f"Get flight for edit error: {str(e)}")
        flash('An error occurred while loading flight details', 'danger')
        return redirect(url_for('admin_flights'))
    finally:
        if 'conn' in locals():
            conn.close()

# Cancel Flight
@app.route('/admin/flights/cancel/<int:flight_id>', methods=['POST'])
@admin_required
def admin_cancel_flight(flight_id):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # Check if flight exists
            cursor.execute("SELECT id FROM flights WHERE id = %s", (flight_id,))
            if not cursor.fetchone():
                flash('Flight not found', 'danger')
                return redirect(url_for('admin_flights'))
            
            # Update flight status
            cursor.execute("""
                UPDATE flights SET status = 'Cancelled' 
                WHERE id = %s
            """, (flight_id,))
            
            # Cancel all bookings for this flight
            cursor.execute("""
                UPDATE bookings SET status = 'cancelled' 
                WHERE flight_id = %s AND status = 'confirmed'
            """, (flight_id,))
            
            conn.commit()
            
            flash('Flight and related bookings cancelled successfully!', 'success')
            
    except Exception as e:
        app.logger.error(f"Cancel flight error: {str(e)}")
        flash('An error occurred while cancelling the flight', 'danger')
        if 'conn' in locals():
            conn.rollback()
    finally:
        if 'conn' in locals():
            conn.close()
    
    return redirect(url_for('admin_flights'))

# User Management
@app.route('/admin/users')
@admin_required
def admin_users():
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 10
        
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # Get total count
            cursor.execute("SELECT COUNT(*) as total FROM users")
            total = cursor.fetchone()['total']
            
            # Calculate pagination
            offset = (page - 1) * per_page
            
            # Get paginated users
            cursor.execute("""
                SELECT u.*, 
                       (SELECT COUNT(*) FROM bookings WHERE user_id = u.id) as booking_count
                FROM users u
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            """, (per_page, offset))
            users = cursor.fetchall()
            
            # Calculate total pages
            total_pages = (total + per_page - 1) // per_page
            
            return render_template('admin.html', 
                                 users=users,
                                 user_pagination={
                                     'page': page,
                                     'per_page': per_page,
                                     'total': total,
                                     'total_pages': total_pages,
                                     'has_prev': page > 1,
                                     'has_next': page < total_pages,
                                     'prev_num': page - 1,
                                     'next_num': page + 1
                                 })
            
    except Exception as e:
        app.logger.error(f"Admin users error: {str(e)}")
        flash('An error occurred while loading users', 'danger')
        return redirect(url_for('admin_dashboard'))
    finally:
        if 'conn' in locals():
            conn.close()

# View User Details
@app.route('/admin/users/<int:user_id>')
@admin_required
def admin_view_user(user_id):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # Get user details
            cursor.execute("""
                SELECT u.*, 
                       (SELECT COUNT(*) FROM bookings WHERE user_id = u.id) as booking_count
                FROM users u
                WHERE u.id = %s
            """, (user_id,))
            user = cursor.fetchone()
            
            if not user:
                flash('User not found', 'danger')
                return redirect(url_for('admin_users'))
            
            # Get user's bookings
            cursor.execute("""
                SELECT b.*, f.flight_number, f.departure_city, f.arrival_city,
                       f.departure_time, f.arrival_time
                FROM bookings b
                JOIN flights f ON b.flight_id = f.id
                WHERE b.user_id = %s
                ORDER BY b.booking_date DESC
            """, (user_id,))
            bookings = cursor.fetchall()
            
            return render_template('admin.html', user_details=user, user_bookings=bookings)
            
    except Exception as e:
        app.logger.error(f"View user error: {str(e)}")
        flash('An error occurred while loading user details', 'danger')
        return redirect(url_for('admin_users'))
    finally:
        if 'conn' in locals():
            conn.close()

# Delete User
@app.route('/admin/users/delete/<int:user_id>', methods=['POST'])
@admin_required
def admin_delete_user(user_id):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # Check if user exists
            cursor.execute("SELECT id FROM users WHERE id = %s", (user_id,))
            if not cursor.fetchone():
                flash('User not found', 'danger')
                return redirect(url_for('admin_users'))
            
            # Delete user's bookings first
            cursor.execute("DELETE FROM bookings WHERE user_id = %s", (user_id,))
            
            # Delete user
            cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
            
            conn.commit()
            
            flash('User and related bookings deleted successfully!', 'success')
            
    except Exception as e:
        app.logger.error(f"Delete user error: {str(e)}")
        flash('An error occurred while deleting the user', 'danger')
        if 'conn' in locals():
            conn.rollback()
    finally:
        if 'conn' in locals():
            conn.close()
    
    return redirect(url_for('admin_users'))

# Booking Management
@app.route('/admin/bookings')
@admin_required
def admin_bookings():
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 10
        status_filter = request.args.get('status', 'all')
        
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # Build base query
            query = """
                SELECT b.*, 
                       u.name as user_name, 
                       u.email as user_email,
                       f.flight_number,
                       f.departure_city,
                       f.arrival_city,
                       f.departure_time,
                       f.arrival_time
                FROM bookings b
                JOIN users u ON b.user_id = u.id
                JOIN flights f ON b.flight_id = f.id
            """
            
            params = []
            
            # Add status filter if not 'all'
            if status_filter != 'all':
                query += " WHERE b.status = %s"
                params.append(status_filter)
            
            # Add ordering
            query += " ORDER BY b.booking_date DESC"
            
            # Get total count
            count_query = "SELECT COUNT(*) as total FROM bookings"
            if status_filter != 'all':
                count_query += " WHERE status = %s"
            
            cursor.execute(count_query, params)
            total = cursor.fetchone()['total']
            
            # Calculate pagination
            offset = (page - 1) * per_page
            
            # Add pagination to main query
            query += " LIMIT %s OFFSET %s"
            params.extend([per_page, offset])
            
            # Get paginated bookings
            cursor.execute(query, params)
            bookings = cursor.fetchall()
            
            # Calculate total pages
            total_pages = (total + per_page - 1) // per_page
            
            return render_template('admin.html', 
                                 bookings=bookings,
                                 booking_pagination={
                                     'page': page,
                                     'per_page': per_page,
                                     'total': total,
                                     'total_pages': total_pages,
                                     'has_prev': page > 1,
                                     'has_next': page < total_pages,
                                     'prev_num': page - 1,
                                     'next_num': page + 1
                                 },
                                 status_filter=status_filter)
            
    except Exception as e:
        app.logger.error(f"Admin bookings error: {str(e)}")
        flash('An error occurred while loading bookings', 'danger')
        return redirect(url_for('admin_dashboard'))
    finally:
        if 'conn' in locals():
            conn.close()

# View Booking Details
@app.route('/admin/bookings/<int:booking_id>')
@admin_required
def admin_booking_details(booking_id):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT b.*, 
                       u.name as user_name, 
                       u.email as user_email,
                       u.phone as user_phone,
                       f.*,
                       TIMESTAMPDIFF(MINUTE, f.departure_time, f.arrival_time) as duration_minutes
                FROM bookings b
                JOIN users u ON b.user_id = u.id
                JOIN flights f ON b.flight_id = f.id
                WHERE b.id = %s
            """, (booking_id,))
            booking = cursor.fetchone()
            
            if not booking:
                flash('Booking not found', 'danger')
                return redirect(url_for('admin_bookings'))
            
            return render_template('admin.html', booking_details=booking)
            
    except Exception as e:
        app.logger.error(f"Booking details error: {str(e)}")
        flash('An error occurred while loading booking details', 'danger')
        return redirect(url_for('admin_bookings'))
    finally:
        if 'conn' in locals():
            conn.close()

# Cancel Booking
@app.route('/admin/bookings/cancel/<int:booking_id>', methods=['POST'])
@admin_required
def admin_cancel_booking(booking_id):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # Get booking details
            cursor.execute("""
                SELECT b.*, f.available_seats 
                FROM bookings b
                JOIN flights f ON b.flight_id = f.id
                WHERE b.id = %s AND b.status = 'confirmed'
            """, (booking_id,))
            booking = cursor.fetchone()
            
            if not booking:
                flash('Booking not found or already cancelled', 'warning')
                return redirect(url_for('admin_bookings'))
            
            # Update booking status
            cursor.execute("""
                UPDATE bookings SET status = 'cancelled' 
                WHERE id = %s
            """, (booking_id,))
            
            # Return seats to flight
            cursor.execute("""
                UPDATE flights SET available_seats = available_seats + %s 
                WHERE id = %s
            """, (booking['passengers'], booking['flight_id']))
            
            conn.commit()
            
            flash('Booking cancelled successfully! Seats have been returned to the flight.', 'success')
            
    except Exception as e:
        app.logger.error(f"Cancel booking error: {str(e)}")
        flash('An error occurred while cancelling the booking', 'danger')
        if 'conn' in locals():
            conn.rollback()
    finally:
        if 'conn' in locals():
            conn.close()
    
    return redirect(url_for('admin_bookings'))

# System Settings
@app.route('/admin/settings', methods=['GET', 'POST'])
@admin_required
def admin_settings():
    if request.method == 'POST':
        try:
            site_name = request.form.get('site_name')
            maintenance_mode = request.form.get('maintenance_mode', '0')
            booking_cutoff = request.form.get('booking_cutoff')
            
            conn = get_db_connection()
            with conn.cursor() as cursor:
                # Update settings
                cursor.execute("""
                    INSERT INTO system_settings (setting_name, setting_value)
                    VALUES 
                        ('site_name', %s),
                        ('maintenance_mode', %s),
                        ('booking_cutoff', %s)
                    ON DUPLICATE KEY UPDATE setting_value = VALUES(setting_value)
                """, (site_name, maintenance_mode, booking_cutoff))
                
                conn.commit()
                
                flash('Settings updated successfully!', 'success')
                return redirect(url_for('admin_settings'))
                
        except Exception as e:
            app.logger.error(f"Update settings error: {str(e)}")
            flash('An error occurred while updating settings', 'danger')
            if 'conn' in locals():
                conn.rollback()
        finally:
            if 'conn' in locals():
                conn.close()
    
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM system_settings")
            settings = {row['setting_name']: row['setting_value'] for row in cursor.fetchall()}
            
            return render_template('admin.html', settings=settings)
            
    except Exception as e:
        app.logger.error(f"Get settings error: {str(e)}")
        flash('An error occurred while loading settings', 'danger')
        return redirect(url_for('admin_dashboard'))
    finally:
        if 'conn' in locals():
            conn.close()

# Create Backup
@app.route('/admin/backup', methods=['POST'])
@admin_required
def admin_create_backup():
    try:
        backup_name = request.form.get('backup_name', f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        backup_type = request.form.get('backup_type', 'full')
        compress = request.form.get('compress', 'false') == 'true'
        
        # In a real application, you would implement actual backup logic here
        # This is just a placeholder
        backup_path = f"backups/{backup_name}.sql"
        
        # Create backups directory if it doesn't exist
        os.makedirs('backups', exist_ok=True)
        
        # Simulate backup creation
        with open(backup_path, 'w') as f:
            f.write(f"-- Database Backup\n")
            f.write(f"-- Type: {backup_type}\n")
            f.write(f"-- Created: {datetime.now()}\n")
            f.write(f"-- By: {session['admin_name']}\n")
        
        if compress:
            # Simulate compression
            compressed_path = f"{backup_path}.zip"
            with open(compressed_path, 'w') as f:
                f.write(f"Compressed version of {backup_path}\n")
            os.remove(backup_path)
            backup_path = compressed_path
        
        flash(f'Backup created successfully at {backup_path}', 'success')
        
    except Exception as e:
        app.logger.error(f"Create backup error: {str(e)}")
        flash('An error occurred while creating the backup', 'danger')
    
    return redirect(url_for('admin_dashboard'))

# Clear Cache
@app.route('/admin/clear-cache', methods=['POST'])
@admin_required
def admin_clear_cache():
    # In a real application, you would implement actual cache clearing logic here
    flash('System cache cleared successfully', 'success')
    return redirect(url_for('admin_dashboard'))

# System Logs
@app.route('/admin/logs')
@admin_required
def admin_system_logs():
    # In a real application, you would implement actual log viewing logic here
    logs = [
        {'timestamp': '2023-01-01 10:00:00', 'level': 'INFO', 'message': 'System started'},
        {'timestamp': '2023-01-01 10:05:00', 'level': 'INFO', 'message': 'Admin logged in'},
        {'timestamp': '2023-01-01 10:10:00', 'level': 'WARNING', 'message': 'Low disk space'},
    ]
    return render_template('admin.html', system_logs=logs)
