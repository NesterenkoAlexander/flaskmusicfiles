from flask import Flask, render_template, request, send_file, redirect, url_for
import wave
import os

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
PROCESSED_FOLDER = "processed"
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PROCESSED_FOLDER'] = PROCESSED_FOLDER

# Ensure folders exist
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

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/cut', methods=['GET', 'POST'])
def cut():
    if request.method == 'POST':
        file = request.files['audio-file']
        if file:
            start_time_str = request.form.get('start-time', '0:00')
            end_time_str = request.form.get('end-time', '0:05')

            filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(filepath)

            # Open the audio file
            with wave.open(filepath, 'rb') as audio:
                frame_rate = audio.getframerate()
                total_frames = audio.getnframes()
                total_duration = total_frames / frame_rate

                # Convert time strings to seconds
                start_time = time_to_seconds(start_time_str)
                end_time = time_to_seconds(end_time_str)

                # Ensure end time does not exceed total duration
                if end_time > total_duration:
                    end_time = total_duration

                start_frame = int(start_time * frame_rate)
                end_frame = int(end_time * frame_rate)

                # Set up the new audio
                audio.setpos(start_frame)
                frames = audio.readframes(end_frame - start_frame)

                # Save the processed audio
                output_path = os.path.join(app.config['PROCESSED_FOLDER'], "processed_" + file.filename)
                with wave.open(output_path, 'wb') as output_audio:
                    output_audio.setparams(audio.getparams())
                    output_audio.writeframes(frames)

            return send_file(output_path, as_attachment=True)
    return render_template('cut.html')

@app.route('/merge', methods=['GET', 'POST'])
def merge():
    if request.method == 'POST':
        file1 = request.files['audio-file-1']
        file2 = request.files['audio-file-2']
        if file1 and file2:
            filepath1 = os.path.join(app.config['UPLOAD_FOLDER'], file1.filename)
            filepath2 = os.path.join(app.config['UPLOAD_FOLDER'], file2.filename)
            file1.save(filepath1)
            file2.save(filepath2)

            # Open both audio files
            with wave.open(filepath1, 'rb') as audio1, wave.open(filepath2, 'rb') as audio2:
                if audio1.getparams() != audio2.getparams():
                    return "Файлы должны иметь одинаковые параметры (каналы, разрядность, частота дискретизации).", 400

                frames1 = audio1.readframes(audio1.getnframes())
                frames2 = audio2.readframes(audio2.getnframes())

                # Merge the audio frames
                merged_frames = frames1 + frames2

                # Save the merged audio
                output_path = os.path.join(app.config['PROCESSED_FOLDER'], "merged_" + file1.filename)
                with wave.open(output_path, 'wb') as output_audio:
                    output_audio.setparams(audio1.getparams())
                    output_audio.writeframes(merged_frames)

            return send_file(output_path, as_attachment=True)
    return render_template('merge.html')

@app.route('/add_silence', methods=['GET', 'POST'])
def add_silence():
    if request.method == 'POST':
        file = request.files['audio-file']
        if file:
            position = request.form.get('position', 'start')
            duration_str = request.form.get('duration', '0:05')
            duration = time_to_seconds(duration_str)

            filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(filepath)

            # Open the audio file
            with wave.open(filepath, 'rb') as audio:
                params = audio.getparams()
                frames = audio.readframes(audio.getnframes())

                # Generate silence
                silence_frames = generate_silence(duration, params.framerate, params.nchannels, params.sampwidth)

                # Add silence to the beginning or end
                if position == 'start':
                    new_frames = silence_frames + frames
                else:
                    new_frames = frames + silence_frames

                # Save the new audio file
                output_path = os.path.join(app.config['PROCESSED_FOLDER'], "silence_" + file.filename)
                with wave.open(output_path, 'wb') as output_audio:
                    output_audio.setparams(params)
                    output_audio.writeframes(new_frames)

            return send_file(output_path, as_attachment=True)
    return render_template('silence.html')

if __name__ == '__main__':
    app.run(debug=True)
