import threading
import subprocess
import uuid
import time
from flask import Flask, request, jsonify, render_template

app = Flask(__name__)

tasks = {}
max_workers = 1
running = {}
lock = threading.Lock()

class Task:
    def __init__(self, subtitle):
        self.id = str(uuid.uuid4())
        self.subtitle = subtitle
        self.progress = 0
        self.status = 'queued'
        self.log = []
        self.process = None


def run_task(task: Task):
    cmd = ['python', 'main.py', '--subtitle', task.subtitle]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, bufsize=1)
    task.process = process
    task.status = 'running'
    for line in process.stdout:
        task.log.append(line)
        if line.startswith('[PROGRESS]'):
            try:
                parts = line.strip().split(' ', 2)
                task.progress = int(parts[1])
            except Exception:
                pass
    process.wait()
    task.status = 'finished'
    task.progress = 100
    with lock:
        running.pop(task.id, None)


def scheduler():
    while True:
        with lock:
            while len(running) < max_workers:
                queued = [t for t in tasks.values() if t.status == 'queued']
                if not queued:
                    break
                task = queued[0]
                running[task.id] = task
                thread = threading.Thread(target=run_task, args=(task,), daemon=True)
                thread.start()
        time.sleep(1)


threading.Thread(target=scheduler, daemon=True).start()


@app.route('/')
def index():
    return render_template('index.html', workers=max_workers)


@app.route('/start', methods=['POST'])
def start():
    subtitle = request.form.get('subtitle', 'records')
    task = Task(subtitle)
    tasks[task.id] = task
    return jsonify({'task_id': task.id})


@app.route('/set_workers', methods=['POST'])
def set_workers():
    global max_workers
    workers = int(request.form.get('workers', 1))
    max_workers = max(1, workers)
    return jsonify({'workers': max_workers})


@app.route('/tasks')
def list_tasks():
    return jsonify({tid: {
        'subtitle': t.subtitle,
        'status': t.status,
        'progress': t.progress
    } for tid, t in tasks.items()})


if __name__ == '__main__':
    app.run(debug=True)
