from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import sys
import uuid
import random
from datetime import datetime
import pytz
import shutil  # 👈 Añadido para mover archivos de forma segura

# --------------------------------------------------
# 1. RUTAS REALES (tu carpeta actual)
# --------------------------------------------------
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
PYTHON_DIR = BASE_DIR
sys.path.insert(0, PYTHON_DIR)
os.chdir(PYTHON_DIR)

# --------------------------------------------------
# 2. CARGAR CONFIGURACIONES REALES (sin tocar)
# --------------------------------------------------
try:
    from config import (
        COMPROBANTE1_CONFIG,
        COMPROBANTE4_CONFIG,
        COMPROBANTE_MOVIMIENTO_CONFIG,
        COMPROBANTE_MOVIMIENTO2_CONFIG,
        COMPROBANTE_QR_CONFIG,
        COMPROBANTE_MOVIMIENTO3_CONFIG
    )
    from utils import generar_comprobante
    print("✅ Configuraciones y utils cargadas correctamente")
except ImportError as e:
    print("❌ ERROR al importar config.py o utils.py:", e)
    sys.exit(1)

# --------------------------------------------------
# 3. FLASK
# --------------------------------------------------
app = Flask(__name__, static_folder=os.path.join(BASE_DIR, 'static'))
CORS(app)

GENERATED_DIR = os.path.join(BASE_DIR, 'generated_comprobantes')
os.makedirs(GENERATED_DIR, exist_ok=True)

# --------------------------------------------------
# 4. HELPERS
# --------------------------------------------------
def fecha_colombia():
    # Meses en español (minúsculas)
    meses = {
        "enero": "enero", "febrero": "febrero", "marzo": "marzo", "abril": "abril",
        "mayo": "mayo", "junio": "junio", "julio": "julio", "agosto": "agosto",
        "septiembre": "septiembre", "octubre": "octubre", "noviembre": "noviembre", "diciembre": "diciembre"
    }
    now = datetime.now(pytz.timezone("America/Bogota"))
    mes = now.strftime("%B").lower()  # devuelve español
    return now.strftime(f"%d de {mes} de %Y a las %I:%M %p").lower().replace("am", "a. m.").replace("pm", "p. m.")

def ref_aleatoria():
    return f"M{random.randint(10000000, 99999999)}"

# --------------------------------------------------
# 5. ENDPOINTS
# --------------------------------------------------
@app.route('/api/check-files', methods=['GET'])
def check_files():
    plantillas = {
        'plantilla1.jpg': 'Nequi',
        'plantilla4.jpg': 'Transfiya',
        'plantilla_qr.jpg': 'QR',
        'comprobante_movimiento.jpg': 'Mov Nequi',
        'plantilla2.jpg': 'Mov Transfiya',
        'comprobante_movimiento3.jpg': 'Mov QR'
    }
    fuentes = {
        'Manrope-Medium.ttf': 'Medium',
        'Manrope-Bold.ttf': 'Bold'
    }
    out = {}
    for f, name in plantillas.items():
        out[f] = {'exists': os.path.isfile(os.path.join(PYTHON_DIR, 'img', f)), 'name': name}
    for f, name in fuentes.items():
        out[f] = {'exists': os.path.isfile(os.path.join(PYTHON_DIR, 'fuentes', f)), 'name': name}
    return jsonify({'python_dir': PYTHON_DIR, 'files': out})

@app.post('/api/generate-comprobante')
def api_generate():
    data = request.get_json(silent=True) or {}
    tipo = data.get('tipo')
    valor = data.get('valor', 0)

    if tipo not in ('nequi', 'transfiya', 'qr'):
        return jsonify({'error': 'Tipo debe ser nequi | transfiya | qr'}), 400
    if valor <= 0:
        return jsonify({'error': 'Valor debe ser > 0'}), 400

    # Según tipo
    if tipo == 'nequi':
        nombre = data.get('nombre', '').strip()
        telefono = data.get('telefono', '').strip()
        if not nombre or not telefono or len(telefono) != 10 or not telefono.isdigit():
            return jsonify({'error': 'Nombre y teléfono (10 dígitos) requeridos'}), 400
        comp_data = {'nombre': nombre, 'telefono': telefono, 'valor': valor}
        mov_data = {**comp_data, 'nombre': nombre.upper(), 'valor': -abs(valor)}
        cfg_comp, cfg_mov = COMPROBANTE1_CONFIG, COMPROBANTE_MOVIMIENTO_CONFIG

    elif tipo == 'transfiya':
        telefono = data.get('telefono', '').strip()
        if not telefono or len(telefono) != 10 or not telefono.isdigit():
            return jsonify({'error': 'Teléfono (10 dígitos) requerido'}), 400
        comp_data = {'telefono': telefono, 'valor': valor}
        mov_data = {'telefono': telefono, 'valor': -abs(valor), 'nombre': telefono}
        cfg_comp, cfg_mov = COMPROBANTE4_CONFIG, COMPROBANTE_MOVIMIENTO2_CONFIG

    else:  # qr
        nombre = data.get('nombre', '').strip()
        if not nombre:
            return jsonify({'error': 'Nombre del negocio requerido'}), 400
        comp_data = {'nombre': nombre, 'valor': valor}
        mov_data = {'nombre': nombre.upper(), 'valor': -abs(valor)}
        cfg_comp, cfg_mov = COMPROBANTE_QR_CONFIG, COMPROBANTE_MOVIMIENTO3_CONFIG

    # Generar imágenes
    try:
        path_comp = generar_comprobante(comp_data, cfg_comp)
        path_mov = generar_comprobante(mov_data, cfg_mov)
    except Exception as e:
        return jsonify({'error': f'Error generando imágenes: {e}'}), 500

    # Mover a carpeta pública (usando shutil.move para evitar errores)
    def guardar(p):
        filename = os.path.basename(p)
        destino = os.path.join(GENERATED_DIR, filename)
        # Si ya existe, lo sobreescribimos
        if os.path.exists(destino):
            os.remove(destino)
        shutil.move(p, destino)
        return destino

    final_comp = guardar(path_comp)
    final_mov = guardar(path_mov)

    return jsonify({
        'success': True,
        'comprobante': {
            'tipo': tipo,
            'nombre': comp_data.get('nombre') or comp_data.get('telefono'),
            'telefono': comp_data.get('telefono'),
            'valor': valor,
            'fecha': fecha_colombia(),
            'referencia': ref_aleatoria(),
            'disponible': 'Disponible',
            'url': f"/download/{os.path.basename(final_comp)}"
        },
        'movimiento': {
            'tipo': tipo,
            'nombre': mov_data.get('nombre'),
            'valor': mov_data['valor'],
            'fecha': fecha_colombia(),
            'url': f"/download/{os.path.basename(final_mov)}"
        }
    })

@app.route('/download/<path:filename>')
def serve_generated(filename):
    return send_from_directory(GENERATED_DIR, filename)

# 👇 RUTAS PARA SERVIR LOS ARCHIVOS HTML
@app.route('/')
def login_page():
    """Página de login por defecto"""
    return send_from_directory(app.static_folder, 'login.html')

@app.route('/index')
def index_page():
    """App principal después del login"""
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/admin')
def admin_page():
    """Panel de administración"""
    return send_from_directory(app.static_folder, 'home.html')

# 👇 SERVIR OTROS ARCHIVOS ESTÁTICOS (manifest, icons, etc.)
@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory(app.static_folder, filename)

# --------------------------------------------------
if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)