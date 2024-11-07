from flask import Flask, render_template, request, redirect, url_for, session, send_file
import wave
import os
import json

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Необходимо для работы сессий

UPLOAD_FOLDER = "uploads"
PROCESSED_FOLDER = "processed"
USERS_FILE = "users.json"  # Файл для хранения данных пользователей

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PROCESSED_FOLDER'] = PROCESSED_FOLDER

# Создаем папки, если они не существуют
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

def time_to_seconds(time_str):
    """Convert time in 'minutes:seconds' format to total seconds."""
    minutes, seconds = map(int, time_str.split(':'))
    return minutes * 60 + seconds

def generate_silence(duration, framerate, n_channels, sampwidth):
    """Generate silence of specified duration."""
    num_frames = int(duration * framerate)
    silence = (b'\x00' * sampwidth) * num_frames * n_channels
    return silence

def load_users():
    """Load users from JSON file."""
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    else:
        return {}

def save_users(users):
    """Save users to JSON file."""
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f)

def login_required(f):
    """Decorator to check if user is logged in."""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        users = load_users()
        if username in users:
            error = 'Пользователь уже существует.'
            return render_template('register.html', error=error)
        users[username] = password  # В реальном приложении нужно хранить хеш пароля
        save_users(users)
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        users = load_users()
        if username in users and users[username] == password:
            session['username'] = username
            next_page = request.args.get('next')
            return redirect(next_page or url_for('home'))
        else:
            error = 'Неправильное имя пользователя или пароль.'
            return render_template('login.html', error=error)
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('home'))

@app.route('/cut', methods=['GET', 'POST'])
@login_required
def cut():
    if request.method == 'POST':
        file = request.files['audio-file']
        if file:
            start_time_str = request.form.get('start-time', '0:00')
            end_time_str = request.form.get('end-time', '0:05')

            filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(filepath)

            # Открытие аудиофайла
            with wave.open(filepath, 'rb') as audio:
                frame_rate = audio.getframerate()
                total_frames = audio.getnframes()
                total_duration = total_frames / frame_rate

                # Преобразование времени в секунды
                start_time = time_to_seconds(start_time_str)
                end_time = time_to_seconds(end_time_str)

                # Ограничение конечного времени длительностью файла
                if end_time > total_duration:
                    end_time = total_duration

                start_frame = int(start_time * frame_rate)
                end_frame = int(end_time * frame_rate)

                # Вырезание отрывка
                audio.setpos(start_frame)
                frames = audio.readframes(end_frame - start_frame)

                # Сохранение обработанного файла
                output_path = os.path.join(app.config['PROCESSED_FOLDER'], "processed_" + file.filename)
                with wave.open(output_path, 'wb') as output_audio:
                    output_audio.setparams(audio.getparams())
                    output_audio.writeframes(frames)

            return send_file(output_path, as_attachment=True)
    return render_template('cut.html')

@app.route('/merge', methods=['GET', 'POST'])
@login_required
def merge():
    if request.method == 'POST':
        file1 = request.files['audio-file-1']
        file2 = request.files['audio-file-2']
        if file1 and file2:
            filepath1 = os.path.join(app.config['UPLOAD_FOLDER'], file1.filename)
            filepath2 = os.path.join(app.config['UPLOAD_FOLDER'], file2.filename)
            file1.save(filepath1)
            file2.save(filepath2)

            # Открытие обоих аудиофайлов
            with wave.open(filepath1, 'rb') as audio1, wave.open(filepath2, 'rb') as audio2:
                if audio1.getparams() != audio2.getparams():
                    return "Файлы должны иметь одинаковые параметры (каналы, разрядность, частота дискретизации).", 400

                frames1 = audio1.readframes(audio1.getnframes())
                frames2 = audio2.readframes(audio2.getnframes())

                # Склейка фреймов
                merged_frames = frames1 + frames2

                # Сохранение объединенного файла
                output_path = os.path.join(app.config['PROCESSED_FOLDER'], "merged_" + file1.filename)
                with wave.open(output_path, 'wb') as output_audio:
                    output_audio.setparams(audio1.getparams())
                    output_audio.writeframes(merged_frames)

            return send_file(output_path, as_attachment=True)
    return render_template('merge.html')

@app.route('/add_silence', methods=['GET', 'POST'])
@login_required
def add_silence():
    if request.method == 'POST':
        file = request.files['audio-file']
        if file:
            position = request.form.get('position', 'start')
            duration_str = request.form.get('duration', '0:05')
            duration = time_to_seconds(duration_str)

            filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(filepath)

            # Открытие аудиофайла
            with wave.open(filepath, 'rb') as audio:
                params = audio.getparams()
                frames = audio.readframes(audio.getnframes())

                # Генерация тишины
                silence_frames = generate_silence(duration, params.framerate, params.nchannels, params.sampwidth)

                # Добавление тишины в начало или конец
                if position == 'start':
                    new_frames = silence_frames + frames
                else:
                    new_frames = frames + silence_frames

                # Сохранение нового файла с добавленной паузой
                output_path = os.path.join(app.config['PROCESSED_FOLDER'], "silence_" + file.filename)
                with wave.open(output_path, 'wb') as output_audio:
                    output_audio.setparams(params)
                    output_audio.writeframes(new_frames)

            return send_file(output_path, as_attachment=True)
    return render_template('silence.html')

if __name__ == '__main__':
    app.run(debug=True)
