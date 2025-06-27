#app.py
import os
import logging
from flask import Flask, render_template, jsonify, request, redirect, url_for, flash
from flask_login import LoginManager, login_required, current_user, login_user, logout_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import tweepy
import requests
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import instaloader
from datetime import datetime, timedelta
import threading
import time
import json
from typing import Dict, List, Optional
import sqlite3
from contextlib import contextmanager
import re
from dataclasses import dataclass

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('indian_movie_monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class SocialAccount:
    """Data class for social media accounts"""
    name: str
    platform: str
    username: str
    account_type: str  # production_house, actor, director, news_portal
    language: str  # telugu, tamil, hindi, english, multi
    is_active: bool = True

class Config:
    """Application configuration"""
    
    # Flask Settings
    SECRET_KEY = os.getenv('SECRET_KEY', 'indian-movie-monitor-secret-key')
    DEBUG = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    
    # Database
    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///indian_movie_updates.db')
    
    # API Configurations
    TWITTER_BEARER_TOKEN = os.getenv('TWITTER_BEARER_TOKEN')
    TWITTER_API_KEY = os.getenv('TWITTER_API_KEY')
    TWITTER_API_SECRET = os.getenv('TWITTER_API_SECRET')
    TWITTER_ACCESS_TOKEN = os.getenv('TWITTER_ACCESS_TOKEN')
    TWITTER_ACCESS_TOKEN_SECRET = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')
    
    # Instagram Basic Display API
    INSTAGRAM_APP_ID = os.getenv('INSTAGRAM_APP_ID')
    INSTAGRAM_APP_SECRET = os.getenv('INSTAGRAM_APP_SECRET')
    INSTAGRAM_ACCESS_TOKEN = os.getenv('INSTAGRAM_ACCESS_TOKEN')
    
    # YouTube Configuration
    YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')
    
    # Telegram Configuration
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    TELEGRAM_CHANNEL_ID = os.getenv('TELEGRAM_CHANNEL_ID')
    
    # News API Configuration
    NEWS_API_KEY = os.getenv('NEWS_API_KEY')
    
    # Monitoring Intervals (minutes)
    TWITTER_INTERVAL = int(os.getenv('TWITTER_INTERVAL', '10'))
    INSTAGRAM_INTERVAL = int(os.getenv('INSTAGRAM_INTERVAL', '30'))
    YOUTUBE_INTERVAL = int(os.getenv('YOUTUBE_INTERVAL', '20'))
    NEWS_INTERVAL = int(os.getenv('NEWS_INTERVAL', '30'))
    
    # Indian movie keywords
    MOVIE_KEYWORDS = [
        'movie', 'cinema', 'film', 'trailer', 'teaser', 'poster', 'first look',
        'telugu movie', 'tamil movie', 'hindi movie', 'bollywood', 'tollywood',
        'kollywood', 'pushpa', 'rrr', 'prabhas', 'allu arjun', 'mahesh babu',
        'ntr', 'ram charan', 'chiranjeevi', 'kamal hassan', 'rajinikanth',
        'shah rukh khan', 'salman khan', 'aamir khan'
    ]
    
    # Admin credentials
    ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')

class DatabaseManager:
    """Enhanced database manager for Indian movie monitoring"""
    
    def __init__(self, db_path: str = "indian_movie_updates.db"):
        self.db_path = db_path
        self.init_database()
    
    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def init_database(self):
        """Initialize database with Indian movie specific tables"""
        with self.get_connection() as conn:
            # Movie updates table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS movie_updates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform TEXT NOT NULL,
                    account_name TEXT NOT NULL,
                    content_id TEXT NOT NULL,
                    title TEXT,
                    content TEXT,
                    url TEXT,
                    language TEXT,
                    movie_name TEXT,
                    actor_name TEXT,
                    director_name TEXT,
                    production_house TEXT,
                    update_type TEXT, -- trailer, poster, news, announcement
                    engagement_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    posted_to_telegram BOOLEAN DEFAULT FALSE,
                    UNIQUE(platform, content_id)
                )
            ''')
            
            # Social media accounts table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS social_accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    username TEXT NOT NULL,
                    account_type TEXT NOT NULL,
                    language TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    last_checked TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(platform, username)
                )
            ''')
            
            # Monitoring statistics
            conn.execute('''
                CREATE TABLE IF NOT EXISTS monitoring_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform TEXT NOT NULL,
                    account_name TEXT,
                    status TEXT NOT NULL,
                    message TEXT,
                    updates_found INTEGER DEFAULT 0,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # User table for admin
            conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    is_admin BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            self._populate_default_accounts()
    
    def _populate_default_accounts(self):
        """Populate with Telugu Film Industry accounts"""
        default_accounts = [
            # Production Houses
            SocialAccount("Geetha Arts", "twitter", "GeethaArts", "production_house", "telugu"),
            SocialAccount("Geetha Arts", "instagram", "geethaarts", "production_house", "telugu"),
            SocialAccount("Mythri Movie Makers", "twitter", "MythriOfficial", "production_house", "telugu"),
            SocialAccount("Mythri Movie Makers", "instagram", "mythrimoviemakers", "production_house", "telugu"),
            SocialAccount("People Media Factory", "twitter", "peoplemediafcy", "production_house", "telugu"),
            SocialAccount("People Media Factory", "instagram", "peoplemediafactory", "production_house", "telugu"),
            SocialAccount("Sri Venkateswara Creations", "twitter", "SVC_official", "production_house", "telugu"),
            SocialAccount("Vyjayanthi Movies", "twitter", "VyjayanthiFilms", "production_house", "telugu"),
            SocialAccount("Vyjayanthi Movies", "instagram", "vyjayanthimovies", "production_house", "telugu"),
            
            # Actors
            SocialAccount("Allu Arjun", "twitter", "alluarjun", "actor", "telugu"),
            SocialAccount("Allu Arjun", "instagram", "alluarjunonline", "actor", "telugu"),
            SocialAccount("Prabhas", "instagram", "actorprabhas", "actor", "telugu"),
            SocialAccount("Mahesh Babu", "twitter", "urstrulyMahesh", "actor", "telugu"),
            SocialAccount("Mahesh Babu", "instagram", "urstrulymahesh", "actor", "telugu"),
            SocialAccount("Jr. NTR", "twitter", "tarak9999", "actor", "telugu"),
            SocialAccount("Jr. NTR", "instagram", "jrntr", "actor", "telugu"),
            SocialAccount("Ram Charan", "twitter", "AlwaysRamCharan", "actor", "telugu"),
            SocialAccount("Ram Charan", "instagram", "alwaysramcharan", "actor", "telugu"),
            SocialAccount("Chiranjeevi", "twitter", "KChiruTweets", "actor", "telugu"),
            SocialAccount("Chiranjeevi", "instagram", "chiranjeevikonidela", "actor", "telugu"),
            SocialAccount("Rashmika Mandanna", "twitter", "iamRashmika", "actor", "multi"),
            SocialAccount("Rashmika Mandanna", "instagram", "rashmika_mandanna", "actor", "multi"),
            
            # Directors
            SocialAccount("S.S. Rajamouli", "twitter", "ssrajamouli", "director", "telugu"),
            SocialAccount("S.S. Rajamouli", "instagram", "ssrajamouli", "director", "telugu"),
            SocialAccount("Puri Jagannadh", "twitter", "purijagan", "director", "telugu"),
            SocialAccount("Puri Jagannadh", "instagram", "purijagannadh", "director", "telugu"),
            
            # News Portals
            SocialAccount("Telugu Film Nagar", "twitter", "telugufilmnagar", "news_portal", "telugu"),
            SocialAccount("Telugu Film Nagar", "instagram", "telugufilmnagar", "news_portal", "telugu"),
            SocialAccount("Andhra Box Office", "twitter", "AndhraBoxOffice", "news_portal", "telugu"),
            SocialAccount("T2BLive", "twitter", "T2BLive", "news_portal", "telugu"),
            SocialAccount("Gulte", "twitter", "gulteofficial", "news_portal", "telugu"),
            SocialAccount("123Telugu", "twitter", "123telugu", "news_portal", "telugu"),
        ]
        
        with self.get_connection() as conn:
            for account in default_accounts:
                conn.execute('''
                    INSERT OR IGNORE INTO social_accounts 
                    (name, platform, username, account_type, language) 
                    VALUES (?, ?, ?, ?, ?)
                ''', (account.name, account.platform, account.username, 
                     account.account_type, account.language))
            conn.commit()
    
    def get_active_accounts(self, platform: str = None) -> List[Dict]:
        """Get all active social media accounts"""
        with self.get_connection() as conn:
            if platform:
                accounts = conn.execute('''
                    SELECT * FROM social_accounts 
                    WHERE is_active = TRUE AND platform = ?
                    ORDER BY account_type, name
                ''', (platform,)).fetchall()
            else:
                accounts = conn.execute('''
                    SELECT * FROM social_accounts 
                    WHERE is_active = TRUE
                    ORDER BY platform, account_type, name
                ''').fetchall()
            
            return [dict(account) for account in accounts]
    
    def save_movie_update(self, platform: str, account_name: str, content_id: str, 
                         title: str, content: str, url: str, **kwargs):
        """Save movie update with enhanced metadata"""
        try:
            with self.get_connection() as conn:
                conn.execute('''
                    INSERT OR IGNORE INTO movie_updates 
                    (platform, account_name, content_id, title, content, url, 
                     language, movie_name, actor_name, director_name, production_house, 
                     update_type, engagement_count) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (platform, account_name, content_id, title, content, url,
                     kwargs.get('language', ''), kwargs.get('movie_name', ''),
                     kwargs.get('actor_name', ''), kwargs.get('director_name', ''),
                     kwargs.get('production_house', ''), kwargs.get('update_type', ''),
                     kwargs.get('engagement_count', 0)))
                conn.commit()
                return conn.lastrowid
        except Exception as e:
            logger.error(f"Error saving movie update: {e}")
            return None

class User(UserMixin):
    """User class for Flask-Login"""
    def __init__(self, id, username, is_admin=False):
        self.id = id
        self.username = username
        self.is_admin = is_admin

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Global variables
twitter_client = None
youtube_client = None
instagram_session = None
monitoring_active = False
monitoring_threads = {}
db_manager = DatabaseManager()

@login_manager.user_loader
def load_user(user_id):
    with db_manager.get_connection() as conn:
        user = conn.execute(
            'SELECT * FROM users WHERE id = ?', (user_id,)
        ).fetchone()
        if user:
            return User(user['id'], user['username'], user['is_admin'])
    return None

def initialize_apis():
    """Initialize API clients"""
    global twitter_client, youtube_client, instagram_session
    
    try:
        # Initialize Twitter API
        if Config.TWITTER_BEARER_TOKEN:
            twitter_client = tweepy.Client(
                bearer_token=Config.TWITTER_BEARER_TOKEN,
                consumer_key=Config.TWITTER_API_KEY,
                consumer_secret=Config.TWITTER_API_SECRET,
                access_token=Config.TWITTER_ACCESS_TOKEN,
                access_token_secret=Config.TWITTER_ACCESS_TOKEN_SECRET,
                wait_on_rate_limit=True
            )
            logger.info("Twitter API initialized")
        
        # Initialize YouTube API
        if Config.YOUTUBE_API_KEY:
            youtube_client = build('youtube', 'v3', developerKey=Config.YOUTUBE_API_KEY)
            logger.info("YouTube API initialized")
        
        # Initialize Instagram session
        if Config.INSTAGRAM_ACCESS_TOKEN:
            instagram_session = requests.Session()
            logger.info("Instagram API initialized")
        
        return True
        
    except Exception as e:
        logger.error(f"Error initializing APIs: {e}")
        return False

def extract_movie_info(text: str) -> Dict:
    """Extract movie information from text using regex and keywords"""
    info = {
        'movie_name': '',
        'actor_name': '',
        'director_name': '',
        'update_type': '',
        'language': ''
    }
    
    # Common Telugu/Indian movie patterns
    movie_patterns = [
        r'#(\w+)(?:Movie|Film|Cinema)',
        r'(\w+)\s+(?:trailer|teaser|poster|first look)',
        r'#(\w+)(?:2|3|Chapter)'
    ]
    
    # Actor patterns
    actor_patterns = [
        r'(?:@|#)?(alluarjun|prabhas|maheshbabu|ntr|ramcharan|chiranjeevi)',
        r'(?:Allu Arjun|Prabhas|Mahesh Babu|Jr\.? NTR|Ram Charan|Chiranjeevi)'
    ]
    
    # Update type patterns
    if any(word in text.lower() for word in ['trailer', 'official trailer']):
        info['update_type'] = 'trailer'
    elif any(word in text.lower() for word in ['teaser', 'glimpse']):
        info['update_type'] = 'teaser'
    elif any(word in text.lower() for word in ['poster', 'first look']):
        info['update_type'] = 'poster'
    elif any(word in text.lower() for word in ['release', 'announcement']):
        info['update_type'] = 'announcement'
    else:
        info['update_type'] = 'news'
    
    # Language detection
    if any(word in text.lower() for word in ['telugu', 'tollywood']):
        info['language'] = 'telugu'
    elif any(word in text.lower() for word in ['tamil', 'kollywood']):
        info['language'] = 'tamil'
    elif any(word in text.lower() for word in ['hindi', 'bollywood']):
        info['language'] = 'hindi'
    
    return info

def send_telegram_notification(message: str, photo_url: str = None) -> bool:
    """Send notification to Telegram channel"""
    if not Config.TELEGRAM_BOT_TOKEN or not Config.TELEGRAM_CHANNEL_ID:
        return False
    
    try:
        base_url = f"https://api.telegram.org/bot{Config.TELEGRAM_BOT_TOKEN}"
        
        if photo_url:
            # Send photo with caption
            url = f"{base_url}/sendPhoto"
            data = {
                'chat_id': Config.TELEGRAM_CHANNEL_ID,
                'photo': photo_url,
                'caption': message,
                'parse_mode': 'HTML'
            }
        else:
            # Send text message
            url = f"{base_url}/sendMessage"
            data = {
                'chat_id': Config.TELEGRAM_CHANNEL_ID,
                'text': message,
                'parse_mode': 'HTML'
            }
        
        response = requests.post(url, data=data, timeout=10)
        return response.status_code == 200
        
    except Exception as e:
        logger.error(f"Telegram notification failed: {e}")
        return False

def monitor_twitter():
    """Monitor Twitter accounts for movie updates"""
    global monitoring_active
    
    while monitoring_active:
        try:
            if not twitter_client:
                time.sleep(60)
                continue
            
            accounts = db_manager.get_active_accounts('twitter')
            
            for account in accounts:
                if not monitoring_active:
                    break
                
                try:
                    # Get user's recent tweets
                    user = twitter_client.get_user(username=account['username'])
                    if not user.data:
                        continue
                    
                    tweets = twitter_client.get_users_tweets(
                        user.data.id,
                        max_results=10,
                        tweet_fields=['created_at', 'public_metrics', 'attachments'],
                        exclude=['retweets', 'replies']
                    )
                    
                    if tweets.data:
                        for tweet in tweets.data:
                            # Check if tweet is recent (last 24 hours)
                            if tweet.created_at < datetime.now(tweet.created_at.tzinfo) - timedelta(hours=24):
                                continue
                            
                            # Extract movie information
                            movie_info = extract_movie_info(tweet.text)
                            
                            # Save to database
                            update_id = db_manager.save_movie_update(
                                platform="twitter",
                                account_name=account['name'],
                                content_id=tweet.id,
                                title=f"Tweet by {account['name']}",
                                content=tweet.text,
                                url=f"https://twitter.com/{account['username']}/status/{tweet.id}",
                                language=movie_info['language'] or account['language'],
                                movie_name=movie_info['movie_name'],
                                actor_name=movie_info['actor_name'],
                                update_type=movie_info['update_type'],
                                engagement_count=tweet.public_metrics['like_count'] if tweet.public_metrics else 0
                            )
                            
                            # Send to Telegram if significant
                            if update_id and (
                                movie_info['update_type'] in ['trailer', 'teaser', 'poster'] or
                                (tweet.public_metrics and tweet.public_metrics['like_count'] > 500)
                            ):
                                notification = f"🎬 <b>{account['name']}</b>\n\n{tweet.text[:300]}...\n\n🔗 <a href='https://twitter.com/{account['username']}/status/{tweet.id}'>View Tweet</a>"
                                send_telegram_notification(notification)
                    
                    time.sleep(5)  # Rate limiting
                    
                except Exception as e:
                    logger.error(f"Error monitoring Twitter account {account['username']}: {e}")
                    continue
            
            db_manager.log_monitoring_event("twitter", "success", f"Monitored {len(accounts)} accounts")
            time.sleep(Config.TWITTER_INTERVAL * 60)
            
        except Exception as e:
            logger.error(f"Twitter monitoring error: {e}")
            time.sleep(60)

def monitor_instagram():
    """Monitor Instagram accounts using Instagram Basic Display API"""
    global monitoring_active
    
    while monitoring_active:
        try:
            if not Config.INSTAGRAM_ACCESS_TOKEN:
                time.sleep(60)
                continue
            
            accounts = db_manager.get_active_accounts('instagram')
            
            for account in accounts:
                if not monitoring_active:
                    break
                
                try:
                    # Get user media using Instagram Basic Display API
                    url = f"https://graph.instagram.com/me/media"
                    params = {
                        'fields': 'id,caption,media_type,media_url,thumbnail_url,timestamp,permalink',
                        'access_token': Config.INSTAGRAM_ACCESS_TOKEN,
                        'limit': 10
                    }
                    
                    response = requests.get(url, params=params, timeout=10)
                    
                    if response.status_code == 200:
                        data = response.json()
                        
                        for post in data.get('data', []):
                            # Check if post is recent
                            post_time = datetime.fromisoformat(post['timestamp'].replace('Z', '+00:00'))
                            if post_time < datetime.now(post_time.tzinfo) - timedelta(hours=24):
                                continue
                            
                            caption = post.get('caption', '')
                            movie_info = extract_movie_info(caption)
                            
                            # Save to database
                            update_id = db_manager.save_movie_update(
                                platform="instagram",
                                account_name=account['name'],
                                content_id=post['id'],
                                title=f"Instagram post by {account['name']}",
                                content=caption,
                                url=post['permalink'],
                                language=movie_info['language'] or account['language'],
                                movie_name=movie_info['movie_name'],
                                update_type=movie_info['update_type']
                            )
                            
                            # Send to Telegram if significant
                            if update_id and movie_info['update_type'] in ['trailer', 'teaser', 'poster']:
                                photo_url = post.get('media_url') if post['media_type'] == 'IMAGE' else post.get('thumbnail_url')
                                notification = f"📸 <b>{account['name']}</b>\n\n{caption[:200]}...\n\n🔗 <a href='{post['permalink']}'>View Post</a>"
                                send_telegram_notification(notification, photo_url)
                    
                    time.sleep(10)  # Rate limiting
                    
                except Exception as e:
                    logger.error(f"Error monitoring Instagram account {account['username']}: {e}")
                    continue
            
            time.sleep(Config.INSTAGRAM_INTERVAL * 60)
            
        except Exception as e:
            logger.error(f"Instagram monitoring error: {e}")
            time.sleep(60)

def monitor_youtube():
    """Monitor YouTube channels for movie content"""
    global monitoring_active
    
    while monitoring_active:
        try:
            if not youtube_client:
                time.sleep(60)
                continue
            
            # Search for Indian movie content
            search_queries = [
                'telugu movie trailer 2025',
                'tamil movie trailer 2025',
                'hindi movie trailer 2025',
                'prabhas new movie',
                'allu arjun pushpa',
                'tollywood latest',
                'bollywood trailer'
            ]
            
            for query in search_queries:
                if not monitoring_active:
                    break
                
                try:
                    request = youtube_client.search().list(
                        part='snippet',
                        q=query,
                        type='video',
                        order='date',
                        maxResults=5,
                        publishedAfter=(datetime.now() - timedelta(hours=24)).isoformat() + 'Z'
                    )
                    
                    response = request.execute()
                    
                    for item in response.get('items', []):
                        video_id = item['id']['videoId']
                        title = item['snippet']['title']
                        description = item['snippet']['description']
                        channel_title = item['snippet']['channelTitle']
                        
                        movie_info = extract_movie_info(title + ' ' + description)
                        
                        # Save to database
                        update_id = db_manager.save_movie_update(
                            platform="youtube",
                            account_name=channel_title,
                            content_id=video_id,
                            title=title,
                            content=description,
                            url=f"https://www.youtube.com/watch?v={video_id}",
                            language=movie_info['language'],
                            movie_name=movie_info['movie_name'],
                            update_type=movie_info['update_type']
                        )
                        
                        # Send to Telegram for trailers/teasers
                        if update_id and movie_info['update_type'] in ['trailer', 'teaser']:
                            notification = f"🎥 <b>YouTube - {channel_title}</b>\n\n<b>{title}</b>\n\n🔗 <a href='https://www.youtube.com/watch?v={video_id}'>Watch Video</a>"
                            send_telegram_notification(notification)
                    
                    time.sleep(5)  # Rate limiting
                    
                except Exception as e:
                    logger.error(f"Error searching YouTube for '{query}': {e}")
                    continue
            
            time.sleep(Config.YOUTUBE_INTERVAL * 60)
            
        except Exception as e:
            logger.error(f"YouTube monitoring error: {e}")
            time.sleep(60)

# Routes
@app.route('/')
def index():
    """Main dashboard"""
    with db_manager.get_connection() as conn:
        # Get recent updates
        recent_updates = conn.execute('''
            SELECT * FROM movie_updates 
            ORDER BY created_at DESC 
            LIMIT 20
        ''').fetchall()
        
        # Get statistics
        stats = {
            'total_updates': conn.execute('SELECT COUNT(*) FROM movie_updates').fetchone()[0],
            'today_updates': conn.execute('''
                SELECT COUNT(*) FROM movie_updates 
                WHERE DATE(created_at) = DATE('now')
            ''').fetchone()[0],
            'active_accounts': conn.execute('''
                SELECT COUNT(*) FROM social_accounts WHERE is_active = TRUE
            ''').fetchone()[0]
        }
    
    return render_template('dashboard.html', 
                         updates=[dict(u) for u in recent_updates],
                         stats=stats,
                         monitoring_active=monitoring_active)

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Admin login"""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if username == Config.ADMIN_USERNAME and password == Config.ADMIN_PASSWORD:
            user = User(1, username, True)
            login_user(user)
            return redirect(url_for('admin'))
        else:
            flash('Invalid credentials')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/admin')
@login_required
def admin():
    """Admin panel"""
    accounts = db_manager.get_active_accounts()
    return render_template('admin.html', accounts=accounts)

@app.route('/admin/add-account', methods=['POST'])
@login_required
def add_account():
    """Add new social media account"""
    data = request.json
    
    with db_manager.get_connection() as conn:
        conn.execute('''
            INSERT OR REPLACE INTO social_accounts 
            (name, platform, username, account_type, language, is_active) 
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (data['name'], data['platform'], data['username'], 
             data['account_type'], data['language'], True))
        conn.commit()
    
    return jsonify({'status': 'success'})

@app.route('/api/start-monitoring', methods=['POST'])
@login_required
def start_monitoring():
    """Start monitoring services"""
    global monitoring_active, monitoring_threads
    
    if monitoring_active:
        return jsonify({'status': 'already_running'})
    
    monitoring_active = True
    
    # Start monitoring threads
    monitoring_threads['twitter'] = threading.Thread(target=monitor_twitter, daemon=True)
    monitoring_threads['twitter'].start()
    
    monitoring_threads['instagram'] = threading.Thread(target=monitor_instagram, daemon=True)
    monitoring_threads['instagram'].start()
    
    monitoring_threads['youtube'] = threading.Thread(target=monitor_youtube, daemon=True)
    monitoring_threads['youtube'].start()
    
    send_telegram_notification("🎬 <b>Indian Movie Monitoring Started!</b>\n\nMonitoring Telugu, Tamil, Hindi and other Indian movie updates...")
    
    return jsonify({'status': 'started'})

@app.route('/api/stop-monitoring', methods=['POST'])
@login_required
def stop_monitoring():
    """Stop monitoring services"""
    global monitoring_active
    
    monitoring_active = False
    send_telegram_notification("⏹️ <b>Movie Monitoring Stopped</b>")
    
    return jsonify({'status': 'stopped'})

@app.route('/api/updates')
def get_updates():
    """Get movie updates with filters"""
    platform = request.args.get('platform')
    language = request.args.get('language')
    update_type = request.args.get('update_type')
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    
    with db_manager.get_connection() as conn:
        query = 'SELECT * FROM movie_updates WHERE 1=1'
        params = []
        
        if platform:
            query += ' AND platform = ?'
            params.append(platform)
        
        if language:
            query += ' AND language = ?'
            params.append(language)
        
        if update_type:
            query += ' AND update_type = ?'
            params.append(update_type)
        
        query += ' ORDER BY created_at DESC LIMIT ? OFFSET ?'
        params.extend([per_page, (page - 1) * per_page])
        
        updates = conn.execute(query, params).fetchall()
        
        # Get total count
        count_query = query.replace('SELECT *', 'SELECT COUNT(*)', 1).split('ORDER BY')[0]
        total = conn.execute(count_query, params[:-2]).fetchone()[0]
    
    return jsonify({
        'updates': [dict(u) for u in updates],
        'total': total,
        'page': page,
        'per_page': per_page
    })

@app.route('/api/accounts')
@login_required
def get_accounts():
    """Get all social media accounts"""
    accounts = db_manager.get_active_accounts()
    return jsonify({'accounts': accounts})

@app.route('/api/accounts/<int:account_id>/toggle', methods=['POST'])
@login_required
def toggle_account(account_id):
    """Toggle account active status"""
    with db_manager.get_connection() as conn:
        conn.execute('''
            UPDATE social_accounts 
            SET is_active = NOT is_active 
            WHERE id = ?
        ''', (account_id,))
        conn.commit()
    
    return jsonify({'status': 'success'})

@app.route('/api/accounts/<int:account_id>', methods=['DELETE'])
@login_required
def delete_account(account_id):
    """Delete social media account"""
    with db_manager.get_connection() as conn:
        conn.execute('DELETE FROM social_accounts WHERE id = ?', (account_id,))
        conn.commit()
    
    return jsonify({'status': 'success'})

@app.route('/api/stats')
def get_stats():
    """Get monitoring statistics"""
    with db_manager.get_connection() as conn:
        stats = {
            'total_updates': conn.execute('SELECT COUNT(*) FROM movie_updates').fetchone()[0],
            'today_updates': conn.execute('''
                SELECT COUNT(*) FROM movie_updates 
                WHERE DATE(created_at) = DATE('now')
            ''').fetchone()[0],
            'week_updates': conn.execute('''
                SELECT COUNT(*) FROM movie_updates 
                WHERE created_at >= DATE('now', '-7 days')
            ''').fetchone()[0],
            'by_platform': dict(conn.execute('''
                SELECT platform, COUNT(*) 
                FROM movie_updates 
                GROUP BY platform
            ''').fetchall()),
            'by_language': dict(conn.execute('''
                SELECT language, COUNT(*) 
                FROM movie_updates 
                WHERE language != '' 
                GROUP BY language
            ''').fetchall()),
            'by_type': dict(conn.execute('''
                SELECT update_type, COUNT(*) 
                FROM movie_updates 
                WHERE update_type != '' 
                GROUP BY update_type
            ''').fetchall()),
            'active_accounts': conn.execute('''
                SELECT COUNT(*) FROM social_accounts WHERE is_active = TRUE
            ''').fetchone()[0]
        }
    
    return jsonify(stats)

@app.route('/api/search')
def search_updates():
    """Search movie updates"""
    query = request.args.get('q', '')
    if not query:
        return jsonify({'updates': []})
    
    with db_manager.get_connection() as conn:
        updates = conn.execute('''
            SELECT * FROM movie_updates 
            WHERE title LIKE ? OR content LIKE ? OR movie_name LIKE ? OR actor_name LIKE ?
            ORDER BY created_at DESC 
            LIMIT 50
        ''', (f'%{query}%', f'%{query}%', f'%{query}%', f'%{query}%')).fetchall()
    
    return jsonify({'updates': [dict(u) for u in updates]})

# Enhanced monitoring functions with better error handling and logging

def monitor_news_websites():
    """Monitor news websites for movie updates"""
    global monitoring_active
    
    news_sources = [
        'timesofindia.indiatimes.com',
        'indianexpress.com',
        'hindustantimes.com',
        'news18.com',
        'firstpost.com'
    ]
    
    while monitoring_active:
        try:
            if not Config.NEWS_API_KEY:
                time.sleep(60)
                continue
            
            for source in news_sources:
                if not monitoring_active:
                    break
                
                try:
                    url = 'https://newsapi.org/v2/everything'
                    params = {
                        'apiKey': Config.NEWS_API_KEY,
                        'domains': source,
                        'q': 'movie OR cinema OR bollywood OR tollywood OR kollywood',
                        'sortBy': 'publishedAt',
                        'from': (datetime.now() - timedelta(hours=6)).isoformat(),
                        'language': 'en'
                    }
                    
                    response = requests.get(url, params=params, timeout=10)
                    
                    if response.status_code == 200:
                        data = response.json()
                        
                        for article in data.get('articles', []):
                            title = article.get('title', '')
                            description = article.get('description', '')
                            content = title + ' ' + (description or '')
                            
                            movie_info = extract_movie_info(content)
                            
                            # Save to database
                            db_manager.save_movie_update(
                                platform="news",
                                account_name=source,
                                content_id=article.get('url', '').split('/')[-1],
                                title=title,
                                content=description or '',
                                url=article.get('url', ''),
                                language=movie_info['language'],
                                movie_name=movie_info['movie_name'],
                                update_type=movie_info['update_type']
                            )
                    
                    time.sleep(5)
                    
                except Exception as e:
                    logger.error(f"Error monitoring news source {source}: {e}")
                    continue
            
            time.sleep(Config.NEWS_INTERVAL * 60)
            
        except Exception as e:
            logger.error(f"News monitoring error: {e}")
            time.sleep(60)

def enhanced_extract_movie_info(text: str) -> Dict:
    """Enhanced movie information extraction with better patterns"""
    info = {
        'movie_name': '',
        'actor_name': '',
        'director_name': '',
        'production_house': '',
        'update_type': '',
        'language': ''
    }
    
    text_lower = text.lower()
    
    # Telugu movie patterns
    telugu_patterns = [
        r'#?(\w+)(?:movie|film)(?:\s+telugu)?',
        r'(\w+)\s+(?:trailer|teaser|poster|first look|glimpse)',
        r'#(\w+)(?:2|3|chapter|part)'
    ]
    
    # Famous Telugu actors
    telugu_actors = {
        'allu arjun': 'Allu Arjun',
        'prabhas': 'Prabhas',
        'mahesh babu': 'Mahesh Babu',
        'jr ntr': 'Jr. NTR',
        'ntr': 'Jr. NTR',
        'ram charan': 'Ram Charan',
        'chiranjeevi': 'Chiranjeevi',
        'balakrishna': 'Balakrishna',
        'vijay deverakonda': 'Vijay Deverakonda',
        'nani': 'Nani',
        'ravi teja': 'Ravi Teja',
        'nithiin': 'Nithiin',
        'sharwanand': 'Sharwanand'
    }
    
    # Famous directors
    directors = {
        'rajamouli': 'S.S. Rajamouli',
        'puri jagannadh': 'Puri Jagannadh',
        'trivikram': 'Trivikram Srinivas',
        'koratala siva': 'Koratala Siva',
        'sukumar': 'Sukumar',
        'vamshi paidipally': 'Vamshi Paidipally'
    }
    
    # Production houses
    production_houses = {
        'geetha arts': 'Geetha Arts',
        'mythri movie makers': 'Mythri Movie Makers',
        'people media factory': 'People Media Factory',
        'sri venkateswara creations': 'Sri Venkateswara Creations',
        'vyjayanthi movies': 'Vyjayanthi Movies',
        'dvv entertainments': 'DVV Entertainments'
    }
    
    # Extract actors
    for actor_key, actor_name in telugu_actors.items():
        if actor_key in text_lower:
            info['actor_name'] = actor_name
            break
    
    # Extract directors
    for director_key, director_name in directors.items():
        if director_key in text_lower:
            info['director_name'] = director_name
            break
    
    # Extract production houses
    for house_key, house_name in production_houses.items():
        if house_key in text_lower:
            info['production_house'] = house_name
            break
    
    # Extract update type
    if any(word in text_lower for word in ['trailer', 'official trailer']):
        info['update_type'] = 'trailer'
    elif any(word in text_lower for word in ['teaser', 'glimpse', 'sneak peek']):
        info['update_type'] = 'teaser'
    elif any(word in text_lower for word in ['poster', 'first look', 'character poster']):
        info['update_type'] = 'poster'
    elif any(word in text_lower for word in ['release date', 'announcement', 'official']):
        info['update_type'] = 'announcement'
    elif any(word in text_lower for word in ['box office', 'collection', 'earnings']):
        info['update_type'] = 'box_office'
    elif any(word in text_lower for word in ['review', 'rating']):
        info['update_type'] = 'review'
    else:
        info['update_type'] = 'news'
    
    # Extract language
    if any(word in text_lower for word in ['telugu', 'tollywood', 'andhra', 'telangana']):
        info['language'] = 'telugu'
    elif any(word in text_lower for word in ['tamil', 'kollywood', 'tamilnadu']):
        info['language'] = 'tamil'
    elif any(word in text_lower for word in ['hindi', 'bollywood', 'mumbai']):
        info['language'] = 'hindi'
    elif any(word in text_lower for word in ['malayalam', 'mollywood', 'kerala']):
        info['language'] = 'malayalam'
    elif any(word in text_lower for word in ['kannada', 'sandalwood', 'karnataka']):
        info['language'] = 'kannada'
    
    # Extract movie name (basic pattern matching)
    movie_patterns = [
        r'#(\w+)(?:movie|film|trailer|teaser)',
        r'(\w+)\s+(?:movie|film|trailer|teaser)',
        r'"([^"]+)"',
        r"'([^']+)'"  # Fixed the single quote pattern
    ]
    
    for pattern in movie_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            info['movie_name'] = matches[0]
            break
    
    return info

def monitor_instagram_enhanced():
    """Enhanced Instagram monitoring with Instagram Graph API"""
    global monitoring_active
    
    while monitoring_active:
        try:
            accounts = db_manager.get_active_accounts('instagram')
            
            for account in accounts:
                if not monitoring_active:
                    break
                
                try:
                    # Use Instagram Graph API for business accounts
                    if Config.INSTAGRAM_ACCESS_TOKEN:
                        url = f"https://graph.instagram.com/me/media"
                        params = {
                            'fields': 'id,caption,media_type,media_url,thumbnail_url,timestamp,permalink,like_count,comments_count',
                            'access_token': Config.INSTAGRAM_ACCESS_TOKEN,
                            'limit': 25
                        }
                        
                        response = requests.get(url, params=params, timeout=15)
                        
                        if response.status_code == 200:
                            data = response.json()
                            
                            for post in data.get('data', []):
                                # Check if post is recent (last 12 hours)
                                post_time = datetime.fromisoformat(post['timestamp'].replace('Z', '+00:00'))
                                if post_time < datetime.now(post_time.tzinfo) - timedelta(hours=12):
                                    continue
                                
                                caption = post.get('caption', '')
                                if not caption:
                                    continue
                                
                                movie_info = enhanced_extract_movie_info(caption)
                                
                                # Save to database
                                update_id = db_manager.save_movie_update(
                                    platform="instagram",
                                    account_name=account['name'],
                                    content_id=post['id'],
                                    title=f"Instagram post by {account['name']}",
                                    content=caption,
                                    url=post['permalink'],
                                    language=movie_info['language'] or account['language'],
                                    movie_name=movie_info['movie_name'],
                                    actor_name=movie_info['actor_name'],
                                    director_name=movie_info['director_name'],
                                    production_house=movie_info['production_house'],
                                    update_type=movie_info['update_type'],
                                    engagement_count=post.get('like_count', 0)
                                )
                                
                                # Send to Telegram for significant updates
                                if update_id and (
                                    movie_info['update_type'] in ['trailer', 'teaser', 'poster', 'announcement'] or
                                    post.get('like_count', 0) > 1000
                                ):
                                    photo_url = post.get('media_url') if post['media_type'] == 'IMAGE' else post.get('thumbnail_url')
                                    
                                    notification = f"📸 <b>{account['name']}</b>"
                                    if movie_info['movie_name']:
                                        notification += f" - {movie_info['movie_name']}"
                                    if movie_info['actor_name']:
                                        notification += f" ({movie_info['actor_name']})"
                                    
                                    notification += f"\n\n{caption[:250]}..."
                                    if post.get('like_count'):
                                        notification += f"\n❤️ {post['like_count']} likes"
                                    
                                    notification += f"\n\n🔗 <a href='{post['permalink']}'>View Post</a>"
                                    
                                    send_telegram_notification(notification, photo_url)
                    
                    time.sleep(10)  # Rate limiting
                    
                except Exception as e:
                    logger.error(f"Error monitoring Instagram account {account['username']}: {e}")
                    continue
            
            time.sleep(Config.INSTAGRAM_INTERVAL * 60)
            
        except Exception as e:
            logger.error(f"Instagram monitoring error: {e}")
            time.sleep(60)

def monitor_youtube_enhanced():
    """Enhanced YouTube monitoring with channel-specific searches"""
    global monitoring_active
    
    # Telugu movie channels
    telugu_channels = [
        'UCaayLD9i5x4MmIoVZxXSv_g',  # Goldmines Telugu
        'UCjvgGbPPn-FgYeguc5nxG4A',  # Aditya Movies
        'UCsKVlYTrvddO4kZJYUFtA6Q',  # Suresh Productions
        'UCM7-2cDXfBiZYXm_WfMGS_g',  # Mythri Movie Makers
    ]
    
    while monitoring_active:
        try:
            if not youtube_client:
                time.sleep(60)
                continue
            
            # Monitor specific channels
            for channel_id in telugu_channels:
                if not monitoring_active:
                    break
                
                try:
                    # Get channel uploads
                    channel_response = youtube_client.channels().list(
                        part='contentDetails',
                        id=channel_id
                    ).execute()
                    
                    if channel_response['items']:
                        uploads_playlist_id = channel_response['items'][0]['contentDetails']['relatedPlaylists']['uploads']
                        
                        # Get recent videos
                        playlist_response = youtube_client.playlistItems().list(
                            part='snippet',
                            playlistId=uploads_playlist_id,
                            maxResults=10
                        ).execute()
                        
                        for item in playlist_response['items']:
                            video_id = item['snippet']['resourceId']['videoId']
                            title = item['snippet']['title']
                            description = item['snippet']['description']
                            channel_title = item['snippet']['channelTitle']
                            published_at = datetime.fromisoformat(item['snippet']['publishedAt'].replace('Z', '+00:00'))
                            
                            # Check if video is recent (last 6 hours)
                            if published_at < datetime.now(published_at.tzinfo) - timedelta(hours=6):
                                continue
                            
                            movie_info = enhanced_extract_movie_info(title + ' ' + description)
                            
                            # Get video statistics
                            stats_response = youtube_client.videos().list(
                                part='statistics',
                                id=video_id
                            ).execute()
                            
                            view_count = 0
                            if stats_response['items']:
                                view_count = int(stats_response['items'][0]['statistics'].get('viewCount', 0))
                            
                            # Save to database
                            update_id = db_manager.save_movie_update(
                                platform="youtube",
                                account_name=channel_title,
                                content_id=video_id,
                                title=title,
                                content=description,
                                url=f"https://www.youtube.com/watch?v={video_id}",
                                language=movie_info['language'] or 'telugu',
                                movie_name=movie_info['movie_name'],
                                actor_name=movie_info['actor_name'],
                                director_name=movie_info['director_name'],
                                production_house=movie_info['production_house'],
                                update_type=movie_info['update_type'],
                                engagement_count=view_count
                            )
                            
                            # Send to Telegram for significant updates
                            if update_id and movie_info['update_type'] in ['trailer', 'teaser', 'poster']:
                                notification = f"🎥 <b>YouTube - {channel_title}</b>"
                                if movie_info['movie_name']:
                                    notification += f" - {movie_info['movie_name']}"
                                
                                notification += f"\n\n<b>{title}</b>"
                                if view_count > 0:
                                    notification += f"\n👀 {view_count:,} views"
                                
                                notification += f"\n\n🔗 <a href='https://www.youtube.com/watch?v={video_id}'>Watch Video</a>"
                                
                                send_telegram_notification(notification)
                    
                    time.sleep(3)  # Rate limiting
                    
                except Exception as e:
                    logger.error(f"Error monitoring YouTube channel {channel_id}: {e}")
                    continue
            
            # General search queries
            search_queries = [
                'telugu movie trailer 2025',
                'prabhas new movie 2025',
                'allu arjun pushpa 2',
                'mahesh babu new movie',
                'ram charan new movie',
                'tollywood latest trailers'
            ]
            
            for query in search_queries:
                if not monitoring_active:
                    break
                
                try:
                    request = youtube_client.search().list(
                        part='snippet',
                        q=query,
                        type='video',
                        order='date',
                        maxResults=5,
                        publishedAfter=(datetime.now() - timedelta(hours=12)).isoformat() + 'Z'
                    )
                    
                    response = request.execute()
                    
                    for item in response.get('items', []):
                        video_id = item['id']['videoId']
                        title = item['snippet']['title']
                        description = item['snippet']['description']
                        channel_title = item['snippet']['channelTitle']
                        
                        movie_info = enhanced_extract_movie_info(title + ' ' + description)
                        
                        # Save to database
                        db_manager.save_movie_update(
                            platform="youtube",
                            account_name=channel_title,
                            content_id=video_id,
                            title=title,
                            content=description,
                            url=f"https://www.youtube.com/watch?v={video_id}",
                            language=movie_info['language'],
                            movie_name=movie_info['movie_name'],
                            actor_name=movie_info['actor_name'],
                            update_type=movie_info['update_type']
                        )
                    
                    time.sleep(5)  # Rate limiting
                    
                except Exception as e:
                    logger.error(f"Error searching YouTube for '{query}': {e}")
                    continue
            
            time.sleep(Config.YOUTUBE_INTERVAL * 60)
            
        except Exception as e:
            logger.error(f"YouTube monitoring error: {e}")
            time.sleep(60)

# Update the database manager with missing method
class DatabaseManager:
    # ... (previous methods remain the same)
    
    def log_monitoring_event(self, platform: str, status: str, message: str, updates_found: int = 0):
        """Log monitoring events"""
        try:
            with self.get_connection() as conn:
                conn.execute('''
                    INSERT INTO monitoring_stats 
                    (platform, status, message, updates_found) 
                    VALUES (?, ?, ?, ?)
                ''', (platform, status, message, updates_found))
                conn.commit()
        except Exception as e:
            logger.error(f"Error logging monitoring event: {e}")

# Update the start monitoring route
@app.route('/api/start-monitoring', methods=['POST'])
@login_required
def start_monitoring_updated():
    """Start monitoring services"""
    global monitoring_active, monitoring_threads
    
    if monitoring_active:
        return jsonify({'status': 'already_running'})
    
    monitoring_active = True
    
    # Start monitoring threads
    monitoring_threads['twitter'] = threading.Thread(target=monitor_twitter, daemon=True)
    monitoring_threads['twitter'].start()
    
    monitoring_threads['instagram'] = threading.Thread(target=monitor_instagram_enhanced, daemon=True)
    monitoring_threads['instagram'].start()
    
    monitoring_threads['youtube'] = threading.Thread(target=monitor_youtube_enhanced, daemon=True)
    monitoring_threads['youtube'].start()
    
    monitoring_threads['news'] = threading.Thread(target=monitor_news_websites, daemon=True)
    monitoring_threads['news'].start()
    
    send_telegram_notification("🎬 <b>Indian Movie Monitoring Started!</b>\n\nMonitoring Telugu, Tamil, Hindi and other Indian movie updates across social media platforms...")
    
    return jsonify({'status': 'started'})

if __name__ == '__main__':
    # Initialize APIs
    initialize_apis()
    
    # Create admin user if not exists
    with db_manager.get_connection() as conn:
        conn.execute('''
            INSERT OR IGNORE INTO users (username, password_hash, is_admin) 
            VALUES (?, ?, ?)
        ''', (Config.ADMIN_USERNAME, generate_password_hash(Config.ADMIN_PASSWORD), True))
        conn.commit()
    
    logger.info("Starting Indian Movie Monitoring Application")
    app.run(host='0.0.0.0', port=5000, debug=Config.DEBUG)
    