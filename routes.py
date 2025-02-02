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
    
    @app.route('/view_mva_data')
    def view_mva_data():
        """Displays the imported MVA data with search and filter options."""
        # Get search and filter parameters from the request
        full_name = request.args.get('full_name', '')
        school_name = request.args.get('school_name', '')
        sort_by = request.args.get('sort_by', 'state_id')  # Default sort by State ID
        sort_order = request.args.get('sort_order', 'asc')  # Default sort order

        # Build the query
        query = MVA.query.join(Student).join(School)

        if full_name:
            # Split the full name into first and last name
            names = full_name.split()
            if len(names) > 0:
                first_name = names[0]
                query = query.filter(Student.first_name.ilike(f'%{first_name}%'))
            if len(names) > 1:
                last_name = names[1]
                query = query.filter(Student.last_name.ilike(f'%{last_name}%'))

        if school_name:
            query = query.filter(School.school_name.ilike(f'%{school_name}%'))

        # Apply sorting based on the model
        if sort_by in ['state_id', 'first_name', 'last_name', 'grade_year']:
            if sort_order == 'asc':
                query = query.order_by(getattr(Student, sort_by).asc())
            else:
                query = query.order_by(getattr(Student, sort_by).desc())
        elif sort_by == 'school_name':
            if sort_order == 'asc':
                query = query.order_by(School.school_name.asc())
            else:
                query = query.order_by(School.school_name.desc())
        else:
            if sort_order == 'asc':
                query = query.order_by(getattr(MVA, sort_by).asc())
            else:
                query = query.order_by(getattr(MVA, sort_by).desc())

        # Fetch the list of schools for the dropdown
        schools = School.query.all()

        # Pagination
        page = request.args.get('page', 1, type=int)
        per_page = 10  # Number of records per page
        mva_records = query.paginate(page=page, per_page=per_page, error_out=False)

        # Calculate start and end pages for pagination
        start_page = max(1, mva_records.page - 2)
        end_page = min(mva_records.pages, mva_records.page + 2)

        return render_template('view_mva_data.html', mva_records=mva_records, start_page=start_page, end_page=end_page, schools=schools, sort_by=sort_by, sort_order=sort_order)

