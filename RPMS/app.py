from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import pyodbc
from functools import wraps
import sys

app = Flask(__name__)
app.secret_key = '123'

# Database connection
conn = pyodbc.connect('DRIVER={SQL Server};SERVER=DESKTOP-QI6H2EA;DATABASE=ResearchPublicationsManagement;Trusted_Connection=yes;')
cursor = conn.cursor()

def force_post(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.method != 'POST':
            # If the request is not POST, redirect with POST method
            return redirect(url_for(request.endpoint), code=307)
        return f(*args, **kwargs)
    return decorated_function

@app.route('/register', methods=['GET'])
def register_page():
    return render_template('Register.html')

@app.route('/register', methods=['POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user_type = request.form['user-type']  # Get the user type from the form
        
        # Insert the new user into the LoginCredentials table
        cursor.execute('INSERT INTO LoginCredentials (username, password, usertype) VALUES (?, ?, ?)', (username, password, user_type))
        conn.commit()
        
        # Redirect the user to the login page after successful registration
        return redirect('/')

@app.route('/dashboard')
def dashboard():
    cursor.execute('SELECT title, jcr_if, type, status, authors, publisher FROM publications')
    publications = []
    for row in cursor.fetchall():
        publication = {
            'title': row.title,
            'jcr_if': row.jcr_if,
            'type': row.type,
            'status': row.status,
            'authors': row.authors,
            'publisher': row.publisher
        }
        publications.append(publication)
    
    # Check if user is admin
    usertype = session.get('usertype')
    return render_template('Dashboard.html', publications=publications, usertype=usertype)


@app.route('/')
def login_page():
    return render_template('Login.html')

@app.route('/login', methods=['POST'])
def login():
    # Handle form submission for POST requests
    username = request.form['username']
    password = request.form['password']
    
    # Authenticate the user
    cursor.execute('SELECT * FROM LoginCredentials WHERE username = ? AND password = ?', (username, password))
    row = cursor.fetchone()
    
    if row:
        session['usertype'] = row.usertype
        session['username'] = username
        # Redirect to dashboard page
        return redirect('/dashboard')
    else:
        # Redirect back to login page if login failed
        return redirect('/')
    
@app.route('/profile')
def profile():
    # Retrieve username from session
    username = session.get('username')
    if not username:
        # Redirect to login page if username is not in session
        return redirect('/')
    
    # Fetch user information from the database based on the provided username
    cursor.execute('SELECT usertype FROM LoginCredentials WHERE username = ?', (username,))
    row = cursor.fetchone()
    if row:
        usertype = row.usertype
    else:
        # Handle the case where user information is not found
        return "User information not found"

    # Check if user is an admin
    if usertype == 'admin':
        # Redirect to AdminProfile page for admins
        return redirect('/admin_profile')
    elif usertype == 'reviewer':
        # Fetch publications where the user is one of the authors
        cursor.execute('SELECT title, jcr_if, type, status, authors, publisher FROM publications WHERE authors LIKE ?', ('%' + username + '%',))
        publications = [{'title': row.title, 'jcr_if': row.jcr_if, 'type': row.type, 'status': row.status, 'authors': row.authors, 'publisher': row.publisher} for row in cursor.fetchall()]

        # Render the profile page with user information and list of publications
        return render_template('Profile.html', username=username, usertype=usertype, publications=publications)
    else:
        # Redirect or show error message for non-admin and non-reviewer users
        return redirect('/dashboard')  # Redirect to dashboard or handle differently based on your application's logic
    
@app.route('/admin_profile')
def admin_profile():
    # Retrieve username from session
    username = session.get('username')
    if not username:
        # Redirect to login page if username is not in session
        return redirect('/')
    
    # Fetch user information from the database based on the provided username
    cursor.execute('SELECT usertype FROM LoginCredentials WHERE username = ?', (username,))
    row = cursor.fetchone()
    if row:
        usertype = row.usertype
    else:
        # Handle the case where user information is not found
        return "User information not found"
    
    # Check if user is an admin
    if usertype == 'admin':
        # Fetch username and usertype for the admin
        admin_info = {'username': username, 'usertype': usertype}
        
        # Render the AdminProfile page with admin information
        return render_template('AdminProfile.html', admin_info=admin_info)
    else:
        # Redirect or show error message for non-admin users
        return redirect('/dashboard')  # Redirect to dashboard or handle differently based on your application's logic

@app.route('/edit_users')
def edit_users():
    # Fetch all users from the database
    cursor.execute('SELECT username, usertype FROM LoginCredentials')
    users = [{'username': row.username, 'usertype': row.usertype} for row in cursor.fetchall()]

    # Render the EditUsers page with the list of users
    return render_template('EditUsers.html', users=users)

@app.route('/submit_edit_user', methods=['POST'])
def submit_edit_user():
    try:
        # Retrieve form data from the request
        username = request.form['username']  # Retrieve the original username from the form data
        new_username = request.form['new_username']
        new_usertype = request.form['new_usertype']
        
        # Update the user's information in the database
        cursor.execute('UPDATE LoginCredentials SET username=?, usertype=? WHERE username=?', (new_username, new_usertype, username))
        conn.commit()
        
        # Redirect the user back to the edit users page after submission
        return redirect('/edit_users')
    except Exception as e:
        # Handle any exceptions and display an error message
        error_message = "An error occurred while updating the user: " + str(e)
        return error_message, 500
        
@app.route('/edit_publication', methods=['GET', 'POST'])
def edit_publication():
    if request.method == 'GET':
        # Fetch publication details based on title from request args
        title = request.args.get('title')
        # Check if user is admin or included as an author
        usertype = session.get('usertype')
        username = session.get('username')
        if usertype == 'admin':
            # Fetch publication details from the database based on title
            cursor.execute('SELECT title, jcr_if, type, status, authors, publisher FROM publications WHERE title = ?', (title,))
            publication = cursor.fetchone()
            if publication:
                # Pass the publication details to the template
                return render_template('EditPublication.html', publication=publication)
            else:
                # Handle the case where publication is not found
                return "Publication not found."
        else:
            # Check if the current user is included as an author
            cursor.execute('SELECT * FROM publications WHERE title = ? AND authors LIKE ?', (title, '%' + username + '%'))
            publication = cursor.fetchone()
            if publication:
                # Fetch publication details from the database based on title
                cursor.execute('SELECT title, jcr_if, type, status, authors, publisher FROM publications WHERE title = ?', (title,))
                publication = cursor.fetchone()
                if publication:
                    # Pass the publication details to the template
                    return render_template('EditPublication.html', publication=publication)
                else:
                    # Handle the case where publication is not found
                    return "Publication not found."
            else:
                # Show error message or redirect to dashboard
                return "You don't have permission to edit this publication."
    elif request.method == 'POST':
        # Update publication in the database (admin or author only)
        # Redirect to dashboard
        return redirect('/dashboard')

# Route for handling the submission of edited publication details
@app.route('/submit_edit_publication', methods=['POST'])
def submit_edit_publication():
    try:
        # Retrieve edited publication details from the form submission
        title = request.form['title']
        jcr_if = request.form['jcr_if']
        type = request.form['type']
        status = request.form['status']
        authors = request.form['authors']
        publisher = request.form['publisher']
        
        # Retrieve the old title from the form data
        old_title = request.form['old_title']
        
        # Update the corresponding publication record in the database with the edited details
        cursor.execute('UPDATE publications SET title=?, jcr_if=?, type=?, status=?, authors=?, publisher=? WHERE title=?', (title, jcr_if, type, status, authors, publisher, old_title))
        conn.commit()
        
        # Redirect the user back to the dashboard page after submission
        return redirect('/dashboard')
    except Exception as e:
        # Handle any exceptions and display an error message
        error_message = "An error occurred while updating the publication: " + str(e)
        return error_message, 500
    
@app.route('/add_publication', methods=['GET'])
def add_publication_form():
    return render_template('AddPublication.html')

@app.route('/submit_add_publication', methods=['POST'])
def submit_add_publication():
    try:
        # Retrieve publication details from the form submission
        title = request.form['title']
        jcr_if = request.form['jcr_if']
        type = request.form['type']
        status = request.form['status']
        authors = request.form['authors']
        publisher = request.form['publisher']
        
        # Insert the new publication into the database
        cursor.execute('INSERT INTO publications (title, jcr_if, type, status, authors, publisher) VALUES (?, ?, ?, ?, ?, ?)', (title, jcr_if, type, status, authors, publisher))
        conn.commit()
        
        # Redirect the user back to the dashboard page after adding the publication
        return redirect('/dashboard')
    except Exception as e:
        # Handle any exceptions and display an error message
        error_message = "An error occurred while adding the publication: " + str(e)
        return error_message, 500
    
@app.route('/delete_publication', methods=['POST'])
def delete_publication():
    title = request.form['title']
    cursor.execute('SELECT * FROM publications WHERE title = ?', (title,))
    publication = cursor.fetchone()
    
    if publication:  # Check if publication exists
        usertype = session.get('usertype')
        if usertype == 'admin':
            cursor.execute('DELETE FROM publications WHERE title = ?', (title,))
            conn.commit()  # Commit the transaction
            return 'Publication deleted successfully', 200
        else:
            return "You don't have permission to delete publications."
    else:
        return "Publication not found."

@app.route('/search_publications')
def search_publications():
    search_term = request.args.get('search_term')
    search_parameter = request.args.get('search_parameter')

    # Fetch publications from the database based on search term and parameter
    query = f"SELECT title, jcr_if, type, status, authors, publisher FROM publications WHERE {search_parameter} LIKE '%{search_term}%'"
    cursor.execute(query)
    publications = []
    for row in cursor.fetchall():
        publication = {
            'title': row.title,
            'jcr_if': row.jcr_if,
            'type': row.type,
            'status': row.status,
            'authors': row.authors,
            'publisher': row.publisher
        }
        publications.append(publication)
    
    return jsonify(publications)

@app.route('/submit_edit_request', methods=['POST'])
def submit_edit_request():
    try:
        # Retrieve form data from the request
        title = request.form['title']
        jcr_if = request.form['jcr_if']
        type = request.form['type']
        status = request.form['status']
        authors = request.form['authors']
        publisher = request.form['publisher']
        
        # Print form data for debugging
        print("Form Data:")
        print("Title:", title)
        print("JCR IF:", jcr_if)
        print("Type:", type)
        print("Status:", status)
        print("Authors:", authors)
        print("Publisher:", publisher)
        
        # Insert the edit request into the database
        cursor.execute('INSERT INTO EditRequests (title, jcr_if, type, status, authors, publisher) VALUES (?, ?, ?, ?, ?, ?)', (title, jcr_if, type, status, authors, publisher))
        conn.commit()
        
        # Redirect the user back to the dashboard page after submission
        return redirect('/dashboard')
    except Exception as e:
        # Handle any exceptions and display an error message
        error_message = "An error occurred while submitting the edit request: " + str(e)
        return error_message, 500
    
@app.route('/pending_approvals')
def pending_approvals():
    # Fetch pending edit requests from the database
    cursor.execute('SELECT title, jcr_if, type, status, authors, publisher FROM EditRequests')
    edit_requests = [{'title': row.title, 'jcr_if': row.jcr_if, 'type': row.type, 'status': row.status, 'authors': row.authors, 'publisher': row.publisher} for row in cursor.fetchall()]
    return render_template('PendingApprovals.html', edit_requests=edit_requests)

# Route to handle approval of edit requests
@app.route('/approve_request', methods=['POST'])
def approve_request():
    try:
        # Retrieve request data
        title = request.form['title']
        jcr_if = request.form['jcr_if']
        type = request.form['type']
        status = request.form['status']
        authors = request.form['authors']
        publisher = request.form['publisher']
        
        # Print request data for debugging
        print("Request Data:")
        print("Title:", title)
        print("JCR IF:", jcr_if)
        print("Type:", type)
        print("Status:", status)
        print("Authors:", authors)
        print("Publisher:", publisher)
        
        # Fetch the request details from the database based on the provided title
        cursor.execute('SELECT * FROM EditRequests WHERE title=?', (title,))
        request_data = cursor.fetchone()
        
        if request_data:
            # Fetch the existing publication from the database based on the title
            cursor.execute('SELECT * FROM publications WHERE title = ?', (title,))
            existing_publication = cursor.fetchone()
            
            if existing_publication:
                # Update the existing publication with the edited values
                cursor.execute('UPDATE publications SET jcr_if=?, type=?, status=?, authors=?, publisher=? WHERE title=?',
                               (jcr_if, type, status, authors, publisher, title))
                conn.commit()
                
                # Delete the request from the EditRequests table
                cursor.execute('DELETE FROM EditRequests WHERE title=?', (title,))
                conn.commit()
                
                return 'Request approved successfully', 200
            else:
                return 'Existing publication not found', 404
        else:
            return 'Request not found', 404
    except Exception as e:
        error_message = "An error occurred while approving the request: " + str(e)
        return error_message, 500

@app.route('/not_approved', methods=['POST'])
def not_approved():
    try:
        # Retrieve title from the request
        title = request.form['title']
        
        # Delete the request from the EditRequests table
        cursor.execute('DELETE FROM EditRequests WHERE title=?', (title,))
        conn.commit()
        
        return 'Request marked as Not Approved successfully', 200
    except Exception as e:
        error_message = "An error occurred while processing the request: " + str(e)
        return error_message, 500

if __name__ == '__main__':
    app.run(debug=True)