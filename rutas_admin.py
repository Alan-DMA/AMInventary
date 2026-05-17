from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash
from models import db, Producto, Vendedor, InventarioVendedor, Cliente, Venta, Traslado
from datetime import datetime, timedelta
from sqlalchemy import func


def format_identificacion(prefijo: str, numero: str) -> str:
    numero = (numero or '').strip()
    prefijo = (prefijo or '').strip().upper()
    if prefijo not in ['V', 'J', 'E', 'G']:
        raise ValueError('Seleccione un tipo válido: V, J, E o G.')
    if not numero.isdigit():
        raise ValueError('El número de identificación debe contener solo dígitos.')
    max_len = 8 if prefijo == 'V' else 9
    if len(numero) != max_len:
        raise ValueError(f"Para '{prefijo}' debe ingresar exactamente {max_len} dígitos.")
    return f"{prefijo}-{numero}"


def format_telefono(prefijo: str, numero: str) -> str:
    numero = (numero or '').strip()
    prefijo = (prefijo or '').strip()
    if prefijo not in ['0412', '0422', '0414', '0424', '0416']:
        raise ValueError('Seleccione un prefijo de teléfono válido.')
    if not numero.isdigit() or len(numero) != 7:
        raise ValueError('El número de teléfono debe tener exactamente 7 dígitos.')
    return f"{prefijo}{numero}"


admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.before_request
def require_admin():
    if 'user_rol' not in session or session['user_rol'] != 'admin':
        flash("Acceso denegado. Se requieren permisos de administrador.", "danger")
        return redirect(url_for('auth.login'))

@admin_bp.context_processor
def inject_pending_sales():
    # Contamos facturas únicas (pedidos agrupados) + ventas viejas sin código
    count_facturas = db.session.query(Venta.codigo_factura).filter(Venta.estado == 'En espera', Venta.codigo_factura != None).distinct().count()
    count_viejos = Venta.query.filter_by(estado='En espera', codigo_factura=None).count()
    return dict(pedidos_pendientes=count_facturas + count_viejos)

@admin_bp.route('/dashboard')
def dashboard():
    total_ventas_actual = db.session.query(func.sum(Venta.total)).scalar() or 0.0
    vendedoras_stats = db.session.query(
        Vendedor.nombre,
        func.coalesce(func.sum(Venta.total), 0).label('total')
    ).outerjoin(Venta).group_by(Vendedor.id).order_by(func.coalesce(func.sum(Venta.total), 0).desc()).all()

    mejor_vendedora = vendedoras_stats[0][0] if vendedoras_stats else "N/A"
    peor_vendedora = vendedoras_stats[-1][0] if len(vendedoras_stats) > 1 else (vendedoras_stats[0][0] if vendedoras_stats else "N/A")

    top_vendedoras = [v[0] for v in vendedoras_stats[:3]]
    top_vendedoras += ["N/A"] * (3 - len(top_vendedoras))

    meses_labels = ["Marzo", "Abril", "Mayo"]
    ventas_por_mes = [4500, 5200, total_ventas_actual]

    mes_actual = [float(v[1]) for v in vendedoras_stats[:3]]
    mes_actual += [0.0] * (3 - len(mes_actual))
    mes_anterior = [float(v * 0.85) for v in mes_actual]
    mes_tras_anterior = [float(v * 0.7) for v in mes_actual]

    producto_stats = db.session.query(
        Producto.nombre,
        func.coalesce(func.sum(Venta.cantidad), 0).label('cantidad')
    ).outerjoin(Venta).group_by(Producto.id).order_by(func.coalesce(func.sum(Venta.cantidad), 0).desc()).all()

    top_productos = [{'nombre': p[0], 'cantidad': int(p[1])} for p in producto_stats[:3]]
    bottom_productos = [{'nombre': p[0], 'cantidad': int(p[1])} for p in producto_stats[::-1][:3]]

    three_months_ago = datetime.now() - timedelta(days=90)
    ventas_vendedores_3m = db.session.query(
        Vendedor.nombre,
        func.coalesce(func.sum(Venta.total), 0).label('total')
    ).join(Venta).filter(Venta.fecha >= three_months_ago).group_by(Vendedor.id).order_by(func.coalesce(func.sum(Venta.total), 0).desc()).all()

    ventas_productos_3m = db.session.query(
        Producto.nombre,
        func.coalesce(func.sum(Venta.total), 0).label('total')
    ).join(Venta).filter(Venta.fecha >= three_months_ago).group_by(Producto.id).order_by(func.coalesce(func.sum(Venta.total), 0).desc()).all()

    reporte_ventas_vendedores = [{'nombre': v[0], 'total': float(v[1])} for v in ventas_vendedores_3m]
    reporte_ventas_productos = [{'nombre': p[0], 'total': float(p[1])} for p in ventas_productos_3m]
    reporte_ventas_total = sum(item['total'] for item in reporte_ventas_vendedores) if reporte_ventas_vendedores else sum(item['total'] for item in reporte_ventas_productos)

    comparativa_vendedoras = {
        "labels": top_vendedoras,
        "mes_actual": mes_actual,
        "mes_anterior": mes_anterior,
        "mes_tras_anterior": mes_tras_anterior
    }

    return render_template(
        'dashboard_admin.html', 
        total_ventas=total_ventas_actual,
        mejor_vendedora=mejor_vendedora,
        peor_vendedora=peor_vendedora,
        top_productos=top_productos,
        bottom_productos=bottom_productos,
        meses_labels=meses_labels,
        ventas_por_mes=ventas_por_mes,
        comparativa_vendedoras=comparativa_vendedoras,
        reporte_ventas_vendedores=reporte_ventas_vendedores,
        reporte_ventas_productos=reporte_ventas_productos,
        reporte_ventas_total=reporte_ventas_total,
        productos=Producto.query.all(),
        vendedores=Vendedor.query.all(),
        clientes=Cliente.query.all()
    )

@admin_bp.route('/reporte_inventario')
def reporte_inventario():
    productos = Producto.query.all()
    vendedores = Vendedor.query.filter_by(rol='vendedor').all()
    valor_central = sum(p.stock_central * p.precios for p in productos)
    valor_por_vendedora = {v.id: sum(inv.cantidad * inv.producto.precios for inv in v.inventario) for v in vendedores}
    alertas_stock = [p for p in productos if p.stock_central < 10]
    
    return render_template('reporte_inventario.html', 
                           productos=productos, 
                           vendedores=vendedores,
                           valor_central=valor_central,
                           valor_por_vendedora=valor_por_vendedora,
                           alertas_stock=alertas_stock)

@admin_bp.route('/trasladar_mercancia', methods=['POST'])
def trasladar_mercancia():
    id_producto = request.form.get('id_producto')
    id_vendedor = request.form.get('id_vendedor')
    cantidad = int(request.form.get('cantidad'))
    sentido = request.form.get('sentido') # 'CtoV' (Central to Vendor) o 'VtoC' (Vendor to Central)
    
    producto = Producto.query.get(id_producto)
    inv = InventarioVendedor.query.filter_by(id_vendedor=id_vendedor, id_producto=id_producto).first()
    
    if sentido == 'CtoV':
        if producto.stock_central >= cantidad:
            producto.stock_central -= cantidad
            if inv:
                inv.cantidad += cantidad
            else:
                db.session.add(InventarioVendedor(id_vendedor=id_vendedor, id_producto=id_producto, cantidad=cantidad))
            
            # Registrar Historial
            db.session.add(Traslado(id_producto=id_producto, id_vendedor=id_vendedor, tipo='Central -> Vendedora', cantidad=cantidad))
            db.session.commit()
            flash(f"Traslado a vendedor exitoso.", "success")
        else:
            flash("Error: Stock central insuficiente.", "danger")
            
    elif sentido == 'VtoC':
        if inv and inv.cantidad >= cantidad:
            inv.cantidad -= cantidad
            producto.stock_central += cantidad
            
            # Registrar Historial
            db.session.add(Traslado(id_producto=id_producto, id_vendedor=id_vendedor, tipo='Vendedora -> Central', cantidad=cantidad))
            db.session.commit()
            flash(f"Retorno a central exitoso.", "success")
        else:
            flash("Error: El vendedor no tiene suficiente stock en su maletín.", "danger")
        
    return redirect(url_for('admin.reporte_inventario'))

@admin_bp.route('/historial_traslados')
def historial_traslados():
    traslados = Traslado.query.order_by(Traslado.fecha.desc()).all()
    return render_template('historial_traslados.html', traslados=traslados)

@admin_bp.route('/gestion_pedidos')
def gestion_pedidos():
    vendedores = Vendedor.query.all()
    
    vendedor_id = request.args.get('vendedor_id')
    query = Venta.query
    if vendedor_id:
        query = query.filter_by(id_vendedor=vendedor_id)
    
    todas_ventas = query.order_by(Venta.fecha.desc()).all()
    
    # Agrupamiento por factura
    pedidos_dict = {}
    for v in todas_ventas:
        key = v.codigo_factura if v.codigo_factura else f"FAC-{v.id}"
        if key not in pedidos_dict:
            pedidos_dict[key] = {
                'codigo': key,
                'vendedor': v.vendedor,
                'cliente': v.cliente,
                'fecha': v.fecha,
                'estado': v.estado,
                'total': 0,
                'productos': []
            }
        pedidos_dict[key]['total'] += v.total
        pedidos_dict[key]['productos'].append({
            'nombre': v.producto.nombre,
            'cantidad': v.cantidad,
            'subtotal': v.total
        })
    
    # Lógica de Ciclos (del 5 al 4)
    ciclos = {}
    for data in pedidos_dict.values():
        fecha = data['fecha']
        if fecha.day < 5:
            mes_ciclo = (fecha.replace(day=1) - timedelta(days=1)).strftime('%B %Y')
        else:
            mes_ciclo = fecha.strftime('%B %Y')
        
        if mes_ciclo not in ciclos:
            ciclos[mes_ciclo] = []
        ciclos[mes_ciclo].append(data)

    # Convertir a lista ordenada para el template
    lista_ciclos = []
    for mes, facts in ciclos.items():
        lista_ciclos.append({
            'nombre_mes': mes,
            'pedidos': facts,
            'total_mes': sum(f['total'] for f in facts)
        })

    return render_template('ventas_recibidas.html', 
                         vendedores=vendedores, 
                         ciclos=lista_ciclos)

@admin_bp.route('/actualizar_pedido/<string:codigo_f>/<string:nuevo_estado>')
def actualizar_pedido(codigo_f, nuevo_estado):
    if codigo_f.startswith('FAC-'):
        id_v = int(codigo_f.split('-')[1])
        ventas_a_actualizar = [Venta.query.get(id_v)]
    else:
        ventas_a_actualizar = Venta.query.filter_by(codigo_factura=codigo_f).all()
        
    for v in ventas_a_actualizar:
        if v:
            v.estado = nuevo_estado
    
    db.session.commit()
    flash(f"Factura {codigo_f} ahora está '{nuevo_estado}'.", "success")
    return redirect(url_for('admin.gestion_pedidos'))

@admin_bp.route('/nuevo_producto', methods=['GET', 'POST'])
def nuevo_producto():
    if request.method == 'POST':
        nuevo = Producto(
            codigo=request.form['codigo'], 
            nombre=request.form['nombre'], 
            categoria=request.form['categoria'], 
            precios=float(request.form['precio']), 
            comision=float(request.form['comision']),
            stock_central=int(request.form['stock'])
        )
        db.session.add(nuevo)
        db.session.commit()
        flash(f"Producto '{nuevo.nombre}' registrado con éxito.", "success")
        return redirect(url_for('admin.reporte_inventario'))
    return render_template('admin_nuevo_producto.html')

@admin_bp.route('/nuevo_cliente', methods=['GET', 'POST'])
def nuevo_cliente():
    if request.method == 'POST':
        try:
            rif = format_identificacion(request.form['rif_tipo'], request.form['rif_numero'])
            telefono = format_telefono(request.form['telefono_prefijo'], request.form['telefono_num'])
            nuevo = Cliente(
                rif=rif,
                nombre=request.form['nombre'],
                direccion=request.form['direccion'],
                telefono=telefono,
                estado=request.form['estado']
            )
            db.session.add(nuevo)
            db.session.commit()
            flash(f"Cliente '{nuevo.nombre}' registrado con éxito.", "success")
            return redirect(url_for('admin.nuevo_cliente'))
        except ValueError as e:
            flash(str(e), "danger")
            return redirect(url_for('admin.nuevo_cliente'))
    return render_template('admin_nuevo_cliente.html')

@admin_bp.route('/nuevo_vendedor', methods=['GET', 'POST'])
def nuevo_vendedor():
    if request.method == 'POST':
        try:
            cedula = format_identificacion(request.form['cedula_tipo'], request.form['cedula_numero'])
            rol = request.form.get('rol', 'vendedor')
            nuevo = Vendedor(
                cedula=cedula,
                nombre=request.form['nombre'],
                usuario=request.form['usuario'],
                password=generate_password_hash(request.form['password']),
                rol=rol,
                zona=request.form['zona']
            )
            db.session.add(nuevo)
            db.session.commit()
            flash(f"Vendedor '{nuevo.nombre}' registrado con éxito.", "success")
            return redirect(url_for('admin.nuevo_vendedor'))
        except ValueError as e:
            flash(str(e), "danger")
            return redirect(url_for('admin.nuevo_vendedor'))
    productos = Producto.query.all()
    return render_template('admin_nuevo_vendedor.html', productos=productos)

@admin_bp.route('/directorio')
def directorio():
    vendedores = Vendedor.query.all()
    clientes = Cliente.query.all()
    return render_template('admin_directorio.html', vendedores=vendedores, clientes=clientes)

@admin_bp.route('/editar_producto/<int:id>', methods=['GET', 'POST'])
def editar_producto(id):
    producto = Producto.query.get_or_404(id)
    if request.method == 'POST':
        producto.codigo = request.form['codigo']
        producto.nombre = request.form['nombre']
        producto.categoria = request.form['categoria']
        producto.precios = float(request.form['precio'])
        producto.comision = float(request.form['comision'])
        producto.stock_central = int(request.form['stock'])
        db.session.commit()
        flash(f"Producto '{producto.nombre}' actualizado con éxito.", "success")
        return redirect(url_for('admin.reporte_inventario'))
    return render_template('admin_editar_producto.html', producto=producto)

@admin_bp.route('/editar_vendedor/<int:id>', methods=['GET', 'POST'])
def editar_vendedor(id):
    vendedor = Vendedor.query.get_or_404(id)
    if request.method == 'POST':
        try:
            vendedor.cedula = format_identificacion(request.form['cedula_tipo'], request.form['cedula_numero'])
            vendedor.nombre = request.form['nombre']
            vendedor.usuario = request.form['usuario']
            if request.form.get('password'):
                vendedor.password = generate_password_hash(request.form['password'])
            if request.form.get('rol'):
                vendedor.rol = request.form['rol']
            vendedor.zona = request.form['zona']
            db.session.commit()
            flash(f"Usuario '{vendedor.nombre}' actualizado con éxito.", "success")
            return redirect(url_for('admin.directorio'))
        except ValueError as e:
            flash(str(e), "danger")
            return redirect(url_for('admin.editar_vendedor', id=id))
    return render_template('admin_editar_vendedor.html', vendedor=vendedor)

@admin_bp.route('/editar_cliente/<int:id>', methods=['GET', 'POST'])
def editar_cliente(id):
    cliente = Cliente.query.get_or_404(id)
    if request.method == 'POST':
        try:
            cliente.rif = format_identificacion(request.form['rif_tipo'], request.form['rif_numero'])
            cliente.nombre = request.form['nombre']
            cliente.direccion = request.form['direccion']
            cliente.telefono = format_telefono(request.form['telefono_prefijo'], request.form['telefono_num'])
            cliente.estado = request.form['estado']
            db.session.commit()
            flash(f"Cliente '{cliente.nombre}' actualizado con éxito.", "success")
            return redirect(url_for('admin.directorio'))
        except ValueError as e:
            flash(str(e), "danger")
            return redirect(url_for('admin.editar_cliente', id=id))
    return render_template('admin_editar_cliente.html', cliente=cliente)