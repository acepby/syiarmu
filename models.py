from datetime import datetime, timezone
from extensions import db

class Organization(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    instagram_link = db.Column(db.String(300))
    website_link = db.Column(db.String(300))
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    last_scraped_at = db.Column(db.DateTime, nullable=True) 
    posts = db.relationship('Post', backref='organization', lazy=True)
    logs = db.relationship('ActivityLog', backref='organization', lazy=True)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)
    source = db.Column(db.String(50), nullable=False) # Sebaiknya not null
    title = db.Column(db.String(500))
    # TAMBAHKAN unique=True DI SINI 👇
    url = db.Column(db.String(500), unique=True, nullable=False) 
    fetched_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

class ActivityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)
    source = db.Column(db.String(50))
    post_count = db.Column(db.Integer, default=0)
    scraped_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    status_msg = db.Column(db.String(200))