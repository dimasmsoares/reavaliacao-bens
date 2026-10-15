"""
Backup diário do sistema de reavaliação de bens móveis.

Gera um .zip com um snapshot consistente do banco (reavaliacao.db) + todos os
screenshots, salva em backups/ (local) e copia para a pasta de rede do SEREG.
Remove backups mais antigos que RETENTION_DAYS em ambos os destinos.

Uso:
    python backup.py

Agendado para rodar diariamente via Agendador de Tarefas do Windows
(ver instruções no final do README ou pergunte ao Claude Code).
"""
import os
import shutil
import sqlite3
import sys
import zipfile
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'reavaliacao.db')
SCREENSHOTS_DIR = os.path.join(BASE_DIR, 'screenshots')
LOCAL_BACKUP_DIR = os.path.join(BASE_DIR, 'backups')
REMOTE_BACKUP_DIR = (
    r'\\Redecamara\DfsData\Sereg\Registro de Bens Móveis'
    r'\Reavaliação de Bens Móveis\Backup'
)
RETENTION_DAYS = 30
LOG_PATH = os.path.join(LOCAL_BACKUP_DIR, 'backup_log.txt')


def log(message):
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}"
    print(line)
    os.makedirs(LOCAL_BACKUP_DIR, exist_ok=True)
    with open(LOG_PATH, 'a', encoding='utf-8') as f:
        f.write(line + '\n')


def safe_db_copy(dest_path):
    """Snapshot consistente do banco (funciona mesmo com WAL e app rodando)."""
    src = sqlite3.connect(DB_PATH)
    dst = sqlite3.connect(dest_path)
    with dst:
        src.backup(dst)
    dst.close()
    src.close()


def build_backup_zip(timestamp):
    os.makedirs(LOCAL_BACKUP_DIR, exist_ok=True)
    tmp_db = os.path.join(LOCAL_BACKUP_DIR, f'_tmp_{timestamp}.db')
    zip_name = f'reavaliacao_backup_{timestamp}.zip'
    zip_path = os.path.join(LOCAL_BACKUP_DIR, zip_name)

    safe_db_copy(tmp_db)

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.write(tmp_db, 'reavaliacao.db')
        if os.path.isdir(SCREENSHOTS_DIR):
            for root, _dirs, files in os.walk(SCREENSHOTS_DIR):
                for fname in files:
                    fpath = os.path.join(root, fname)
                    arcname = os.path.join(
                        'screenshots', os.path.relpath(fpath, SCREENSHOTS_DIR)
                    )
                    zf.write(fpath, arcname)

    os.remove(tmp_db)
    return zip_path, zip_name


def copy_to_remote(zip_path, zip_name):
    try:
        os.makedirs(REMOTE_BACKUP_DIR, exist_ok=True)
        dest = os.path.join(REMOTE_BACKUP_DIR, zip_name)
        shutil.copy2(zip_path, dest)
        log(f'Copiado para rede: {dest}')
        return True
    except OSError as e:
        log(f'AVISO: falha ao copiar para a rede ({REMOTE_BACKUP_DIR}): {e}')
        return False


def cleanup_old_backups(directory):
    if not os.path.isdir(directory):
        return
    cutoff = datetime.now() - timedelta(days=RETENTION_DAYS)
    for fname in os.listdir(directory):
        if not (fname.startswith('reavaliacao_backup_') and fname.endswith('.zip')):
            continue
        fpath = os.path.join(directory, fname)
        try:
            mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
            if mtime < cutoff:
                os.remove(fpath)
                log(f'Removido backup antigo: {fpath}')
        except OSError as e:
            log(f'AVISO: falha ao remover {fpath}: {e}')


def run_backup():
    """Executa o backup e retorna um dict com o resultado (sem sys.exit).

    Usado tanto pelo agendamento (via main()) quanto pela rota do admin.
    """
    if not os.path.isfile(DB_PATH):
        log(f'ERRO: banco não encontrado em {DB_PATH}')
        return {'success': False, 'error': f'Banco não encontrado em {DB_PATH}'}

    timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    log(f'Iniciando backup ({timestamp})...')

    try:
        zip_path, zip_name = build_backup_zip(timestamp)
    except Exception as e:
        log(f'ERRO ao gerar backup local: {e}')
        return {'success': False, 'error': str(e)}

    size_mb = os.path.getsize(zip_path) / (1024 * 1024)
    log(f'Backup local criado: {zip_path} ({size_mb:.1f} MB)')

    remote_ok = copy_to_remote(zip_path, zip_name)

    cleanup_old_backups(LOCAL_BACKUP_DIR)
    cleanup_old_backups(REMOTE_BACKUP_DIR)

    log('Backup concluído.')

    return {
        'success': True,
        'zip_path': zip_path,
        'zip_name': zip_name,
        'size_mb': size_mb,
        'remote_ok': remote_ok,
    }


def main():
    result = run_backup()
    if not result['success']:
        sys.exit(1)


if __name__ == '__main__':
    main()
