from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import secrets

db = SQLAlchemy()

# Association table for many-to-many relationship between ShareableLink and Resident
shareable_residents = db.Table('shareable_residents',
    db.Column('shareable_link_id', db.Integer, db.ForeignKey('shareable_link.id'), primary_key=True),
    db.Column('resident_id', db.Integer, db.ForeignKey('resident.id'), primary_key=True)
)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(80), nullable=True)
    password_hash = db.Column(db.String(128))
    google_id = db.Column(db.String(100), unique=True, nullable=True)
    profile_picture = db.Column(db.String(200), nullable=True)
    is_google_user = db.Column(db.Boolean, default=False)
    is_premium = db.Column(db.Boolean, default=False)
    usage_count = db.Column(db.Integer, default=0)
    last_usage_reset = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    residents = db.relationship('Resident', backref='owner', lazy=True, cascade='all, delete-orphan')
    shareable_links = db.relationship('ShareableLink', backref='creator', lazy=True, cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_remaining_usage(self):
        # Reset usage count if it's a new month
        now = datetime.utcnow()
        if self.last_usage_reset.month != now.month or self.last_usage_reset.year != now.year:
            self.usage_count = 0
            self.last_usage_reset = now
            db.session.commit()
        
        if self.is_premium:
            return float('inf')  # Unlimited for premium users
        else:
            return max(0, 10 - self.usage_count)  # 10 free uses per month

    def increment_usage(self):
        self.usage_count += 1
        db.session.commit()

    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'name': self.name,
            'profile_picture': self.profile_picture,
            'is_premium': self.is_premium,
            'remaining_usage': self.get_remaining_usage(),
            'is_google_user': self.is_google_user,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Resident(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    age = db.Column(db.Integer, nullable=True)
    gender = db.Column(db.String(10), nullable=True)
    room_number = db.Column(db.String(20), nullable=True)
    admission_date = db.Column(db.Date, nullable=True)
    emergency_contact_name = db.Column(db.String(80), nullable=True)
    emergency_contact_phone = db.Column(db.String(20), nullable=True)
    medical_conditions = db.Column(db.Text, nullable=True)
    medications = db.Column(db.Text, nullable=True)
    care_notes = db.Column(db.Text, nullable=True)
    current_care_plan = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Foreign key
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Relationships
    care_plan_history = db.relationship('CarePlanHistory', backref='resident', lazy=True, cascade='all, delete-orphan')
    care_tasks = db.relationship('CareTask', backref='resident', lazy=True, cascade='all, delete-orphan')

    def to_dict(self, include_tasks=False, include_history=False):
        result = {
            'id': self.id,
            'name': self.name,
            'age': self.age,
            'gender': self.gender,
            'room_number': self.room_number,
            'admission_date': self.admission_date.isoformat() if self.admission_date else None,
            'emergency_contact_name': self.emergency_contact_name,
            'emergency_contact_phone': self.emergency_contact_phone,
            'medical_conditions': self.medical_conditions,
            'medications': self.medications,
            'care_notes': self.care_notes,
            'current_care_plan': self.current_care_plan,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'owner_id': self.owner_id
        }
        
        if include_tasks:
            result['care_tasks'] = [task.to_dict() for task in self.care_tasks]
        
        if include_history:
            result['care_plan_history'] = [history.to_dict() for history in self.care_plan_history]
        
        return result

class CarePlanHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    ai_suggestions = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    version = db.Column(db.Integer, default=1)
    
    # Foreign key
    resident_id = db.Column(db.Integer, db.ForeignKey('resident.id'), nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'content': self.content,
            'ai_suggestions': self.ai_suggestions,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'version': self.version,
            'resident_id': self.resident_id
        }

class CareTask(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    priority = db.Column(db.String(20), default='medium')  # low, medium, high, urgent
    status = db.Column(db.String(20), default='pending')  # pending, in_progress, completed, cancelled
    due_date = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    assigned_to = db.Column(db.String(80), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Foreign key
    resident_id = db.Column(db.Integer, db.ForeignKey('resident.id'), nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'priority': self.priority,
            'status': self.status,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'assigned_to': self.assigned_to,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'resident_id': self.resident_id
        }

class ShareableLink(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    share_token = db.Column(db.String(64), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    password_hash = db.Column(db.String(128), nullable=False)
    created_date = db.Column(db.DateTime, default=datetime.utcnow)
    expires_date = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    access_count = db.Column(db.Integer, default=0)
    
    # Foreign key
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Many-to-many relationship with residents
    residents = db.relationship('Resident', secondary=shareable_residents, backref='shared_links')

    def __init__(self, **kwargs):
        super(ShareableLink, self).__init__(**kwargs)
        if not self.share_token:
            self.share_token = secrets.token_urlsafe(32)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_expired(self):
        if self.expires_date:
            return datetime.utcnow() > self.expires_date
        return False

    def increment_access(self):
        self.access_count += 1
        db.session.commit()

    def to_dict(self, include_residents=False):
        result = {
            'id': self.id,
            'share_token': self.share_token,
            'title': self.title,
            'description': self.description,
            'created_date': self.created_date.isoformat() if self.created_date else None,
            'expires_date': self.expires_date.isoformat() if self.expires_date else None,
            'is_active': self.is_active,
            'is_expired': self.is_expired(),
            'access_count': self.access_count,
            'created_by': self.created_by
        }
        
        if include_residents:
            result['residents'] = [resident.to_dict() for resident in self.residents]
        
        return result 