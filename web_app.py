import threading
import uuid
import time
from flask import Flask, request, jsonify, render_template
import processor

app = Flask(__name__)

tasks = {}
max_workers = 1
running = {}
lock = threading.Lock()

class Task:
    def __init__(self, params):
        self.id = str(uuid.uuid4())
        self.params = params
        self.progress = 0
        self.status = 'queued'
        self.log = []


def run_task(task: Task):
    def progress(p, msg):
        task.log.append(f"{p} {msg}")
        task.progress = p

    task.status = 'running'
    processor.process_folder(progress_callback=progress, **task.params)
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
    params = {
        'subtitle': request.form.get('subtitle', 'records'),
        'speeds': request.form.get('speeds', 'speeds.csv'),
        'delay': float(request.form.get('delay', '0.00001')),
        'voice': request.form.get('voice', 'basic_ref_en.wav'),
        'text': request.form.get('text', 'some call me nature, others call me mother nature.'),
        'coef': float(request.form.get('coef', '0.2')),
        'videoext': request.form.get('videoext', '.mp4'),
        'srtext': request.form.get('srtext', '.srt'),
        'outfileending': request.form.get('outfileending', '_out_mix.mp4'),
        'vocabular': request.form.get('vocabular', 'vocabular.txt'),
        'config': request.form.get('config', 'basic.toml'),
    }
    task = Task(params)
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
        'subtitle': t.params.get('subtitle'),
        'status': t.status,
        'progress': t.progress
    } for tid, t in tasks.items()})


if __name__ == '__main__':
    app.run(debug=True)
