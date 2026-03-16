#!/usr/bin/env python3
"""
簡易說話人標註校正工具

啟動方式：
    python annotation_tool.py --audio /path/to/audio.wav --rttm /path/to/initial.rttm

功能：
    - 可視化顯示說話人片段
    - 播放指定片段
    - 修改說話人標籤
    - 合併/分割片段
    - 導出校正後的 RTTM
"""
import os
import sys
import json
import argparse
from flask import Flask, render_template_string, request, jsonify, send_file
import soundfile as sf

app = Flask(__name__)

# 全局變量
AUDIO_PATH = None
RTTM_PATH = None
SEGMENTS = []
AUDIO_DURATION = 0

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>說話人標註工具</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1a1a2e; color: #eee; padding: 20px;
        }
        h1 { margin-bottom: 20px; color: #6366f1; }
        .container { max-width: 1400px; margin: 0 auto; }

        /* 音頻播放器 */
        .audio-section {
            background: #16213e; padding: 20px; border-radius: 12px;
            margin-bottom: 20px;
        }
        audio { width: 100%; margin-bottom: 10px; }

        /* 時間軸 */
        .timeline {
            position: relative; height: 120px; background: #0f0f23;
            border-radius: 8px; overflow: hidden; margin-bottom: 20px;
        }
        .segment {
            position: absolute; height: 40px; border-radius: 4px;
            cursor: pointer; display: flex; align-items: center;
            justify-content: center; font-size: 12px; font-weight: bold;
            transition: all 0.2s; border: 2px solid transparent;
        }
        .segment:hover { transform: scaleY(1.1); border-color: #fff; }
        .segment.selected { border-color: #ffd700; box-shadow: 0 0 10px #ffd700; }
        .segment.playing { animation: pulse 0.5s infinite; }
        @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.7; } }

        /* 說話人顏色 */
        .speaker-0 { background: #3b82f6; top: 10px; }
        .speaker-1 { background: #10b981; top: 60px; }
        .speaker-2 { background: #f59e0b; top: 10px; }
        .speaker-3 { background: #ef4444; top: 60px; }
        .speaker-4 { background: #8b5cf6; top: 10px; }
        .speaker-5 { background: #ec4899; top: 60px; }
        .speaker-6 { background: #06b6d4; top: 10px; }
        .speaker-7 { background: #84cc16; top: 60px; }

        /* 片段列表 */
        .segments-list {
            background: #16213e; padding: 20px; border-radius: 12px;
            max-height: 400px; overflow-y: auto;
        }
        .segment-item {
            display: grid; grid-template-columns: 80px 120px 1fr 100px;
            gap: 10px; padding: 10px; border-radius: 8px;
            align-items: center; margin-bottom: 8px;
            background: #0f0f23; cursor: pointer;
        }
        .segment-item:hover { background: #1e1e3f; }
        .segment-item.selected { background: #2d2d5a; border: 1px solid #6366f1; }
        .segment-item .time { font-family: monospace; color: #888; }
        .segment-item select {
            padding: 6px; border-radius: 4px; border: none;
            background: #2d2d5a; color: #fff;
        }
        .segment-item button {
            padding: 6px 12px; border: none; border-radius: 4px;
            cursor: pointer; font-size: 12px;
        }
        .btn-play { background: #10b981; color: #fff; }
        .btn-delete { background: #ef4444; color: #fff; }
        .btn-merge { background: #f59e0b; color: #000; }

        /* 工具欄 */
        .toolbar {
            display: flex; gap: 10px; margin-bottom: 20px;
        }
        .toolbar button {
            padding: 10px 20px; border: none; border-radius: 8px;
            cursor: pointer; font-weight: bold;
        }
        .btn-save { background: #6366f1; color: #fff; }
        .btn-export { background: #10b981; color: #fff; }
        .btn-add { background: #3b82f6; color: #fff; }

        /* 統計 */
        .stats {
            display: flex; gap: 20px; margin-bottom: 20px;
        }
        .stat-item {
            background: #16213e; padding: 15px 25px; border-radius: 8px;
        }
        .stat-value { font-size: 24px; font-weight: bold; color: #6366f1; }
        .stat-label { font-size: 12px; color: #888; }

        /* 快捷鍵提示 */
        .shortcuts {
            background: #16213e; padding: 15px; border-radius: 8px;
            margin-top: 20px; font-size: 12px; color: #888;
        }
        .shortcuts kbd {
            background: #2d2d5a; padding: 2px 6px; border-radius: 4px;
            margin: 0 4px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎙️ 說話人標註校正工具</h1>

        <div class="stats">
            <div class="stat-item">
                <div class="stat-value" id="total-segments">0</div>
                <div class="stat-label">總片段數</div>
            </div>
            <div class="stat-item">
                <div class="stat-value" id="total-speakers">0</div>
                <div class="stat-label">說話人數</div>
            </div>
            <div class="stat-item">
                <div class="stat-value" id="duration">0:00</div>
                <div class="stat-label">音頻時長</div>
            </div>
        </div>

        <div class="audio-section">
            <audio id="audio-player" controls></audio>
            <div class="timeline" id="timeline"></div>
        </div>

        <div class="toolbar">
            <button class="btn-save" onclick="saveChanges()">💾 保存修改</button>
            <button class="btn-export" onclick="exportRTTM()">📤 導出 RTTM</button>
            <button class="btn-add" onclick="addSegment()">➕ 新增片段</button>
            <button class="btn-merge" onclick="mergeSelected()">🔗 合併選中</button>
        </div>

        <div class="segments-list" id="segments-list"></div>

        <div class="shortcuts">
            <strong>快捷鍵：</strong>
            <kbd>Space</kbd> 播放/暫停 |
            <kbd>1-8</kbd> 設置說話人 |
            <kbd>Delete</kbd> 刪除片段 |
            <kbd>M</kbd> 合併選中 |
            <kbd>S</kbd> 保存
        </div>
    </div>

    <script>
        let segments = [];
        let selectedIndices = new Set();
        let audioDuration = 0;
        const audioPlayer = document.getElementById('audio-player');
        const speakerColors = ['speaker-0','speaker-1','speaker-2','speaker-3',
                               'speaker-4','speaker-5','speaker-6','speaker-7'];

        // 載入數據
        async function loadData() {
            const resp = await fetch('/api/data');
            const data = await resp.json();
            segments = data.segments;
            audioDuration = data.duration;
            audioPlayer.src = '/api/audio';

            updateStats();
            renderTimeline();
            renderList();
        }

        function updateStats() {
            document.getElementById('total-segments').textContent = segments.length;
            const speakers = new Set(segments.map(s => s.speaker));
            document.getElementById('total-speakers').textContent = speakers.size;
            const mins = Math.floor(audioDuration / 60);
            const secs = Math.floor(audioDuration % 60);
            document.getElementById('duration').textContent = `${mins}:${secs.toString().padStart(2,'0')}`;
        }

        function renderTimeline() {
            const timeline = document.getElementById('timeline');
            timeline.innerHTML = '';

            segments.forEach((seg, idx) => {
                const left = (seg.start / audioDuration) * 100;
                const width = (seg.duration / audioDuration) * 100;
                const speakerNum = parseInt(seg.speaker.replace('speaker_', '')) % 8;

                const div = document.createElement('div');
                div.className = `segment ${speakerColors[speakerNum]} ${selectedIndices.has(idx) ? 'selected' : ''}`;
                div.style.left = left + '%';
                div.style.width = Math.max(width, 0.5) + '%';
                div.textContent = seg.speaker.replace('speaker_', 'S');
                div.onclick = (e) => toggleSelect(idx, e.shiftKey);
                div.ondblclick = () => playSegment(idx);
                timeline.appendChild(div);
            });
        }

        function renderList() {
            const list = document.getElementById('segments-list');
            list.innerHTML = '';

            segments.forEach((seg, idx) => {
                const div = document.createElement('div');
                div.className = `segment-item ${selectedIndices.has(idx) ? 'selected' : ''}`;
                div.onclick = (e) => { if(e.target.tagName !== 'SELECT' && e.target.tagName !== 'BUTTON') toggleSelect(idx, e.shiftKey); };

                const startMin = Math.floor(seg.start / 60);
                const startSec = (seg.start % 60).toFixed(1);
                const endTime = seg.start + seg.duration;
                const endMin = Math.floor(endTime / 60);
                const endSec = (endTime % 60).toFixed(1);

                div.innerHTML = `
                    <span class="time">${startMin}:${startSec.padStart(4,'0')}</span>
                    <select onchange="changeSpeaker(${idx}, this.value)">
                        ${[0,1,2,3,4,5,6,7].map(i =>
                            `<option value="speaker_${i}" ${seg.speaker === 'speaker_'+i ? 'selected' : ''}>
                                說話人 ${String.fromCharCode(65+i)}
                            </option>`
                        ).join('')}
                    </select>
                    <span>${seg.duration.toFixed(1)}秒</span>
                    <div>
                        <button class="btn-play" onclick="playSegment(${idx})">▶</button>
                        <button class="btn-delete" onclick="deleteSegment(${idx})">✕</button>
                    </div>
                `;
                list.appendChild(div);
            });
        }

        function toggleSelect(idx, multi) {
            if (multi) {
                if (selectedIndices.has(idx)) selectedIndices.delete(idx);
                else selectedIndices.add(idx);
            } else {
                selectedIndices.clear();
                selectedIndices.add(idx);
            }
            renderTimeline();
            renderList();
        }

        function playSegment(idx) {
            const seg = segments[idx];
            audioPlayer.currentTime = seg.start;
            audioPlayer.play();

            // 自動停止
            setTimeout(() => {
                if (audioPlayer.currentTime >= seg.start + seg.duration - 0.1) {
                    audioPlayer.pause();
                }
            }, seg.duration * 1000);
        }

        function changeSpeaker(idx, speaker) {
            segments[idx].speaker = speaker;
            renderTimeline();
        }

        function deleteSegment(idx) {
            if (confirm('確定刪除此片段？')) {
                segments.splice(idx, 1);
                selectedIndices.clear();
                updateStats();
                renderTimeline();
                renderList();
            }
        }

        function mergeSelected() {
            if (selectedIndices.size < 2) {
                alert('請選擇至少 2 個片段（按住 Shift 多選）');
                return;
            }

            const indices = Array.from(selectedIndices).sort((a,b) => a-b);
            const first = segments[indices[0]];
            const last = segments[indices[indices.length-1]];

            const merged = {
                speaker: first.speaker,
                start: first.start,
                duration: (last.start + last.duration) - first.start
            };

            // 刪除選中的片段，插入合併後的
            for (let i = indices.length - 1; i >= 0; i--) {
                segments.splice(indices[i], 1);
            }
            segments.splice(indices[0], 0, merged);
            segments.sort((a,b) => a.start - b.start);

            selectedIndices.clear();
            updateStats();
            renderTimeline();
            renderList();
        }

        async function saveChanges() {
            const resp = await fetch('/api/save', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({segments})
            });
            if (resp.ok) alert('✅ 已保存！');
        }

        async function exportRTTM() {
            window.open('/api/export', '_blank');
        }

        function addSegment() {
            const start = parseFloat(prompt('開始時間（秒）：', '0'));
            const duration = parseFloat(prompt('持續時間（秒）：', '3'));
            const speaker = prompt('說話人（speaker_0 ~ speaker_7）：', 'speaker_0');

            if (!isNaN(start) && !isNaN(duration)) {
                segments.push({start, duration, speaker});
                segments.sort((a,b) => a.start - b.start);
                updateStats();
                renderTimeline();
                renderList();
            }
        }

        // 鍵盤快捷鍵
        document.addEventListener('keydown', (e) => {
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;

            if (e.code === 'Space') {
                e.preventDefault();
                if (audioPlayer.paused) audioPlayer.play();
                else audioPlayer.pause();
            }
            if (e.key >= '1' && e.key <= '8' && selectedIndices.size > 0) {
                const speaker = 'speaker_' + (parseInt(e.key) - 1);
                selectedIndices.forEach(idx => segments[idx].speaker = speaker);
                renderTimeline();
                renderList();
            }
            if (e.code === 'Delete' && selectedIndices.size > 0) {
                if (confirm('刪除選中的片段？')) {
                    const indices = Array.from(selectedIndices).sort((a,b) => b-a);
                    indices.forEach(idx => segments.splice(idx, 1));
                    selectedIndices.clear();
                    updateStats();
                    renderTimeline();
                    renderList();
                }
            }
            if (e.key.toLowerCase() === 'm') mergeSelected();
            if (e.key.toLowerCase() === 's' && e.ctrlKey) {
                e.preventDefault();
                saveChanges();
            }
        });

        // 音頻時間更新
        audioPlayer.addEventListener('timeupdate', () => {
            // 高亮當前播放的片段
            const currentTime = audioPlayer.currentTime;
            document.querySelectorAll('.segment').forEach((el, idx) => {
                const seg = segments[idx];
                if (seg && currentTime >= seg.start && currentTime <= seg.start + seg.duration) {
                    el.classList.add('playing');
                } else {
                    el.classList.remove('playing');
                }
            });
        });

        loadData();
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/data')
def get_data():
    return jsonify({
        'segments': SEGMENTS,
        'duration': AUDIO_DURATION
    })

@app.route('/api/audio')
def get_audio():
    return send_file(AUDIO_PATH, mimetype='audio/wav')

@app.route('/api/save', methods=['POST'])
def save_changes():
    global SEGMENTS
    data = request.json
    SEGMENTS = data['segments']

    # 保存到 RTTM
    save_rttm(RTTM_PATH, SEGMENTS)
    return jsonify({'status': 'ok'})

@app.route('/api/export')
def export_rttm():
    file_id = os.path.splitext(os.path.basename(AUDIO_PATH))[0]
    output_path = RTTM_PATH.replace('.rttm', '_corrected.rttm')
    save_rttm(output_path, SEGMENTS)
    return send_file(output_path, as_attachment=True,
                     download_name=f'{file_id}_corrected.rttm')


def save_rttm(path: str, segments: list):
    file_id = os.path.splitext(os.path.basename(AUDIO_PATH))[0]
    with open(path, 'w') as f:
        for seg in sorted(segments, key=lambda x: x['start']):
            line = f"SPEAKER {file_id} 1 {seg['start']:.3f} {seg['duration']:.3f} <NA> <NA> {seg['speaker']} <NA> <NA}\n"
            f.write(line)


def load_rttm(path: str) -> list:
    segments = []
    if not os.path.exists(path):
        return segments

    with open(path, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 8 and parts[0] == 'SPEAKER':
                segments.append({
                    'start': float(parts[3]),
                    'duration': float(parts[4]),
                    'speaker': parts[7]
                })

    return sorted(segments, key=lambda x: x['start'])


def main():
    global AUDIO_PATH, RTTM_PATH, SEGMENTS, AUDIO_DURATION

    parser = argparse.ArgumentParser(description='說話人標註校正工具')
    parser.add_argument('--audio', required=True, help='音頻文件路徑')
    parser.add_argument('--rttm', required=True, help='RTTM 文件路徑')
    parser.add_argument('--port', type=int, default=5555, help='Web 服務端口')

    args = parser.parse_args()

    AUDIO_PATH = os.path.abspath(args.audio)
    RTTM_PATH = os.path.abspath(args.rttm)

    if not os.path.exists(AUDIO_PATH):
        print(f"❌ 音頻文件不存在：{AUDIO_PATH}")
        sys.exit(1)

    # 載入音頻信息
    audio_info = sf.info(AUDIO_PATH)
    AUDIO_DURATION = audio_info.duration

    # 載入 RTTM
    SEGMENTS = load_rttm(RTTM_PATH)

    print(f"🎵 音頻：{AUDIO_PATH}")
    print(f"📄 RTTM：{RTTM_PATH}")
    print(f"⏱️  時長：{AUDIO_DURATION:.1f} 秒")
    print(f"📊 片段：{len(SEGMENTS)} 個")
    print(f"\n🌐 請在瀏覽器打開：http://localhost:{args.port}")

    app.run(host='0.0.0.0', port=args.port, debug=False)


if __name__ == '__main__':
    main()
