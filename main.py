from models import db
from views import *

db.create_all()
db.session.commit()

if __name__ == '__main__':
    app.run(host='localhost', port=8000, debug=True)
