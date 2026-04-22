import os
import base64
import functools
from datetime import datetime
from flask import (Flask, render_template, request, session, redirect,
                   url_for, flash, jsonify, send_from_directory)
from werkzeug.security import generate_password_hash, check_password_hash
from PIL import Image
import io

import database as db
from excel_loader import load_excel_files
from excel_exporter import export_all

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCREENSHOTS_DIR = os.path.join(BASE_DIR, 'screenshots')

app = Flask(__name__)
app.secret_key = 'reavaliacao-bens-camara-2024-chave-secreta'
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024  # 20 MB


# ── Filtros de template ──────────────────────────────────────────────────────

@app.template_filter('brl')
def brl_filter(value):
    if value is None:
        return 'N/D'
    return f"R$ {value:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')


@app.template_filter('planilha_curta')
def planilha_curta_filter(planilha):
    if ' - ' in planilha:
        return planilha.split(' - ', 1)[1]
    return planilha


# ── Decoradores de autenticação ──────────────────────────────────────────────

def login_required(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        if session.get('role') != 'admin':
            flash('Acesso restrito ao administrador.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return wrapper


# ── Raiz ────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if session.get('role') == 'admin':
        return redirect(url_for('admin_dashboard'))
    return redirect(url_for('avaliar'))


# ── Autenticação ─────────────────────────────────────────────────────────────

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        password = request.form.get('password', '')
        user = db.get_user_by_name(name)
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['role'] = user['role']
            return redirect(url_for('index'))
        flash('Usuário ou senha inválidos.', 'danger')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ── Admin — Dashboard ────────────────────────────────────────────────────────

@app.route('/admin')
@admin_required
def admin_dashboard():
    progress = db.get_global_progress()
    users_progress = db.get_all_users_progress()
    planilha_progress = db.get_progress_by_planilha()
    return render_template('admin/dashboard.html',
                           progress=progress,
                           users_progress=users_progress,
                           planilha_progress=planilha_progress)


@app.route('/admin/export', methods=['POST'])
@admin_required
def admin_export():
    files = export_all()
    if files:
        flash(f'{len(files)} arquivo(s) exportado(s) para a pasta "output/".',
              'success')
    else:
        flash('Nenhum bem foi avaliado ainda. Nada a exportar.', 'warning')
    return redirect(url_for('admin_dashboard'))


# ── Admin — Servidores ───────────────────────────────────────────────────────

@app.route('/admin/usuarios', methods=['GET', 'POST'])
@admin_required
def admin_usuarios():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        password = request.form.get('password', '')
        if not name or not password:
            flash('Nome e senha são obrigatórios.', 'warning')
        elif len(password) < 4:
            flash('A senha deve ter pelo menos 4 caracteres.', 'warning')
        else:
            if db.create_user(name, generate_password_hash(password), 'servidor'):
                flash(f'Servidor "{name}" criado com sucesso.', 'success')
            else:
                flash(f'Já existe um usuário com o nome "{name}".', 'danger')
        return redirect(url_for('admin_usuarios'))
    users = db.get_all_users()
    users_progress = {u['id']: u for u in db.get_all_users_progress()}
    return render_template('admin/usuarios.html',
                           users=users,
                           users_progress=users_progress)


@app.route('/admin/usuarios/<int:user_id>/editar', methods=['GET', 'POST'])
@admin_required
def admin_editar_usuario(user_id):
    user = db.get_user_by_id(user_id)
    if not user or user['role'] != 'servidor':
        flash('Servidor não encontrado.', 'danger')
        return redirect(url_for('admin_usuarios'))
    if request.method == 'POST':
        password = request.form.get('password', '')
        if len(password) < 4:
            flash('A senha deve ter pelo menos 4 caracteres.', 'warning')
        else:
            db.update_user_password(user_id, generate_password_hash(password))
            flash(f'Senha de "{user["name"]}" atualizada.', 'success')
            return redirect(url_for('admin_usuarios'))
    return render_template('admin/editar_usuario.html', user=user)


# ── Admin — Distribuição ─────────────────────────────────────────────────────

@app.route('/admin/distribuir', methods=['GET', 'POST'])
@admin_required
def admin_distribuir():
    if request.method == 'POST':
        mode = request.form.get('mode')
        user_id = request.form.get('user_id', type=int)
        user = db.get_user_by_id(user_id) if user_id else None
        if not user or user['role'] != 'servidor':
            flash('Selecione um servidor válido.', 'danger')
        elif mode == 'planilha':
            planilha = request.form.get('planilha', '').strip()
            if not planilha:
                flash('Selecione uma planilha.', 'warning')
            else:
                count = db.assign_by_planilha(planilha, user_id)
                flash(f'{count} bens de "{planilha_curta_filter(planilha)}" '
                      f'atribuídos a {user["name"]}.', 'success')
        elif mode == 'quantidade':
            n = request.form.get('quantidade', type=int, default=0)
            if n <= 0:
                flash('Informe uma quantidade válida (maior que zero).', 'warning')
            else:
                count = db.assign_by_quantity(n, user_id)
                flash(f'{count} bens atribuídos a {user["name"]}.', 'success')
        elif mode == 'redistribuir':
            from_user_id = request.form.get('from_user_id', type=int)
            from_user = db.get_user_by_id(from_user_id) if from_user_id else None
            if not from_user:
                flash('Selecione o servidor de origem.', 'warning')
            elif from_user_id == user_id:
                flash('Origem e destino não podem ser o mesmo servidor.', 'warning')
            else:
                count = db.reassign_pending(from_user_id, user_id)
                flash(f'{count} bens pendentes de "{from_user["name"]}" '
                      f'redistribuídos para "{user["name"]}".', 'success')
        return redirect(url_for('admin_distribuir'))

    users = db.get_all_users()
    planilhas = db.get_distinct_planilhas()
    unassigned = db.get_unassigned_count_by_planilha()
    users_progress = db.get_all_users_progress()
    return render_template('admin/distribuir.html',
                           users=users,
                           planilhas=planilhas,
                           unassigned=unassigned,
                           users_progress=users_progress)


# ── Servidor — Avaliação ─────────────────────────────────────────────────────

@app.route('/avaliar')
@login_required
def avaliar():
    if session.get('role') == 'admin':
        return redirect(url_for('admin_dashboard'))
    asset = db.get_next_pending_asset(session['user_id'])
    if asset:
        return redirect(url_for('avaliar_bem', asset_id=asset['id']))
    # Todos concluídos
    progress = db.get_user_progress(session['user_id'])
    return render_template('servidor/avaliar.html',
                           asset=None,
                           review=None,
                           progress=progress,
                           assets_list=[],
                           prev_id=None,
                           next_in_order_id=None,
                           next_pending_id=None,
                           position=None)


@app.route('/avaliar/<int:asset_id>', methods=['GET', 'POST'])
@login_required
def avaliar_bem(asset_id):
    if session.get('role') == 'admin':
        return redirect(url_for('admin_dashboard'))

    asset = db.get_asset(asset_id)
    if not asset:
        flash('Bem não encontrado.', 'danger')
        return redirect(url_for('avaliar'))

    # Garante que o bem pertence ao servidor logado
    user_asset_ids = {a['id'] for a in db.get_assets_for_user(session['user_id'])}
    if asset_id not in user_asset_ids:
        flash('Este bem não está atribuído a você.', 'danger')
        return redirect(url_for('avaliar'))

    if request.method == 'POST':
        valor_str = request.form.get('valor_mercado', '').replace(',', '.').strip()
        screenshot_data = request.form.get('screenshot_data', '').strip()

        try:
            valor = float(valor_str)
            if valor < 0:
                raise ValueError()
        except ValueError:
            flash('Informe um valor de mercado válido (ex: 1.500,00).', 'danger')
            return _render_avaliar(asset_id, asset)

        screenshot_path = None
        if screenshot_data:
            try:
                screenshot_path = _save_screenshot(asset_id, screenshot_data)
            except Exception as e:
                flash(f'Erro ao salvar imagem: {e}', 'danger')
                return _render_avaliar(asset_id, asset)

        # Se não há nova imagem, preserva a anterior
        if not screenshot_path:
            existing = db.get_review(asset_id)
            if existing:
                screenshot_path = existing.get('screenshot_path')

        db.save_review(asset_id, session['user_id'], valor, screenshot_path)
        flash('Avaliação salva!', 'success')

        next_asset = db.get_next_pending_asset(session['user_id'])
        if next_asset:
            return redirect(url_for('avaliar_bem', asset_id=next_asset['id']))
        return redirect(url_for('avaliar'))

    return _render_avaliar(asset_id, asset)


def _render_avaliar(asset_id, asset):
    review = db.get_review(asset_id)
    progress = db.get_user_progress(session['user_id'])
    prev_id, next_id, position, _ = db.get_adjacent_asset_ids(
        session['user_id'], asset_id
    )
    next_pending = db.get_next_pending_asset(session['user_id'])
    next_pending_id = next_pending['id'] if next_pending else None

    # Sidebar: apenas IDs + status leve para não sobrecarregar
    assets_list = db.get_assets_for_user(session['user_id'])

    return render_template('servidor/avaliar.html',
                           asset=asset,
                           review=review,
                           progress=progress,
                           assets_list=assets_list,
                           prev_id=prev_id,
                           next_in_order_id=next_id,
                           next_pending_id=next_pending_id,
                           position=position)


# ── API ──────────────────────────────────────────────────────────────────────

@app.route('/api/progress')
@login_required
def api_progress():
    return jsonify(db.get_user_progress(session['user_id']))


@app.route('/screenshots/<path:filename>')
@login_required
def serve_screenshot(filename):
    return send_from_directory(SCREENSHOTS_DIR, filename)


# ── Utilitários ──────────────────────────────────────────────────────────────

def _save_screenshot(asset_id, data_url):
    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
    if ',' in data_url:
        data_url = data_url.split(',', 1)[1]
    image_bytes = base64.b64decode(data_url)
    img = Image.open(io.BytesIO(image_bytes))
    img = img.convert('RGB')
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{asset_id}_{timestamp}.png"
    img.save(os.path.join(SCREENSHOTS_DIR, filename), 'PNG', optimize=True)
    return filename


# ── Inicialização ────────────────────────────────────────────────────────────

if __name__ == '__main__':
    db.init_db()
    if not db.get_user_by_name('admin'):
        db.create_user('admin', generate_password_hash('admin123'), 'admin')
        print("Usuário admin criado com senha padrão: admin123")
        print("IMPORTANTE: altere a senha após o primeiro acesso.")
    load_excel_files()
    total = db.count_assets()
    print(f"Bens carregados no banco: {total}")
    print("Servidor iniciando em http://localhost:5000")
    app.run(debug=False, host='0.0.0.0', port=5000)
