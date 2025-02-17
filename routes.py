import pandas as pd
from flask import flash, redirect, render_template, url_for, request
from flask_login import login_required, login_user, logout_user
from forms import LoginForm
from models import CTEMVA, MVA, DualCreditMVA, InternshipMVA, MVAStatus, School, Student, StudentMVA, User, db
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
        csv_path = 'data/mva.csv'
        try:
            df = pd.read_csv(csv_path)
            total_rows = len(df)
            print(f"Starting import of {total_rows} rows from {csv_path}.")
            
            success_count = 0
            error_count = 0

            for index, row in df.iterrows():
                try:
                    # Print progress every 100 rows
                    if index % 100 == 0:
                        print(f"Processing row {index + 1} of {total_rows}...")
                        print(f"Successes: {success_count}, Errors: {error_count}")

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
                        db.session.commit()
                    
                    # Process CTE courses and credits
                    cte_courses_2023 = {}
                    cte_courses_2024 = {}
                    
                    # Get 2023 courses and credits
                    for i in range(1, 5):
                        course = row.get(f'coursename{i}')
                        if pd.notna(course) and course != '0':
                            cte_courses_2023[course] = 0.5
                    
                    # Get 2024 courses and credits
                    for i in range(1, 5):
                        course = row.get(f'coursename{i}')
                        if pd.notna(course) and course != '0':
                            cte_courses_2024[course] = 0.5
                    
                    # Calculate total credits
                    total_credits = float(row.get('total credits CTE 23&24', 0))
                    
                    # Determine MVA status and action items
                    status = MVAStatus.NOT_STARTED.value
                    action_items = []
                    
                    if pd.notna(row['Action']):
                        action_items.append(row['Action'])
                    if pd.notna(row['Action 2']):
                        action_items.append(row['Action 2'])
                    
                    if "working on CTE" in str(row['MVA progress']):
                        status = MVAStatus.IN_PROGRESS.value
                    elif "completed" in str(row['MVA progress']):
                        status = MVAStatus.COMPLETED.value
                    
                    # Create or update MVA
                    mva = MVA.query.filter_by(student_id=student.id, mva_type='CTE').first()
                    if not mva:
                        mva = MVA(
                            student_id=student.id,
                            mva_type='CTE',
                            description=row['MVA progress'],
                            hours_earned=total_credits,
                            courses_2023=cte_courses_2023,
                            courses_2024=cte_courses_2024,
                            action_items=action_items,
                            staff_notes=row.get('Staff notes', ''),
                            status=status
                        )
                        db.session.add(mva)
                    else:
                        mva.description = row['MVA progress']
                        mva.hours_earned = total_credits
                        mva.courses_2023 = cte_courses_2023
                        mva.courses_2024 = cte_courses_2024
                        mva.action_items = action_items
                        mva.staff_notes = row.get('Staff notes', '')
                        mva.status = status
                    
                    db.session.commit()
                    success_count += 1
                    
                except Exception as row_error:
                    error_count += 1
                    print(f"Error processing row {index + 1}: {str(row_error)}")
                    db.session.rollback()
                    continue

            print(f"Import completed. Processed {total_rows} rows.")
            print(f"Successes: {success_count}, Errors: {error_count}")
            flash(f'MVA data imported successfully! ({success_count} successes, {error_count} errors)', 'success')
            
        except Exception as e:
            print(f"Fatal error during import: {str(e)}")
            flash(f'An error occurred while importing MVA data: {str(e)}', 'danger')
        
        return redirect(url_for('admin'))
    
    @app.route('/view_mva_data')
    def view_mva_data():
        """Displays the imported MVA data with search and filter options."""
        # Get search and filter parameters from the request
        full_name = request.args.get('full_name', '')
        school_name = request.args.get('school_name', '')
        mva_status = request.args.get('mva_status', '')  # Get the MVA status filter
        sort_by = request.args.get('sort_by', 'state_id')  # Default sort by State ID
        sort_order = request.args.get('sort_order', 'asc')  # Default sort order
        results_per_page = request.args.get('results_per_page', 10, type=int)  # Default results per page

        # Build the query
        query = MVA.query.join(Student).join(School).options(
            db.joinedload(MVA.student).joinedload(Student.mvas)
        )

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

        # Filter by MVA status
        if mva_status == 'completed':
            query = query.filter(MVA.description.ilike('%completed%'))
        elif mva_status == 'in_progress':
            query = query.filter(MVA.description.ilike('%working on%'))
        elif mva_status == 'not_started':
            query = query.filter(MVA.description.ilike('%no known%'))

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
        mva_records = query.paginate(page=page, per_page=results_per_page, error_out=False)

        # Calculate start and end pages for pagination
        start_page = max(1, mva_records.page - 2)
        end_page = min(mva_records.pages, mva_records.page + 2)

        # Process MVA data for each student
        for record in mva_records.items:
            student = record.student
            
            # Calculate total completed MVAs
            student.total_mvas_completed = sum(
                1 for mva in student.mvas 
                if 'completed' in (mva.description or '').lower()
            )
            
            # Calculate MVAs in progress
            student.mvas_in_progress = sum(
                1 for mva in student.mvas 
                if 'working on' in (mva.description or '').lower()
            )

        return render_template(
            'view_mva_data.html',
            mva_records=mva_records,
            start_page=start_page,
            end_page=end_page,
            schools=schools,
            sort_by=sort_by,
            sort_order=sort_order
        )

    @app.route('/student/<int:student_id>')
    def student_detail(student_id: int):
        """Display detailed MVA information for a specific student.
        
        Args:
            student_id: The unique identifier for the student
            
        Returns:
            Rendered template with student's detailed MVA information
        """
        # Get student with all related data
        student = Student.query.options(
            db.joinedload(Student.school),
            db.joinedload(Student.mvas)
        ).get_or_404(student_id)
        
        # Create StudentMVA instance for comprehensive tracking
        student_mva = StudentMVA(
            student_id=student.state_id,
            grad_year=student.grade_year
        )
        
        # Process CTE MVAs
        cte_courses = {}
        cte_status = MVAStatus.NOT_STARTED
        for mva in student.mvas:
            if mva.mva_type == 'CTE':
                if mva.hours_earned:
                    cte_courses[mva.description] = float(mva.hours_earned)
                if 'working on' in (mva.description or '').lower():
                    cte_status = MVAStatus.IN_PROGRESS
                elif 'completed' in (mva.description or '').lower():
                    cte_status = MVAStatus.COMPLETED
        
        student_mva.cte = CTEMVA(
            cte_courses=cte_courses,
            total_credits=sum(cte_courses.values()),
            status=cte_status
        )
        
        # Process Dual Credit MVAs
        dual_credit_courses = []
        college_credits = 0
        dc_status = MVAStatus.NOT_STARTED
        for mva in student.mvas:
            if mva.mva_type == 'College Credits':
                if mva.description:
                    dual_credit_courses.append(mva.description)
                if mva.hours_earned:
                    college_credits += float(mva.hours_earned)
                if 'working on' in (mva.description or '').lower():
                    dc_status = MVAStatus.IN_PROGRESS
                elif 'completed' in (mva.description or '').lower():
                    dc_status = MVAStatus.COMPLETED
        
        student_mva.dual_credit = DualCreditMVA(
            enrolled_eca='Early College Academy' in ' '.join(dual_credit_courses),
            dual_credit_courses=dual_credit_courses,
            college_credits=college_credits,
            status=dc_status
        )
        
        # Process Internship MVAs
        internship_status = MVAStatus.NOT_STARTED
        program_name = None
        placement_confirmed = False
        for mva in student.mvas:
            if mva.mva_type == 'Internship':
                if 'ProX' in (mva.description or ''):
                    program_name = 'ProX'
                if 'placement confirmed' in (mva.description or '').lower():
                    placement_confirmed = True
                if 'working on' in (mva.description or '').lower():
                    internship_status = MVAStatus.IN_PROGRESS
                elif 'completed' in (mva.description or '').lower():
                    internship_status = MVAStatus.COMPLETED
        
        student_mva.internship = InternshipMVA(
            program_name=program_name,
            status=internship_status,
            placement_confirmed=placement_confirmed
        )
        
        # Calculate overall MVA statistics
        mva_stats = {
            'total_completed': sum(1 for mva in student.mvas if 'completed' in (mva.description or '').lower()),
            'total_in_progress': sum(1 for mva in student.mvas if 'working on' in (mva.description or '').lower()),
            'cte_credits': student_mva.cte.total_credits,
            'dual_credits': student_mva.dual_credit.college_credits,
            'enrolled_eca': student_mva.dual_credit.enrolled_eca,
            'internship_program': student_mva.internship.program_name,
            'internship_confirmed': student_mva.internship.placement_confirmed,
            'cte_status': student_mva.cte.status,
            'dual_credit_status': student_mva.dual_credit.status,
            'internship_status': student_mva.internship.status,
            'cte_courses': student_mva.cte.cte_courses,
            'dual_credit_courses': student_mva.dual_credit.dual_credit_courses
        }
        
        return render_template(
            'student_detail.html',
            student=student,
            mva_stats=mva_stats,
            student_mva=student_mva
        )

