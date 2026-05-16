from flask import Flask
from models import db, Producto, Cliente, Vendedor, InventarioVendedor
from rutas_vendedor import vendedor_bp 
from rutas_admin import admin_bp 

from rutas_auth import auth_bp
from werkzeug.security import generate_password_hash

app = Flask(__name__)

# Configuración de la base de datos local
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sistema_belleza.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'dev_key_proyecto_ami' # Necesario para flash y sesiones

# Conectamos la base de datos a esta aplicación Flask
db.init_app(app)

# Registramos los Blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(vendedor_bp)
app.register_blueprint(admin_bp)

# Ruta principal redirige a login
@app.route('/')
def index():
    return redirect(url_for('auth.login'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        # 0. Crear Administrador Maestro (Alan Mujica)
        admin_user = Vendedor.query.filter_by(cedula="27622091").first()
        if not admin_user:
            admin_test = Vendedor(
                cedula="27622091",
                nombre="Alan Mujica",
                usuario="alan_m",
                password=generate_password_hash("Ab123456"),
                rol="admin"
            )
            db.session.add(admin_test)

        # 1. Crear Producto de prueba
        if not Producto.query.first():
            producto_test = Producto(
                codigo="B001", 
                nombre="Ácido Hialurónico 1ml", 
                categoria="Estética", 
                precios=150.0, 
                comision=15.0,
                stock_central=100
            )
            db.session.add(producto_test)
        
        # 2. Crear Cliente de prueba
        if not Cliente.query.first():
            cliente_test = Cliente(
                rif="J-12345678-0", 
                nombre="Clínica Dermalife", 
                direccion="Las Mercedes, Caracas", 
                telefono="0412-0000000"
            )
            db.session.add(cliente_test)
            
        # 3. Crear Vendedor de prueba (Alejandra) para que el dashboard funcione
        vendedor_test = Vendedor.query.filter_by(usuario="alejandra").first()
        if not vendedor_test:
            vendedor_test = Vendedor(
                cedula="V-20123456",
                nombre="Alejandra Pérez",
                usuario="alejandra",
                password=generate_password_hash("password123"),
                rol="vendedor"
            )
            db.session.add(vendedor_test)
            db.session.commit() # Commiteamos para tener el ID del vendedor
            
            # Asignamos stock al vendedor para que pueda vender
            producto = Producto.query.first()
            if producto:
                inv_test = InventarioVendedor(
                    id_vendedor=vendedor_test.id,
                    id_producto=producto.id,
                    cantidad=10
                )
                db.session.add(inv_test)
        
        db.session.commit()
        print("✅ Base de datos lista con datos de prueba.")
    
    app.run(debug=True)