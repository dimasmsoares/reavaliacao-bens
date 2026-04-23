import os
import re
import json
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

@app.template_filter('strip_codigo')
def strip_codigo_filter(material):
    if not material:
        return ''
    return re.sub(r'\s*\(\d+\)\s*$', '', material).strip()


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
    unique_counts = db.get_unique_count_by_planilha()
    return render_template('admin/dashboard.html',
                           progress=progress,
                           users_progress=users_progress,
                           planilha_progress=planilha_progress,
                           unique_counts=unique_counts)


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
        elif mode == 'grupos_unicos':
            planilha = request.form.get('planilha', '').strip()
            n = request.form.get('n_grupos', type=int, default=0)
            if not planilha:
                flash('Selecione uma planilha.', 'warning')
            elif n <= 0:
                flash('Informe uma quantidade de grupos maior que zero.', 'warning')
            else:
                assets_count, groups_count = db.assign_by_unique_groups(planilha, n, user_id)
                if assets_count == 0:
                    flash(f'Nenhum grupo disponível em "{planilha_curta_filter(planilha)}" para distribuir.', 'warning')
                else:
                    flash(
                        f'{assets_count} bem(ns) em {groups_count} grupo(s) único(s) de '
                        f'"{planilha_curta_filter(planilha)}" atribuídos a {user["name"]}.',
                        'success'
                    )
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
    unique_unassigned = db.get_unique_unassigned_by_planilha()
    return render_template('admin/distribuir.html',
                           users=users,
                           planilhas=planilhas,
                           unassigned=unassigned,
                           users_progress=users_progress,
                           unique_unassigned=unique_unassigned)


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
        # Preços
        try:
            prices = [float(p) for p in json.loads(request.form.get('prices_json', '[]'))
                      if str(p).strip()]
        except Exception:
            prices = []

        if not prices:
            flash('Adicione ao menos um preço encontrado.', 'danger')
            return _render_avaliar(asset_id, asset)

        valor = sum(prices) / len(prices)

        # Screenshots existentes a manter
        try:
            keep_paths = json.loads(request.form.get('existing_screenshots', '[]'))
            if not isinstance(keep_paths, list):
                keep_paths = []
        except Exception:
            keep_paths = []

        # Novos screenshots enviados como screenshot_data_0, screenshot_data_1, ...
        new_paths = []
        idx = 0
        while True:
            data = request.form.get(f'screenshot_data_{idx}', '').strip()
            if not data:
                break
            try:
                new_paths.append(_save_screenshot(asset_id, data, idx))
            except Exception as e:
                flash(f'Erro ao salvar imagem {idx + 1}: {e}', 'warning')
            idx += 1

        all_paths = keep_paths + new_paths
        observacao = request.form.get('observacao', '').strip() or None
        db.save_review(asset_id, session['user_id'], valor,
                       screenshot_path=all_paths[0] if all_paths else None,
                       prices=prices,
                       screenshot_paths=all_paths if all_paths else None,
                       observacao=observacao)
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

    group_size = db.get_group_size(asset_id)

    return render_template('servidor/avaliar.html',
                           asset=asset,
                           review=review,
                           progress=progress,
                           assets_list=assets_list,
                           prev_id=prev_id,
                           next_in_order_id=next_id,
                           next_pending_id=next_pending_id,
                           position=position,
                           group_size=group_size)


# ── Servidor — Desfazer avaliação ────────────────────────────────────────────

@app.route('/avaliar/<int:asset_id>/desfazer', methods=['POST'])
@login_required
def desfazer_avaliacao(asset_id):
    if session.get('role') == 'admin':
        return redirect(url_for('admin_dashboard'))
    user_asset_ids = {a['id'] for a in db.get_assets_for_user(session['user_id'])}
    if asset_id not in user_asset_ids:
        flash('Este bem não está atribuído a você.', 'danger')
        return redirect(url_for('avaliar'))
    db.delete_review(asset_id, session['user_id'])
    flash('Avaliação removida. Você pode refazê-la agora.', 'info')
    return redirect(url_for('avaliar_bem', asset_id=asset_id))


# ── Servidor — Alterar senha ─────────────────────────────────────────────────

@app.route('/minha_senha', methods=['GET', 'POST'])
@login_required
def minha_senha():
    if request.method == 'POST':
        nova = request.form.get('password', '')
        confirma = request.form.get('confirm', '')
        if len(nova) < 4:
            flash('A senha deve ter pelo menos 4 caracteres.', 'warning')
        elif nova != confirma:
            flash('As senhas não coincidem.', 'warning')
        else:
            db.update_user_password(session['user_id'], generate_password_hash(nova))
            flash('Senha alterada com sucesso!', 'success')
            return redirect(url_for('index'))
    return render_template('servidor/minha_senha.html')


# ── Admin — Bens de um servidor ──────────────────────────────────────────────

@app.route('/admin/avaliacoes/<int:asset_id>/desfazer', methods=['POST'])
@admin_required
def admin_desfazer_avaliacao(asset_id):
    asset = db.get_asset(asset_id)
    if not asset:
        flash('Bem não encontrado.', 'danger')
        return redirect(url_for('admin_dashboard'))
    review = db.get_review(asset_id)
    if not review:
        flash('Este bem não possui avaliação registrada.', 'warning')
        return redirect(request.referrer or url_for('admin_dashboard'))
    justificativa = request.form.get('justificativa', '').strip()
    if not justificativa:
        flash('A justificativa é obrigatória para desfazer uma avaliação.', 'warning')
        return redirect(request.referrer or url_for('admin_dashboard'))
    target_user_id = review.get('user_id')
    db.admin_delete_review(asset_id, session['user_id'], target_user_id, justificativa)
    flash(f'Avaliação do bem NRP {asset["nrp"]} desfeita. O servidor deverá reavaliá-lo.', 'success')
    return redirect(request.referrer or url_for('admin_dashboard'))


@app.route('/admin/usuarios/<int:user_id>/bens')
@admin_required
def admin_usuario_bens(user_id):
    user = db.get_user_by_id(user_id)
    if not user or user['role'] != 'servidor':
        flash('Servidor não encontrado.', 'danger')
        return redirect(url_for('admin_usuarios'))
    assets = db.get_assets_for_user(user_id)
    return render_template('admin/usuario_bens.html', user=user, assets=assets)


# ── Admin — Excluir servidor ─────────────────────────────────────────────────

@app.route('/admin/usuarios/<int:user_id>/excluir', methods=['POST'])
@admin_required
def admin_excluir_usuario(user_id):
    if user_id == session['user_id']:
        flash('Você não pode excluir sua própria conta.', 'danger')
        return redirect(url_for('admin_usuarios'))
    user = db.get_user_by_id(user_id)
    if not user or user['role'] != 'servidor':
        flash('Servidor não encontrado.', 'danger')
        return redirect(url_for('admin_usuarios'))
    db.delete_user(user_id)
    flash(f'Servidor "{user["name"]}" excluído. Os bens foram liberados para redistribuição.', 'success')
    return redirect(url_for('admin_usuarios'))


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

def _save_screenshot(asset_id, data_url, idx=0):
    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
    if ',' in data_url:
        data_url = data_url.split(',', 1)[1]
    image_bytes = base64.b64decode(data_url)
    img = Image.open(io.BytesIO(image_bytes))
    img = img.convert('RGB')
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{asset_id}_{timestamp}_{idx}.jpg"
    img.save(os.path.join(SCREENSHOTS_DIR, filename), 'JPEG', quality=90, optimize=True)
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
