# app.py
import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from sqlalchemy import text
from db import engine
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'clave_defecto_para_dev')


@app.route('/')
def index():
    """
    Página principal: muestra el formulario de login si no hay sesión,
    o el menú principal si ya existe sesión.
    """
    return render_template('index.html')


@app.route('/login', methods=['POST'])
def login():
    """
    Procesa el login usando la tabla `beneficiario` de la base local.
    Solo verifica que el RUT exista. (No hay columna 'clave' en init.sql).
    """
    rut = request.form.get('rut', '').strip()
    clave = request.form.get('clave', '').strip()

    if not rut:
        flash("Por favor ingresa RUT.", "error")
        return redirect(url_for('index'))

    # Conectamos a la base local y buscamos el beneficiario por rut
    with engine.connect() as conn:
        stmt = text("SELECT nombre, tramo_ingreso FROM beneficiario WHERE rut = :rut")
        result = conn.execute(stmt, {"rut": rut}).mappings().first()

    if not result:
        flash("RUT no encontrado en la base local.", "error")
        return redirect(url_for('index'))

    # Como init.sql no incluye clave, omitimos validación de contraseña.
    # Si quieres validar clave, agrega la columna 'clave' y modifica la consulta.

    session['rut'] = rut
    session['nombre'] = result['nombre']
    session['tramo'] = result['tramo_ingreso']

    flash(f"Bienvenido, {session['nombre']} (Tramo {session['tramo']})", "success")
    return redirect(url_for('index'))


@app.route('/logout')
def logout():
    """
    Cierra la sesión y redirige al login.
    """
    session.clear()
    flash("Has cerrado sesión.", "info")
    return redirect(url_for('index'))


@app.route('/actualizar_datos', methods=['GET', 'POST'])
def actualizar_datos():
    """
    Permite al beneficiario actualizar su nombre y tramo_ingreso.
    Usa la tabla `beneficiario` de la base local.
    """
    if not session.get('rut'):
        flash("Debes iniciar sesión primero.", "error")
        return redirect(url_for('index'))

    rut = session['rut']

    if request.method == 'POST':
        nuevo_nombre = request.form.get('nombre').strip()
        nuevo_tramo = request.form.get('tramo').strip()

        if not nuevo_nombre or not nuevo_tramo:
            flash("Debes completar nombre y tramo.", "error")
            return redirect(url_for('actualizar_datos'))

        # Actualizamos en la base de datos local
        with engine.begin() as conn:
            stmt_upd = text("""
                UPDATE beneficiario
                SET nombre = :nombre, tramo_ingreso = :tramo
                WHERE rut = :rut
            """)
            conn.execute(stmt_upd, {
                "nombre": nuevo_nombre,
                "tramo": nuevo_tramo,
                "rut": rut
            })

        # Actualizamos los datos en la sesión
        session['nombre'] = nuevo_nombre
        session['tramo'] = nuevo_tramo

        flash("Datos actualizados correctamente.", "success")
        return redirect(url_for('actualizar_datos'))

    # Si es GET, obtenemos los datos actuales para mostrar en el formulario
    with engine.connect() as conn:
        stmt_sel = text("""
            SELECT nombre, tramo_ingreso 
            FROM beneficiario 
            WHERE rut = :rut
        """)
        beneficiario = conn.execute(stmt_sel, {"rut": rut}).mappings().first()

    if not beneficiario:
        flash("No se encontró tu registro en la base local.", "error")
        return redirect(url_for('index'))

    return render_template(
        'actualizarDatos.html',
        beneficiario=beneficiario
    )


@app.route('/comprar_bono', methods=['GET', 'POST'])
def comprar_bono():
    """
    Muestra el formulario de compra de bono y procesa su inserción en la tabla `bono`.
    """
    if not session.get('rut'):
        flash("Debes iniciar sesión primero.", "error")
        return redirect(url_for('index'))

    if request.method == 'POST':
        # Obtenemos campos del formulario (modal)
        id_bono = request.form.get('id_bono', '').strip()
        fecha_emision = request.form.get('fecha_emision', '').strip()  # yyyy-mm-dd
        descripcion = request.form.get('descripcion', '').strip()
        valor_total = request.form.get('valor_total', '').strip()
        valor_copago = request.form.get('valor_copago', '').strip()
        valor_apagar = request.form.get('valor_apagar', '').strip()
        rut_medico = request.form.get('rut_medico', '').strip()
        rut_beneficiario = session.get('rut')

        # Validación básica
        if not all([id_bono, fecha_emision, valor_total, valor_copago, valor_apagar, rut_medico]):
            flash("Faltan datos para registrar el bono.", "error")
            return redirect(url_for('comprar_bono'))

        # Insertamos en la tabla `bono`
        try:
            with engine.begin() as conn:
                insert_stmt = text("""
                    INSERT INTO bono (
                        id_bono, fecha_emision, descripcion, 
                        valor_total, valor_copago, valor_apagar, 
                        rut_beneficiario, rut_medico
                    ) VALUES (
                        :id_bono, :fecha_emision, :descripcion, 
                        :valor_total, :valor_copago, :valor_apagar, 
                        :rut_beneficiario, :rut_medico
                    )
                """)
                conn.execute(insert_stmt, {
                    "id_bono": id_bono,
                    "fecha_emision": fecha_emision,
                    "descripcion": descripcion,
                    "valor_total": valor_total,
                    "valor_copago": valor_copago,
                    "valor_apagar": valor_apagar,
                    "rut_beneficiario": rut_beneficiario,
                    "rut_medico": rut_medico
                })
            flash("Bono registrado correctamente.", "success")
        except Exception as e:
            flash(f"Error al guardar el bono: {e}", "error")

        return redirect(url_for('ver_bono'))

    # Si es GET, solo mostramos la página para buscar médicos y comprar
    return render_template('comprarBono.html')


@app.route('/ver_bono', methods=['GET'])
def ver_bono():
    """
    Lista todos los bonos del beneficiario logueado.
    """
    if not session.get('rut'):
        flash("Debes iniciar sesión primero.", "error")
        return redirect(url_for('index'))

    rut_benef = session.get('rut')
    bonos = []

    try:
        with engine.connect() as conn:
            stmt = text("""
                SELECT id_bono, fecha_emision, descripcion, 
                       valor_total, valor_copago, valor_apagar, rut_medico
                FROM bono
                WHERE rut_beneficiario = :rut
                ORDER BY fecha_emision DESC
            """)
            rows = conn.execute(stmt, {"rut": rut_benef}).mappings().all()
            bonos = [dict(r) for r in rows]
    except Exception as e:
        flash(f"Error al obtener bonos: {e}", "error")

    return render_template('verBonos.html', bonos=bonos)


if __name__ == '__main__':
    # Ejecuta la aplicación en localhost:5000
    app.run(host='0.0.0.0', port=5000, debug=True)
