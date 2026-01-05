from flask import Blueprint, render_template, jsonify, request, redirect, url_for, flash
from sqlalchemy import func
from datetime import datetime, timedelta, timezone
from extensions import db
from models import Organization, Post, ActivityLog
import scraper  # Import modul scraper untuk akses status dan fungsi utilitas

main = Blueprint('main', __name__)

@main.route('/')
def index():
    orgs = Organization.query.order_by(Organization.last_scraped_at.desc()).all()
    limits = scraper.limiter.get_status()
    
    # Initial Chart & Wordcloud Data
    stats_query = db.session.query(func.date(Post.fetched_at).label('date'), Post.source, func.count(Post.id)).group_by('date', Post.source).all()
    unique_dates = sorted(list(set([item.date for item in stats_query if item.date is not None])))
    web_counts = [next((item[2] for item in stats_query if item.date == d and item.source == 'Website'), 0) for d in unique_dates]
    ig_counts = [next((item[2] for item in stats_query if item.date == d and item.source == 'Instagram'), 0) for d in unique_dates]

    web_wc_labels, web_wc_data = scraper.calculate_word_freq('Website')
    ig_wc_labels, ig_wc_data = scraper.calculate_word_freq('Instagram')

    return render_template('dashboard.html', 
        orgs=orgs, status=scraper.scan_status, limits=limits,
        chart_dates=unique_dates, chart_web=web_counts, chart_ig=ig_counts,
        web_wc_labels=web_wc_labels, web_wc_data=web_wc_data,
        ig_wc_labels=ig_wc_labels, ig_wc_data=ig_wc_data
    )

@main.route('/api/status')
def api_status(): 
    return jsonify({"scan": scraper.scan_status, "limits": scraper.limiter.get_status()})

@main.route('/api/map_data')
def map_data():
    orgs = Organization.query.all()
    data = []
    recent = datetime.now(timezone.utc) - timedelta(hours=12)
    for org in orgs:
        has_new = ActivityLog.query.filter_by(org_id=org.id).filter(ActivityLog.scraped_at >= recent, ActivityLog.post_count > 0).first() is not None
        latest_web = Post.query.filter_by(org_id=org.id, source='Website').order_by(Post.id.desc()).first()
        latest_ig = Post.query.filter_by(org_id=org.id, source='Instagram').order_by(Post.id.desc()).first()
        if org.latitude and org.longitude:
            data.append({"id": org.id, "name": org.name, "lat": org.latitude, "lng": org.longitude, "has_new": has_new, "web": org.website_link, "ig": org.instagram_link, 
            'web_title': latest_web.title[:30] + '...' if latest_web else '-', 'web_url': latest_web.url if latest_web else '#',
            'ig_title': latest_ig.title[:30] + '...' if latest_ig else '-', 'ig_url': latest_ig.url if latest_ig else '#'
            })
    return jsonify(data)

@main.route('/api/chart_data')
def chart_data_api():
    stats_query = db.session.query(func.date(Post.fetched_at).label('date'), Post.source, func.count(Post.id)).group_by('date', Post.source).all()
    unique_dates = sorted(list(set([item.date for item in stats_query if item.date is not None])))
    web_counts = [next((item[2] for item in stats_query if item.date == d and item.source == 'Website'), 0) for d in unique_dates]
    ig_counts = [next((item[2] for item in stats_query if item.date == d and item.source == 'Instagram'), 0) for d in unique_dates]
    web_wc_labels, web_wc_data = scraper.calculate_word_freq('Website')
    ig_wc_labels, ig_wc_data = scraper.calculate_word_freq('Instagram')
    return jsonify({'dates': unique_dates, 'web_counts': web_counts, 'ig_counts': ig_counts, 'web_wc_labels': web_wc_labels, 'web_wc_data': web_wc_data, 'ig_wc_labels': ig_wc_labels, 'ig_wc_data': ig_wc_data})

@main.route('/api/table_data')
def table_data():
    orgs = Organization.query.order_by(Organization.last_scraped_at.desc()).all()
    data = []
    for org in orgs:
        latest_web = Post.query.filter_by(org_id=org.id, source='Website').order_by(Post.id.desc()).first()
        latest_ig = Post.query.filter_by(org_id=org.id, source='Instagram').order_by(Post.id.desc()).first()
        data.append({
            'id': org.id, 'name': org.name, 'web_link': org.website_link, 'ig_link': org.instagram_link,
            'last_scraped': org.last_scraped_at.strftime('%d-%m %H:%M') if org.last_scraped_at else 'Pending',
            'web_title': latest_web.title[:30] + '...' if latest_web else '-', 'web_url': latest_web.url if latest_web else '#',
            'ig_title': latest_ig.title[:30] + '...' if latest_ig else '-', 'ig_url': latest_ig.url if latest_ig else '#',
            'lat': org.latitude, 'lng': org.longitude
        })
    return jsonify(data)

@main.route('/api/history/<int:org_id>')
def org_history(org_id):
    posts = Post.query.filter_by(org_id=org_id).order_by(Post.fetched_at.desc()).limit(50).all()
    post_list = [{'source': p.source, 'title': p.title, 'url': p.url, 'time': p.fetched_at.strftime('%Y-%m-%d %H:%M:%S')} for p in posts]
    stats = db.session.query(func.date(Post.fetched_at).label('date'), Post.source, func.count(Post.id)).filter_by(org_id=org_id).group_by('date', Post.source).all()
    dates = sorted(list(set([s.date for s in stats if s.date])))
    web_data = [next((s[2] for s in stats if s.date == d and s.source == 'Website'), 0) for d in dates]
    ig_data = [next((s[2] for s in stats if s.date == d and s.source == 'Instagram'), 0) for d in dates]
    return jsonify({'posts': post_list, 'chart': {'dates': dates, 'web': web_data, 'ig': ig_data}})

@main.route('/add_org', methods=['POST'])
def add_org():
    name = request.form.get('name')
    web_link = request.form.get('web_link')
    ig_link = request.form.get('ig_link')
    lat = request.form.get('lat')
    lng = request.form.get('lng')
    if name:
        if Organization.query.filter_by(name=name).first(): flash('Exists!', 'danger')
        else:
            db.session.add(Organization(name=name, website_link=web_link, instagram_link=ig_link, latitude=(float(lat) if lat else None), longitude=(float(lng) if lng else None)))
            db.session.commit()
            flash('Added!', 'success')
    return redirect(url_for('main.index'))

@main.route('/edit_org', methods=['POST'])
def edit_org():
    org_id = request.form.get('id')
    name = request.form.get('name')
    web_link = request.form.get('web_link')
    ig_link = request.form.get('ig_link')
    lat = request.form.get('lat')
    lng = request.form.get('lng')
    if org_id:
        org = Organization.query.get(org_id)
        if org:
            org.name = name; org.website_link = web_link; org.instagram_link = ig_link
            if lat and lng:
                try: org.latitude = float(lat); org.longitude = float(lng)
                except: pass
            db.session.commit()
            flash('Updated!', 'success')
    return redirect(url_for('main.index'))