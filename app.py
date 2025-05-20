from flask import Flask, render_template, request, redirect, url_for, session, flash
import pymysql
from pymysql.cursors import DictCursor
import re
import uuid
from werkzeug.utils import secure_filename
import mysql.connector
import os
from functools import wraps
import time
from datetime import timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import traceback  
import logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.secret_key = 'your_very_strong_secret_key_here'
# Upload folder path
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Allowed file types
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
import pymysql
from pymysql.cursors import DictCursor

DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'aniket123@',
    'database': 'airline_booking',
    'cursorclass': DictCursor
}

def get_db_connection():
    return pymysql.connect(**DB_CONFIG)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.context_processor
def inject_admin():
    """Make admin data available to all templates"""
    if 'admin_id' in session:
        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT id, name, email, image_path 
                    FROM admins 
                    WHERE id = %s
                """, (session['admin_id'],))
                admin = cursor.fetchone()
                
                if admin and admin.get('image_path'):
                    # Normalize image path
                    admin['image_path'] = admin['image_path'].replace('\\', '/').replace('static/', '').lstrip('/')
                    
                return {'admin': admin}
        except Exception as e:
            app.logger.error(f"Error loading admin data: {str(e)}")
            return {'admin': None}
        finally:
            if 'conn' in locals():
                conn.close()
    return {'admin': None}
@app.context_processor

def inject_user():
    """Make user data available to all templates"""
    if 'user_id' in session:
        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT id, name, email, image_path 
                    FROM users 
                    WHERE id = %s
                """, (session['user_id'],))
                user = cursor.fetchone()
                
                if user and user.get('image_path'):
                    # Normalize image path
                    user['image_path'] = user['image_path'].replace('\\', '/').replace('static/', '').lstrip('/')
                    
                return {'user': user}
        except Exception as e:
            app.logger.error(f"Error loading user data: {str(e)}")
            return {'user': None}
        finally:
            if 'conn' in locals():
                conn.close()
    return {'user': None}

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if 'user_id' not in session:
        flash('Please login to upload profile picture', 'warning')
        return redirect(url_for('login'))

    if request.method == 'POST':
        # Check if the post request has the file part
        if 'image' not in request.files:
            flash('No file part in the request', 'danger')
            return redirect(request.url)
        
        file = request.files['image']
        
        # If user does not select file, browser submits empty file without filename
        if file.filename == '':
            flash('No selected file', 'danger')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            try:
                # Create secure filename and unique path
                filename = secure_filename(file.filename)
                unique_filename = f"{session['user_id']}_{filename}"
                save_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                
                # Ensure upload directory exists
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                
                # Save the file
                file.save(save_path)
                
                # Store relative path in database (without 'static/' prefix)
                relative_path = os.path.join('uploads', unique_filename)
                
                # Update user's profile picture in database
                conn = get_db_connection()
                try:
                    with conn.cursor() as cursor:
                        # First get old image path to delete it
                        cursor.execute("SELECT image_path FROM users WHERE id = %s", (session['user_id'],))
                        old_image = cursor.fetchone()
                        
                        # Update with new image path
                        cursor.execute("UPDATE users SET image_path = %s WHERE id = %s", 
                                     (relative_path, session['user_id']))
                        conn.commit()
                        
                        # Delete old image if it exists
                        if old_image and old_image['image_path']:
                            old_path = os.path.join('static', old_image['image_path'])
                            if os.path.exists(old_path):
                                os.remove(old_path)
                    
                    flash('Profile picture updated successfully!', 'success')
                    return redirect(url_for('profile'))
                    
                except Exception as e:
                    conn.rollback()
                    flash(f'Database error: {str(e)}', 'danger')
                    # Return debug info in development
                    if app.debug:
                        return render_template('upload.html', 
                                            debug_info=f"Database Error: {str(e)}\n\nTraceback:\n{traceback.format_exc()}")
                    return redirect(url_for('upload'))
                finally:
                    conn.close()
            except Exception as e:
                flash(f'Error saving file: {str(e)}', 'danger')
                # Return debug info in development
                if app.debug:
                    return render_template('upload.html', 
                                        debug_info=f"File Save Error: {str(e)}\n\nTraceback:\n{traceback.format_exc()}")
                return redirect(url_for('upload'))
        else:
            flash('Allowed file types are: png, jpg, jpeg, gif', 'danger')
            return redirect(url_for('upload'))

    return render_template('upload.html')
def get_db_connection():
    """Establish and return a new database connection"""
    return pymysql.connect(**DB_CONFIG)

# Verify database connection at startup
try:
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("SELECT 1")
        print("✅ Database connection successful!")
    conn.close()
except Exception as e:
    print(f"❌ Database connection failed: {e}")
    raise RuntimeError("Database connection failed") from e

@app.template_filter('duration')
def format_duration(delta):
    """Convert duration to 'Xh Ym' format handling both timedelta and minutes"""
    if delta is None:
        return "N/A"
        
    if isinstance(delta, int):  # Already in minutes
        hours = delta // 60
        minutes = delta % 60
    else:  # Assume timedelta
        total_seconds = delta.total_seconds()
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
    
    return f"{hours}h {minutes}m"# Routes

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/admin')
def admin():
    return render_template('admin.html')

@app.route('/test_flights')
def test_flights():
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM flights LIMIT 5")
            flights = cursor.fetchall()
            return str(flights)
    except Exception as e:
        return f"Database error: {str(e)}"
    finally:
        conn.close()

@app.route('/login', methods=['GET', 'POST'])
def login():
    msg = ''
    if request.method == 'POST' and 'email' in request.form and 'password' in request.form:
        email = request.form['email']
        password = request.form['password']
        
        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
                user = cursor.fetchone()
                
                if user and check_password_hash(user['password'], password):
                    session['loggedin'] = True
                    session['user_id'] = user['id']
                    session['email'] = user['email']
                    session['name'] = user['name']
                    msg = 'Logged in successfully!'
                    return redirect(url_for('dashboard'))
                else:
                    msg = 'Incorrect email/password!'
        except Exception as e:
            msg = f'Database error: {str(e)}'
        finally:
            conn.close()
    
    return render_template('login.html', msg=msg)

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully!', 'success')
    return redirect(url_for('home'))

@app.route('/register', methods=['GET', 'POST']) 
def register():
    msg = ''
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        phone = request.form.get('phone')
        landline = request.form.get('landline')
        address = request.form.get('address')
        pincode = request.form.get('pincode')
        city = request.form.get('city')
        state = request.form.get('state')
        country = request.form.get('country')

        image_path = None
        if 'profile_image' in request.files:
            file = request.files['profile_image']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                unique_filename = f"{str(uuid.uuid4())[:8]}_{filename}"
                save_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                file.save(save_path)
                image_path = os.path.join('uploads', unique_filename)
        user_id = str(uuid.uuid4())[:8]  # generate short unique ID
        created_at = datetime.now()

        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
                account = cursor.fetchone()

                if account:
                    msg = 'Account already exists!'
                elif not re.match(r'[^@]+@[^@]+\.[^@]+', email):
                    msg = 'Invalid email address!'
                elif not all([name, email, password]):
                    msg = 'Please fill out all required fields!'
                else:
                    hashed_password = generate_password_hash(password)
                    cursor.execute(
                        '''
                        INSERT INTO users 
                        (user_id, name, email, password, phone, landline, address, pincode, city, state, country, image_path, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ''',
                        (user_id, name, email, hashed_password, phone, landline, address, pincode, city, state, country, image_path, created_at)
                    )
                    conn.commit()
                    flash('You have successfully registered! Please login.', 'success')
                    return redirect(url_for('login'))
        except Exception as e:
            conn.rollback()
            msg = f'Error occurred: {str(e)}'
        finally:
            conn.close()

    return render_template('register.html', msg=msg)
@app.route('/dashboard')
def dashboard():
    if 'loggedin' in session:
        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                # Fetch available flights
                cursor.execute('SELECT * FROM flights WHERE departure_time > NOW() ORDER BY departure_time LIMIT 5')
                flights = cursor.fetchall()
                
                # Fetch user's bookings
                cursor.execute('''
                    SELECT b.*, f.flight_number, f.departure_city, f.arrival_city, 
                           f.departure_time, f.arrival_time, f.price
                    FROM bookings b
                    JOIN flights f ON b.flight_id = f.id
                    WHERE b.user_id = %s
                    ORDER BY b.booking_date DESC
                ''', (session['user_id'],))
                bookings = cursor.fetchall()
                
                return render_template('dashboard.html', 
                                     name=session['name'], 
                                     flights=flights, 
                                     bookings=bookings)
        except Exception as e:
            flash(f'Database error: {str(e)}', 'danger')
            return redirect(url_for('home'))
        finally:
            conn.close()
    return redirect(url_for('login'))
@app.route('/search_flights', methods=['GET', 'POST'])

def search_flights():
    if 'loggedin' not in session:
        flash('Please login to search flights', 'warning')
        return redirect(url_for('login'))

    current_date = datetime.now().strftime('%Y-%m-%d')
    
    if request.method == 'POST':
        try:
            # Get and validate form data
            departure_city = request.form.get('departure_city', '').strip()
            arrival_city = request.form.get('arrival_city', '').strip()
            departure_date = request.form.get('departure_date', '').strip()
            passengers = request.form.get('passengers', '1')

            # Validate passengers
            try:
                passengers = int(passengers)
                if passengers < 1 or passengers > 10:
                    raise ValueError
            except ValueError:
                flash('Please enter valid number of passengers (1-10)', 'danger')
                return redirect(url_for('search_flights'))

            conn = get_db_connection()
            with conn.cursor() as cursor:  # Fixed: Added parentheses here
                # Build base query with parameterized inputs
                query = """
                    SELECT *, 
                           TIMESTAMPDIFF(MINUTE, departure_time, arrival_time) AS duration_minutes
                    FROM flights 
                    WHERE departure_time >= NOW()
                    AND available_seats >= %s
                """
                params = [passengers]

                # Add city filters if provided
                if departure_city:
                    query += " AND (LOWER(departure_city) = LOWER(%s) OR LOWER(departure_airport_code) = LOWER(%s))"
                    params.extend([departure_city, departure_city])

                if arrival_city:
                    query += " AND (LOWER(arrival_city) = LOWER(%s) OR LOWER(arrival_airport_code) = LOWER(%s))"
                    params.extend([arrival_city, arrival_city])

                # Add date filter if provided
                if departure_date:
                    try:
                        departure_datetime = datetime.strptime(departure_date, '%Y-%m-%d')
                        query += " AND DATE(departure_time) = DATE(%s)"
                        params.append(departure_datetime)
                    except ValueError:
                        flash('Invalid date format. Please use YYYY-MM-DD', 'danger')
                        return redirect(url_for('search_flights'))

                query += " ORDER BY departure_time, price"
                
                app.logger.debug(f"Executing query: {query}")
                app.logger.debug(f"With parameters: {params}")
                
                cursor.execute(query, params)
                flights = cursor.fetchall()

                if not flights:
                    flash('No flights found matching your criteria', 'info')
                    return redirect(url_for('search_flights'))

                return render_template('search_results.html', flights=flights)

        except Exception as e:
            app.logger.error(f"Error in search_flights: {str(e)}")
            flash('An error occurred while searching for flights', 'danger')
            return redirect(url_for('search_flights'))
        finally:
            if 'conn' in locals():
                conn.close()

    # GET request - show search form
    return render_template('search_flights.html', current_date=current_date)
# Add this temporary route to verify flights exist
@app.route('/debug_flights')
def debug_flights():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM flights WHERE departure_time >= NOW() LIMIT 10")
    flights = cursor.fetchall()
    cursor.close()
    conn.close()
    return str(flights)

# Test the exact query being generated
@app.route('/test_query')
def test_query():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    query = "YOUR_QUERY_HERE"
    params = [YOUR_PARAMS_HERE]
    cursor.execute(query, params)
    results = cursor.fetchall()
    cursor.close()
    conn.close()
    return str(results)
@app.route('/book_flight/<int:flight_id>', methods=['GET', 'POST'])
def book_flight(flight_id):
    if 'loggedin' not in session:
        flash('Please login to book flights', 'warning')
        return redirect(url_for('login'))
    
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # Get flight details with duration calculation
            cursor.execute('''
                SELECT *, 
                       TIMESTAMPDIFF(MINUTE, departure_time, arrival_time) AS duration_minutes
                FROM flights 
                WHERE id = %s
            ''', (flight_id,))
            flight = cursor.fetchone()
            
            if not flight:
                flash('Flight not found', 'danger')
                return redirect(url_for('search_flights'))
            
            if request.method == 'POST':
                try:
                    passengers = int(request.form['passengers'])
                    if passengers < 1 or passengers > flight['available_seats']:
                        raise ValueError
                except (KeyError, ValueError):
                    flash('Invalid number of passengers', 'danger')
                    return redirect(url_for('book_flight', flight_id=flight_id))
                
                total_price = flight['price'] * passengers
                
                # Create booking
                cursor.execute('''
                    INSERT INTO bookings (user_id, flight_id, passengers, total_price, booking_date)
                    VALUES (%s, %s, %s, %s, NOW())
                ''', (session['user_id'], flight_id, passengers, total_price))
                
                # Update available seats
                cursor.execute('''
                    UPDATE flights SET available_seats = available_seats - %s 
                    WHERE id = %s
                ''', (passengers, flight_id))
                
                conn.commit()
                flash('Booking confirmed!', 'success')
                return redirect(url_for('dashboard'))
            
            # GET request - show booking form
            return render_template('book_flight.html', flight=flight)  # Ensure this matches your template name
            
    except Exception as e:
        app.logger.error(f"Booking error: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
        flash('An error occurred during booking', 'danger')
        return redirect(url_for('search_flights'))
    finally:
        if 'conn' in locals():
            conn.close()
@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/cancel_booking/<int:booking_id>')
def cancel_booking(booking_id):
    if 'loggedin' not in session:
        return redirect(url_for('login'))
    
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute('SELECT * FROM bookings WHERE id = %s AND user_id = %s', (booking_id, session['user_id']))
            booking = cursor.fetchone()
            
            if booking:
                # Return seats to flight
                cursor.execute('''
                    UPDATE flights SET available_seats = available_seats + %s 
                    WHERE id = %s
                ''', (booking['passengers'], booking['flight_id']))
                
                # Delete booking
                cursor.execute('DELETE FROM bookings WHERE id = %s', (booking_id,))
                conn.commit()
                flash('Booking cancelled successfully!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Error: {str(e)}', 'danger')
    finally:
        conn.close()
    
    return redirect(url_for('dashboard'))
@app.route('/profile')
def profile():
    try:
        # Check if user is logged in
        if 'user_id' not in session:
            app.logger.warning('Unauthorized access attempt to profile page')
            flash('Please login to view your profile', 'warning')
            return redirect(url_for('login'))
        
        app.logger.debug(f"Fetching profile for user_id: {session['user_id']}")
        
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                # Get user data including profile picture path
                cursor.execute("""
                    SELECT id, user_id, name, email, phone, address, 
                           pincode, city, state, country, image_path, created_at
                    FROM users 
                    WHERE id = %s
                """, (session['user_id'],))
                user = cursor.fetchone()
                
                if not user:
                    app.logger.error(f"User not found in database: {session['user_id']}")
                    flash('User account not found', 'danger')
                    return redirect(url_for('logout'))
                
                # Generate user_id if missing (legacy support)
                if not user.get('user_id'):
                    user['user_id'] = f"user{user['id']:04d}"
                    app.logger.info(f"Generated user_id: {user['user_id']}")
                
                # Normalize image path
                if user.get('image_path'):
                    # Ensure path uses forward slashes and doesn't start with static/
                    user['image_path'] = user['image_path'].replace('\\', '/')
                    if user['image_path'].startswith('static/'):
                        user['image_path'] = user['image_path'][7:]  # Remove static/ prefix
                    elif user['image_path'].startswith('/static/'):
                        user['image_path'] = user['image_path'][8:]
                
                app.logger.debug(f"Profile data retrieved for {user['email']}")
                return render_template('profile.html', user=user)
                
        except pymysql.Error as e:
            app.logger.error(f"Database error in profile route: {str(e)}")
            flash('Database error occurred while loading profile', 'danger')
            return redirect(url_for('dashboard'))
        finally:
            if conn:
                conn.close()
                
    except Exception as e:
        app.logger.error(f"Unexpected error in profile route: {str(e)}", exc_info=True)
        flash('An unexpected error occurred', 'danger')
        return redirect(url_for('home'))
    
    

@app.route('/update_profile', methods=['GET', 'POST'])
def update_profile():
    if 'user_id' not in session:
        return redirect('/login')

    try:
        conn = get_db_connection()
        
        if request.method == 'POST':
            # Get form data
            form_data = {
                'name': request.form.get('name'),
                'email': request.form.get('email'),
                'phone': request.form.get('phone'),
                'address': request.form.get('address'),
                'pincode': request.form.get('pincode'),
                'city': request.form.get('city'),
                'state': request.form.get('state'),
                'country': request.form.get('country'),
                'landline': request.form.get('landline'),
                'id': session['user_id']
            }

            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE users SET 
                    name = %(name)s,
                    email = %(email)s,
                    phone = %(phone)s,
                    address = %(address)s,
                    pincode = %(pincode)s,
                    city = %(city)s,
                    state = %(state)s,
                    country = %(country)s,
                    landline = %(landline)s
                    WHERE id = %(id)s
                """, form_data)
                conn.commit()

            return redirect('/profile')

        # GET request - show edit form
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE id = %s", (session['user_id'],))
            user = cursor.fetchone()

        return render_template('update_profile.html', user=user)

    except Exception as e:
        return f"Error: {str(e)}", 500

    finally:
        conn.close()
@app.route('/change-password', methods=['GET', 'POST'])
def change_password():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = None
    cursor = None

    try:
        # Establish database connection
        conn = get_db_connection()
        cursor = conn.cursor()  # Removed dictionary=True

        if request.method == 'POST':
            current_password = request.form['current_password']
            new_password = request.form['new_password']
            confirm_password = request.form['confirm_password']
            
            # Fetch the current user from DB
            cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            user = cursor.fetchone()
            
            if not user:
                flash('User not found.')
                return redirect(url_for('change_password'))
            
            # Check if current password matches
            if not check_password_hash(user['password'], current_password):
                flash('Current password is incorrect.')
                return redirect(url_for('change_password'))
            
            # Check if new passwords match
            if new_password != confirm_password:
                flash('New passwords do not match.')
                return redirect(url_for('change_password'))
            
            # Update password in the database
            hashed_password = generate_password_hash(new_password)
            cursor.execute("UPDATE users SET password = %s WHERE id = %s", (hashed_password, user_id))
            conn.commit()
            
            flash('Password changed successfully.')
            return redirect(url_for('profile'))

        return render_template('change_password.html')

    except Exception as e:
        # In case of any error, print the error and return a message
        print(f"Error: {str(e)}")
        return f"An error occurred: {str(e)}", 500

    finally:
        # Ensure cursor and connection are closed properly
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# Admin routes
@app.route('/admin/add_flight', methods=['GET', 'POST'])
def add_flight():
    if 'loggedin' not in session or session.get('email') != 'admin@example.com':  # Replace with your admin check
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        flight_number = request.form['flight_number']
        airline = request.form['airline']
        departure_city = request.form['departure_city']
        arrival_city = request.form['arrival_city']
        departure_time = request.form['departure_time']
        arrival_time = request.form['arrival_time']
        price = float(request.form['price'])
        available_seats = int(request.form['available_seats'])
        
        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute('''
                    INSERT INTO flights (flight_number, airline, departure_city, arrival_city,
                                       departure_time, arrival_time, price, available_seats)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ''', (flight_number, airline, departure_city, arrival_city,
                     departure_time, arrival_time, price, available_seats))
                conn.commit()
                flash('Flight added successfully!', 'success')
                return redirect(url_for('dashboard'))
        except Exception as e:
            conn.rollback()
            flash(f'Error: {str(e)}', 'danger')
        finally:
            conn.close()
    
    return render_template('add_flight.html')
# Add these imports at the top of app.py

# Admin required decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_loggedin' not in session:
            flash('Please login to access this page', 'warning')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function
# Admin Login
@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    msg = ''
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute('SELECT * FROM admins WHERE email = %s', (email,))
                admin = cursor.fetchone()
                
                if admin and check_password_hash(admin['password'], password):
                    session['admin_loggedin'] = True
                    session['admin_id'] = admin['id']
                    session['admin_email'] = admin['email']
                    session['admin_name'] = admin['name']
                    msg = 'Logged in successfully!'
                    return redirect(url_for('admin_dashboard'))
                else:
                    msg = 'Incorrect email/password!'
        except Exception as e:
            msg = f'Database error: {str(e)}'
        finally:
            conn.close()
    
    return render_template('admin_login.html', msg=msg)
# Admin Logout Route
@app.route('/admin_logout')
def admin_logout():
    session.pop('admin_loggedin', None)
    session.pop('admin_id', None)
    session.pop('admin_email', None)
    session.pop('admin_name', None)
    flash('You have been logged out successfully!', 'success')
    return redirect(url_for('admin_login'))
# Middleware to protect admin routes
        
        
# Admin Register
@app.route('/admin_register', methods=['GET', 'POST'])
def admin_register():
    msg = ''
    if request.method == 'POST':
        
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        phone = request.form.get('phone', '')
        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute('SELECT * FROM admins WHERE email = %s', (email,))
                account = cursor.fetchone()

                if account:
                    msg = 'Account already exists!'
                elif not re.match(r'[^@]+@[^@]+\.[^@]+', email):
                    msg = 'Invalid email address!'
                elif not all([name, email, password]):
                    msg = 'Please fill out all required fields!'
                else:
                    hashed_password = generate_password_hash(password)
                    cursor.execute(
                        'INSERT INTO admins (name, email, password, phone) VALUES (%s, %s, %s, %s)',
                        (name, email, hashed_password, phone)
                    )
                    conn.commit()
                    flash('You have successfully registered! Please login.', 'success')
                    return redirect(url_for('admin_login'))
        except Exception as e:
            conn.rollback()
            msg = f'Error occurred: {str(e)}'
        finally:
            conn.close()

    return render_template('admin_register.html', msg=msg)

@app.route('/admin_dashboard')
def admin_dashboard():
    if 'admin_loggedin' not in session:
        return redirect(url_for('admin_login'))
    
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # Get flight count
            cursor.execute('SELECT COUNT(*) as flight_count FROM flights')
            flight_count = cursor.fetchone()['flight_count']
            
            # Get user count
            cursor.execute('SELECT COUNT(*) as user_count FROM users')
            user_count = cursor.fetchone()['user_count']
            
            # Get booking count
            cursor.execute('SELECT COUNT(*) as booking_count FROM bookings')
            booking_count = cursor.fetchone()['booking_count']
            
            # Get recent flights
            cursor.execute('SELECT * FROM flights ORDER BY departure_time DESC LIMIT 5')
            flights = cursor.fetchall()
            
            # Get recent bookings
            cursor.execute('''
                SELECT b.*, u.name as user_name, f.flight_number 
                FROM bookings b
                JOIN users u ON b.user_id = u.id
                JOIN flights f ON b.flight_id = f.id
                ORDER BY b.booking_date DESC LIMIT 5
            ''')
            bookings = cursor.fetchall()
            
            return render_template('admin.html', 
                                 flight_count=flight_count,
                                 user_count=user_count,
                                 booking_count=booking_count,
                                 flights=flights,
                                 bookings=bookings,
                                 admin_name=session['admin_name'])
    except Exception as e:
        flash(f'Database error: {str(e)}', 'danger')
        return redirect(url_for('admin_login'))
    finally:
        conn.close()

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
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # Explicitly select all needed columns
            cursor.execute("""
                SELECT 
                    id, flight_number, airline, departure_city,
                    departure_airport_code, arrival_city, arrival_airport_code,
                    departure_time, arrival_time, price, total_seats,
                    available_seats, status
                FROM flights 
                WHERE id = %s
            """, (flight_id,))
            flight = cursor.fetchone()
            
            if not flight:
                flash('Flight not found', 'danger')
                return redirect(url_for('admin_flights'))
                
            app.logger.debug(f"Flight data: {flight}")  # Debug output
            
            if request.method == 'POST':
                # Process form data
                flight_data = {
                    'flight_number': request.form['flight_number'],
                    # ... other fields ...
                    'status': request.form.get('status', 'Scheduled'),
                    'flight_id': flight_id
                }
                
                # Update query
                cursor.execute("""
                    UPDATE flights SET
                        flight_number = %(flight_number)s,
                        # ... other fields ...
                        status = %(status)s
                    WHERE id = %(flight_id)s
                """, flight_data)
                conn.commit()
                
                flash('Flight updated!', 'success')
                return redirect(url_for('admin_flights'))
                
        return render_template('admin.html', flight_to_edit=flight)
        
    except Exception as e:
        app.logger.error(f"Edit flight error: {str(e)}", exc_info=True)
        flash('Error updating flight', 'danger')
        if 'conn' in locals():
            conn.rollback()
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

# Add this to your existing app.py before if __name__ == '__main__':
app.start_time = time.time()

if __name__ == '__main__':
    app.run(debug=True)