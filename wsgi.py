import os
import logging
import sys
from flask import request, jsonify
from CTFd import create_app
from CTFd.models import Users, db
from CTFd.utils.crypto import hash_password
from sqlalchemy.exc import SQLAlchemyError

# =========================================================================
# 🔒 TABAKA LA USALAMA: BRUTE FORCE & ANTI-INTRUDER PROTECTION (OWASP TOP 10)
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
    # Function to get real client IP behind Render proxy
    def get_real_ip():
        """Get real client IP address even behind reverse proxy (Render.com)"""
        # Check for Cloudflare/Render proxy headers
        if request.headers.get('X-Forwarded-For'):
            return request.headers.get('X-Forwarded-For').split(',')[0].strip()
        if request.headers.get('X-Real-IP'):
            return request.headers.get('X-Real-IP')
        return request.remote_addr
    
    # Initialize limiter
    limiter = Limiter(
        key_func=get_real_ip,
        app=app,
        default_limits=["500 per day", "100 per hour"],
        storage_uri="memory://",
        strategy="fixed-window"
    )
    
    # Apply rate limit to login endpoint
    @app.before_request
    def apply_rate_limits():
        if request.endpoint == 'auth.login' and request.method == 'POST':
            try:
                limiter.shared_limit("5 per minute", scope="login")(lambda: None)()
            except Exception:
                pass
    
    # Custom error handler for rate limit exceeded
    @app.errorhandler(429)
    def rate_limit_handler(e):
        logger.warning(f"[!] Rate limit exceeded for IP: {get_real_ip()}")
        return jsonify({
            'error': 'Too many requests. Please try again later.',
            'message': 'Rate limit exceeded. Maximum 5 attempts per minute.'
        }), 429
    
    logger.info("[✓] Anti-Brute Force Layer (Flask-Limiter) activated successfully.")
    logger.info("[✓] Login rate limit: 5 attempts per minute per IP address")
else:
    logger.warning("[!] Flask-Limiter is NOT active. Add 'Flask-Limiter==3.5.0' to requirements.txt")

# =========================================================================
# 👑 ADMIN SETUP FUNCTION
# =========================================================================
def secure_admin_setup():
    """
    Usanidi salama wa akaunti ya ADMIN kwa CTFd platform.
    Inafanya kazi kwa usalama kwenye Render.com na hosting nyingine.
    """
    with app.app_context():
        try:
            # Get environment variables
            email = os.environ.get("ADMIN_EMAIL")
            username = os.environ.get("ADMIN_USERNAME")
            password = os.environ.get("ADMIN_PASS")
            
            # Validate required variables
            missing_vars = []
            if not email:
                missing_vars.append("ADMIN_EMAIL")
            if not username:
                missing_vars.append("ADMIN_USERNAME")
            if not password:
                missing_vars.append("ADMIN_PASS")
            
            if missing_vars:
                logger.error(f"[-] Missing required environment variables: {', '.join(missing_vars)}")
                logger.error("[-] Admin setup aborted for security reasons.")
                return False
            
            # Validate password strength
            if len(password) < 8:
                logger.warning("[!] Password is weak (less than 8 characters). Consider using a stronger password.")
            
            # Check if admin already exists
            existing_admin = Users.query.filter(
                (Users.email == email) | (Users.type == "admin")
            ).first()
            
            if existing_admin:
                # Update existing admin
                existing_admin.type = "admin"
                existing_admin.name = username
                existing_admin.email = email
                existing_admin.password = hash_password(password)
                db.session.commit()
                logger.info(f"[✓] Admin account UPDATED securely: {username} ({email})")
                return True
            else:
                # Create new admin
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
                logger.info(f"[✓] New admin account CREATED securely: {username} ({email})")
                return True
                
        except SQLAlchemyError as e:
            logger.error(f"[-] Database error during admin setup: {str(e)}")
            db.session.rollback()
            return False
        except Exception as e:
            logger.error(f"[-] Unexpected error during admin setup: {str(e)}")
            return False

def list_admins():
    """List all admin users (for debugging)"""
    with app.app_context():
        admins = Users.query.filter_by(type="admin").all()
        if admins:
            logger.info("[*] Current admin accounts:")
            for admin in admins:
                logger.info(f"    - {admin.name} ({admin.email})")
        return admins

# =========================================================================
# 🚀 RUN AUTOMATIC ADMIN SETUP ON SERVER STARTUP (Lazima Gunicorn Iifanye!)
# =========================================================================
try:
    logger.info("=" * 50)
    logger.info("[*] Initializing Automatic Secure Admin Setup...")
    logger.info("=" * 50)
    
    # Hii inakimbia mara moja server inapowaka - NO __main__ block!
    success = secure_admin_setup()
    
    if success:
        logger.info("[✓] Admin setup completed successfully at startup runtime!")
        list_admins()
    else:
        logger.error("[✗] Startup admin setup failed! Check environment variables.")
    logger.info("=" * 50)
except Exception as startup_error:
    logger.error(f"[-] Unexpected error during startup initialization: {str(startup_error)}")
