# pyrefly: ignore [missing-import]
from flask_sqlalchemy import SQLAlchemy
db = SQLAlchemy()

class Producto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(20), unique=True, nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    categoria = db.Column(db.String(100), nullable=False)
    precios = db.Column(db.Float, nullable=False)  
    comision = db.Column(db.Float)  
    stock_central = db.Column(db.Integer, default=0) # Almacén principal

class Cliente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    rif = db.Column(db.String(20), unique=True, nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    direccion = db.Column(db.String(200))  
    telefono = db.Column(db.String(20))
    estado = db.Column(db.String(50)) # Estado de Venezuela

class Vendedor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cedula = db.Column(db.String(20), unique=True, nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    usuario = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    rol = db.Column(db.String(20), default='vendedor') # 'vendedor' o 'admin'
    zona = db.Column(db.String(50)) # Estado de Venezuela (Caracas, Zulia, etc.)
    # Relación para ver qué productos tiene este vendedor
    inventario = db.relationship('InventarioVendedor', backref='vendedor', lazy=True)

class InventarioVendedor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    id_vendedor = db.Column(db.Integer, db.ForeignKey('vendedor.id'), nullable=False)
    id_producto = db.Column(db.Integer, db.ForeignKey('producto.id'), nullable=False)
    cantidad = db.Column(db.Integer, default=0) # El stock de la vendedora
    
    # Para saber qué producto es
    producto = db.relationship('Producto', backref='inventarios')

class Venta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codigo_factura = db.Column(db.String(20)) # Para agrupar productos de una misma venta
    id_vendedor = db.Column(db.Integer, db.ForeignKey('vendedor.id'), nullable=False)
    id_cliente = db.Column(db.Integer, db.ForeignKey('cliente.id'), nullable=False)
    id_producto = db.Column(db.Integer, db.ForeignKey('producto.id'), nullable=False)
    cantidad = db.Column(db.Integer, nullable=False)
    total = db.Column(db.Float, nullable=False)
    fecha = db.Column(db.DateTime, default=db.func.current_timestamp())
    estado = db.Column(db.String(20), default='En espera') # En espera, Procesada, Rechazada
    
    # Relaciones para acceder fácilmente a los nombres en los templates
    vendedor = db.relationship('Vendedor', backref='ventas')
    cliente = db.relationship('Cliente', backref='ventas')
    # El atributo 'producto' ya existe por el backref en InventarioVendedor o puede definirse aquí
    producto = db.relationship('Producto')

class Traslado(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    id_producto = db.Column(db.Integer, db.ForeignKey('producto.id'), nullable=False)
    id_vendedor = db.Column(db.Integer, db.ForeignKey('vendedor.id'), nullable=False)
    tipo = db.Column(db.String(50), nullable=False) # 'Central -> Vendedora' o 'Vendedora -> Central'
    cantidad = db.Column(db.Integer, nullable=False)
    fecha = db.Column(db.DateTime, default=db.func.current_timestamp())

    producto = db.relationship('Producto')
    vendedor = db.relationship('Vendedor', backref='traslados')