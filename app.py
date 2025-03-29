from flask import Flask, request, render_template, redirect, session, flash, url_for, send_from_directory
from flask_sqlalchemy import SQLAlchemy
import bcrypt
from datetime import datetime
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}
app.secret_key = 'secret_key'

db = SQLAlchemy(app)

# Modèle Utilisateur
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    articles = db.relationship('Article', backref='author', lazy=True)

    def __init__(self, email, password, name):
        self.name = name
        self.email = email
        self.password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    def check_password(self, password):
        return bcrypt.checkpw(password.encode('utf-8'), self.password.encode('utf-8'))

# Modèle Article
class Article(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    image_filename = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# Fonctions utilitaires
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def is_logged_in():
    return 'email' in session

def get_current_user():
    if is_logged_in():
        return User.query.filter_by(email=session['email']).first()
    return None

# Création du dossier uploads s'il n'existe pas
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Routes
@app.route('/')
def home():
    return redirect('/dashboard') if is_logged_in() else redirect('/login')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if is_logged_in():
        return redirect('/dashboard')

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            session['email'] = user.email
            flash('Connexion réussie!', 'success')
            return redirect('/dashboard')
        else:
            flash('Email ou mot de passe incorrect', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('email', None)
    flash('Déconnexion réussie!', 'success')
    return redirect('/login')

@app.route('/register',methods=['GET','POST'])
def register():
    if request.method == 'POST':
        # handle request
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        new_user = User(name=name,email=email,password=password)
        db.session.add(new_user)
        db.session.commit()
        return redirect('/login')



    return render_template('register.html')

@app.route('/dashboard')
def dashboard():
    if not is_logged_in():
        return redirect('/login')
    
    user = get_current_user()
    articles = Article.query.filter_by(user_id=user.id).order_by(Article.created_at.desc()).all()
    return render_template('dashboard.html', user=user, articles=articles)

@app.route('/articles')
def articles():
    all_articles = Article.query.order_by(Article.created_at.desc()).all()
    return render_template('articles.html', articles=all_articles)

@app.route('/article/<int:article_id>')
def article(article_id):
    article = Article.query.get_or_404(article_id)
    return render_template('article.html', article=article)

@app.route('/add_article', methods=['GET', 'POST'])
def add_article():
    if not is_logged_in():
        return redirect('/login')
    
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        user = get_current_user()
        
        # Gestion de l'upload de l'image
        image_filename = None
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_filename = filename
        
        new_article = Article(
            title=title,
            content=content,
            image_filename=image_filename,
            author=user
        )
        db.session.add(new_article)
        db.session.commit()
        
        flash('Article créé avec succès!', 'success')
        return redirect('/dashboard')
    
    return render_template('add_article.html')

@app.route('/edit_article/<int:article_id>', methods=['GET', 'POST'])
def edit_article(article_id):
    if not is_logged_in():
        return redirect('/login')
    
    article = Article.query.get_or_404(article_id)
    user = get_current_user()
    
    if article.user_id != user.id:
        flash("Vous n'êtes pas autorisé à modifier cet article", 'danger')
        return redirect('/dashboard')
    
    if request.method == 'POST':
        article.title = request.form['title']
        article.content = request.form['content']
        
        # Gestion de la nouvelle image
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '' and allowed_file(file.filename):
                # Supprime l'ancienne image si elle existe
                if article.image_filename:
                    old_path = os.path.join(app.config['UPLOAD_FOLDER'], article.image_filename)
                    if os.path.exists(old_path):
                        os.remove(old_path)
                
                # Sauvegarde la nouvelle image
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                article.image_filename = filename
        
        db.session.commit()
        flash('Article modifié avec succès!', 'success')
        return redirect('/dashboard')
    
    return render_template('edit_article.html', article=article)

@app.route('/delete_article/<int:article_id>', methods=['POST'])
def delete_article(article_id):
    if not is_logged_in():
        return redirect('/login')
    
    article = Article.query.get_or_404(article_id)
    user = get_current_user()
    
    if article.user_id != user.id:
        flash("Vous n'êtes pas autorisé à supprimer cet article", 'danger')
        return redirect('/dashboard')
    
    # Suppression de l'image associée
    if article.image_filename:
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], article.image_filename)
        if os.path.exists(image_path):
            os.remove(image_path)
    
    db.session.delete(article)
    db.session.commit()
    flash('Article supprimé avec succès!', 'success')
    return redirect('/dashboard')

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# Initialisation de la base de données
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)