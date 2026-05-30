import os
import logging
import sys
from CTFd import create_app
from CTFd.models import Users, db
from CTFd.utils.crypto import hash_password

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = loggin.getLogger(__name__)

# Create CTFd app safely
app = create_app()

# Lazimisha ulinzi wa kuki kupitia HTTPS ya Render
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True

# =========================================================================
# 👑 ADMIN SETUP FUNCTION (Salama na Nyepesi bila kufunga database)
# =========================================================================
def secure_admin_setup():
    with app.app_context():
        try:
            email = os.environ.get("ADMIN_EMAIL")
            username = os.environ.get("ADMIN_USERNAME")
            password = os.environ.get("ADMIN_PASS")
            
            if not email or not username or not password:
                logger.error("[-] Missing required admin environment variables in Render dashboard.")
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
                logger.info(f"[✓] Admin credentials verified and synchronized for: {username}")
                return True
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
                logger.info(f"[✓] Fresh secure admin account deployed: {username}")
                return True
                
        except Exception as e:
            logger.error(f"[-] Startup exception bypassed safely: {str(e)}")
            db.session.rollback()
            return False

# =========================================================================
# 🚀 AUTOMATIC INITIALIZATION (Inakimbia tu kama script ya pembeni)
# =========================================================================
if __name__ == "__main__":
    try:
        secure_admin_setup()
    except Exception:
        pass
