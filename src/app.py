from flask import Flask, render_template, redirect, url_for, request, session, flash
from flask_wtf.csrf import CSRFProtect
from config import config
import oracledb

app = Flask(__name__)
csrf=CSRFProtect()
oracledb.init_oracle_client()


pool = oracledb.SessionPool(
    user='PROYECTO',
    password='123456',
    dsn= 'PROYECTO/123456@localhost:1521/xe',
    min=2,
    max=5,
    increment=1,
    encoding="UTF-8")


@app.route('/')
def index():
    return redirect(url_for('home'))


@app.route('/home')
def home():
    return render_template('home.html')


@app.route('/inicio_pedido', methods=['GET', 'POST'])
def inicio_pedido(): 
    if request.method=="POST":
        rut = request.form['rut_cliente']
        nombre = request.form['nombre_cliente']
        apellido = request.form['apellido_cliente']
        direccion = request.form['direccion_cliente']
        telefono = request.form['telefono_cliente']

        session['cliente'] = {'rut': rut, 'nombre': nombre, 'apellido': apellido,
                            'direccion': direccion, 'telefono': telefono}
        
        return redirect(url_for('menu'))
    else:
        return render_template('cliente.html')


@app.route('/error', methods=['GET'])
def error():
    return render_template('error.html')

@app.route('/descargar_reporte')
def descargar_reporte():
    return "holi"
    #return send_file(ruta_archivo,mimetype='text/csv',download_name = filename, as_attachment=True)

@app.route('/administradores', methods=['GET', 'POST'])
def administradores():
    if request.method=="POST":
        _usuario = request.form['usuario']
        _password = request.form['contraseña']
        conn = pool.acquire()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM ADMINISTRADORES WHERE USUARIO=(:0) AND CLAVE=(:1)", (_usuario, _password))
        data = cursor.fetchone()
        cursor.close()
        pool.release(conn)
        if data != None:
                return render_template('reporte.html', admin=_usuario)
        else:
            flash("Usuario o Clave Invalidos....")
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
                'total_precio': _cantidad * res['PRECIO']}}

        precio_pedido_completo = 0
        cantidad_pedido_completa = 0
                 
        if 'pedido' in session:
            if res['CODIGO'] in session['pedido']:
                total_cantidad = session['pedido'][res['CODIGO']]['cantidad'] + _cantidad
                session['pedido'][res['CODIGO']]['cantidad'] = total_cantidad
                session['pedido'][res['CODIGO']]['total_precio'] = total_cantidad * res['PRECIO']

            else:
                session['pedido'][res['CODIGO']] = item[res['CODIGO']]
         
            cantidad_pedido_completa = sum(map(lambda x: session['pedido'][x]['cantidad'] , session['pedido']))
            precio_pedido_completo = sum(map(lambda x: session['pedido'][x]['total_precio'] , session['pedido']))
        else:
            session['pedido'] = item
            cantidad_pedido_completa += _cantidad
            precio_pedido_completo  += _cantidad * res['PRECIO']
             
        session['precio_pedido_completo'] = precio_pedido_completo
        session['cantidad_pedido_completa'] = cantidad_pedido_completa
                 
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

    item = session['pedido'][codigo]
    if item['cantidad'] == 1:
        session['pedido'].pop(codigo, None)
    else:
        session['pedido'][codigo]['cantidad'] -= 1
        session['pedido'][codigo]['total_precio'] = session['pedido'][codigo]['cantidad'] * session['pedido'][codigo]['precio']

         
    if 'pedido' in session:
        cantidad_pedido_completa = sum(map(lambda x: session['pedido'][x]['cantidad'] , session['pedido']))
        precio_pedido_completo = sum(map(lambda x: session['pedido'][x]['total_precio'] , session['pedido']))
        
    if cantidad_pedido_completa == 0:
        session.pop('pedido', None)
        session['precio_pedido_completo'] = 0
        session['cantidad_pedido_completa'] = 0

    else:
        session['precio_pedido_completo'] = precio_pedido_completo
        session['cantidad_pedido_completa'] = cantidad_pedido_completa
            
    return redirect(url_for('confirmacion_pedido'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.config.from_object(config['development'])
    csrf.init_app(app)
    app.run()

