from datetime import datetime
import csv
import io
from flask import Flask, render_template, request, redirect, url_for, flash, session, make_response
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'votre_cle_secrete_tres_securisee' # À changer en production
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///yoga_studio.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- MODÈLES DE LA BASE DE DONNÉES ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='client') # 'admin' ou 'client'
    nom = db.Column(db.String(100), nullable=True)
    prenom = db.Column(db.String(100), nullable=True)
    adresse = db.Column(db.String(200), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    telephone = db.Column(db.String(20), nullable=True)
    registrations = db.relationship('Registration', backref='client', lazy=True)

class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titre = db.Column(db.String(100), nullable=False)
    date_heure = db.Column(db.DateTime, nullable=False)
    duree = db.Column(db.String(50), nullable=False) # ex: "1h", "1h30"
    lieu = db.Column(db.String(100), nullable=False)
    capacite = db.Column(db.Integer, nullable=False)
    registrations = db.relationship('Registration', backref='course', lazy=True)

class Registration(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)

with app.app_context():
    db.create_all()
    # Créer un admin par défaut s'il n'en existe pas
    if not User.query.filter_by(role='admin').first():
        admin_user = User(
            username='admin',
            password=generate_password_hash('admin123'),
            role='admin',
            nom='Admin',
            prenom='Studio',
            email='admin@yoga.com'
        )
        db.session.add(admin_user)
        db.session.commit()

# --- ROUTES ---

@app.route('/')
def index():
    if 'user_id' in session:
        if session.get('role') == 'admin':
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('client_dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['role'] = user.role
            session['username'] = user.username
            flash('Connexion réussie !', 'success')
            return redirect(url_for('index'))
        else:
            flash('Identifiant ou mot de passe incorrect.', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        if User.query.filter_by(username=username).first():
            flash('Ce nom d\'utilisateur existe déjà.', 'danger')
            return redirect(url_for('register'))
        
        new_user = User(
            username=username,
            password=generate_password_hash(request.form['password']),
            role='client',
            nom=request.form['nom'],
            prenom=request.form['prenom'],
            adresse=request.form['adresse'],
            email=request.form['email'],
            telephone=request.form['telephone']
        )
        db.session.add(new_user)
        db.session.commit()
        flash('Compte créé avec succès ! Vous pouvez vous connecter.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Vous avez été déconnecté.', 'info')
    return redirect(url_for('login'))

@app.route('/client/dashboard')
def client_dashboard():
    if session.get('role') != 'client':
        return redirect(url_for('login'))
    
    courses = Course.query.all()
    user_id = session['user_id']
    # Récupérer les IDs des cours auxquels le client est déjà inscrit
    registered_course_ids = [r.course_id for r in Registration.query.filter_by(user_id=user_id).all()]
    
    # Calculer les places restantes pour chaque cours
    course_data = []
    for c in courses:
        nb_inscrits = len(c.registrations)
        places_restantes = c.capacite - nb_inscrits
        pourcentage = int((nb_inscrits / c.capacite) * 100) if c.capacite > 0 else 100
        course_data.append({
            'course': c,
            'nb_inscrits': nb_inscrits,
            'places_restantes': places_restantes,
            'pourcentage': pourcentage,
            'is_registered': c.id in registered_course_ids
        })
        
    return render_template('client_dashboard.html', course_data=course_data)

@app.route('/client/book/<int:course_id>', methods=['POST'])
def book_course(course_id):
    if session.get('role') != 'client':
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    course = Course.query.get_or_404(course_id)
    
    # Vérifier si déjà inscrit
    existing = Registration.query.filter_by(user_id=user_id, course_id=course_id).first()
    if existing:
        flash('Vous êtes déjà inscrit à ce cours.', 'warning')
        return redirect(url_for('client_dashboard'))
        
    # Vérifier les places
    if len(course.registrations) >= course.capacite:
        flash('Désolé, ce cours est complet.', 'danger')
        return redirect(url_for('client_dashboard'))
        
    # Inscription
    new_reg = Registration(user_id=user_id, course_id=course_id)
    db.session.add(new_reg)
    db.session.commit()
    
    # Simulation/Envoi d'email (Ici vous intégrerez votre service d'envoi d'email réel type Flask-Mail ou SendGrid)
    user = User.query.get(user_id)
    print(f"EMAIL À L'ADMIN : Le client {user.prenom} {user.nom} s'est inscrit au cours '{course.titre}'.")
    print(f"EMAIL AU CLIENT ({user.email}) : Confirmation d'inscription pour le cours '{course.titre}' le {course.date_heure}.")
    
    flash('Inscription réussie ! Un e-mail de confirmation vous a été envoyé.', 'success')
    return redirect(url_for('client_dashboard'))

@app.route('/admin/dashboard', methods=['GET', 'POST'])
def admin_dashboard():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        titre = request.form['titre']
        date_heure_str = request.form['date_heure']
        date_heure = datetime.strptime(date_heure_str, '%Y-%m-%dT%H:%M')
        duree = request.form['duree']
        lieu = request.form['lieu']
        capacite = int(request.form['capacite'])
        
        new_course = Course(titre=titre, date_heure=date_heure, duree=duree, lieu=lieu, capacite=capacite)
        db.session.add(new_course)
        db.session.commit()
        flash('Cours planifié avec succès !', 'success')
        return redirect(url_for('admin_dashboard'))
        
    courses = Course.query.all()
    registrations = Registration.query.all()
    return render_template('admin_dashboard.html', courses=courses, registrations=registrations)

@app.route('/admin/export_csv')
def export_csv():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
        
    si = io.StringIO()
    cw = csv.writer(si)
    # En-tête CSV
    cw.writerow(['ID Inscription', 'Nom Client', 'Prénom Client', 'Email', 'Téléphone', 'Cours', 'Date du cours', 'Lieu'])
    
    registrations = Registration.query.all()
    for r in registrations:
        cw.writerow([
            r.id,
            r.client.nom,
            r.client.prenom,
            r.client.email,
            r.client.telephone,
            r.course.titre,
            r.course.date_heure.strftime('%Y-%m-%d %H:%M'),
            r.course.lieu
        ])
        
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=inscriptions_yoga.csv"
    output.headers["Content-type"] = "text/csv"
    return output

if __name__ == '__main__':
    app.run(debug=True)