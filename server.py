import os
import requests
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__, static_folder='.', static_url_path='')
MAX_PROMPT = 1000

@app.get('/')
def home():
    return send_from_directory('.', 'index.html')

@app.get('/health')
def health():
    return jsonify(status='ok', music_api_configured=bool(os.getenv('MUSIC_API_URL') and os.getenv('MUSIC_API_KEY')))

@app.post('/api/generate')
def generate():
    data = request.get_json(silent=True) or {}
    prompt = str(data.get('prompt', '')).strip()
    if not prompt:
        return jsonify(error='Please enter a song description.'), 400
    if len(prompt) > MAX_PROMPT:
        return jsonify(error=f'Your song description must be {MAX_PROMPT} characters or fewer.'), 400

    api_url = os.getenv('MUSIC_API_URL', '').strip()
    api_key = os.getenv('MUSIC_API_KEY', '').strip()
    if not api_url or not api_key:
        return jsonify(error='The music-generation engine is not connected yet. The website is ready, but you must add a supported music API URL and API key in Render before songs can be generated.'), 503

    # Provider adapter contract: configure an endpoint that accepts this JSON and
    # returns JSON containing audio_url (completed track) or job_id (async job).
    payload = {
        'prompt': prompt,
        'genres': data.get('genres', []),
        'mood': data.get('mood', 'Uplifting'),
        'language': data.get('language', 'English'),
        'voice': data.get('voice', 'Male vocals'),
        'length': data.get('length', 'Standard'),
        'lyrics': data.get('lyrics', ''),
        'instrumental': bool(data.get('instrumental', False)),
        'generate_lyrics': bool(data.get('generate_lyrics', True)),
    }
    try:
        response = requests.post(api_url, json=payload,
            headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}, timeout=45)
        response.raise_for_status()
        result = response.json()
        audio_url = result.get('audio_url') or result.get('audioUrl')
        job_id = result.get('job_id') or result.get('id')
        if not audio_url and not job_id:
            return jsonify(error='The music provider responded, but its response format is not yet mapped. We need its API documentation to finish the connection.'), 502
        return jsonify(message='Your song request was accepted by the music provider.', audio_url=audio_url,
                       job_id=job_id, title=result.get('title', ''))
    except requests.Timeout:
        return jsonify(error='The music provider took too long to respond. Please try again.'), 504
    except requests.RequestException as exc:
        app.logger.exception('Music provider request failed')
        return jsonify(error='Could not contact the music provider. Check the API settings in Render.'), 502
    except ValueError:
        return jsonify(error='The music provider returned an unreadable response.'), 502

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', '10000')))
