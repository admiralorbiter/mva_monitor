# models.py

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone
from flask_login import UserMixin
from dataclasses import dataclass
from typing import List, Optional, Dict
from enum import Enum

db = SQLAlchemy()

# User model
class User(db.Model, UserMixin):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    first_name = db.Column(db.String(64))
    last_name = db.Column(db.String(64))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

# Student model
class Student(db.Model):
    """Represents a student in the system."""
    
    __tablename__ = 'students'
    
    id = db.Column(db.Integer, primary_key=True)
    state_id = db.Column(db.String(64), nullable=False)
    school_district_id = db.Column(db.String(64), nullable=False)
    first_name = db.Column(db.String(64), nullable=False)
    last_name = db.Column(db.String(64), nullable=False)
    grade_year = db.Column(db.Integer, nullable=False)

# School model
class School(db.Model):
    """Represents a school in the system."""
    
    __tablename__ = 'schools'
    
    id = db.Column(db.Integer, primary_key=True)
    district_name = db.Column(db.String(128), nullable=False)
    school_name = db.Column(db.String(128), nullable=False)
    
    students = db.relationship('Student', backref='school', lazy=True)

# MVA model
class MVA(db.Model):
    """Represents a Most Valuable Accomplishment (MVA) for a student."""
    
    __tablename__ = 'mvas'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    mva_type = db.Column(db.String(64), nullable=False)  # e.g., 'Internship', 'Client Project', 'College Credits', 'IRC', 'Entrepreneurial Experience'
    description = db.Column(db.String(256), nullable=True)  # Optional description of the MVA
    hours_earned = db.Column(db.Integer, nullable=True)  # Number of hours earned, if applicable

    student = db.relationship('Student', backref='mvas', lazy=True)

class MVAStatus(Enum):
    """Enum for tracking MVA completion status."""
    NOT_STARTED = "no known MVA progress"
    IN_PROGRESS = "working on"
    COMPLETED = "completed"
    
@dataclass
class DualCreditMVA:
    """Tracks Early College Academy and Dual Credit progress.
    
    Attributes:
        enrolled_eca: Whether student is enrolled in Early College Academy
        dual_credit_courses: List of dual credit courses enrolled/completed
        college_credits: Total number of college credits earned
        target_credits: Credits needed for MVA completion (typically 9)
        status: Current MVA completion status
    """
    enrolled_eca: bool = False
    dual_credit_courses: List[str] = None
    college_credits: int = 0
    target_credits: int = 9
    status: MVAStatus = MVAStatus.NOT_STARTED
    
    def __post_init__(self):
        self.dual_credit_courses = self.dual_credit_courses or []
        
@dataclass        
class CTEMVA:
    """Tracks Career & Technical Education progress.
    
    Attributes:
        cte_courses: Dict mapping course names to credits earned
        total_credits: Total CTE credits earned
        target_credits: Credits needed for MVA completion
        status: Current MVA completion status
    """
    cte_courses: Dict[str, float] = None
    total_credits: float = 0
    target_credits: float = 3.0
    status: MVAStatus = MVAStatus.NOT_STARTED
    
    def __post_init__(self):
        self.cte_courses = self.cte_courses or {}

@dataclass
class InternshipMVA:
    """Tracks internship and client project progress.
    
    Attributes:
        program_name: Name of internship program (e.g. "ProX")
        start_date: Planned/actual start date
        status: Current MVA completion status
        placement_confirmed: Whether work site placement is confirmed
    """
    program_name: Optional[str] = None
    start_date: Optional[datetime] = None
    status: MVAStatus = MVAStatus.NOT_STARTED
    placement_confirmed: bool = False

@dataclass
class StudentMVA:
    """Combines all MVA tracking for a student.
    
    Attributes:
        student_id: Student's unique identifier
        grad_year: Expected graduation year
        dual_credit: Dual Credit MVA tracking
        cte: CTE MVA tracking
        internship: Internship MVA tracking
        total_mvas_completed: Count of completed MVAs
    """
    student_id: str
    grad_year: int
    dual_credit: DualCreditMVA = None
    cte: CTEMVA = None  
    internship: InternshipMVA = None
    total_mvas_completed: int = 0
    
    def __post_init__(self):
        self.dual_credit = self.dual_credit or DualCreditMVA()
        self.cte = self.cte or CTEMVA()
        self.internship = self.internship or InternshipMVA()