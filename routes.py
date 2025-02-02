import pandas as pd
from flask import flash, redirect, render_template, url_for, request
from flask_login import login_required, login_user, logout_user
from forms import LoginForm
from models import MVA, MVAStatus, School, Student, User, db
from werkzeug.security import check_password_hash, generate_password_hash


def init_routes(app):
    @app.route('/')
    def index():
        return render_template('index.html')
    
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        form = LoginForm()
        if form.validate_on_submit():
            user = User.query.filter_by(username=form.username.data).first()
            if user and check_password_hash(user.password_hash, form.password.data):
                login_user(user)
                flash('Logged in successfully.', 'success')
                return redirect(url_for('index'))
            else:
                flash('Invalid username or password.', 'danger')
        return render_template('login.html', form=form)
    
    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        flash('You have been logged out.', 'info')
        return redirect(url_for('index')) 
    
    @app.route('/admin')
    @login_required
    def admin():
        return render_template('admin.html')
    
    @app.route('/import_mva_data', methods=['POST'])
    def import_mva_data():
        """Imports MVA data from a CSV file."""
        csv_path = 'data/mva.csv'  # Ensure this path is correct
        try:
            df = pd.read_csv(csv_path)  # Read the CSV file
            
            for _, row in df.iterrows():
                # Ensure School exists
                school = School.query.filter_by(school_name=row['SchoolName']).first()
                if not school:
                    school = School(school_name=row['SchoolName'], district_name="Unknown")
                    db.session.add(school)
                    db.session.commit()
                
                # Ensure Student exists
                student = Student.query.filter_by(state_id=row['state ID']).first()
                if not student:
                    student = Student(
                        state_id=row['state ID'],
                        school_district_id=row['KCPS ID'],
                        first_name=row['First name'],
                        last_name=row['Last name'],
                        grade_year=row['grad year'],
                        school_id=school.id
                    )
                    db.session.add(student)
                else:
                    student.school_district_id = row['KCPS ID']
                    student.first_name = row['First name']
                    student.last_name = row['Last name']
                    student.grade_year = row['grad year']
                    student.school_id = school.id
                
                db.session.commit()
                
                # Determine MVA status
                mva_status = MVAStatus.NOT_STARTED
                if "working on CTE" in str(row['MVA progress']):
                    mva_status = MVAStatus.IN_PROGRESS
                elif "completed" in str(row['MVA progress']):
                    mva_status = MVAStatus.COMPLETED
                
                # Create or update MVA
                mva = MVA.query.filter_by(student_id=student.id, mva_type='CTE').first()
                if not mva:
                    mva = MVA(student_id=student.id, mva_type='CTE', description=row['MVA progress'])
                    db.session.add(mva)
                else:
                    mva.description = row['MVA progress']
                
                db.session.commit()
            
            flash('MVA data imported successfully!', 'success')
        except Exception as e:
            flash(f'An error occurred while importing MVA data: {str(e)}', 'danger')
        
        return redirect(url_for('admin'))  # Redirect back to the admin page

