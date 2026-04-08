import os
from CTFd import create_app
from CTFd.models import Users, db

app = create_app()

# Hii inampa Frank u-Admin kila server inapowaka
with app.app_context():
    user = Users.query.filter_by(email="frankkarani280@gmail.com").first()
    if user:
        user.type = "admin"
        db.session.commit()
        print("Mamlaka ya Admin yamewekwa kwa frankkarani280@gmail.com")

if __name__ == "__main__":
    # Tumia 0.0.0.0 ili Render iweze kuunganisha
    app.run(debug=True, threaded=True, host="0.0.0.0", port=4000)