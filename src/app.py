from flask import Flask, render_template, redirect, url_for, request, session, flash, send_file
from flask_wtf.csrf import CSRFProtect
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models.ModelUser import ModelUser
from models.entities.User import User
from config import config
import oracledb
import re
import pandas as pd

app = Flask(__name__)
csrf=CSRFProtect()
oracledb.init_oracle_client()
login_manager_app = LoginManager(app)

pool = oracledb.SessionPool(
    user='PROYECTO',
    password='123456',
    dsn= 'PROYECTO/123456@localhost:1521/xe',
    min=2,
    max=5,
    increment=1,
    encoding="UTF-8")


@login_manager_app.user_loader
def load_user(id):
    return ModelUser.get_by_id(pool, id)

@app.route('/')
def index():
    return redirect(url_for('home'))


@app.route('/home')
def home():
    if 'cliente' in session:
        session.clear()
    return render_template('home.html')


@app.route('/inicio_pedido', methods=['GET', 'POST'])
def inicio_pedido(): 
    if request.method=="POST":
        rut = request.form['rut_cliente']
        nombre = request.form['nombre_cliente']
        apellido = request.form['apellido_cliente']
        direccion = request.form['direccion_cliente']
        telefono = request.form['telefono_cliente']

        validacion = re.findall('^(\\d{1,3}(?:\\.\\d{3}){2}-[\\dkK])$', rut)
        if len(validacion) == 1:

            session['cliente'] = {'rut': rut, 'nombre': nombre, 'apellido': apellido,
                                'direccion': direccion, 'telefono': telefono}
            
            return redirect(url_for('menu'))
        else:
            flash('El rut debe tener el siguiente formato ej: (11.111.111-1)')
            return render_template('cliente.html')
    else:
        return render_template('cliente.html')


@app.route('/error', methods=['GET'])
def error():
    return render_template('error.html')

@app.route('/descargar_reporte')
@login_required
def descargar_reporte():
    conn = pool.acquire()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM REPORTE")
    data = cursor.fetchall()
    encabezados = [i[0] for i in cursor.description]
    cursor.close()
    pool.release(conn)

    df = pd.DataFrame(data, columns=encabezados)
    df.to_csv('src/files/reporte_hamburgesotas.csv', index=False)

    return send_file('files/reporte_hamburgesotas.csv', mimetype='text/csv',
                    download_name= 'reporte_hamburgesotas.csv', as_attachment=True)


@app.route('/ver_stock')
@login_required
def ver_stock():
    conn = pool.acquire()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM PRODUCTO WHERE STOCK <= STOCK_MIN")
    data = cursor.fetchall()
    res = [dict((cursor.description[i][0], value) for i, value in enumerate(row)) for row in data]
    cursor.close()
    pool.release(conn)

    return render_template('modif_stock.html', productos=res)

@app.route('/agregar_stock', methods=['POST'])
@login_required
def agregar_stock():
    _cantidad = int(request.form['cantidad'])
    _codigo = request.form['codigo']

    if _cantidad and _codigo and request.method == 'POST':

        conn = pool.acquire()
        cursor = conn.cursor()
        try: 
            cursor.callproc('AGREGAR_STOCK',[_codigo, _cantidad])

        except oracledb.DatabaseError as e:
            error_obj, = e.args
            print("Error Code:", error_obj.code)
            conn.rollback()
        else:
            cursor.close()
            conn.commit()
            pool.release(conn)
            return redirect(url_for('ver_stock'))
    else:
        return 'error'

@app.route('/menu_admin', methods=['GET'])
@login_required
def menu_admin():
    return render_template('menu_admin.html', admin= current_user.usuario)


@app.route('/administradores', methods=['GET', 'POST'])
def administradores():
    if request.method=="POST":
        _usuario = request.form['usuario']
        _password = request.form['contraseña']

        user = User(0, _usuario, _password)
        logged_user = ModelUser.login(pool, user)
        if logged_user != None:
            if logged_user.password:
                login_user(logged_user)
                return redirect(url_for('menu_admin'))
            else:
                flash("Clave Invalida...")
            return render_template('login.html')
        else:
            flash("Usuario no Encontrado...")
            return render_template('login.html')

    else:
        return render_template('login.html')

@app.route('/menu', methods=['GET'])
def menu():
    if 'cliente' in session:
        return render_template('menu.html')
    return redirect(url_for('error'))

@app.route('/productos/<string:categoria>')
def productos(categoria):
    if 'cliente' in session:
        conn = pool.acquire()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM PRODUCTO WHERE CATEGORIA=(:0)", (categoria,))
        data = cursor.fetchall()
        res = [dict((cursor.description[i][0], value) for i, value in enumerate(row)) for row in data]
        cursor.close()
        pool.release(conn)

        return render_template('productos.html', productos=res)
    else:
        return redirect(url_for('error'))

@app.route('/agregar', methods=['POST'])
def agregar_producto_al_carrito():
    _cantidad = int(request.form['cantidad'])
    _codigo = request.form['codigo']
    _categoria = request.form['categoria']

    if _cantidad and _codigo and request.method == 'POST':
        conn = pool.acquire()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM PRODUCTO WHERE CODIGO=(:0)", (_codigo,))
        data = cursor.fetchone()
        res = dict((cursor.description[i][0], value) for i, value in enumerate(data))
        cursor.close()
        pool.release(conn)

        item = {res['CODIGO'] : {'nombre' : res['NOMBRE'], 'codigo' : res['CODIGO'],
                'cantidad' : _cantidad, 'precio' : res['PRECIO'], 'imagen' : res['IMAGEN'],
                'impuesto': _cantidad * (res['PRECIO'] * 0.19), 'total_precio': _cantidad * res['PRECIO'] }}

        precio_pedido_completo = 0
        cantidad_pedido_completa = 0
        iva_pedido_completo = 0
                 
        if 'pedido' in session:
            if res['CODIGO'] in session['pedido']:
                total_cantidad = session['pedido'][res['CODIGO']]['cantidad'] + _cantidad
                session['pedido'][res['CODIGO']]['cantidad'] = total_cantidad
                session['pedido'][res['CODIGO']]['total_precio'] = total_cantidad * res['PRECIO']
                session['pedido'][res['CODIGO']]['impuesto'] = total_cantidad * (res['PRECIO'] * 0.19)

            else:
                session['pedido'][res['CODIGO']] = item[res['CODIGO']]

            precio_pedido_completo = sum(map(lambda x: session['pedido'][x]['total_precio'] , session['pedido']))
            cantidad_pedido_completa = sum(map(lambda x: session['pedido'][x]['cantidad'] , session['pedido']))
            iva_pedido_completo = sum(map(lambda x: session['pedido'][x]['impuesto'] , session['pedido']))
            
        else:
            session['pedido'] = item
            cantidad_pedido_completa += _cantidad
            precio_pedido_completo  += _cantidad * res['PRECIO']
            iva_pedido_completo +=  _cantidad * (res['PRECIO'] * 0.19)
             
        session['precio_pedido_completo'] = precio_pedido_completo
        session['cantidad_pedido_completa'] = cantidad_pedido_completa
        session['iva_pedido_completo'] = iva_pedido_completo
        session['total_pedido'] = precio_pedido_completo + iva_pedido_completo
                 
        return redirect(url_for('productos', categoria=_categoria))
    return 'Error'

@app.route('/confirmacion_pedido', methods=['GET'])
def confirmacion_pedido():
    if 'cliente' in session:
        if 'pedido' in session:
            return render_template('carrito.html')
        else:
            flash('TU CARRITO ESTA VACIO!')
            return redirect(url_for('menu'))
    return redirect(url_for('error'))

@app.route('/eliminar/<string:codigo>')
def eliminar_producto(codigo):
    precio_pedido_completo = 0
    cantidad_pedido_completa = 0
    iva_pedido_completo = 0

    item = session['pedido'][codigo]
    if item['cantidad'] == 1:
        session['pedido'].pop(codigo, None)
    else:
        session['pedido'][codigo]['cantidad'] -= 1
        session['pedido'][codigo]['total_precio'] = session['pedido'][codigo]['cantidad'] * session['pedido'][codigo]['precio']
        session['pedido'][codigo]['impuesto'] = session['pedido'][codigo]['cantidad'] * session['pedido'][codigo]['precio'] * 0.19

         
    if 'pedido' in session:
        precio_pedido_completo = sum(map(lambda x: session['pedido'][x]['total_precio'] , session['pedido']))
        cantidad_pedido_completa = sum(map(lambda x: session['pedido'][x]['cantidad'] , session['pedido']))
        iva_pedido_completo = sum(map(lambda x: session['pedido'][x]['impuesto'] , session['pedido']))
        
    if cantidad_pedido_completa == 0:
        session.pop('pedido', None)
        session['precio_pedido_completo'] = 0
        session['cantidad_pedido_completa'] = 0
        session['iva_pedido_completo'] = 0
        session['total_pedido'] = 0

    else:
        session['precio_pedido_completo'] = precio_pedido_completo
        session['cantidad_pedido_completa'] = cantidad_pedido_completa
        session['iva_pedido_completo'] = iva_pedido_completo
        session['total_pedido'] = precio_pedido_completo + iva_pedido_completo
            
    return redirect(url_for('confirmacion_pedido'))


@app.route('/eliminar_carrito')
def eliminar_carrito():
    session.pop('pedido', None)
    session['precio_pedido_completo'] = 0
    session['cantidad_pedido_completa'] = 0
    session['iva_pedido_completo'] = 0
    session['total_pedido'] = 0
    return redirect(url_for('confirmacion_pedido'))

@app.route('/boleta', methods=['GET'])
def boleta():
    if 'cliente' in session:
        if 'pedido' in session:
            return render_template('boletita.html')
        else:
            flash('TU CARRITO ESTA VACIO!')
            return redirect(url_for('menu'))
    return redirect(url_for('error'))


@app.route('/error_pedido/<int:error>', methods=['GET'])
def error_pedido(error):
    if error == 20004:
        mensaje = 'PEDIDO CANCELADO POR FALTA DE STOCK. VUELVE A INGRESAR Y MODIFICAR TU PEDIDO.'
    return render_template('error_pedido.html', mensaje=mensaje)   

@app.route('/pagar', methods=['GET'])
def pagar():
    if 'cliente' in session:
        if 'pedido' in session:
            conn = pool.acquire()
            cursor = conn.cursor()
            try: 
                cursor.callproc('INGRESAR_CLIENTE', [session['cliente']['rut'],
                                                    session['cliente']['nombre'],
                                                    session['cliente']['apellido'],
                                                    session['cliente']['direccion'],
                                                    session['cliente']['telefono']])

                cursor.callproc('VENDER',[session['cliente']['rut'],
                                        session['precio_pedido_completo'],
                                        session['iva_pedido_completo'],
                                        session['total_pedido']])
                contador = 0
                for key, value in session['pedido'].items():
                    cursor.callproc('VENDER_DETALLE',[contador, value['codigo'], value['cantidad'],
                                                    value['precio'], value['total_precio']])
                    contador+=1

            except oracledb.DatabaseError as e:
                error_obj, = e.args
                print("Error Code:", error_obj.code)
                cursor.close()
                conn.rollback()
                pool.release(conn)
            else:
                cursor.close()
                conn.commit()
                pool.release(conn)
                return redirect(url_for('boleta'))

        else:
            flash('TU CARRITO ESTA VACIO!')
            return redirect(url_for('menu'))
    return redirect(url_for('error_pedido', error=error_obj.code))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/logout_admin')
def logout_admin():
    logout_user()
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.config.from_object(config['development'])
    csrf.init_app(app)
    app.run()

