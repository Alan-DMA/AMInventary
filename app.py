from flask import Flask, redirect, url_for
from models import db, Producto, Cliente, Vendedor, InventarioVendedor, Venta
from rutas_vendedor import vendedor_bp 
from rutas_admin import admin_bp 

from rutas_auth import auth_bp
from werkzeug.security import generate_password_hash
import random
from datetime import datetime

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

def seed_data():
    with app.app_context():
        db.create_all()
        
        # 0. Crear Administrador Maestro (Alan Mujica)
        admin_user = Vendedor.query.filter(
            (Vendedor.cedula == "27622091") | (Vendedor.usuario == "alan_m")
        ).first()
        if not admin_user:
            admin_test = Vendedor(
                cedula="27622091",
                nombre="Alan Mujica",
                usuario="alan_m",
                password=generate_password_hash("Ab123456"),
                rol="admin"
            )
            db.session.add(admin_test)
            db.session.commit()

        # 1. Crear hasta 6 productos de prueba
        productos_data = [
            ("B001", "Ácido Hialurónico 1ml", "Estética", 150.0, 15),
            ("B002", "Vitamina C 20%", "Estética", 120.0, 12),
            ("B003", "Áloe Vera Gel 100ml", "Cuidado", 85.0, 10),
            ("B004", "Crema Antiedad", "Cosmética", 200.0, 18),
            ("B005", "Suero Capilar", "Belleza", 110.0, 14),
            ("B006", "Mascarilla Facial", "Spa", 95.0, 11),
        ]
        for codigo, nombre, categoria, precios, comision in productos_data:
            if not Producto.query.filter_by(codigo=codigo).first():
                producto_test = Producto(
                    codigo=codigo,
                    nombre=nombre,
                    categoria=categoria,
                    precios=precios,
                    comision=comision,
                    stock_central=random.randint(0, 10)
                )
                db.session.add(producto_test)
        db.session.commit()

        # 2. Crear hasta 6 clientes de prueba
        clientes_data = [
            ("J-12345678-0", "Clínica Dermalife", "Las Mercedes, Caracas", "0412", "0000000", "Distrito Capital"),
            ("J-22334455-1", "Dermastore", "C.C. San Ignacio, Caracas", "0424", "1234567", "Distrito Capital"),
            ("J-33445566-2", "Salud Belleza", "Av. Francisco de Miranda, Caracas", "0416", "2345678", "Distrito Capital"),
            ("J-44556677-3", "Instituto Estético", "C.C. Sambil, Caracas", "0422", "3456789", "Distrito Capital"),
            ("J-55667788-4", "Spa Femenino", "El Rosal, Caracas", "0414", "4567890", "Distrito Capital"),
            ("J-66778899-5", "Centro Médico", "Chacao, Caracas", "0412", "5678901", "Distrito Capital"),
        ]
        for rif, nombre, direccion, prefijo, telefono_num, estado in clientes_data:
            if not Cliente.query.filter_by(rif=rif).first():
                cliente_test = Cliente(
                    rif=rif,
                    nombre=nombre,
                    direccion=direccion,
                    telefono=f"{prefijo}{telefono_num}",
                    estado=estado
                )
                db.session.add(cliente_test)
        db.session.commit()

        # 3. Crear hasta 6 vendedores de prueba
        vendedores_data = [
            ("V-20123456", "Alejandra Pérez", "alejandra", "vendedor", "Miranda"),
            ("V-30123456", "Laura Díaz", "laura_d", "vendedor", "Caracas"),
            ("V-40123456", "Valentina Gómez", "valentina_g", "vendedor", "Zulia"),
            ("V-50123456", "Sofía Rojas", "sofia_r", "vendedor", "Carabobo"),
            ("V-60123456", "Camila Torres", "camila_t", "vendedor", "Barinas"),
            ("V-70123456", "María López", "maria_l", "vendedor", "Guárico"),
        ]
        for cedula, nombre, usuario, rol, zona in vendedores_data:
            if not Vendedor.query.filter_by(usuario=usuario).first():
                vendedor_test = Vendedor(
                    cedula=cedula,
                    nombre=nombre,
                    usuario=usuario,
                    password=generate_password_hash("password123"),
                    rol=rol,
                    zona=zona
                )
                db.session.add(vendedor_test)
        db.session.commit()

        # 4. Crear inventario aleatorio para cada vendedor
        productos = Producto.query.all()
        vendedores = Vendedor.query.filter_by(rol='vendedor').all()
        for vendedor in vendedores:
            for producto in productos:
                if not InventarioVendedor.query.filter_by(id_vendedor=vendedor.id, id_producto=producto.id).first():
                    inv_test = InventarioVendedor(
                        id_vendedor=vendedor.id,
                        id_producto=producto.id,
                        cantidad=random.randint(1, 10)
                    )
                    db.session.add(inv_test)
        db.session.commit()

        # 5. Generar 3 ventas de prueba por vendedor si no existen
        clientes = Cliente.query.all()
        if not Venta.query.first():
            for vendedor in vendedores:
                inventarios = InventarioVendedor.query.filter_by(id_vendedor=vendedor.id).all()
                productos_con_stock = [inv for inv in inventarios if inv.cantidad > 0]
                if not productos_con_stock and inventarios:
                    inventarios[0].cantidad = random.randint(1, 10)
                    db.session.add(inventarios[0])
                    productos_con_stock = [inventarios[0]]

                for n in range(3):
                    if not productos_con_stock:
                        break
                    inv = random.choice(productos_con_stock)
                    cantidad = random.randint(1, min(10, inv.cantidad))
                    if cantidad <= 0:
                        continue
                    inv.cantidad -= cantidad
                    db.session.add(inv)
                    cliente = random.choice(clientes)
                    codigo_f = f"F-{datetime.now().strftime('%y%m%d%H%M%S')}-{vendedor.id}{n}"
                    venta_test = Venta(
                        codigo_factura=codigo_f,
                        id_vendedor=vendedor.id,
                        id_cliente=cliente.id,
                        id_producto=inv.id_producto,
                        cantidad=cantidad,
                        total=inv.producto.precios * cantidad,
                        estado='Procesada'
                    )
                    db.session.add(venta_test)
            db.session.commit()

        print("✅ Base de datos lista con datos de prueba.")

# ==========================================
# RUTAS DE CONFIGURACIÓN PARA LA PWA (Añadir aquí)
# ==========================================
@app.route('/sw.js')
def serve_sw():
    return app.send_static_file('sw.js')

@app.route('/manifest.json')
def serve_manifest():
    return app.send_static_file('manifest.json')
# ==========================================

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # ... (el resto de tu código de inicialización de prueba se mantiene igual)
        app.run(debug=True)