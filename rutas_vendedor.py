from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models import db, Producto, Cliente, InventarioVendedor, Venta, Vendedor


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


vendedor_bp = Blueprint('vendedor', __name__, url_prefix='/vendedor')

@vendedor_bp.before_request
def require_login():
    if 'user_id' not in session:
        flash("Debes iniciar sesión para acceder a esta página.", "warning")
        return redirect(url_for('auth.login'))

@vendedor_bp.route('/dashboard')
def dashboard():
    id_vendedor = session['user_id']
    vendedor = Vendedor.query.get(id_vendedor)
    nombre = vendedor.nombre if vendedor else "Alejandra Pérez"
    iniciales = "".join([n[0] for n in nombre.split()])[:2].upper()
    
    # Cálculo de comisiones
    ventas_vendedor = Venta.query.filter_by(id_vendedor=id_vendedor).all()
    comisiones = sum((v.total * (v.producto.comision or 0) / 100) for v in ventas_vendedor)
    
    # Top 3 Productos (por cantidad vendida)
    from sqlalchemy import func, and_, outerjoin
    # Hacemos un LEFT OUTER JOIN incluyendo la condición del vendedor en la cláusula ON
    prod_join = outerjoin(Producto, Venta, and_(Venta.id_producto == Producto.id, Venta.id_vendedor == id_vendedor))
    top_productos_query = db.session.query(
        Producto.nombre,
        func.coalesce(func.sum(Venta.cantidad), 0).label('total')
    ).select_from(prod_join).group_by(Producto.id).order_by(func.coalesce(func.sum(Venta.cantidad), 0).desc()).limit(3).all()
    top_productos_list = [[p[0], int(p[1])] for p in top_productos_query]

    # Top 3 Clientes (por cantidad de compras)
    top_clientes_query = db.session.query(
        Cliente.nombre, func.count(Venta.id).label('total')
    ).join(Venta).filter(Venta.id_vendedor == id_vendedor).group_by(Cliente.id).order_by(func.count(Venta.id).desc()).limit(3).all()
    top_clientes_list = [[c[0], int(c[1])] for c in top_clientes_query]

    # Productos con poco stock en el maletín (Top 3)
    stock_bajo = InventarioVendedor.query.filter_by(id_vendedor=id_vendedor).order_by(InventarioVendedor.cantidad.asc()).limit(3).all()

    # Actividad reciente (últimas 5 ventas)
    actividad = Venta.query.filter_by(id_vendedor=id_vendedor).order_by(Venta.fecha.desc()).limit(5).all()

    return render_template(
        'dashboard_vendedor.html', 
        nombre_vendedor=nombre,
        iniciales=iniciales,
        comisiones="{:,.2f}".format(comisiones),
        top_productos=top_productos_list,
        top_clientes=top_clientes_list,
        stock_bajo=stock_bajo,
        actividad=actividad
    )

@vendedor_bp.route('/inventario')
def inventario():
    id_vendedor = session['user_id']
    # Obtener inventario personal
    inventario = InventarioVendedor.query.filter_by(id_vendedor=id_vendedor).all()
    
    # Filtros por URL
    sort = request.args.get('sort', 'nombre') # nombre, cantidad_asc, cantidad_desc
    cat = request.args.get('cat', '')

    if cat:
        inventario = [item for item in inventario if item.producto.categoria == cat]
    
    if sort == 'nombre':
        inventario.sort(key=lambda x: x.producto.nombre)
    elif sort == 'cantidad_asc':
        inventario.sort(key=lambda x: x.cantidad)
    elif sort == 'cantidad_desc':
        inventario.sort(key=lambda x: x.cantidad, reverse=True)

    categorias = db.session.query(Producto.categoria).distinct().all()
    categorias = [c[0] for c in categorias]

    return render_template('vendedores_inventario.html', inventario=inventario, categorias=categorias)

@vendedor_bp.route('/reporte_ventas')
def reporte_ventas():
    id_vendedor = session['user_id']
    todas_ventas = Venta.query.filter_by(id_vendedor=id_vendedor).order_by(Venta.fecha.desc()).all()
    
    # Agrupar por factura
    facturas_dict = {}
    for v in todas_ventas:
        key = v.codigo_factura if v.codigo_factura else f"FAC-{v.id}"
        if key not in facturas_dict:
            facturas_dict[key] = {
                'codigo': key,
                'cliente': v.cliente,
                'fecha': v.fecha,
                'estado': v.estado,
                'total_venta': 0,
                'comision_total': 0,
                'productos': []
            }
        facturas_dict[key]['total_venta'] += v.total
        facturas_dict[key]['comision_total'] += (v.total * (v.producto.comision or 0) / 100)
        facturas_dict[key]['productos'].append({
            'nombre': v.producto.nombre,
            'cantidad': v.cantidad,
            'comision_p': v.producto.comision
        })

    # Lógica de Meses/Ciclos (del 5 al 4)
    ciclos = {}
    for f_code, data in facturas_dict.items():
        fecha = data['fecha']
        # Si es antes del 5, pertenece al ciclo del mes anterior
        if fecha.day < 5:
            # Ciclo que inició el 5 del mes anterior
            mes_ciclo = (fecha.replace(day=1) - timedelta(days=1)).strftime('%B %Y')
        else:
            # Ciclo que inició el 5 de este mes
            mes_ciclo = fecha.strftime('%B %Y')
        
        if mes_ciclo not in ciclos:
            ciclos[mes_ciclo] = []
        ciclos[mes_ciclo].append(data)

    # Ordenar ciclos por fecha (el más reciente primero)
    # Convertimos a lista de tuplas para el template
    lista_ciclos = []
    for mes, facts in ciclos.items():
        lista_ciclos.append({
            'nombre_mes': mes,
            'facturas': facts,
            'total_mes': sum(f['total_venta'] for f in facts),
            'comision_mes': sum(f['comision_total'] for f in facts)
        })

    clientes = Cliente.query.all()
    
    return render_template('vendedor_reporte_ventas.html', ciclos=lista_ciclos, clientes=clientes)

@vendedor_bp.route('/nueva_venta', methods=['GET', 'POST'])
def nueva_venta():
    id_vendedora_actual = session['user_id']

    if request.method == 'POST':
        cliente_raw = request.form.get('cliente_nombre')
        origen = request.form.get('origen', 'maletin')  # 'maletin' or 'bta'
        cliente_nombre = cliente_raw.split('|')[0].strip() if cliente_raw and '|' in cliente_raw else (cliente_raw or '').strip()
        cliente = None
        if cliente_nombre:
            cliente = Cliente.query.filter(
                (Cliente.nombre.ilike(f"%{cliente_nombre}%")) |
                (Cliente.rif.ilike(f"%{cliente_nombre}%"))
            ).first()

        if not cliente:
            flash(f"Error: No se encontró al cliente '{cliente_nombre}'.", "danger")
            return redirect(url_for('vendedor.nueva_venta'))

        nombres_productos_raw = request.form.getlist('producto_nombre[]')
        cantidades = request.form.getlist('cantidad[]')

        try:
            import datetime
            import random
            # Generar un código único para esta factura (Ej: F-20231027-X123)
            now = datetime.datetime.now()
            codigo_f = f"F-{now.strftime('%y%m%d%H%M')}-{random.randint(100, 999)}"

            for i in range(len(nombres_productos_raw)):
                raw_p = nombres_productos_raw[i]
                p_nombre = raw_p.split('|')[0].strip() if '|' in raw_p else raw_p.strip()
                p_cantidad = int(cantidades[i])

                producto = Producto.query.filter(Producto.nombre.ilike(f"%{p_nombre}%")).first()

                if not producto:
                    flash(f"Producto '{p_nombre}' no encontrado.", "warning")
                    continue

                if origen == 'bta':
                    # Usar stock central (Producto.stock_central)
                    stock_disponible = producto.stock_central or 0
                    if stock_disponible >= p_cantidad:
                        producto.stock_central = stock_disponible - p_cantidad
                        db.session.add(producto)
                        nueva_v = Venta(
                            codigo_factura=codigo_f,
                            id_vendedor=id_vendedora_actual,
                            id_cliente=cliente.id,
                            id_producto=producto.id,
                            cantidad=p_cantidad,
                            total=producto.precios * p_cantidad
                        )
                        db.session.add(nueva_v)
                    else:
                        flash(f"Stock insuficiente en BTA para {p_nombre}. Disponible: {stock_disponible}.", "danger")
                else:
                    inv = InventarioVendedor.query.filter_by(
                        id_vendedor=id_vendedora_actual, 
                        id_producto=producto.id
                    ).first()

                    stock_disponible = inv.cantidad if inv else 0

                    if stock_disponible >= p_cantidad:
                        if inv:
                            inv.cantidad -= p_cantidad
                            db.session.add(inv)
                        nueva_v = Venta(
                            codigo_factura=codigo_f,
                            id_vendedor=id_vendedora_actual,
                            id_cliente=cliente.id,
                            id_producto=producto.id,
                            cantidad=p_cantidad,
                            total=producto.precios * p_cantidad
                        )
                        db.session.add(nueva_v)
                    else:
                        flash(f"Stock insuficiente para {p_nombre}. Tienes {stock_disponible} en maletín.", "danger")
            
            db.session.commit()
            flash(f"Venta registrada con éxito (Factura: {codigo_f}). Enviada a central.", "success")
            return redirect(url_for('vendedor.dashboard'))

        except Exception as e:
            db.session.rollback()
            flash(f"Error en el proceso: {str(e)}", "danger")
            return redirect(url_for('vendedor.nueva_venta'))

    # Ahora mostramos TODOS los productos para que no se "pierdan" los nuevos
    lista_productos = Producto.query.all()
    lista_clientes = Cliente.query.all()
    
    return render_template(
        'vendedor_nueva_venta.html', 
        lista_productos=lista_productos, 
        lista_clientes=lista_clientes
    )

@vendedor_bp.route('/editar_factura/<string:codigo_f>', methods=['GET', 'POST'])
def editar_factura(codigo_f):
    id_vendedora_actual = session['user_id']
    ventas_existentes = Venta.query.filter_by(codigo_factura=codigo_f, id_vendedor=id_vendedora_actual).all()
    
    if not ventas_existentes:
        flash("Factura no encontrada.", "danger")
        return redirect(url_for('vendedor.reporte_ventas'))
        
    if ventas_existentes[0].estado != 'En espera':
        flash("Solo puedes editar facturas que están En espera.", "warning")
        return redirect(url_for('vendedor.reporte_ventas'))

    if request.method == 'POST':
        cliente_raw = request.form.get('cliente_nombre')
        cliente_nombre = cliente_raw.split('|')[0].strip() if '|' in cliente_raw else cliente_raw.strip()
        cliente = Cliente.query.filter_by(nombre=cliente_nombre).first()
        
        if not cliente:
            flash(f"Error: No se encontró al cliente '{cliente_nombre}'.", "danger")
            return redirect(url_for('vendedor.editar_factura', codigo_f=codigo_f))

        nombres_productos_raw = request.form.getlist('producto_nombre[]')
        cantidades = request.form.getlist('cantidad[]')

        try:
            # Revertir inventario de la factura original
            for v in ventas_existentes:
                inv = InventarioVendedor.query.filter_by(id_vendedor=id_vendedora_actual, id_producto=v.id_producto).first()
                if inv:
                    inv.cantidad += v.cantidad
                db.session.delete(v)
            
            db.session.flush()

            # Procesar los nuevos items
            for i in range(len(nombres_productos_raw)):
                raw_p = nombres_productos_raw[i]
                p_nombre = raw_p.split('|')[0].strip() if '|' in raw_p else raw_p.strip()
                p_cantidad = int(cantidades[i])

                producto = Producto.query.filter_by(nombre=p_nombre).first()
                if not producto:
                    continue

                inv = InventarioVendedor.query.filter_by(id_vendedor=id_vendedora_actual, id_producto=producto.id).first()
                stock_disponible = inv.cantidad if inv else 0

                if stock_disponible >= p_cantidad:
                    if inv:
                        inv.cantidad -= p_cantidad
                    
                    nueva_v = Venta(
                        codigo_factura=codigo_f,
                        id_vendedor=id_vendedora_actual,
                        id_cliente=cliente.id,
                        id_producto=producto.id,
                        cantidad=p_cantidad,
                        total=producto.precios * p_cantidad,
                        estado='En espera',
                        fecha=ventas_existentes[0].fecha
                    )
                    db.session.add(nueva_v)
                else:
                    db.session.rollback()
                    flash(f"Stock insuficiente para {p_nombre}. Tienes {stock_disponible} en maletín.", "danger")
                    return redirect(url_for('vendedor.editar_factura', codigo_f=codigo_f))
            
            db.session.commit()
            flash(f"Factura {codigo_f} actualizada con éxito.", "success")
            return redirect(url_for('vendedor.reporte_ventas'))

        except Exception as e:
            db.session.rollback()
            flash(f"Error al actualizar la factura: {str(e)}", "danger")
            return redirect(url_for('vendedor.editar_factura', codigo_f=codigo_f))

    factura_obj = {
        'codigo': codigo_f,
        'cliente': ventas_existentes[0].cliente.nombre,
        'productos': [{'nombre': v.producto.nombre, 'cantidad': v.cantidad} for v in ventas_existentes]
    }
    
    lista_productos = Producto.query.all()
    lista_clientes = Cliente.query.all()
    
    return render_template(
        'vendedor_nueva_venta.html', 
        lista_productos=lista_productos, 
        lista_clientes=lista_clientes,
        factura_obj=factura_obj
    )

@vendedor_bp.route('/nuevo_cliente', methods=['GET', 'POST'])
def nuevo_cliente():
    if request.method == 'POST':
        try:
            nombre = request.form.get('nombre')
            rif = format_identificacion(request.form.get('rif_tipo'), request.form.get('rif_numero'))
            telefono = format_telefono(request.form.get('telefono_prefijo'), request.form.get('telefono_num'))
            direccion = request.form.get('direccion')
            estado = request.form.get('estado')

            nuevo_cliente = Cliente(
                nombre=nombre,
                rif=rif,
                telefono=telefono,
                direccion=direccion,
                estado=estado
            )
            db.session.add(nuevo_cliente)
            db.session.commit()

            flash("Cliente registrado con éxito. Ya puedes seleccionarlo.", "success")
            return redirect(url_for('vendedor.nueva_venta'))
        except ValueError as e:
            db.session.rollback()
            flash(str(e), "danger")
            return redirect(url_for('vendedor.nuevo_cliente'))
        except Exception as e:
            db.session.rollback()
            flash(f"Error al registrar cliente: {str(e)}", "danger")
            return redirect(url_for('vendedor.nuevo_cliente'))

    return render_template('vendedor_nuevo_cliente.html')