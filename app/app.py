import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from sqlalchemy import text
from db import engine
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY')


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/login', methods=['POST'])
def login():
    rut = request.form.get('rut', '').strip()
    clave_ingresada = request.form.get('clave', '').strip()

    if not rut or not clave_ingresada:
        flash("Por favor ingresa RUT y clave.", "error")
        return redirect(url_for('index'))

    with engine.connect() as conn:
        stmt = text("""
            SELECT nombre, tramo_ingreso, clave
            FROM beneficiario
            WHERE rut = :rut
        """)
        result = conn.execute(stmt, {"rut": rut}).mappings().first()

    if not result:
        flash("RUT no encontrado en la base local.", "error")
        return redirect(url_for('index'))

    if clave_ingresada != result['clave']:
        flash("Clave incorrecta.", "error")
        return redirect(url_for('index'))

    session['rut'] = rut
    session['nombre'] = result['nombre']
    session['tramo'] = result['tramo_ingreso']
    flash(f"Bienvenido, {session['nombre']} (Tramo {session['tramo']})", "success")
    return redirect(url_for('portal'))

@app.route('/portal')
def portal():
    if not session.get('rut'):
        flash("Debes iniciar sesión primero.", "error")
        return redirect(url_for('index'))
    return render_template('portal.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("Has cerrado sesión.", "info")
    return redirect(url_for('index'))


@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        rut = request.form['rut'].strip()
        nombre = request.form['nombre'].strip()
        tramo = request.form['tramo'].strip()
        clave = request.form['clave'].strip()

        with engine.begin() as conn:
            stmt = text("""
                INSERT INTO beneficiario (rut, nombre, tramo_ingreso, clave)
                VALUES (:rut, :nombre, :tramo, :clave)
            """)
            conn.execute(stmt, {
                "rut": rut,
                "nombre": nombre,
                "tramo": tramo,
                "clave": clave
            })

        flash("Registro exitoso. Ahora puedes iniciar sesión.", "success")
        return redirect(url_for('index'))

    return render_template('registro.html')


@app.route('/actualizar_datos', methods=['GET', 'POST'])
def actualizar_datos():
    if not session.get('rut'):
        flash("Debes iniciar sesión primero.", "error")
        return redirect(url_for('index'))

    rut = session['rut']

    if request.method == 'POST':
        nuevo_nombre = request.form.get('nombre', '').strip()
        nuevo_tramo = request.form.get('tramo', '').strip()

        if not nuevo_nombre or not nuevo_tramo:
            flash("Debes completar nombre y tramo.", "error")
            return redirect(url_for('actualizar_datos'))

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

        session['nombre'] = nuevo_nombre
        session['tramo'] = nuevo_tramo
        flash("Datos actualizados correctamente.", "success")
        return redirect(url_for('actualizar_datos'))

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


@app.route('/comprar_bono', methods=['GET'])
def comprar_bono():
    if not session.get('rut'):
        flash("Debes iniciar sesión primero.", "error")
        return redirect(url_for('index'))

    # 1) Comunas disponibles
    with engine.connect() as conn:
        comunas_result = conn.execute(
            text("SELECT DISTINCT comuna FROM medico ORDER BY comuna")
        ).mappings().all()
        comunas_disponibles = [row['comuna'] for row in comunas_result]

    # 2) Leer filtros GET
    tipo_busqueda  = request.args.get('tipoBusqueda', '').strip()
    valor_busqueda = request.args.get('valorBusqueda', '').strip()
    especialidad   = request.args.get('especialidad', '').strip()
    comuna_sel     = request.args.get('comuna', '').strip()

    # 3) Construir consulta dinámica
    sql_base = "SELECT rut, nombre, especialidad, comuna FROM medico"
    condiciones = []
    parametros = {}

    if valor_busqueda:
        if tipo_busqueda == 'nombre':
            condiciones.append("nombre ILIKE :valor_busqueda")
            parametros['valor_busqueda'] = f"%{valor_busqueda}%"
        elif tipo_busqueda == 'rutProfesional':
            condiciones.append("rut ILIKE :valor_busqueda")
            parametros['valor_busqueda'] = f"%{valor_busqueda}%"

    if especialidad:
        condiciones.append("especialidad = :especialidad")
        parametros['especialidad'] = especialidad

    if comuna_sel:
        condiciones.append("comuna = :comuna_sel")
        parametros['comuna_sel'] = comuna_sel

    where_clause = (" WHERE " + " AND ".join(condiciones)) if condiciones else ""
    sql_final = sql_base + where_clause + " ORDER BY nombre ASC"

    with engine.connect() as conn:
        stmt = text(sql_final)
        rows = conn.execute(stmt, parametros).mappings().all()
        medicos = [dict(r) for r in rows]

    return render_template(
        'comprarBono.html',
        medicos=medicos,
        comunas_disponibles=comunas_disponibles,
        filtros={
            'tipoBusqueda': tipo_busqueda,
            'valorBusqueda': valor_busqueda,
            'especialidad': especialidad,
            'comuna': comuna_sel
        }
    )


@app.route('/confirmar_compra', methods=['POST'])
def confirmar_compra():
    if not session.get('rut'):
        flash("Debes iniciar sesión primero.", "error")
        return redirect(url_for('index'))

    id_bono         = request.form.get('id_bono', '').strip()
    fecha_emision   = request.form.get('fecha_emision', '').strip()
    descripcion     = request.form.get('descripcion', '').strip()
    valor_total     = request.form.get('valor_total', '').strip()
    valor_copago    = request.form.get('valor_copago', '').strip()
    valor_apagar    = request.form.get('valor_apagar', '').strip()
    rut_medico      = request.form.get('rut_medico', '').strip()
    rut_beneficiario = session['rut']

    if not all([id_bono, fecha_emision, valor_total, valor_copago, valor_apagar, rut_medico]):
        flash("Faltan datos para registrar el bono.", "error")
        return redirect(url_for('comprar_bono'))

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


@app.route('/ver_bono', methods=['GET'])
def ver_bono():
    if not session.get('rut'):
        flash("Debes iniciar sesión primero.", "error")
        return redirect(url_for('index'))

    rut_benef = session['rut']
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
    app.run(host='0.0.0.0', port=5000, debug=True)
