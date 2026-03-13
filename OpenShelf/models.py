from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_login import UserMixin

db = SQLAlchemy()

# Middle table for favorites
favorites = db.Table('favorites',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('resource_id', db.Integer, db.ForeignKey('resource.id'), primary_key=True)
)

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='user')
    
    # --- THE MISSING LINK ---
    # uselist=False makes this a 1-to-1 relationship instead of 1-to-many
    profile = db.relationship('Profile', backref='owner', uselist=False, cascade="all, delete-orphan")
    
    resources = db.relationship('Resource', backref='uploader', lazy=True)
    comments = db.relationship('Comment', backref='author', lazy=True)
    liked_resources = db.relationship('Resource', secondary=favorites, backref='fans')

class Profile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    job_title = db.Column(db.String(100))
    hobby = db.Column(db.String(100))
    contacts = db.Column(db.String(100))

class Resource(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    filename = db.Column(db.String(100), nullable=False)
    cover_image = db.Column(db.String(255))
    category = db.Column(db.String(50))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    comments = db.relationship('Comment', backref='resource', lazy=True, cascade="all, delete-orphan")

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(500), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    resource_id = db.Column(db.Integer, db.ForeignKey('resource.id'), nullable=False)

class Quote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    author = db.Column(db.String(100)) # Fixed the syntax error here