import os
import logging
import sys
from flask import request, jsonify
from CTFd import create_app
from CTFd.models import Users, db
from CTFd.utils.crypto import hash_password
from sqlalchemy.exc import SQLAlchemyError

# =========================================================================
# 🔒 TABAKA LA USALAMA: BRUTE FORCE & ANTI-INTRUDER PROTECTION
# =========================================================================
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    HAS_LIMITER = True
except ImportError:
    HAS_LIMITER = False
    print("[!] Flask-Limiter not installed. Install with: pip install Flask-Limiter==3.5.0")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Create CTFd app
app = create_app()

# =========================================================================
# 🔒 RATE LIMITING CONFIGURATION - Anti Brute Force
# =========================================================================
if HAS_LIMITER:
    def get_real_ip():
        """Get real client IP address even behind reverse proxy (Render.com)"""
        if request.headers.get('X-Forwarded-For'):
            return request.headers.get('X-Forwarded-For').split(',')[0].strip()
        if request.headers.get('X-Real-IP'):
            return request.headers.get('X-Real-IP')
        return request.remote_addr
    
    limiter = Limiter(
        key_func=get_real_ip,
        app=app,
        default_limits=["500 per day", "100 per hour"],
        storage_uri="memory://",
        strategy="fixed-window"
    )
    
    @app.before_request
    def apply_rate_limits():
        if request.endpoint == 'auth.login' and request.method == 'POST':
            try:
                limiter.shared_limit("5 per minute", scope="login")(lambda: None)()
            except Exception:
                pass
    
    @app.errorhandler(429)
    def rate_limit_handler(e):
        logger.warning(f"[!] Rate limit exceeded for IP: {get_real_ip()}")
        return jsonify({
            'error': 'Too many requests. Please try again later.',
            'message': 'Maximum 5 attempts per minute.'
        }), 429
    
    logger.info("[✓] Anti-Brute Force Layer activated. Limit: 5 attempts/minute")

# =========================================================================
# 👑 ADMIN SETUP FUNCTION
# =========================================================================
def secure_admin_setup():
    with app.app_context():
        try:
            email = os.environ.get("ADMIN_EMAIL")
            username = os.environ.get("ADMIN_USERNAME")
            password = os.environ.get("ADMIN_PASS")
            
            missing_vars = []
            if not email:
                missing_vars.append("ADMIN_EMAIL")
            if not username:
                missing_vars.append("ADMIN_USERNAME")
            if not password:
                missing_vars.append("ADMIN_PASS")
            
            if missing_vars:
                logger.error(f"[-] Missing: {', '.join(missing_vars)}")
                return False
            
            existing_admin = Users.query.filter(
                (Users.email == email) | (Users.type == "admin")
            ).first()
            
            if existing_admin:
                existing_admin.type = "admin"
                existing_admin.name = username
                existing_admin.email = email
                existing_admin.password = hash_password(password)
                db.session.commit()
                logger.info(f"[✓] Admin UPDATED: {username}")
            else:
                new_admin = Users(
                    name=username,
                    email=email,
                    password=hash_password(password),
                    type="admin",
                    verified=True,
                    hidden=False
                )
                db.session.add(new_admin)
                db.session.commit()
                logger.info(f"[✓] Admin CREATED: {username}")
            return True
                
        except Exception as e:
            logger.error(f"[-] Admin setup error: {str(e)}")
            db.session.rollback()
            return False

def list_admins():
    with app.app_context():
        admins = Users.query.filter_by(type="admin").all()
        if admins:
            logger.info("[*] Current admins:")
            for admin in admins:
                logger.info(f"    - {admin.name} ({admin.email})")
        return admins

# =========================================================================
# 🚀 RUN ON STARTUP
# =========================================================================
try:
    logger.info("=" * 50)
    logger.info("[*] Initializing Secure Admin Setup...")
    logger.info("=" * 50)
    
    success = secure_admin_setup()
    
    if success:
        logger.info("[✓] Admin setup completed!")
        list_admins()
    else:
        logger.error("[✗] Admin setup failed! Check environment variables.")
    
    # Debug: Check environment variables
    logger.info("[*] Environment check:")
    logger.info(f"    ADMIN_EMAIL: {'✓' if os.environ.get('ADMIN_EMAIL') else '✗'}")
    logger.info(f"    ADMIN_USERNAME: {'✓' if os.environ.get('ADMIN_USERNAME') else '✗'}")
    logger.info(f"    ADMIN_PASS: {'✓' if os.environ.get('ADMIN_PASS') else '✗'}")
    logger.info("=" * 50)
    
except Exception as e:
    logger.error(f"[-] Startup error: {str(e)}")
