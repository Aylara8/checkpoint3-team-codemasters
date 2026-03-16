from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_login import UserMixin

db = SQLAlchemy()

# --- ASSOCIATION TABLE ---
favorites = db.Table('favorites',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('resource_id', db.Integer, db.ForeignKey('resource.id'), primary_key=True),
    extend_existing=True
)

# --- USER MODEL ---
class User(db.Model, UserMixin):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='user')
    
    # Relationships
    profile = db.relationship('Profile', backref='owner', uselist=False, cascade="all, delete-orphan")
    resources = db.relationship('Resource', backref='uploader', lazy=True)
    comments = db.relationship('Comment', backref='author', lazy=True)
    liked_resources = db.relationship('Resource', secondary=favorites, backref='fans')
    community_messages = db.relationship('CommunityMessage', backref='sender', lazy=True)

# --- PROFILE MODEL ---
class Profile(db.Model):
    __tablename__ = 'profile'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    job_title = db.Column(db.String(100))
    hobby = db.Column(db.String(100))
    contacts = db.Column(db.String(100))

# --- RESOURCE MODEL (Merged & Fixed) ---
class Resource(db.Model):
    __tablename__ = 'resource'
    __table_args__ = {'extend_existing': True} 
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    filename = db.Column(db.String(500), nullable=False) # Stores Supabase URL
    cover_image = db.Column(db.String(500))
    category = db.Column(db.String(50))
    is_private = db.Column(db.Boolean, default=False) # Privacy flag added here
    
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Relationships
    # Using a unique backref name to avoid collision with other models
    comments = db.relationship('Comment', backref='parent_resource', lazy=True, cascade="all, delete-orphan")

# --- COMMENT MODEL ---
class Comment(db.Model):
    __tablename__ = 'comment'
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(500), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    resource_id = db.Column(db.Integer, db.ForeignKey('resource.id'), nullable=False)

# --- COMMUNITY MESSAGE MODEL ---
class CommunityMessage(db.Model):
    __tablename__ = 'community_message'
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# --- QUOTE MODEL ---
class Quote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    author = db.Column(db.String(100))
    # We use a timestamp so we can show the "Quote of the Day"
    date_saved = db.Column(db.DateTime, default=datetime.utcnow)