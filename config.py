
import os
from datetime import timedelta
from typing import Dict, Any, Optional
import logging

class Config:

    # Flask Settings
    SECRET_KEY = os.getenv('SECRET_KEY', 'movie-monitor-secret-key-please-change-in-production')
    DEBUG = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    TESTING = False
    
    # Database Configuration
    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///movie_updates.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Session Configuration
    PERMANENT_SESSION_LIFETIME = timedelta(hours=2)
    SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'false').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # API Configurations
    TWITTER_BEARER_TOKEN = os.getenv('TWITTER_BEARER_TOKEN')
    INSTAGRAM_ACCESS_TOKEN = os.getenv('INSTAGRAM_ACCESS_TOKEN')
    YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    TELEGRAM_CHANNEL_ID = os.getenv('TELEGRAM_CHANNEL_ID')
    
    # Monitoring Intervals (minutes)
    TWITTER_INTERVAL = int(os.getenv('TWITTER_INTERVAL', '15'))
    INSTAGRAM_INTERVAL = int(os.getenv('INSTAGRAM_INTERVAL', '20'))
    YOUTUBE_INTERVAL = int(os.getenv('YOUTUBE_INTERVAL', '30'))
    
    # Rate Limiting
    TWITTER_RATE_LIMIT = int(os.getenv('TWITTER_RATE_LIMIT', '300'))  # requests per 15 min
    YOUTUBE_RATE_LIMIT = int(os.getenv('YOUTUBE_RATE_LIMIT', '10000'))  # requests per day
    INSTAGRAM_RATE_LIMIT = int(os.getenv('INSTAGRAM_RATE_LIMIT', '200'))  # requests per hour
    
    # Admin Configuration
    ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')
    
    # Logging Configuration
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
    LOG_FILE = os.getenv('LOG_FILE', 'movie_monitor.log')
    LOG_MAX_SIZE = int(os.getenv('LOG_MAX_SIZE', '10485760'))  # 10MB
    LOG_BACKUP_COUNT = int(os.getenv('LOG_BACKUP_COUNT', '5'))
    
    # Application Settings
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', '16777216'))  # 16MB
    POSTS_PER_PAGE = int(os.getenv('POSTS_PER_PAGE', '20'))
    MAX_SEARCH_RESULTS = int(os.getenv('MAX_SEARCH_RESULTS', '100'))
    
    # Notification Settings
    TELEGRAM_NOTIFICATIONS = os.getenv('TELEGRAM_NOTIFICATIONS', 'true').lower() == 'true'
    EMAIL_NOTIFICATIONS = os.getenv('EMAIL_NOTIFICATIONS', 'false').lower() == 'true'
    
    # Email Configuration (if enabled)
    MAIL_SERVER = os.getenv('MAIL_SERVER')
    MAIL_PORT = int(os.getenv('MAIL_PORT', '587'))
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USERNAME = os.getenv('MAIL_USERNAME')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER')
    
    # Priority Thresholds
    HIGH_PRIORITY_THRESHOLD = int(os.getenv('HIGH_PRIORITY_THRESHOLD', '4'))
    AUTO_POST_THRESHOLD = int(os.getenv('AUTO_POST_THRESHOLD', '5'))
    
    # Content Filtering
    MIN_ENGAGEMENT_THRESHOLD = int(os.getenv('MIN_ENGAGEMENT_THRESHOLD', '10'))
    CONTENT_MIN_LENGTH = int(os.getenv('CONTENT_MIN_LENGTH', '20'))
    CONTENT_MAX_LENGTH = int(os.getenv('CONTENT_MAX_LENGTH', '2000'))
    
    # Cache Settings
    CACHE_TYPE = os.getenv('CACHE_TYPE', 'simple')
    CACHE_DEFAULT_TIMEOUT = int(os.getenv('CACHE_DEFAULT_TIMEOUT', '300'))
    
    # Security Settings
    WTF_CSRF_ENABLED = os.getenv('WTF_CSRF_ENABLED', 'true').lower() == 'true'
    WTF_CSRF_TIME_LIMIT = int(os.getenv('WTF_CSRF_TIME_LIMIT', '3600'))
    
    @classmethod
    def validate_config(cls) -> Dict[str, Any]:
        """Validate configuration and return status"""
        validation_results = {
            'valid': True,
            'warnings': [],
            'errors': [],
            'api_status': {}
        }
        
        # Check API credentials
        api_configs = {
            'twitter': cls.TWITTER_BEARER_TOKEN,
            'instagram': cls.INSTAGRAM_ACCESS_TOKEN,
            'youtube': cls.YOUTUBE_API_KEY,
            'telegram': cls.TELEGRAM_BOT_TOKEN and cls.TELEGRAM_CHANNEL_ID
        }
        
        for platform, config in api_configs.items():
            validation_results['api_status'][platform] = bool(config)
            if not config:
                validation_results['warnings'].append(f"{platform.title()} API not configured")
        
        # Check intervals
        intervals = {
            'twitter': cls.TWITTER_INTERVAL,
            'instagram': cls.INSTAGRAM_INTERVAL,
            'youtube': cls.YOUTUBE_INTERVAL
        }
        
        for platform, interval in intervals.items():
            if interval < 5:
                validation_results['errors'].append(f"{platform.title()} interval too low (minimum 5 minutes)")
                validation_results['valid'] = False
            elif interval > 120:
                validation_results['warnings'].append(f"{platform.title()} interval very high ({interval} minutes)")
        
        # Check admin credentials
        if cls.ADMIN_PASSWORD == 'admin123':
            validation_results['warnings'].append("Using default admin password - please change for security")
        
        # Check secret key
        if cls.SECRET_KEY == 'movie-monitor-secret-key-please-change-in-production':
            validation_results['errors'].append("Using default secret key - must change for production")
            validation_results['valid'] = False
        
        return validation_results
    
    @classmethod
    def get_monitoring_config(cls) -> Dict[str, Any]:
        """Get monitoring-specific configuration"""
        return {
            'intervals': {
                'twitter': cls.TWITTER_INTERVAL,
                'instagram': cls.INSTAGRAM_INTERVAL,
                'youtube': cls.YOUTUBE_INTERVAL
            },
            'rate_limits': {
                'twitter': cls.TWITTER_RATE_LIMIT,
                'instagram': cls.INSTAGRAM_RATE_LIMIT,
                'youtube': cls.YOUTUBE_RATE_LIMIT
            },
            'thresholds': {
                'high_priority': cls.HIGH_PRIORITY_THRESHOLD,
                'auto_post': cls.AUTO_POST_THRESHOLD,
                'min_engagement': cls.MIN_ENGAGEMENT_THRESHOLD
            },
            'content_limits': {
                'min_length': cls.CONTENT_MIN_LENGTH,
                'max_length': cls.CONTENT_MAX_LENGTH
            }
        }
    
    @classmethod
    def get_api_config(cls) -> Dict[str, Any]:
        """Get API configuration"""
        return {
            'twitter': {
                'bearer_token': cls.TWITTER_BEARER_TOKEN,
                'rate_limit': cls.TWITTER_RATE_LIMIT,
                'enabled': bool(cls.TWITTER_BEARER_TOKEN)
            },
            'instagram': {
                'access_token': cls.INSTAGRAM_ACCESS_TOKEN,
                'rate_limit': cls.INSTAGRAM_RATE_LIMIT,
                'enabled': bool(cls.INSTAGRAM_ACCESS_TOKEN)
            },
            'youtube': {
                'api_key': cls.YOUTUBE_API_KEY,
                'rate_limit': cls.YOUTUBE_RATE_LIMIT,
                'enabled': bool(cls.YOUTUBE_API_KEY)
            },
            'telegram': {
                'bot_token': cls.TELEGRAM_BOT_TOKEN,
                'channel_id': cls.TELEGRAM_CHANNEL_ID,
                'enabled': bool(cls.TELEGRAM_BOT_TOKEN and cls.TELEGRAM_CHANNEL_ID)
            }
        }

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False
    LOG_LEVEL = 'DEBUG'
    
    # Shorter intervals for development
    TWITTER_INTERVAL = 5
    INSTAGRAM_INTERVAL = 10
    YOUTUBE_INTERVAL = 15
    
    # Lower thresholds for testing
    MIN_ENGAGEMENT_THRESHOLD = 1
    HIGH_PRIORITY_THRESHOLD = 2

class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    DEBUG = True
    DATABASE_URL = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    
    # Disable external API calls during testing
    TWITTER_BEARER_TOKEN = 'test-token'
    INSTAGRAM_ACCESS_TOKEN = 'test-token'
    YOUTUBE_API_KEY = 'test-key'
    TELEGRAM_BOT_TOKEN = 'test-token'
    TELEGRAM_CHANNEL_ID = '@test-channel'

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False
    
    # Enhanced security for production
    SESSION_COOKIE_SECURE = True
    WTF_CSRF_ENABLED = True
    
    # Stricter content filtering
    MIN_ENGAGEMENT_THRESHOLD = 50
    HIGH_PRIORITY_THRESHOLD = 4
    
    # Production logging
    LOG_LEVEL = 'WARNING'

class ConfigManager:
    """Configuration manager to handle different environments"""
    
    configs = {
        'development': DevelopmentConfig,
        'testing': TestingConfig,
        'production': ProductionConfig,
        'default': Config
    }
    
    @classmethod
    def get_config(cls, config_name: Optional[str] = None) -> Config:
        """Get configuration class based on environment"""
        if config_name is None:
            config_name = os.getenv('FLASK_ENV', 'default')
        
        return cls.configs.get(config_name, cls.configs['default'])
    
    @classmethod
    def validate_environment(cls) -> Dict[str, Any]:
        """Validate current environment configuration"""
        env = os.getenv('FLASK_ENV', 'default')
        config_class = cls.get_config(env)
        
        return {
            'environment': env,
            'config_class': config_class.__name__,
            'validation': config_class.validate_config()
        }
    
    @classmethod
    def get_runtime_info(cls) -> Dict[str, Any]:
        """Get runtime configuration information"""
        config = cls.get_config()
        
        return {
            'environment': os.getenv('FLASK_ENV', 'default'),
            'debug': config.DEBUG,
            'testing': config.TESTING,
            'database_url': config.DATABASE_URL.split('://')[0] + '://...',  # Hide credentials
            'log_level': config.LOG_LEVEL,
            'api_status': config.validate_config()['api_status'],
            'monitoring_intervals': {
                'twitter': config.TWITTER_INTERVAL,
                'instagram': config.INSTAGRAM_INTERVAL,
                'youtube': config.YOUTUBE_INTERVAL
            }
        }

# Export the config based on environment
config = ConfigManager.get_config()