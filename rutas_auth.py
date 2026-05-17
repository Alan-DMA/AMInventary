from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import check_password_hash, generate_password_hash
from models import db, Vendedor

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identificador = request.form.get('identificador')
        password = request.form.get('password')

        # Buscar por usuario o cédula
        user = Vendedor.query.filter((Vendedor.usuario == identificador) | (Vendedor.cedula == identificador)).first()

        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['user_rol'] = user.rol
            session['user_nombre'] = user.nombre
            
            flash(f"Bienvenido/a de nuevo, {user.nombre}.", "success")
            if user.rol == 'admin':
                return redirect(url_for('admin.dashboard'))
            else:
                return redirect(url_for('vendedor.dashboard'))
        else:
            flash("Credenciales incorrectas. Intenta de nuevo.", "danger")

    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash("Has cerrado sesión exitosamente.", "success")
    return redirect(url_for('auth.login'))
